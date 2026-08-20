from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pandas as pd
from cobra.core.model import Model
from cobra.io.json import load_json_model

from VmaxBuilder.base.classes import (
    RealImplementation,
)
from VmaxBuilder.base.configs import InputSpec, OutputSpec, Scaffold
from VmaxBuilder.database_retrieval import IdentifierTranslationService
from VmaxBuilder.Kcat_preprocessing.config import (
    TranscriptSmilesGetterConfig,
    TranscriptSmilesGetterConfigProtocol,
)
from VmaxBuilder.Kcat_preprocessing.gene_substrate_preprocessing import (
    get_gene_substrate_mapping,
)
from VmaxBuilder.Kcat_preprocessing.smiles_retrieval import (
    SmilesRetrievalService,
    function_for_identifying_novel_found_SMILES_and_only_doing_those,
    load_manually_curated_smiles_file,
    load_model_data_frame,
)

# todo: make sequence lookup faster, and allow to work from diff of already existing
# Also would be good to save output to original model filepath instead of only output


class TranscriptSMILESGetter(RealImplementation[TranscriptSmilesGetterConfigProtocol]):
    """Generated: validation needed.

    Description:
        Build metabolite SMILES table for transcript-level Kcat preprocessing while
        preserving legacy lookup capabilities behind cleaner service helpers.
    """

    STAGE_NAME: str = "model"  # while necessary for kcat, it really is based on the model
    IMPL_NAME: str = "SMILES_transcript_getter"
    IMPLEMENTATION_CONFIG_CLASS = TranscriptSmilesGetterConfig
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="cobra_model",
            data_type=Model,
            in_scaffold=True,
        ),
        InputSpec(
            name="cobra_model_data",
            data_type=pd.DataFrame,
            loader=load_model_data_frame,
            prefix="model_data",  # for SysBioChalmers models (Human1 etc. ) this is
            # often a .xlsx file with multiple sheets. Rename it to avoid confusion
            extensions=[".csv", ".xlsx"],
            optional=True,
        ),
        InputSpec(
            name="genes_df",
            data_type=pd.DataFrame,
            optional=True,
            prefix="model_genes",  # for SysBioChalmers models (Human1 etc. ) this is
            # often a .xlsx file with multiple sheets. Rename it to avoid confusion
            extensions=[".tsv", ".csv", ".xlsx"],
        ),
        InputSpec(
            name="metabolites_df",
            data_type=pd.DataFrame,
            prefix="model_metabolites",  # for SysBioChalmers models (Human1 etc. ) this is
            # often a .xlsx file with multiple sheets. Rename it to avoid confusion
            extensions=[".tsv", ".csv", ".xlsx"],
            optional=True,
        ),
        InputSpec(
            name="SMILES_df",
            data_type=pd.DataFrame,
            optional=True,
        ),
        InputSpec(
            name="manually_curated_SMILES_df",
            data_type=pd.DataFrame,
            prefix="manually_curated_SMILES",
            loader=load_manually_curated_smiles_file,
            optional=True,
        ),
        InputSpec(
            name="metabolites_SMILES_Inchi_df",
            data_type=pd.DataFrame,
            optional=True,
            prefix="metabolites_SMILES_Inchi",
            extensions=[
                ".tsv",
            ],
        ),
        InputSpec(
            name="transcript_df",
            data_type=pd.DataFrame,
            optional=True,
        ),
        InputSpec(
            name="metabolite_name_synonyms_df",
            data_type=pd.DataFrame,
            optional=True,
            prefix="metabolite_name_synonyms",
            extensions=[".tsv", ".csv"],
        ),
        InputSpec(
            name="chebi_df",
            data_type=pd.DataFrame,
            optional=True,
            prefix="chebi_id_SMILES",
            extensions=[".csv", ".tsv"],
        ),
        InputSpec(
            name="chem_prop_df",
            data_type=pd.DataFrame,
            optional=True,
            prefix="chem_prop",
            extensions=[".tsv", ".csv"],
        ),
        InputSpec(
            name="recon3d_data",
            data_type=dict,
            optional=True,
            prefix="Recon3D",
            extensions=[".json"],
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="SMILES_df",
            data_type=pd.DataFrame,
            scaffold_location="artifacts",
            save_file_name="SMILES_df",
            extension=".csv",
            validator=None,
        ),
        OutputSpec(
            name="transcript_df",
            data_type=pd.DataFrame,
            scaffold_location="artifacts",
            save_file_name="transcript_df",
            extension=".csv",
            validator=None,
        ),
        OutputSpec(
            "gene_substrate_mapping",
            data_type=dict[str, set[str]],
            scaffold_location="artifacts",
            save_file_name="gene_substrate_mapping",
            extension=".json",
        ),
        OutputSpec(
            name="gene_transcript_mapping",
            data_type=pd.DataFrame,
            scaffold_location="artifacts",
            save_file_name="gene_transcript_mapping",
            extension=".csv",
        ),
        OutputSpec(
            name="transcript_to_gene_mapping",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="transcript_to_gene_mapping",
            extension=".json",
        ),
        OutputSpec(
            name="gene_to_transcript_mapping",
            data_type=dict,
            scaffold_location="artifacts",
            save_file_name="gene_to_transcript_mapping",
            extension=".json",
        ),
        OutputSpec(
            name="protein_coding_transcripts",
            data_type=list,
            scaffold_location="artifacts",
            save_file_name="protein_coding_transcripts",
            extension=".json",
        ),
        OutputSpec(
            name="canonical_transcripts",
            data_type=list,
            scaffold_location="artifacts",
            save_file_name="canonical_transcripts",
            extension=".json",
        ),
    ]

    def generate_outputs(self, scaffold: Scaffold) -> dict[str, dict[str, Any]]:
        """Generated: validation needed.

        Description:
            Resolve metabolite SMILES for current model, reuse prior results where
            possible, and return transcript/Kcat preprocessing payloads.

        Args:
            scaffold (Scaffold): Shared pipeline scaffold.

        Returns:
            dict[str, dict[str, Any]]: Scaffold payload containing SMILES artifacts,
                transcript diagnostics, gene-substrate mapping, and metadata.

        Raises:
            ValueError: If COBRA model is unavailable.
        """

        self.load_inputs(scaffold)
        cobra_model = scaffold.get_scaffold_value("cobra_model", Model)
        if cobra_model is None:
            raise ValueError("No COBRA model found in scaffold for SMILES processing.")

        smiles_service = SmilesRetrievalService(
            logger=self.logger,
            use_most_protonated_smiles=self.config.use_most_protonated_smiles,
            smiles_length_limit=self.config.smiles_length_limit,
        )

        elapsed_time, smiles_result = self.get_time_decorator(
            smiles_service.build_smiles_dataframe
        )(
            cobra_model=cobra_model,
            existing_smiles_df=self._get_dataframe_value(scaffold, "SMILES_df"),
            model_data_df=self._get_dataframe_value(scaffold, "cobra_model_data"),
            metabolites_df=self._get_dataframe_value(scaffold, "metabolites_df"),
            manually_curated_smiles_df=self._get_dataframe_value(
                scaffold,
                "manually_curated_SMILES_df",
            ),
            metabolites_smiles_inchi_df=self._get_dataframe_value(
                scaffold,
                "metabolites_SMILES_Inchi_df",
            ),
            metabolite_name_synonyms_df=self._get_dataframe_value(
                scaffold,
                "metabolite_name_synonyms_df",
            ),
            chebi_df=self._get_dataframe_value(scaffold, "chebi_df"),
            chem_prop_df=self._get_dataframe_value(scaffold, "chem_prop_df"),
            recon3d_data=self._get_dictionary_value(scaffold, "recon3d_data"),
        )

        transcript_artifacts = self._get_or_build_transcript_artifacts(scaffold, cobra_model)
        transcript_df = transcript_artifacts["gene_transcript_mapping"]

        gene_substrate_mapping = get_gene_substrate_mapping(cobra_model=cobra_model)
        previous_smiles_df = self._get_dataframe_value(scaffold, "SMILES_df")
        if previous_smiles_df is None:
            previous_smiles_df = pd.DataFrame()
        novel_lookup_targets = (
            function_for_identifying_novel_found_SMILES_and_only_doing_those(
                old_SMILES_df=previous_smiles_df,
                new_SMILES_df=smiles_result.smiles_df,
            )
        )
        scaffold.inputs["SMILES_df"] = smiles_result.smiles_df
        scaffold.inputs["transcript_df"] = transcript_df
        scaffold.artifacts.update(transcript_artifacts)

        metadata = self.create_metadata(
            elapsed_time=elapsed_time,
        )
        diagnostics = {
            "transcript_df": transcript_df,
            "smiles_summary": smiles_result.summary,
            "smiles_diagnostics": smiles_result.diagnostics,
            "novel_lookup_targets": novel_lookup_targets,
            "transcript_lookup_summary": {
                "rows": int(len(transcript_df)),
                "canonical_rows": int(transcript_df["is_canonical"].sum())
                if "is_canonical" in transcript_df.columns
                else 0,
                "contains_alternative_transcripts": bool(
                    (~transcript_df["is_canonical"]).any()
                )
                if "is_canonical" in transcript_df.columns and not transcript_df.empty
                else False,
                "flags_corrected_from_sequence_evidence": int(
                    transcript_artifacts["transcript_sequence_flag_summary"].get(
                        "flags_corrected_from_sequence_evidence",
                        0,
                    )
                ),
            },
            "transcript_sequence_flag_summary": transcript_artifacts[
                "transcript_sequence_flag_summary"
            ],
        }

        return {
            "outputs": {},
            "artifacts": {
                "SMILES_df": smiles_result.smiles_df,
                "transcript_df": transcript_df,
                "gene_substrate_mapping": gene_substrate_mapping,
                **transcript_artifacts,
            },
            "metadata": metadata,
            "diagnostics": diagnostics,
        }

    def create_metadata(self, elapsed_time: float, **kwargs) -> dict[str, Any]:
        metadata = {
            "model": {
                "implementation": type(self).__name__,
                "elapsed_time_seconds": elapsed_time,
                "status": "smiles_transcript_artifacts_built",
                "date_created": pd.Timestamp.now().isoformat(),
                "params": self.get_implementation_config_params(),
            }
        }
        return metadata

    def _get_or_build_transcript_artifacts(
        self,
        scaffold: Scaffold,
        cobra_model: Model,
    ) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Return transcript artifacts from scaffold when provided, otherwise retrieve
            transcript and amino-acid metadata for model genes.

        Args:
            scaffold (Scaffold): Shared scaffold payload.
            cobra_model (Model): COBRA model containing gene identifiers.

        Returns:
            dict[str, Any]: Transcript dataframe plus derived mapping artifacts.
        """

        transcript_df = self._get_dataframe_value(scaffold, "transcript_df")
        sequence_flag_summary = {
            "target_type": "unknown",
            "rows_with_sequence_evidence": 0,
            "protein_coding_flags_corrected": 0,
            "canonical_flags_corrected": 0,
            "flags_corrected_from_sequence_evidence": 0,
        }
        if transcript_df is not None:
            if self.config.enrich_existing_transcript_df_with_sequences:
                identifier_translation_service = IdentifierTranslationService(
                    logger=self.logger
                )
                transcript_df = (
                    identifier_translation_service.enrich_transcript_dataframe_with_sequences(
                        transcript_df,
                        include_cdna_sequence=self.config.include_cdna_sequence,
                        max_workers=(self.full_config.transcripts.id_translation_max_workers),
                    )
                )
                sequence_flag_summary = dict(
                    identifier_translation_service.last_sequence_lookup_summary
                )
            return self._build_transcript_artifact_payload(
                transcript_df,
                sequence_flag_summary=sequence_flag_summary,
            )

        if not self.config.retrieve_transcript_metadata:
            return self._build_transcript_artifact_payload(self._empty_transcript_dataframe())

        genes_in_model = [str(gene.id) for gene in cobra_model.genes if str(gene.id).strip()]
        gene_id_type = self._infer_gene_id_type()
        if not genes_in_model or gene_id_type is None:
            return self._build_transcript_artifact_payload(self._empty_transcript_dataframe())

        identifier_translation_service = IdentifierTranslationService(logger=self.logger)
        target_type = "transcript" if self.config.retrieve_alternative_transcripts else "gene"
        transcript_df = identifier_translation_service.build_gene_transcript_dataframe(
            genes_in_model,
            gene_id_type=gene_id_type,
            target_type=target_type,
            species=self.full_config.transcripts.id_translation_species,
            provider=self.full_config.transcripts.id_translation_provider,
            max_workers=self.full_config.transcripts.id_translation_max_workers,
            batch_size=self.full_config.transcripts.id_translation_batch_size,
            include_sequence_metadata=True,
            include_cdna_sequence=self.config.include_cdna_sequence,
        )
        transcript_df = self._filter_transcript_dataframe(transcript_df)
        sequence_flag_summary = dict(
            identifier_translation_service.last_sequence_lookup_summary
        )
        return self._build_transcript_artifact_payload(
            transcript_df,
            sequence_flag_summary=sequence_flag_summary,
        )

    def _filter_transcript_dataframe(self, transcript_df: pd.DataFrame) -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Apply configured transcript filtering, keeping canonical-only mode as default
            while optionally retaining alternative transcripts.

        Args:
            transcript_df (pd.DataFrame): Retrieved transcript metadata dataframe.

        Returns:
            pd.DataFrame: Filtered transcript metadata dataframe.
        """

        if transcript_df.empty:
            return cast(pd.DataFrame, transcript_df.reset_index(drop=True))

        filtered_transcript_df = transcript_df.copy()
        if self.full_config.transcripts.protein_coding_only and (
            "is_protein_coding" in filtered_transcript_df.columns
        ):
            protein_coding_mask = (
                filtered_transcript_df["is_protein_coding"].fillna(False).astype(bool)
            )
            filtered_transcript_df = filtered_transcript_df.loc[protein_coding_mask].copy()
            if not isinstance(filtered_transcript_df, pd.DataFrame):
                return transcript_df.reset_index(drop=True)

        if self.config.retrieve_alternative_transcripts:
            return cast(pd.DataFrame, filtered_transcript_df.reset_index(drop=True))

        if "is_canonical" not in filtered_transcript_df.columns:
            return cast(pd.DataFrame, filtered_transcript_df.reset_index(drop=True))

        canonical_mask = filtered_transcript_df["is_canonical"].fillna(False)
        canonical_transcript_df = filtered_transcript_df.loc[canonical_mask].copy()
        if not isinstance(canonical_transcript_df, pd.DataFrame):
            return cast(pd.DataFrame, filtered_transcript_df.reset_index(drop=True))
        if canonical_transcript_df.empty:
            return cast(pd.DataFrame, filtered_transcript_df.reset_index(drop=True))
        return cast(pd.DataFrame, canonical_transcript_df.reset_index(drop=True))

    def _build_transcript_artifact_payload(
        self,
        transcript_df: pd.DataFrame,
        *,
        sequence_flag_summary: dict[str, int | str] | None = None,
    ) -> dict[str, Any]:
        """Generated: validation needed.

        Description:
            Build transcript mapping and sequence artifacts from transcript dataframe.

        Args:
            transcript_df (pd.DataFrame): Transcript metadata dataframe.
            sequence_flag_summary (dict[str, int | str] | None): Optional
                diagnostics summary for sequence-based flag corrections.

        Returns:
            dict[str, Any]: Transcript artifacts used by downstream transcript-aware logic.
        """

        if transcript_df.empty:
            transcript_to_gene_mapping: dict[str, str] = {}
            gene_to_transcript_mapping: dict[str, list[str]] = {}
            protein_coding_transcripts: list[str] = []
            canonical_transcripts: list[str] = []
        else:
            working_transcript_df = transcript_df.copy()
            if "is_protein_coding" not in working_transcript_df.columns:
                working_transcript_df["is_protein_coding"] = False
            if "is_canonical" not in working_transcript_df.columns:
                working_transcript_df["is_canonical"] = False

            transcript_to_gene_mapping = transcript_df.set_index("transcript_id")[
                "gene_id"
            ].to_dict()
            gene_to_transcript_mapping = (
                transcript_df.groupby("gene_id")["transcript_id"].agg(list).to_dict()
            )
            protein_coding_transcripts = working_transcript_df[
                working_transcript_df["is_protein_coding"].fillna(False)
            ]["transcript_id"].tolist()
            canonical_transcripts = working_transcript_df[
                working_transcript_df["is_canonical"].fillna(False)
            ]["transcript_id"].tolist()

        return {
            "gene_transcript_mapping": transcript_df.reset_index(drop=True),
            "transcript_to_gene_mapping": transcript_to_gene_mapping,
            "gene_to_transcript_mapping": gene_to_transcript_mapping,
            "protein_coding_transcripts": protein_coding_transcripts,
            "canonical_transcripts": canonical_transcripts,
            "transcript_sequence_flag_summary": sequence_flag_summary
            if sequence_flag_summary is not None
            else {
                "target_type": "unknown",
                "rows_with_sequence_evidence": 0,
                "protein_coding_flags_corrected": 0,
                "canonical_flags_corrected": 0,
                "flags_corrected_from_sequence_evidence": 0,
            },
        }

    def _infer_gene_id_type(self) -> str | None:
        """Generated: validation needed.

        Description:
            Infer identifier-translation source type for model genes from active model config.

        Returns:
            str | None: Translation service gene identifier type, or None when it cannot
                be inferred safely.
        """

        model_config = getattr(self.full_config, "model", None)
        if model_config is None:
            return None

        gene_id_type = getattr(model_config, "gene_id_type", None)
        level = str(getattr(model_config, "level", "gene")).lower()
        if isinstance(gene_id_type, str) and gene_id_type.strip():
            if gene_id_type.startswith("ensembl_") or gene_id_type in {
                "symbol",
                "entrez_gene_id",
                "ensembl_gene_id",
                "ensembl_transcript_id",
            }:
                return gene_id_type
            if gene_id_type == "ensembl":
                return f"ensembl_{level}_id"
            return gene_id_type

        provider_id_type = getattr(model_config, "id_type", None)
        if not isinstance(provider_id_type, str) or not provider_id_type.strip():
            return None
        if provider_id_type == "ensembl":
            return f"ensembl_{level}_id"
        return provider_id_type

    @staticmethod
    def _empty_transcript_dataframe() -> pd.DataFrame:
        """Generated: validation needed.

        Description:
            Create empty transcript metadata dataframe with expected sequence columns.

        Returns:
            pd.DataFrame: Empty transcript metadata dataframe.
        """

        return pd.DataFrame(
            columns=[
                "transcript_id",
                "gene_id",
                "is_protein_coding",
                "is_canonical",
                "translation_id",
                "peptide_len",
                "cdna_len",
                "peptide_seq",
                "cdna_seq",
            ]
        )

    @staticmethod
    def _get_dataframe_value(
        scaffold: Scaffold,
        key: str,
    ) -> pd.DataFrame | None:
        """Generated: validation needed.

        Description:
            Read dataframe-like value from scaffold when present.

        Args:
            scaffold (Scaffold): Shared scaffold payload.
            key (str): Scaffold key to retrieve.

        Returns:
            pd.DataFrame | None: Retrieved dataframe, or None when absent or wrong type.
        """

        value = scaffold.get_scaffold_value(key)
        return value if isinstance(value, pd.DataFrame) else None

    @staticmethod
    def _get_dictionary_value(
        scaffold: Scaffold,
        key: str,
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Generated: validation needed.

        Description:
            Read dictionary- or list-like value from scaffold when present.

        Args:
            scaffold (Scaffold): Shared scaffold payload.
            key (str): Scaffold key to retrieve.

        Returns:
            dict[str, Any] | list[dict[str, Any]] | None: Retrieved value when type is
                compatible with Recon3D-style payloads.
        """

        value = scaffold.get_scaffold_value(key)
        if isinstance(value, dict):
            return value
        if isinstance(value, list) and all(isinstance(entry, dict) for entry in value):
            return value
        return None


if __name__ == "__main__":
    # base_dir = Path(
    #     "/home/p70088775/git/VmaxBuilder/data/run_example_output/NCI_60_human_run/"
    # )
    # swapam_data_dir = Path("E:/git/SWAPAM/data/for_SWAMP/")
    # model_dir = swapam_data_dir / "models" / "HumanGEM_2"
    # model_file = model_dir / "model_HumanGEM_2.json"
    # transcript_df_path = model_dir / "transcript_df.csv"

    base_dir = Path(
        "/home/p70088775/git/VmaxBuilder/data/run_example_output/NCI_60_human_run/"
    )
    swapam_data_dir = Path("/home/p70088775/git/SWAPAM/data/for_SWAMP/")
    model_dir = swapam_data_dir / "models" / "Human-GEM-2.0.0"
    model_file = model_dir / "model_Human-GEM.json"
    transcript_df_path = base_dir / "artifacts" / "model_stage" / "transcript_df.csv"

    # metabolites_file = model_dir / "model_metabolites.tsv"
    # model_data_file = model_dir / "model_data_Human-GEM.xlsx"
    # manually_curated_smiles_file = model_dir / "manually_curated_SMILES.csv"
    # metabolites_smiles_inchi_file = model_dir / "metabolites_SMILES_Inchi.tsv"
    # metabolite_name_synonyms_file = model_dir / "metabolite_name_synonyms.tsv"
    # chebi_file = model_dir / "chebi_id_SMILES.csv"
    # chem_prop_file = model_dir / "chem_prop.tsv"
    # recon3d_file = model_dir / "Recon3D.json"
    #
    cobra_model = load_json_model(model_file)
    # gene_substrate_mapping = get_gene_substrate_mapping(cobra_model=cobra_model)
    # # save in base_dir/artifacts/model_stage/gene_substrate_mapping.json
    # # with open(
    # #     base_dir / "artifacts" / "model_stage" / "gene_substrate_mapping.json", "w"
    # # ) as f:
    # #     import json
    # #
    # #     json.dump(make_json_serializable(gene_substrate_mapping), f, indent=4)
    # print("Number of genes in model:", len(gene_substrate_mapping))
    #
    # model_data_df = load_model_data_frame(model_data_file)
    # metabolites_df = pd.read_csv(metabolites_file, sep="\t")
    # manually_curated_smiles_df = load_manually_curated_smiles_file(
    #     manually_curated_smiles_file
    # )
    # metabolites_smiles_inchi_df = pd.read_csv(
    #     metabolites_smiles_inchi_file,
    #     sep="\t",
    #     dtype=str,
    # )
    # metabolite_name_synonyms_df = pd.read_csv(
    #     metabolite_name_synonyms_file,
    #     sep="\t",
    #     dtype=str,
    # ) if metabolite_name_synonyms_file.exists() else None
    # chebi_df = pd.read_csv(chebi_file, dtype=str) if chebi_file.exists() else None
    # chem_prop_df = (
    #     pd.read_csv(chem_prop_file, sep="\t", dtype=str)
    #     if chem_prop_file.exists()
    #     else None
    # )
    # recon3d_data = None
    # if recon3d_file.exists():
    #     import json
    #
    #     recon3d_data = json.loads(recon3d_file.read_text(encoding="utf-8"))
    #
    # smiles_service = SmilesRetrievalService()
    # smiles_result = smiles_service.build_smiles_dataframe(
    #     cobra_model=cobra_model,
    #     model_data_df=model_data_df,
    #     metabolites_df=metabolites_df,
    #     manually_curated_smiles_df=manually_curated_smiles_df,
    #     metabolites_smiles_inchi_df=metabolites_smiles_inchi_df,
    #     metabolite_name_synonyms_df=metabolite_name_synonyms_df,
    #     chebi_df=chebi_df,
    #     chem_prop_df=chem_prop_df,
    #     recon3d_data=recon3d_data,
    # )
    # base_dir.mkdir(parents=True, exist_ok=True)
    # smiles_result.smiles_df.to_csv(base_dir / "SMILES_df.csv", index=False)
    # print("Total rows in SMILES_df:", len(smiles_result.smiles_df))
    # print("Number of rows with missing smiles:", smiles_result.summary["missing_smiles"])
    # print(
    #     "Number of rows with smiles longer than 218 characters:",
    #     smiles_result.summary["smiles_longer_than_218"],
    # )
    identifier_translation_service = IdentifierTranslationService(logger=None)

    genes_in_model = [str(gene.id) for gene in cobra_model.genes if str(gene.id).strip()]
    genes_in_model = list(set(genes_in_model))[50:150]
    transcript_df = identifier_translation_service.build_gene_transcript_dataframe(
        genes_in_model,
        gene_id_type="ensembl_gene_id",
        # species=self.full_config.transcripts.id_translation_species,
        # provider=self.full_config.transcripts.id_translation_provider,
        # max_workers=self.full_config.transcripts.id_translation_max_workers,
        # batch_size=self.full_config.transcripts.id_translation_batch_size,
        provider="auto",
        max_workers=6,
        batch_size=100,
        include_sequence_metadata=True,
        include_cdna_sequence=True,
    )

    # save it as transcript_df.csv in base_dir/artifacts/model_stage/transcript_df.csv
    transcript_df.to_csv(transcript_df_path, index=False)
