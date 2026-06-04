from __future__ import annotations

import pytest
from cobra import Metabolite, Model, Reaction

from VmaxBuilder.config import APIConfig
from VmaxBuilder.core.protocols import Scaffold
from VmaxBuilder.Kcat import DefaultKcatGPRImplementation


def _make_model_with_gpr_rules() -> Model:
    model = Model("gpr_model")
    metabolite = Metabolite("metabolite_c")

    first_reaction = Reaction("reaction_1")
    first_reaction.add_metabolites({metabolite: -1.0})
    first_reaction.gene_reaction_rule = "(gene_a and gene_b) or gene_c"

    second_reaction = Reaction("reaction_2")
    second_reaction.add_metabolites({metabolite: -1.0})
    second_reaction.gene_reaction_rule = "(gene_a & gene_b) | gene_c"

    third_reaction = Reaction("reaction_3")
    third_reaction.add_metabolites({metabolite: -1.0})
    third_reaction.gene_reaction_rule = "gene_a and (gene_d or gene_e)"

    model.add_reactions([first_reaction, second_reaction, third_reaction])
    return model


def _make_scaffold_with_model(model: Model) -> Scaffold:
    scaffold: Scaffold = {
        "inputs": {},
        "artifacts": {"model": model},
        "outputs": {},
        "metadata": {},
        "diagnostics": {},
        "extras": {},
    }
    return scaffold


def test_simplify_gpr_rule_textual_operators() -> None:
    implementation = DefaultKcatGPRImplementation()

    simplified = implementation._simplify_gpr_rule("(gene_a and gene_b) or gene_c")

    assert simplified == ["gene_a and gene_b", "gene_c"]


def test_simplify_gpr_rule_symbolic_operators() -> None:
    implementation = DefaultKcatGPRImplementation()

    simplified = implementation._simplify_gpr_rule("(gene_a & gene_b) | gene_c")

    assert simplified == ["gene_a and gene_b", "gene_c"]


def test_simplify_gpr_rule_supports_mixed_case_and_unicode_symbols() -> None:
    implementation = DefaultKcatGPRImplementation()

    simplified = implementation._simplify_gpr_rule("gene_a AnD (gene_b ∨ gene_c)")

    assert simplified == ["gene_a and gene_b", "gene_a and gene_c"]


def test_simplify_gpr_rule_rejects_malformed_expression() -> None:
    implementation = DefaultKcatGPRImplementation()

    with pytest.raises(ValueError, match="Unexpected end|Unmatched parenthesis"):
        implementation._simplify_gpr_rule("gene_a and (")


def test_simplification_cache_records_hits_for_repeated_rule() -> None:
    implementation = DefaultKcatGPRImplementation()
    implementation.clear_simplification_cache()

    implementation._simplify_gpr_rule("gene_a and gene_b")
    implementation._simplify_gpr_rule("gene_a and gene_b")
    cache_info = implementation.get_simplification_cache_info()

    assert cache_info["misses"] == 1
    assert cache_info["hits"] >= 1


def test_run_builds_ifp_mapping_for_unique_model_rules() -> None:
    implementation = DefaultKcatGPRImplementation()
    scaffold = _make_scaffold_with_model(_make_model_with_gpr_rules())

    result = implementation.run(scaffold, APIConfig())

    ifp_mapping = result["ifp_mapping"]
    assert "(gene_a and gene_b) or gene_c" in ifp_mapping
    assert ifp_mapping["(gene_a and gene_b) or gene_c"]["expansion_count"] == 2
    assert ifp_mapping["(gene_a and gene_b) or gene_c"]["simplified_gene_ifps"] == [
        "gene_a and gene_b",
        "gene_c",
    ]
    assert scaffold["metadata"]["kcat_stage"]["gpr"]["rule_count"] == 2


def test_run_assigns_bidirectional_reaction_ifp_indexes() -> None:
    implementation = DefaultKcatGPRImplementation()
    scaffold = _make_scaffold_with_model(_make_model_with_gpr_rules())

    implementation.run(scaffold, APIConfig())

    reaction_to_ifps = scaffold["artifacts"]["reaction_to_ifps"]
    ifp_to_reactions = scaffold["artifacts"]["ifp_to_reactions"]

    assert reaction_to_ifps["reaction_1"] == ["gene_a and gene_b", "gene_c"]
    assert reaction_to_ifps["reaction_2"] == ["gene_a and gene_b", "gene_c"]
    assert reaction_to_ifps["reaction_3"] == ["gene_a and gene_d", "gene_a and gene_e"]

    assert ifp_to_reactions["gene_c"] == ["reaction_1", "reaction_2"]
    assert ifp_to_reactions["gene_a and gene_b"] == ["reaction_1", "reaction_2"]


def test_run_converts_gene_ifps_to_transcript_ifps_when_requested() -> None:
    implementation = DefaultKcatGPRImplementation()
    scaffold = _make_scaffold_with_model(_make_model_with_gpr_rules())
    scaffold["artifacts"]["gene_transcript_mapping"] = {
        "gene_a": ["transcript_a1", "transcript_a2"],
        "gene_b": ["transcript_b1"],
        "gene_c": ["transcript_c1", "transcript_c2"],
        "gene_d": ["transcript_d1"],
        "gene_e": ["transcript_e1"],
    }

    config = APIConfig()
    config.run_target_transcript_gene_level = "transcript"
    config.maximum_transcript_ifp_expansion = 10

    result = implementation.run(scaffold, config)

    ifp_mapping = result["ifp_mapping"]
    assert ifp_mapping["(gene_a and gene_b) or gene_c"]["simplified_gene_ifps"] == [
        "transcript_a1 and transcript_b1",
        "transcript_a2 and transcript_b1",
        "transcript_c1",
        "transcript_c2",
    ]
    assert scaffold["artifacts"]["reaction_to_ifps"]["reaction_1"] == [
        "transcript_a1 and transcript_b1",
        "transcript_a2 and transcript_b1",
        "transcript_c1",
        "transcript_c2",
    ]


def test_run_keeps_gene_ifp_and_reports_when_transcript_expansion_exceeds_threshold() -> None:
    implementation = DefaultKcatGPRImplementation()
    scaffold = _make_scaffold_with_model(_make_model_with_gpr_rules())
    scaffold["artifacts"]["gene_transcript_mapping"] = {
        "gene_a": ["transcript_a1", "transcript_a2"],
        "gene_b": ["transcript_b1", "transcript_b2"],
    }

    config = APIConfig()
    config.run_target_transcript_gene_level = "transcript"
    config.maximum_transcript_ifp_expansion = 3

    result = implementation.run(scaffold, config)

    # threshold exceeded for "gene_a and gene_b" -> fallback keeps gene-level IFP
    assert result["ifp_mapping"]["(gene_a and gene_b) or gene_c"]["simplified_gene_ifps"] == [
        "gene_a and gene_b",
        "gene_c",
    ]

    skip_entries = scaffold["diagnostics"]["kcat_stage"]["transcript_ifp_complexity_skips"]
    assert len(skip_entries) == 1
    assert skip_entries[0]["maximum_transcript_ifp_expansion"] == 3
    assert skip_entries[0]["actual_expansion_count"] == 4
    assert skip_entries[0]["affected_reactions"] == ["reaction_1", "reaction_2"]

    assert scaffold["artifacts"]["transcript_ifp_complexity_report"] == skip_entries
