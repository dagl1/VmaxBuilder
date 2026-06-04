from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import pytest

from VmaxBuilder.api import VmaxOrchestrator
from VmaxBuilder.api.protein import ProteinStageOrchestrator
from VmaxBuilder.config import APIConfig, ConfigurationError, LoadingPolicy, ProteinSourceMode
from VmaxBuilder.database_retrieval import IdentifierTranslationResult
from VmaxBuilder.expression import DefaultExpressionImplementation
from VmaxBuilder.protein import (
    DefaultProteinStageCoordinator,
    DefaultProteomicsImplementation,
    DefaultPTRImplementation,
)


class FakeTranslationService:
    def __init__(
        self,
        *,
        gene_mapping: dict[str, str] | None = None,
        transcript_mapping: dict[str, str] | None = None,
        protein_coding_transcripts: set[str] | None = None,
    ) -> None:
        self.gene_mapping = gene_mapping or {}
        self.transcript_mapping = transcript_mapping or {}
        self.protein_coding_transcripts = protein_coding_transcripts or set()
        self.translate_calls: int = 0
        self.transcript_map_calls: int = 0

    def translate_identifiers(
        self,
        identifiers: Sequence[str],
        *,
        source_id_type: str,
        target_id_type: str,
        species: str | None,
        provider: str,
        max_workers: int,
        batch_size: int,
    ) -> IdentifierTranslationResult:
        self.translate_calls += 1
        mapped_identifiers = {
            identifier: self.gene_mapping[identifier]
            for identifier in identifiers
            if identifier in self.gene_mapping
        }
        unresolved_identifiers = [
            identifier for identifier in identifiers if identifier not in mapped_identifiers
        ]
        return IdentifierTranslationResult(
            mapped_identifiers=mapped_identifiers,
            unresolved_identifiers=unresolved_identifiers,
        )

    def build_transcript_gene_dataframe(
        self,
        transcript_ids: Sequence[str],
        *,
        transcript_id_type: str,
        target_gene_id_type: str,
        species: str | None,
        provider: str,
        max_workers: int,
        batch_size: int,
    ) -> pd.DataFrame:
        self.transcript_map_calls += 1
        rows = [
            {
                "transcript_id": transcript_id,
                "gene_id": self.transcript_mapping[transcript_id],
                "is_protein_coding": transcript_id in self.protein_coding_transcripts,
            }
            for transcript_id in transcript_ids
            if transcript_id in self.transcript_mapping
        ]
        return pd.DataFrame(rows, columns=["transcript_id", "gene_id", "is_protein_coding"])


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
    config.expression.sample_type_map = "sample_1"

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
    fake_translation_service = FakeTranslationService(
        transcript_mapping={"ENST1.1": "ENST1", "ENST1.2": "ENST1"},
    )
    expression_implementation = DefaultExpressionImplementation(
        translation_service=fake_translation_service,
    )
    coordinator = DefaultProteinStageCoordinator(
        expression_implementation=expression_implementation,
    )
    config = APIConfig(
        loading=LoadingPolicy(in_memory_inputs={"expression": expression_df, "ptr": ptr_df}),
    )
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR
    config.expression.sample_type_map = "sample_1"
    config.expression.level = "transcript"
    config.expression.id_type = "ensembl"
    config.run_target_transcript_gene_level = "gene"

    scaffold = VmaxOrchestrator(
        config=config,
        protein_stage=ProteinStageOrchestrator(implementation=coordinator),
    ).run_protein()

    protein_df = scaffold["artifacts"]["protein_abundance"]
    assert list(protein_df.index) == ["ENST1"]
    assert protein_df.loc["ENST1", "sample_1"] == 3.0
    assert scaffold["metadata"]["protein_stage"]["required_inputs"] == [
        "expression",
        "ptr",
    ]


def test_expression_ptr_mode_translates_expression_ids_when_model_id_type_mismatch() -> None:
    expression_df = pd.DataFrame(
        {"sample_1": [2.0, 3.0]},
        index=["TP53", "EGFR"],
    )
    ptr_df = pd.DataFrame(
        {"sample_1": [10.0, 20.0]},
        index=["ENSG00000141510", "EGFR"],
    )
    fake_translation_service = FakeTranslationService(
        gene_mapping={"TP53": "ENSG00000141510"},
    )
    expression_implementation = DefaultExpressionImplementation(
        translation_service=fake_translation_service,
    )
    coordinator = DefaultProteinStageCoordinator(
        expression_implementation=expression_implementation,
    )
    config = APIConfig(
        loading=LoadingPolicy(in_memory_inputs={"expression": expression_df, "ptr": ptr_df}),
    )
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR
    config.expression.sample_type_map = "sample_1"
    config.expression.id_type = "symbol"
    config.model.id_type = "ensembl"

    scaffold = VmaxOrchestrator(
        config=config,
        protein_stage=ProteinStageOrchestrator(implementation=coordinator),
    ).run_protein()

    protein_df = scaffold["artifacts"]["protein_abundance"]
    assert fake_translation_service.translate_calls == 1
    assert protein_df.loc["ENSG00000141510", "sample_1"] == 20.0
    assert protein_df.loc["EGFR", "sample_1"] == 60.0
    assert scaffold["diagnostics"]["expression_preparation"]["id_translation"] == {
        "source_id_type": "symbol",
        "target_id_type": "ensembl_gene_id",
        "mapped_identifiers": 1,
        "unresolved_identifiers": ["EGFR"],
    }


def test_expression_ptr_mode_stores_transcript_gene_map_artifact_and_aggregates(
    tmp_path: Path,
) -> None:
    expression_df = pd.DataFrame(
        {"sample_1": [1.0, 2.0, 4.0]},
        index=["ENST0001", "ENST0002", "ENST9999"],
    )
    ptr_df = pd.DataFrame(
        {"sample_1": [10.0, 5.0]},
        index=["ENSG001", "ENST9999"],
    )
    fake_translation_service = FakeTranslationService(
        transcript_mapping={"ENST0001": "ENSG001", "ENST0002": "ENSG001"},
    )
    expression_implementation = DefaultExpressionImplementation(
        translation_service=fake_translation_service,
    )
    coordinator = DefaultProteinStageCoordinator(
        expression_implementation=expression_implementation,
    )
    config = APIConfig(
        loading=LoadingPolicy(
            in_memory_inputs={"expression": expression_df, "ptr": ptr_df},
            output_path=tmp_path,
        ),
    )
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR
    config.expression.sample_type_map = "sample_1"
    config.expression.level = "transcript"
    config.expression.id_type = "ensembl"
    config.run_target_transcript_gene_level = "gene"
    config.model.id_type = "ensembl"
    config.model.level = "gene"

    scaffold = VmaxOrchestrator(
        config=config,
        protein_stage=ProteinStageOrchestrator(implementation=coordinator),
    ).run_protein()

    protein_df = scaffold["artifacts"]["protein_abundance"]
    assert fake_translation_service.transcript_map_calls == 1
    assert list(scaffold["artifacts"]["transcript_gene_map"].columns) == [
        "transcript_id",
        "gene_id",
        "is_protein_coding",
    ]
    assert protein_df.loc["ENSG001", "sample_1"] == 30.0
    assert protein_df.loc["ENST9999", "sample_1"] == 20.0
    assert (
        scaffold["diagnostics"]["expression_preparation"]["transcript_unresolved_count"] == 1
    )


def test_expression_ptr_mode_raises_for_unsupported_transcript_aggregation_policy(
    tmp_path: Path,
) -> None:
    expression_df = pd.DataFrame({"sample_1": [1.0]}, index=["ENST0001"])
    ptr_df = pd.DataFrame({"sample_1": [1.0]}, index=["ENSG001"])
    fake_translation_service = FakeTranslationService(
        transcript_mapping={"ENST0001": "ENSG001"},
    )
    expression_implementation = DefaultExpressionImplementation(
        translation_service=fake_translation_service,
    )
    coordinator = DefaultProteinStageCoordinator(
        expression_implementation=expression_implementation,
    )
    config = APIConfig(
        loading=LoadingPolicy(
            in_memory_inputs={"expression": expression_df, "ptr": ptr_df},
            output_path=tmp_path,
        ),
    )
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR
    config.expression.sample_type_map = "sample_1"
    config.expression.level = "transcript"
    config.expression.transcript_aggregation_policy = "median"
    config.run_target_transcript_gene_level = "gene"

    with pytest.raises(ConfigurationError, match="Unsupported transcript aggregation policy"):
        VmaxOrchestrator(
            config=config,
            protein_stage=ProteinStageOrchestrator(implementation=coordinator),
        ).run_protein()


def test_expression_ptr_mode_uses_protein_coding_only_aggregation_policy(
    tmp_path: Path,
) -> None:
    expression_df = pd.DataFrame({"sample_1": [1.0, 3.0]}, index=["ENST0001", "ENST0002"])
    ptr_df = pd.DataFrame({"sample_1": [2.0]}, index=["ENSG001"])
    fake_translation_service = FakeTranslationService(
        transcript_mapping={"ENST0001": "ENSG001", "ENST0002": "ENSG001"},
        protein_coding_transcripts={"ENST0002"},
    )
    expression_implementation = DefaultExpressionImplementation(
        translation_service=fake_translation_service,
    )
    coordinator = DefaultProteinStageCoordinator(
        expression_implementation=expression_implementation,
    )

    config = APIConfig(
        loading=LoadingPolicy(
            in_memory_inputs={"expression": expression_df, "ptr": ptr_df},
            output_path=tmp_path,
        ),
    )
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR
    config.expression.sample_type_map = "sample_1"
    config.expression.level = "transcript"
    config.run_target_transcript_gene_level = "gene"
    config.transcript_processing.protein_coding_only = True
    config.transcript_processing.protein_coding_aggregation_policy = "mean"

    scaffold = VmaxOrchestrator(
        config=config,
        protein_stage=ProteinStageOrchestrator(implementation=coordinator),
    ).run_protein()

    # only ENST0002 kept by protein_coding_only filter, mean policy applied
    assert scaffold["artifacts"]["protein_abundance"].loc["ENSG001", "sample_1"] == 6.0


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
    config.expression.sample_type_map = "sample_1"

    scaffold = VmaxOrchestrator(config=config).run_protein()

    protein_df = scaffold["artifacts"]["protein_abundance"]
    assert protein_df.loc["gene_a", "sample_1"] == 6.0


def test_expression_ptr_mode_raises_when_sample_type_map_missing() -> None:
    expression_df = pd.DataFrame(
        {"sample_1": [2.0]},
        index=["gene_a"],
    )
    ptr_df = pd.DataFrame(
        {"heart": [3.0]},
        index=["gene_a"],
    )
    config = APIConfig(
        loading=LoadingPolicy(in_memory_inputs={"expression": expression_df, "ptr": ptr_df}),
    )
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR

    with pytest.raises(ConfigurationError, match="expression.sample_type_map is required"):
        VmaxOrchestrator(config=config).run_protein()


def test_expression_ptr_mode_uses_heart_tissue_mapping_with_ensg_expression() -> None:
    eraslan_ptr_df = pd.DataFrame(
        {
            "heart": [10.0, 5.0],
            "lung": [2.0, 2.0],
        },
        index=["ENSG00000141510", "ENSG00000146648"],
    )
    expression_df = pd.DataFrame(
        {"sample_patient_1": [3.0, 4.0]},
        index=["ENSG00000141510", "ENSG00000146648"],
    )
    config = APIConfig(
        loading=LoadingPolicy(
            in_memory_inputs={"expression": expression_df, "ptr": eraslan_ptr_df}
        ),
    )
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR
    config.expression.id_type = "ensembl"
    config.expression.level = "gene"
    config.expression.sample_type_map = "heart"

    scaffold = VmaxOrchestrator(config=config).run_protein()

    protein_df = scaffold["artifacts"]["protein_abundance"]
    assert protein_df.loc["ENSG00000141510", "sample_patient_1"] == 30.0
    assert protein_df.loc["ENSG00000146648", "sample_patient_1"] == 20.0


def test_expression_ptr_mode_allows_missing_sample_type_map_for_nonrequiring_ptr_method() -> (
    None
):
    expression_df = pd.DataFrame(
        {"sample_1": [2.0]},
        index=["gene_a"],
    )
    ptr_df = pd.DataFrame(
        {"sample_1": [3.0]},
        index=["gene_a"],
    )
    config = APIConfig(
        loading=LoadingPolicy(in_memory_inputs={"expression": expression_df, "ptr": ptr_df}),
    )
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR
    config.protein.ptr_method = "ptr_no_sample_mapping_required"

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
