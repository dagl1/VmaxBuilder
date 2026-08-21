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
        InputSpec(
            name="kcat_gene_metabolite_predictions",
            optional=True,
            prefix="kcat_gene_metabolite_predictions",
            extensions=".csv",
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="gene_substrate_predictions",
            extension=".csv",
            scaffold_location="outputs",
            save_file_name="gene_substrate_predictions",
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
        already_performed_gene_substrate_predictions = cast(
            pd.DataFrame, scaffold.get_scaffold_value("kcat_gene_metabolite_predictions")
        )

        if already_performed_gene_substrate_predictions is not None:
            genes_in_predictions = set(
                already_performed_gene_substrate_predictions["ensemble_id"]
            )
            genes_in_predictions = set(sorted(genes_in_predictions))
            missing_gene_substrate_pairs = {
                gene: substrates
                for gene, substrates in gene_substrate_mapping.items()
                if gene not in genes_in_predictions
            }
            gene_substrate_mapping = missing_gene_substrate_pairs

        model_path = cast(
            DiscoveredInput, scaffold.discovered_inputs["model"].get("cobra_model", None)
        )
        model_parent_path = self._get_model_parent_path(model_path)

        # Perform Kcat inference using the utility function
        (elapsed_time, (_kcat_paths, gene_substrate_predictions)) = self.get_time_decorator(
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
    gene_substrate_mapping = dict(list(gene_substrate_mapping.items()))

    lean_kcat_path = Path(base_dir) / "outputs" / "lean_kcat_inference"
    already_performed_gene_substrate_predictions = pd.read_csv(
        lean_kcat_path / "kcat_gene_metabolite_predictions.csv",
    )

    metabolite_ids_in_substrate_mapping = set(
        metabolite
        for metabolites in gene_substrate_mapping.values()
        for metabolite in metabolites
    )
    metabolite_ids_in_smiles_df = set(SMILES_df.index)

    gene_ids_in_substrate_mapping = set(gene_substrate_mapping.keys())
    gene_ids_in_transcript_df = set(transcript_df.index)
    genes_in_predictions = set(already_performed_gene_substrate_predictions["ensemble_id"])
    # sort all
    genes_in_predictions = set(sorted(genes_in_predictions))
    gene_ids_in_substrate_mapping = set(sorted(gene_ids_in_substrate_mapping))

    print("gene_substrate_mapping type:", type(gene_substrate_mapping))
    print("gene_substrate_mapping size:", len(gene_substrate_mapping))
    print("mapping keys type:", type(gene_substrate_mapping.keys()))
    print("first mapping keys:", list(gene_substrate_mapping.keys())[:10])

    print("transcript_df type:", type(transcript_df))
    print("transcript_df shape:", transcript_df.shape)
    print("first transcript index:", list(transcript_df.index[:10]))

    print(
        "already_performed predictions shape:",
        already_performed_gene_substrate_predictions.shape,
    )
    print(
        "first ensemble IDs:",
        already_performed_gene_substrate_predictions["ensemble_id"].head(10).tolist(),
    )
    prediction_genes_missing_from_mapping = (
        genes_in_predictions - gene_ids_in_substrate_mapping
    )
    prediction_genes_missing_from_transcript_df = (
        genes_in_predictions - gene_ids_in_transcript_df
    )
    genes_missing_from_transcript_df = (
        gene_ids_in_substrate_mapping - gene_ids_in_transcript_df
    )
    mapping_genes = set(gene_substrate_mapping)
    transcript_genes = set(transcript_df.index)
    prediction_genes = set(
        already_performed_gene_substrate_predictions["ensemble_id"].dropna()
    )

    print("Mapping:", len(mapping_genes))
    print("Transcript:", len(transcript_genes))
    print("Predictions:", len(prediction_genes))

    print("Mapping ∩ Transcript:", len(mapping_genes & transcript_genes))
    print("Mapping ∩ Predictions:", len(mapping_genes & prediction_genes))
    print("Transcript ∩ Predictions:", len(transcript_genes & prediction_genes))

    print("Mapping - Transcript:", len(mapping_genes - transcript_genes))
    print("Predictions - Mapping:", len(prediction_genes - mapping_genes))
    print("Predictions - Transcript:", len(prediction_genes - transcript_genes))
    print("Mapping - Predictions:", len(mapping_genes - prediction_genes))

    missing_gene_substrate_pairs = {
        gene: substrates
        for gene, substrates in gene_substrate_mapping.items()
        if gene not in genes_in_predictions
    }
    print(
        "Missing gene-substrate pairs (not in predictions):",
        len(missing_gene_substrate_pairs),
    )
    actual_pairs_missing_from_predictions = sum(
        len(substrates) for substrates in missing_gene_substrate_pairs.values()
    )
    print(
        "Actual gene-substrate pairs missing from predictions:",
        actual_pairs_missing_from_predictions,
    )

    mapping_metabolites = set(
        metabolite
        for metabolites in gene_substrate_mapping.values()
        for metabolite in metabolites
    )
    smiles_metabolites = set(SMILES_df.index)
    prediction_metabolites = set(
        already_performed_gene_substrate_predictions["metabolite_id"].dropna()
    )

    print("Mapping metabolites:", len(mapping_metabolites))
    print("SMILES metabolites:", len(smiles_metabolites))
    print("Prediction metabolites:", len(prediction_metabolites))

    print("Mapping ∩ SMILES:", len(mapping_metabolites & smiles_metabolites))
    print("Mapping ∩ Prediction:", len(mapping_metabolites & prediction_metabolites))
    print("SMILES ∩ Prediction:", len(smiles_metabolites & prediction_metabolites))

    print("Mapping - SMILES:", len(mapping_metabolites - smiles_metabolites))
    print("Prediction - Mapping:", len(prediction_metabolites - mapping_metabolites))
    print("Prediction - SMILES:", len(prediction_metabolites - smiles_metabolites))

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
    # print("Output DataFrame:")
    # pprint(output_df)
