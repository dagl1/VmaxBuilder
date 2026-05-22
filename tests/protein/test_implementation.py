from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from VmaxBuilder.api import VmaxOrchestrator
from VmaxBuilder.config import APIConfig, ConfigurationError, LoadingPolicy, ProteinSourceMode
from VmaxBuilder.expression import DefaultExpressionImplementation
from VmaxBuilder.protein import (
    DefaultProteinStageCoordinator,
    DefaultProteomicsImplementation,
    DefaultPTRImplementation,
)


def test_split_protein_submodule_implementations_are_exported() -> None:
    coordinator = DefaultProteinStageCoordinator()

    assert isinstance(coordinator.expression_implementation, DefaultExpressionImplementation)
    assert isinstance(coordinator.ptr_implementation, DefaultPTRImplementation)
    assert isinstance(
        coordinator.proteomics_implementation,
        DefaultProteomicsImplementation,
    )


def test_expression_ptr_mode_raises_when_ptr_missing() -> None:
    expression_df = pd.DataFrame(
        {"sample_1": [1.0, 2.0], "sample_2": [3.0, 4.0]},
        index=["gene_a", "gene_b"],
    )
    config = APIConfig(
        loading=LoadingPolicy(in_memory_inputs={"expression": expression_df}),
    )
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR

    with pytest.raises(ConfigurationError):
        VmaxOrchestrator(config=config).run_protein()


def test_expression_ptr_mode_multiplies_expression_and_ptr() -> None:
    expression_df = pd.DataFrame(
        {"sample_1": [2.0, 3.0]},
        index=["gene_a", "gene_b"],
    )
    ptr_df = pd.DataFrame(
        {"sample_1": [10.0, 20.0]},
        index=["gene_a", "gene_b"],
    )
    config = APIConfig(
        loading=LoadingPolicy(in_memory_inputs={"expression": expression_df, "ptr": ptr_df}),
    )
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR

    scaffold = VmaxOrchestrator(config=config).run_protein()

    protein_df = scaffold["artifacts"]["protein_abundance"]
    assert protein_df.loc["gene_a", "sample_1"] == 20.0
    assert protein_df.loc["gene_b", "sample_1"] == 60.0
    assert scaffold["metadata"]["protein_stage"]["ptr_used"] is True


def test_expression_ptr_mode_applies_transcript_to_gene_placeholder_conversion() -> None:
    expression_df = pd.DataFrame(
        {"sample_1": [1.0, 2.0]},
        index=["ENST1.1", "ENST1.2"],
    )
    ptr_df = pd.DataFrame(
        {"sample_1": [1.0, 1.0]},
        index=["ENST1.1", "ENST1.2"],
    )
    config = APIConfig(
        loading=LoadingPolicy(in_memory_inputs={"expression": expression_df, "ptr": ptr_df}),
    )
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR
    config.expression.origin_transcript_gene_level = "transcript"
    config.run_target_transcript_gene_level = "gene"

    scaffold = VmaxOrchestrator(config=config).run_protein()

    protein_df = scaffold["artifacts"]["protein_abundance"]
    assert list(protein_df.index) == ["ENST1"]
    assert protein_df.loc["ENST1", "sample_1"] == 3.0
    assert scaffold["metadata"]["protein_stage"]["required_inputs"] == [
        "expression",
        "ptr",
    ]


def test_proteomics_mode_imputes_missing_values() -> None:
    proteomics_df = pd.DataFrame(
        {
            "sample_1": [1.0, None],
            "sample_2": [None, 5.0],
        },
        index=["protein_a", "protein_b"],
    )
    config = APIConfig(
        loading=LoadingPolicy(in_memory_inputs={"proteomics": proteomics_df}),
    )
    config.protein.source_mode = ProteinSourceMode.PROTEOMICS

    scaffold = VmaxOrchestrator(config=config).run_protein()

    protein_df = scaffold["artifacts"]["protein_abundance"]
    assert protein_df.isna().sum().sum() == 0
    assert scaffold["metadata"]["protein_stage"]["implementation"] == "proteomics"
    assert scaffold["metadata"]["protein_stage"]["required_inputs"] == ["proteomics"]


def test_expression_ptr_mode_raises_when_expression_missing() -> None:
    config = APIConfig(loading=LoadingPolicy())
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR

    with pytest.raises(ConfigurationError):
        VmaxOrchestrator(config=config).run_protein()


def test_proteomics_mode_raises_when_proteomics_missing() -> None:
    config = APIConfig(loading=LoadingPolicy())
    config.protein.source_mode = ProteinSourceMode.PROTEOMICS

    with pytest.raises(ConfigurationError):
        VmaxOrchestrator(config=config).run_protein()


def test_proteomics_mode_loads_dataframe_from_path(tmp_path: Path) -> None:
    proteomics_df = pd.DataFrame(
        {"sample_1": [1.0, 2.0]},
        index=["protein_a", "protein_b"],
    )
    proteomics_path = tmp_path / "proteomics.csv"
    proteomics_df.to_csv(proteomics_path)

    config = APIConfig(loading=LoadingPolicy(proteomics_path=proteomics_path))
    config.protein.source_mode = ProteinSourceMode.PROTEOMICS

    scaffold = VmaxOrchestrator(config=config).run_protein()

    protein_df = scaffold["artifacts"]["protein_abundance"]
    assert list(protein_df.columns) == ["sample_1"]
    assert list(protein_df.index) == ["protein_a", "protein_b"]


def test_expression_ptr_mode_loads_from_directory_using_default_discovery_rules(
    tmp_path: Path,
) -> None:
    expression_df = pd.DataFrame(
        {"sample_1": [2.0]},
        index=["gene_a"],
    )
    ptr_df = pd.DataFrame(
        {"sample_1": [3.0]},
        index=["gene_a"],
    )
    expression_dir = tmp_path / "expression_dir"
    ptr_dir = tmp_path / "ptr_dir"
    expression_dir.mkdir(parents=True, exist_ok=True)
    ptr_dir.mkdir(parents=True, exist_ok=True)
    expression_df.to_csv(expression_dir / "data__expression.csv")
    ptr_df.to_csv(ptr_dir / "PTR__ratio.tsv", sep="\t")

    config = APIConfig(
        loading=LoadingPolicy(
            expression_path=expression_dir,
            ptr_path=ptr_dir,
        )
    )
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR

    scaffold = VmaxOrchestrator(config=config).run_protein()

    protein_df = scaffold["artifacts"]["protein_abundance"]
    assert protein_df.loc["gene_a", "sample_1"] == 6.0


def test_proteomics_mode_loads_from_directory_using_default_discovery_rules(
    tmp_path: Path,
) -> None:
    proteomics_df = pd.DataFrame(
        {"sample_1": [1.0, 2.0]},
        index=["protein_a", "protein_b"],
    )
    proteomics_dir = tmp_path / "proteomics_dir"
    proteomics_dir.mkdir(parents=True, exist_ok=True)
    proteomics_df.to_csv(proteomics_dir / "data__proteomics.tsv", sep="\t")

    config = APIConfig(loading=LoadingPolicy(proteomics_path=proteomics_dir))
    config.protein.source_mode = ProteinSourceMode.PROTEOMICS

    scaffold = VmaxOrchestrator(config=config).run_protein()

    protein_df = scaffold["artifacts"]["protein_abundance"]
    assert list(protein_df.columns) == ["sample_1"]
    assert list(protein_df.index) == ["protein_a", "protein_b"]
