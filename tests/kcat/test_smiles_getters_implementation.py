from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest
from cobra import Metabolite, Model

from VmaxBuilder.base.classes import ImplementationConfig
from VmaxBuilder.base.configs import (
    FullConfig,
    RunConfig,
    Scaffold,
    TranscriptProcessingConfig,
)
from VmaxBuilder.Kcat_preprocessing.smiles_retrieval import (
    PubChemCandidate,
    function_for_identifying_novel_found_SMILES_and_only_doing_those,
    load_manually_curated_smiles_file,
)
from VmaxBuilder.Kcat_preprocessing.smiles_transcripts_getters_implementation import (
    TranscriptSMILESGetter,
)


@dataclass(slots=True)
class _ModelConfigStub:
    gene_id_type: str = "ensembl"
    level: str = "gene"
    id_type: str = "ensembl"


@pytest.fixture
def full_config(tmp_path: Path) -> FullConfig:
    run_config = RunConfig(output_dir=tmp_path, run_name="smiles")
    return FullConfig(
        model=ImplementationConfig(),
        protein=ImplementationConfig(),
        allocation=ImplementationConfig(),
        Kcat=ImplementationConfig(),
        Vmax=ImplementationConfig(),
        run=run_config,
        paths=run_config.paths,
        transcripts=TranscriptProcessingConfig(),
    )


def _make_scaffold() -> Scaffold:
    return Scaffold(
        inputs={},
        artifacts={},
        outputs={},
        metadata={},
        diagnostics={},
        extras={},
        discovered_inputs={"model": {}},
    )


def _make_model() -> Model:
    model = Model("smiles_model")
    metabolites = [
        Metabolite("water_c", name="Water", formula="H2O", compartment="c"),
        Metabolite("acetate_c", name="Acetate", formula="C2H4O2", compartment="c"),
        Metabolite("persisted_c", name="Persisted", formula="CH4", compartment="c"),
        Metabolite("hexanoylACP_c", name="hexanoylACP", formula="C6H11OS", compartment="c"),
    ]
    model.add_metabolites(metabolites)
    return model


def _make_transcript_lookup_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "transcript_id": "ENST_CANONICAL",
                "gene_id": "ENSG001",
                "is_protein_coding": True,
                "is_canonical": True,
                "peptide_len": 4,
                "cdna_len": 12,
                "peptide_seq": "MPEP",
                "cdna_seq": "ATGCCCGAGCCC",
            },
            {
                "transcript_id": "ENST_ALT",
                "gene_id": "ENSG001",
                "is_protein_coding": True,
                "is_canonical": False,
                "peptide_len": 3,
                "cdna_len": 9,
                "peptide_seq": "MAP",
                "cdna_seq": "ATGGCCCCG",
            },
        ]
    )


def _make_gene_model() -> Model:
    model = Model("gene_model")
    metabolite = Metabolite("gene_met_c", name="GeneMet", formula="H2O", compartment="c")
    model.add_metabolites([metabolite])
    reaction = model.problem is not None  # no-op keep type check calm in old cobra env
    _ = reaction
    from cobra import Reaction

    gene_reaction = Reaction("R_GENE")
    gene_reaction.add_metabolites({metabolite: -1.0})
    gene_reaction.gene_reaction_rule = "ENSG001"
    model.add_reactions([gene_reaction])
    return model


@pytest.mark.unit
def test_load_manually_curated_smiles_file_recovers_unquoted_commas(tmp_path: Path) -> None:
    input_file = tmp_path / "manual.csv"
    input_file.write_text(
        "name,id,id_without_compartment,base_to_work_from,difference,base_smiles,modified_smiles\n"
        "Metabolite, with comma,met_c,met,,,,CCO\n",
        encoding="utf-8",
    )

    loaded_df = load_manually_curated_smiles_file(input_file)

    assert loaded_df.loc[0, "name"] == "Metabolite, with comma"
    assert loaded_df.loc[0, "id"] == "met_c"
    assert loaded_df.loc[0, "modified_smiles"] == "CCO"


@pytest.mark.unit
def test_identify_only_new_or_unresolved_smiles_rows() -> None:
    old_smiles_df = pd.DataFrame(
        {
            "id_without_compartment": ["resolved_met", "missing_met"],
            "isomeric_SMILES": ["C", None],
        }
    )
    new_smiles_df = pd.DataFrame(
        {
            "id_without_compartment": ["resolved_met", "missing_met", "brand_new_met"],
            "isomeric_SMILES": [None, None, None],
        }
    )

    lookup_df = function_for_identifying_novel_found_SMILES_and_only_doing_those(
        old_SMILES_df=old_smiles_df,
        new_SMILES_df=new_smiles_df,
    )

    assert lookup_df["id_without_compartment"].tolist() == ["missing_met", "brand_new_met"]


@pytest.mark.integration
def test_transcript_smiles_getter_builds_smiles_from_local_sources_and_pubchem_fallback(
    full_config: FullConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queried_names: list[str] = []

    def fake_fetch_candidates(
        self, query_names: list[str]
    ) -> dict[str, list[PubChemCandidate]]:
        queried_names.extend(query_names)
        response: dict[str, list[PubChemCandidate]] = {}
        if "hexanoic acid" in query_names:
            response["hexanoic acid"] = [
                PubChemCandidate(
                    compound_id="123",
                    query="hexanoic acid",
                    search_namespace="name",
                    isomeric_smiles="CCCCCC(=O)O",
                    canonical_smiles="CCCCCC(=O)O",
                    inchi="InChI=1S/C6H12O2/c1-2-3-4-5-6(7)8/h2-5H2,1H3,(H,7,8)",
                    molecular_formula="C6H12O2",
                )
            ]
        return response

    def fake_fetch_candidates_by_cid(
        self, compound_ids: list[str]
    ) -> dict[str, list[PubChemCandidate]]:
        return {compound_id: [] for compound_id in compound_ids}

    monkeypatch.setattr(
        "VmaxBuilder.Kcat_preprocessing.smiles_retrieval.PubChemLookupService.fetch_candidates",
        fake_fetch_candidates,
    )
    monkeypatch.setattr(
        "VmaxBuilder.Kcat_preprocessing.smiles_retrieval.PubChemLookupService.fetch_candidates_by_cid",
        fake_fetch_candidates_by_cid,
    )

    implementation = TranscriptSMILESGetter(full_config)
    scaffold = _make_scaffold()
    scaffold.inputs["cobra_model"] = _make_model()
    scaffold.inputs["cobra_model_data"] = pd.DataFrame(
        {
            "ID": ["water_c"],
            "InChI": ["InChI=1S/H2O/h1H2"],
        }
    )
    scaffold.inputs["metabolites_df"] = pd.DataFrame(columns=["mets", "metsNoComp"])
    scaffold.inputs["SMILES_df"] = pd.DataFrame(
        {
            "id_without_compartment": ["persisted"],
            "isomeric_SMILES": ["C"],
            "canonical_SMILES": ["C"],
            "InChI": ["InChI=1S/CH4/h1H4"],
            "source": ["previous_run"],
        }
    )
    scaffold.inputs["manually_curated_SMILES_df"] = pd.DataFrame(
        {
            "name": ["Acetate"],
            "id": ["acetate_c"],
            "id_without_compartment": ["acetate"],
            "base_to_work_from": [None],
            "difference": [None],
            "base_smiles": [None],
            "modified_smiles": ["CC(=O)O"],
        }
    )

    updated_scaffold = implementation.run(scaffold)
    smiles_df = updated_scaffold.get_scaffold_value("SMILES_df")
    assert isinstance(smiles_df, pd.DataFrame)

    assert set(smiles_df["id_without_compartment"]) == {
        "water",
        "acetate",
        "persisted",
        "hexanoylACP",
    }

    water_row = smiles_df.loc[smiles_df["id_without_compartment"] == "water"].iloc[0]
    assert water_row["isomeric_SMILES"] == "O"
    assert water_row["source"] == "local_inchi"

    acetate_row = smiles_df.loc[smiles_df["id_without_compartment"] == "acetate"].iloc[0]
    assert acetate_row["canonical_SMILES"] == "CC(=O)O"
    assert acetate_row["source"] == "manually_curated"

    persisted_row = smiles_df.loc[smiles_df["id_without_compartment"] == "persisted"].iloc[0]
    assert persisted_row["canonical_SMILES"] == "C"
    assert persisted_row["source"] == "previous_run"

    acp_row = smiles_df.loc[smiles_df["id_without_compartment"] == "hexanoylACP"].iloc[0]
    assert acp_row["canonical_SMILES"] == "CCCCCC(=O)S"
    assert acp_row["source"] == "pubchem_synonym_acp"

    smiles_summary = updated_scaffold.get_scaffold_value("smiles_summary")
    assert smiles_summary["missing_smiles"] == 0
    assert "Persisted" not in queried_names
    assert "hexanoic acid" in queried_names


@pytest.mark.integration
def test_transcript_smiles_getter_builds_canonical_transcript_metadata_by_default(
    full_config: FullConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript_lookup_df = _make_transcript_lookup_df()

    def fake_build_gene_transcript_dataframe(
        self,
        gene_ids: list[str],
        **kwargs,
    ) -> pd.DataFrame:
        _ = self, gene_ids, kwargs
        return transcript_lookup_df.copy()

    monkeypatch.setattr(
        "VmaxBuilder.database_retrieval.identifier_translation.IdentifierTranslationService.build_gene_transcript_dataframe",
        fake_build_gene_transcript_dataframe,
    )

    full_config.model = _ModelConfigStub()
    implementation = TranscriptSMILESGetter(full_config)
    scaffold = _make_scaffold()
    scaffold.inputs["cobra_model"] = _make_gene_model()
    scaffold.inputs["cobra_model_data"] = pd.DataFrame(columns=["ID", "InChI"])
    scaffold.inputs["metabolites_df"] = pd.DataFrame(columns=["mets", "metsNoComp"])

    updated_scaffold = implementation.run(scaffold)

    transcript_df = updated_scaffold.get_scaffold_value("transcript_df")
    canonical_transcripts = updated_scaffold.get_scaffold_value("canonical_transcripts")
    gene_to_transcript_mapping = updated_scaffold.get_scaffold_value(
        "gene_to_transcript_mapping"
    )

    assert isinstance(transcript_df, pd.DataFrame)
    assert transcript_df["transcript_id"].tolist() == ["ENST_CANONICAL"]
    assert transcript_df["peptide_seq"].tolist() == ["MPEP"]
    assert canonical_transcripts == ["ENST_CANONICAL"]
    assert gene_to_transcript_mapping == {"ENSG001": ["ENST_CANONICAL"]}
    assert updated_scaffold.get_scaffold_value("transcript_sequences") is None


@pytest.mark.integration
def test_transcript_smiles_getter_can_keep_alternative_transcripts(
    full_config: FullConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript_lookup_df = _make_transcript_lookup_df()

    def fake_build_gene_transcript_dataframe(
        self,
        gene_ids: list[str],
        **kwargs,
    ) -> pd.DataFrame:
        _ = self, gene_ids, kwargs
        return transcript_lookup_df.copy()

    monkeypatch.setattr(
        "VmaxBuilder.database_retrieval.identifier_translation.IdentifierTranslationService.build_gene_transcript_dataframe",
        fake_build_gene_transcript_dataframe,
    )

    full_config.model = _ModelConfigStub()
    implementation = TranscriptSMILESGetter(full_config)
    implementation.config.retrieve_alternative_transcripts = True

    scaffold = _make_scaffold()
    scaffold.inputs["cobra_model"] = _make_gene_model()
    scaffold.inputs["cobra_model_data"] = pd.DataFrame(columns=["ID", "InChI"])
    scaffold.inputs["metabolites_df"] = pd.DataFrame(columns=["mets", "metsNoComp"])

    updated_scaffold = implementation.run(scaffold)

    transcript_df = updated_scaffold.get_scaffold_value("transcript_df")
    gene_to_transcript_mapping = updated_scaffold.get_scaffold_value(
        "gene_to_transcript_mapping"
    )
    transcript_lookup_summary = updated_scaffold.get_scaffold_value(
        "transcript_lookup_summary"
    )

    assert isinstance(transcript_df, pd.DataFrame)
    assert transcript_df["transcript_id"].tolist() == ["ENST_CANONICAL", "ENST_ALT"]
    assert gene_to_transcript_mapping == {"ENSG001": ["ENST_CANONICAL", "ENST_ALT"]}
    assert transcript_lookup_summary["contains_alternative_transcripts"] is True


@pytest.mark.integration
def test_transcript_smiles_getter_enriches_provided_transcript_df_with_aa_sequences(
    full_config: FullConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provided_transcript_df = pd.DataFrame(
        {
            "transcript_id": ["ENST_CANONICAL"],
            "gene_id": ["ENSG001"],
        }
    )

    def fake_enrich_transcript_dataframe_with_sequences(
        self,
        transcript_df: pd.DataFrame,
        **kwargs,
    ) -> pd.DataFrame:
        _ = self, kwargs
        enriched_transcript_df = transcript_df.copy()
        enriched_transcript_df["is_protein_coding"] = True
        enriched_transcript_df["is_canonical"] = True
        enriched_transcript_df["peptide_seq"] = "MPEP"
        enriched_transcript_df["peptide_len"] = 4
        enriched_transcript_df["cdna_seq"] = None
        enriched_transcript_df["cdna_len"] = None
        return enriched_transcript_df

    monkeypatch.setattr(
        "VmaxBuilder.database_retrieval.identifier_translation.IdentifierTranslationService.enrich_transcript_dataframe_with_sequences",
        fake_enrich_transcript_dataframe_with_sequences,
    )

    full_config.model = _ModelConfigStub()
    implementation = TranscriptSMILESGetter(full_config)
    scaffold = _make_scaffold()
    scaffold.inputs["cobra_model"] = _make_gene_model()
    scaffold.inputs["cobra_model_data"] = pd.DataFrame(columns=["ID", "InChI"])
    scaffold.inputs["metabolites_df"] = pd.DataFrame(columns=["mets", "metsNoComp"])
    scaffold.inputs["transcript_df"] = provided_transcript_df

    updated_scaffold = implementation.run(scaffold)

    transcript_df = updated_scaffold.get_scaffold_value("transcript_df")
    assert isinstance(transcript_df, pd.DataFrame)
    assert transcript_df["peptide_seq"].tolist() == ["MPEP"]
    assert transcript_df["peptide_len"].tolist() == [4]


