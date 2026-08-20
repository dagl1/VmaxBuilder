from __future__ import annotations

from typing import Any, cast

import pandas as pd

from VmaxBuilder.base.classes import (
    BaseImplementationDiagnostics,
    RealImplementation,
)
from VmaxBuilder.base.configs import (
    DiscoveredInput,
    FullConfig,
    InputSpec,
    OutputSpec,
    Scaffold,
)
from VmaxBuilder.base.protocols import DependencyChecker
from VmaxBuilder.stages.Kcat.KcatPredictors.UniKP.utils import (
    infer_kcats,
    setup_vmaxbuilder_dependencies,
)
from VmaxBuilder.stages.Kcat.UniKP.config import UniKPConfig


class UniKPDependencyChecker(DependencyChecker):
    def __call__(self, *args, **kwargs) -> bool:
        installed_something = setup_vmaxbuilder_dependencies()
        return installed_something


class UniKPImplementation(RealImplementation[UniKPConfig]):
    STAGE_NAME = "Kcat"
    IMPL_NAME = "UniKP_implementation"
    OPTIONAL_DEPENDENCIES = []
    IMPLEMENTATION_CONFIG_CLASS = UniKPConfig
    DEPENDENCIES = []
    CHILD_IMPLEMENTATIONS = []
    DIAGNOSTICS: list[type[BaseImplementationDiagnostics]] = []
    OPTIONAL_DEPENDENCIES = [UniKPDependencyChecker]
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="SMILES_df",
            in_scaffold=True,
            data_type=pd.DataFrame,
        ),
        InputSpec(
            name="transcript_df",
            in_scaffold=True,
            data_type=pd.DataFrame,
        ),
        InputSpec(
            name="gene_substrate_mapping",
            in_scaffold=True,
            data_type=pd.DataFrame,
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="gene_substrate_predictions",
            extension=".csv",
        ),
    ]

    def __init__(self, full_config: FullConfig):
        super().__init__(full_config)
        # Additional initialization if needed

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        # Load inputs from the scaffold
        smiles_df = cast(pd.DataFrame, scaffold.get_scaffold_value("SMILES_df")).copy()
        # set index
        smiles_df.index = smiles_df["id"].astype(str)

        transcript_df = cast(
            pd.DataFrame, scaffold.get_scaffold_value("transcript_df")
        ).copy()
        if self.full_config.model.level == "gene":
            transcript_df.index = transcript_df["gene_id"].astype(str)
        elif self.full_config.model.level == "transcript":
            transcript_df.index = transcript_df["transcript_id"].astype(str)

        # set index to gene_id if target_type
        # data_type=dict[str, set[str]],
        gene_substrate_mapping = cast(
            dict[str, set[str]], scaffold.get_scaffold_value("gene_substrate_mapping")
        )
        model_path = cast(
            DiscoveredInput, scaffold.discovered_inputs["model"].get("cobra_model", None)
        )
        model_parent_path = self._get_model_parent_path(model_path)

        # Perform Kcat inference using the utility function
        (elapsed_time, (kcat_paths, gene_substrate_predictions)) = self.get_time_decorator(
            infer_kcats
        )(
            smiles_df=smiles_df,
            transcript_df=transcript_df,
            gene_substrate_pairs=gene_substrate_mapping,
            output_path=self.full_config.paths.outputs_dir,
            model_path=str(model_parent_path),
            chunk_size=self.full_config.Kcat.chunk_size,
            embedding_batch_size=self.full_config.Kcat.embedding_batch_size,
            embedding_cache_save_every_batches=self.full_config.Kcat.embedding_cache_save_every_batches,
            prediction_checkpoint_every_chunks=self.full_config.Kcat.prediction_checkpoint_every_chunks,
            amount_of_smiles_replicates=self.full_config.Kcat.amount_of_smiles_replicates,
            type_of_smiles=self.full_config.Kcat.type_of_smiles,
        )

        metadata = self.create_metadata(elapsed_time)

        return {
            "outputs": {
                "gene_substrate_predictions": gene_substrate_predictions,
            },
            "metadata": metadata,
            "artifacts": {},
            "diagnostics": {},
        }

    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]:
        metadata = {
            "Kcat": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "created_gene_substrate_predictions",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata

    def _get_model_parent_path(self, model_path: DiscoveredInput | None) -> Path | None:
        model_parent_path: Path | None = None
        if model_path is not None:
            if isinstance(model_path, DiscoveredInput):
                if model_path.file_path is not None:
                    model_parent_path = model_path.file_path.parent

        if model_parent_path is None:
            self.logger.warning(
                "Model path is not provided or invalid. "
                "This won't affect the Kcat inference, however please make sure to manually"
                " save the predictions for this specific model for future use to save time."
            )

        return model_parent_path


if __name__ == "__main__":
    import json
    from pathlib import Path
    from pprint import pprint

    from cobra.io import load_json_model

    from VmaxBuilder.utils.custom_logging import CustomLogger

    # InputSpec(
    #     name="SMILES_df",
    #     in_scaffold=True,
    #     data_type=pd.DataFrame,
    # ),
    # InputSpec(
    #     name="transcript_df",
    #     in_scaffold=True,
    #     data_type=pd.DataFrame,
    # ),
    # InputSpec(
    #     name="gene_substrate_mapping",
    #     in_scaffold=True,
    #     data_type=pd.DataFrame,
    # ),

    base_dir = r"/home/p70088775/git/VmaxBuilder/data/run_example_output/NCI_60_human_run/"

    swapam_data_dir = Path("/home/p70088775/git/SWAPAM/data/for_SWAMP/")
    model_dir = swapam_data_dir / "models" / "Human-GEM-2.0.0"

    artifacts_dir = Path(base_dir) / "artifacts"
    model_stage_dir = Path(artifacts_dir) / "model_stage"
    SMILES_df = pd.read_csv(Path(model_stage_dir) / "SMILES_df.csv", index_col=0)
    print("SMILES_df columns:", SMILES_df.columns)
    SMILES_df.index = SMILES_df["id"].astype(str)

    transcript_df = pd.read_csv(Path(model_stage_dir) / "transcript_df.csv", index_col=0)
    transcript_df.index = transcript_df["gene_id"].astype(str)
    with open(Path(model_stage_dir) / "gene_substrate_mapping.json", "r") as f:
        gene_substrate_mapping = json.load(f)

    unikp_implementation = object.__new__(UniKPImplementation)
    unikp_implementation.logger = CustomLogger(
        "unikp_implementation",
    )

    # small test on first 50 gene-substrate pairs
    gene_substrate_mapping = dict(list(gene_substrate_mapping.items())[:50])

    _, output_df = infer_kcats(  # ty: ignore
        smiles_df=SMILES_df,
        transcript_df=transcript_df,
        gene_substrate_pairs=gene_substrate_mapping,
        output_path=Path(base_dir) / "Kcat_stage",
        model_path=model_dir,
        chunk_size=200,
        embedding_batch_size=50,
        embedding_cache_save_every_batches=1,
        prediction_checkpoint_every_chunks=5,
        amount_of_smiles_replicates=50,
        type_of_smiles="isomeric_SMILES",
    )
    print("Output DataFrame:")
    pprint(output_df)
