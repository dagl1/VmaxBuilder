from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from VmaxBuilder.base.configs import RunConfig, StageLoading, StageLoadingInfo
from VmaxBuilder.base.orchestrator import Orchestrator
from VmaxBuilder.stages.allocation.FairAllocation.implementation import (
    FairAllocationImplementation,
)
from VmaxBuilder.stages.Kcat.UniKPMainSubstrate.implementation import (
    UniKPMainSubstrateImplementation,
)
from VmaxBuilder.stages.model.default.implementation import (
    DefaultIrreversibleModelImplementation,
)
from VmaxBuilder.stages.protein.MvalueTrimmingExpressionPTR.implementation import (
    MvalueTrimmingExpressionPTRImplementation,
)
from VmaxBuilder.stages.Vmax.default.reaction_resolving import (
    DefaultVmaxReactionResolving,
)


def build_stage_loading(
    model_dir: Path,
    expression_path: Path,
    ptr_path: Path,
    smiles_file_name: str,
    transcript_file_name: str,
) -> StageLoading:
    """Generated: validation needed.

    Description:
        Build stage-loading object for model/protein/allocation/Kcat/Vmax stages.

    Args:
        model_dir (Path): Directory containing model-stage files.
        expression_path (Path): Expression matrix path.
        ptr_path (Path): PTR matrix path.
        smiles_file_name (str): SMILES file name inside model_dir.
        transcript_file_name (str): Transcript file name inside model_dir.

    Returns:
        StageLoading: Fully populated stage-loading config.
    """
    model_loading = StageLoadingInfo(
        stage_name="model",
        directories=model_dir,
        file_paths={
            "smiles_df": model_dir / smiles_file_name,
            "transcript_df": model_dir / transcript_file_name,
        },
    )
    protein_loading = StageLoadingInfo(
        stage_name="protein",
        directories=[expression_path, ptr_path],
    )

    return StageLoading(
        model_loading_info=model_loading,
        protein_loading_info=protein_loading,
        allocation_loading_info=StageLoadingInfo(stage_name="allocation"),
        Kcat_loading_info=StageLoadingInfo(stage_name="Kcat"),
        Vmax_loading_info=StageLoadingInfo(stage_name="Vmax"),
    )


def run_once(
    stage_loading: StageLoading,
    output_dir: Path,
    run_name: str,
    trim_enable: bool,
    sample_type: str,
    print_level: str,
    overwrite: bool,
    trim_genes_remain_part_for_kcat: bool,
) -> Path:
    """Generated: validation needed.

    Description:
        Execute one orchestrator run with either trimmed or untrimmed allocation flow.

    Args:
        stage_loading (StageLoading): Stage input resolution instructions.
        output_dir (Path): Parent output directory.
        run_name (str): Run folder name.
        trim_enable (bool): Whether protein/allocation trimming is enabled.
        sample_type (str): Tissue label fallback for every sample.
        print_level (str): Orchestrator print level.
        overwrite (bool): Whether to overwrite previous outputs.
        trim_genes_remain_part_for_kcat (bool): Whether Vmax Kcat selection
            keeps trimmed genes.

    Returns:
        Path: Result directory for this run.
    """
    run_config = RunConfig(
        output_dir=output_dir,
        run_name=run_name,
        overwrite_existing_results=overwrite,
        print_level=print_level,
    )

    orchestrator = Orchestrator(stage_loading, run_config)
    orchestrator.set_print_level(print_level)
    orchestrator.set_model_implementation(DefaultIrreversibleModelImplementation)
    protein_impl = orchestrator.set_protein_implementation(
        MvalueTrimmingExpressionPTRImplementation
    )
    orchestrator.set_allocation_implementation(FairAllocationImplementation)
    orchestrator.set_Kcat_implementation(UniKPMainSubstrateImplementation)
    orchestrator.set_Vmax_implementation(DefaultVmaxReactionResolving)

    expression_path = stage_loading.protein_loading_info.directories[0]
    expression_df = pd.read_csv(expression_path, index_col=0)
    sample_type_map = {str(sample): sample_type for sample in expression_df.columns}

    protein_impl.config.expression_sample_type_map = sample_type_map
    protein_impl.config.PTR_special_gene_groups = {"transport_reactions": []}
    protein_impl.config.use_special_groups_for_unobserved_imputation = True
    protein_impl.config.trim_enable = trim_enable
    orchestrator.config.Vmax.trim_genes_remain_part_for_Kcat = trim_genes_remain_part_for_kcat

    orchestrator.run()
    return run_config.paths.results_dir


def build_comparison_summary(trimmed_dir: Path, untrimmed_dir: Path) -> dict[str, Any]:
    """Generated: validation needed.

    Description:
        Build summary metrics comparing trimmed and untrimmed run outputs.

    Args:
        trimmed_dir (Path): Trimmed run directory.
        untrimmed_dir (Path): Untrimmed run directory.

    Returns:
        dict[str, Any]: Comparison summary payload.
    """
    summary: dict[str, Any] = {
        "trimmed_run_dir": str(trimmed_dir),
        "untrimmed_run_dir": str(untrimmed_dir),
    }

    trimmed_ifp_path = trimmed_dir / "outputs" / "IFP_abundance_df.csv"
    untrimmed_ifp_path = untrimmed_dir / "outputs" / "IFP_abundance_df.csv"
    trimmed_vmax_path = trimmed_dir / "outputs" / "non_imputed_reaction_capacity_df.csv"
    untrimmed_vmax_path = untrimmed_dir / "outputs" / "non_imputed_reaction_capacity_df.csv"

    if trimmed_ifp_path.exists() and untrimmed_ifp_path.exists():
        trimmed_ifp_df = pd.read_csv(trimmed_ifp_path, index_col=0)
        untrimmed_ifp_df = pd.read_csv(untrimmed_ifp_path, index_col=0)
        shared_rows = trimmed_ifp_df.index.intersection(untrimmed_ifp_df.index)
        shared_cols = trimmed_ifp_df.columns.intersection(untrimmed_ifp_df.columns)
        if len(shared_rows) > 0 and len(shared_cols) > 0:
            trimmed_vals = trimmed_ifp_df.loc[shared_rows, shared_cols].astype(float)
            untrimmed_vals = untrimmed_ifp_df.loc[shared_rows, shared_cols].astype(float)
            diff = trimmed_vals - untrimmed_vals
            summary["ifp"] = {
                "shared_shape": [int(len(shared_rows)), int(len(shared_cols))],
                "sum_trimmed": float(trimmed_vals.to_numpy().sum()),
                "sum_untrimmed": float(untrimmed_vals.to_numpy().sum()),
                "sum_delta": float(diff.to_numpy().sum()),
                "n_cells_increased": int((diff > 0).to_numpy().sum()),
                "n_cells_decreased": int((diff < 0).to_numpy().sum()),
                "n_cells_unchanged": int((diff == 0).to_numpy().sum()),
            }

    if trimmed_vmax_path.exists() and untrimmed_vmax_path.exists():
        trimmed_vmax_df = pd.read_csv(trimmed_vmax_path, index_col=0)
        untrimmed_vmax_df = pd.read_csv(untrimmed_vmax_path, index_col=0)
        shared_rows = trimmed_vmax_df.index.intersection(untrimmed_vmax_df.index)
        shared_cols = trimmed_vmax_df.columns.intersection(untrimmed_vmax_df.columns)
        if len(shared_rows) > 0 and len(shared_cols) > 0:
            trimmed_vals = trimmed_vmax_df.loc[shared_rows, shared_cols].astype(float)
            untrimmed_vals = untrimmed_vmax_df.loc[shared_rows, shared_cols].astype(float)
            diff = trimmed_vals - untrimmed_vals
            summary["vmax"] = {
                "shared_shape": [int(len(shared_rows)), int(len(shared_cols))],
                "sum_trimmed": float(trimmed_vals.to_numpy().sum()),
                "sum_untrimmed": float(untrimmed_vals.to_numpy().sum()),
                "sum_delta": float(diff.to_numpy().sum()),
                "n_cells_increased": int((diff > 0).to_numpy().sum()),
                "n_cells_decreased": int((diff < 0).to_numpy().sum()),
                "n_cells_unchanged": int((diff == 0).to_numpy().sum()),
            }

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run VmaxBuilder twice (trimmed + untrimmed) and write comparison summary."
        )
    )
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--expression-path", type=Path, required=True)
    parser.add_argument("--ptr-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-prefix", type=str, default="comparison")
    parser.add_argument("--sample-type", type=str, default="heart")
    parser.add_argument("--smiles-file-name", type=str, default="SMILES_df.csv")
    parser.add_argument("--transcript-file-name", type=str, default="transcript_df.csv")
    parser.add_argument("--print-level", type=str, default="INFO")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--trim-genes-remain-part-for-kcat", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    stage_loading = build_stage_loading(
        model_dir=args.model_dir,
        expression_path=args.expression_path,
        ptr_path=args.ptr_path,
        smiles_file_name=args.smiles_file_name,
        transcript_file_name=args.transcript_file_name,
    )

    trimmed_run_dir = run_once(
        stage_loading=stage_loading,
        output_dir=args.output_dir,
        run_name=f"{args.run_prefix}_trimmed",
        trim_enable=True,
        sample_type=args.sample_type,
        print_level=args.print_level,
        overwrite=args.overwrite,
        trim_genes_remain_part_for_kcat=args.trim_genes_remain_part_for_kcat,
    )

    untrimmed_run_dir = run_once(
        stage_loading=stage_loading,
        output_dir=args.output_dir,
        run_name=f"{args.run_prefix}_untrimmed",
        trim_enable=False,
        sample_type=args.sample_type,
        print_level=args.print_level,
        overwrite=args.overwrite,
        trim_genes_remain_part_for_kcat=args.trim_genes_remain_part_for_kcat,
    )

    summary = build_comparison_summary(trimmed_run_dir, untrimmed_run_dir)
    summary_path = args.output_dir / f"{args.run_prefix}_comparison_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as file:
        json.dump(summary, file, indent=2)

    print(f"Trimmed run: {trimmed_run_dir}")
    print(f"Untrimmed run: {untrimmed_run_dir}")
    print(f"Comparison summary: {summary_path}")


if __name__ == "__main__":
    main()
