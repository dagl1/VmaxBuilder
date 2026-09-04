import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from VmaxBuilder.base.configs import Scaffold
from VmaxBuilder.stages.allocation.FairAllocation import implementation as allocation_module
from VmaxBuilder.stages.allocation.FairAllocation.implementation import (
    FairAllocationImplementation,
)


def test_generate_outputs_runs_untrimmed_allocation_before_trimmed_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    implementation = object.__new__(FairAllocationImplementation)
    implementation.full_config = SimpleNamespace(
        protein=SimpleNamespace(trim_enable=True),
        allocation=SimpleNamespace(run_untrimmed_separately=True),
        Vmax=SimpleNamespace(trim_genes_remain_part_for_Kcat=False),
    )
    implementation.logger = SimpleNamespace(attention=lambda *args, **kwargs: None)
    implementation.create_metadata = lambda elapsed_time, **kwargs: {"elapsed": elapsed_time}
    implementation.prepare_trimming_diagnostics = lambda trimming_output: {"prepared": True}
    monkeypatch.setattr(
        allocation_module,
        "create_trimming_summary_plots",
        lambda trimming_output: {},
    )

    call_flags: list[bool] = []

    def fake_run_ifp_allocation(
        protein_abundance_df: pd.DataFrame,
        ifp_mapping: dict,
        trimmable_genes: set[str] | None,
        apply_trimming: bool = True,
    ) -> tuple[
        list[set[str]],
        dict[str, str],
        dict[str, dict[str, float]],
        dict[str, dict[str, object]],
        dict[str, list[dict[str, object]]],
    ]:
        call_flags.append(apply_trimming)
        abundance_value = 1.0 if apply_trimming else 2.0
        return (
            [set()],
            {"mode": "trimmed" if apply_trimming else "untrimmed"},
            {"sample_a": {"IFP_a": abundance_value}},
            {"IFP_a": {"genes_trimmed_per_sample": {"sample_a": ["gene_a"]}}}
            if apply_trimming
            else {},
            {"sample_a": []},
        )

    implementation.run_IFP_allocation = fake_run_ifp_allocation

    scaffold = Scaffold(
        inputs={
            "protein_abundance_df": pd.DataFrame({"sample_a": [1.0]}, index=["gene_a"]),
            "adjusted_IFP_mapping": {
                "rule_a": {"IFP_objects": [{"IFP": "IFP_a", "genes_in_IFP": ["gene_a"]}]}
            },
            "trimmable_genes": {"gene_a"},
        },
        artifacts={},
        outputs={},
        metadata={},
        diagnostics={},
        extras={},
    )

    new_scaffold_objects = implementation.generate_outputs(scaffold)

    assert call_flags == [False, True]
    assert (
        new_scaffold_objects["outputs"]["IFP_sample_abundance_df"].loc["IFP_a", "sample_a"]
        == 1.0
    )
    assert (
        new_scaffold_objects["outputs"]["untrimmed_IFP_sample_abundance_df"].loc[
            "IFP_a", "sample_a"
        ]
        == 2.0
    )


def test_run_ifp_allocation_uses_sample_specific_trimmed_definitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    implementation = object.__new__(FairAllocationImplementation)
    implementation.full_config = SimpleNamespace(
        protein=SimpleNamespace(trim_enable=True),
        allocation=SimpleNamespace(trim_minimum_proteins_in_IFP=1),
    )
    implementation.logger = SimpleNamespace(warning=lambda *args, **kwargs: None)

    recorded_connected_genes: list[tuple[tuple[str, ...], ...]] = []
    recorded_adjusted_genes: list[list[tuple[str, ...]]] = []

    def fake_trim_ifps(
        protein_abundance_df: pd.DataFrame,
        ifp_mapping: dict,
        trim_minimum_proteins_in_ifp: int,
        trimmable_genes: set[str],
    ) -> tuple[dict[str, list[dict[str, object]]], dict[str, dict[str, object]]]:
        return (
            {
                "sample_a": [
                    {
                        "IFP": "IFP_A",
                        "remaining_genes_in_IFP": ["gene_b"],
                        "trimmed_genes_in_IFP": ["gene_a"],
                    }
                ]
            },
            {
                "IFP_A": {
                    "genes_trimmed_per_sample": {"sample_a": ["gene_a"]},
                }
            },
        )

    def fake_prepare_ifps(
        ifp_mapping: dict[str, Any],
        sample_specific: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[set[str]], list[str], dict[str, Any]]:
        if sample_specific:
            sample_specific_mapping = {
                "rule": {
                    "IFP_objects": [
                        {"IFP": "IFP_A", "genes_in_IFP": ["gene_b"]},
                        {
                            "IFP": "IFP_B",
                            "genes_in_IFP": ["gene_a", "gene_b"],
                        },
                    ]
                }
            }
        else:
            sample_specific_mapping = {
                "rule": {
                    "IFP_objects": [
                        {
                            "IFP": "IFP_A",
                            "genes_in_IFP": ["gene_a", "gene_b"],
                        },
                        {
                            "IFP": "IFP_B",
                            "genes_in_IFP": ["gene_a", "gene_b"],
                        },
                    ]
                }
            }

        return (
            sample_specific_mapping,
            [{"IFP_A", "IFP_B"}],
            [],
            {"connected_components": 1},
        )

    def fake_prepare_quadratic_problem_model(
        connected_ifps: list[Any],
        all_genes: list[str],
    ) -> SimpleNamespace:
        recorded_connected_genes.append(
            tuple(sorted(tuple(ifp.genes) for ifp in connected_ifps))
        )
        return SimpleNamespace()

    class FakeSolver:
        def solve(self, quadratic_model: object, tee: bool = False) -> SimpleNamespace:
            return SimpleNamespace(
                solver=SimpleNamespace(termination_condition="optimal", status="ok")
            )

    monkeypatch.setattr(implementation, "trim_IFPs", fake_trim_ifps)
    monkeypatch.setattr(implementation, "prepare_IFPs", fake_prepare_ifps)
    monkeypatch.setattr(
        implementation,
        "prepare_quadratic_problem_model",
        fake_prepare_quadratic_problem_model,
    )

    def fake_resolve_non_connected_ifps(*args: Any, **kwargs: Any) -> dict[str, float]:
        return {}

    def fake_adjust_quadratic_model_for_sample_specific(
        quadratic_model: object,
        sample_specific_ifps: list[Any],
        protein_abundance_df: pd.DataFrame,
        sample: str,
    ) -> None:
        recorded_adjusted_genes.append(
            sorted(tuple(ifp.genes) for ifp in sample_specific_ifps)
        )

    monkeypatch.setattr(
        implementation,
        "resolve_non_connected_IFPs",
        fake_resolve_non_connected_ifps,
    )
    monkeypatch.setattr(
        implementation,
        "adjust_quadratic_model_for_sample_specific",
        fake_adjust_quadratic_model_for_sample_specific,
    )
    monkeypatch.setattr(
        implementation,
        "postprocess_results",
        lambda sample_IFP_abundances, quadratic_model, solver_result: sample_IFP_abundances,
    )
    monkeypatch.setattr(
        allocation_module,
        "get_valid_solver",
        lambda *args, **kwargs: (FakeSolver(), None),
    )

    protein_abundance_df = pd.DataFrame(
        {"sample_a": [1.0, 2.0]},
        index=["gene_a", "gene_b"],
    )
    ifp_mapping = {
        "rule": {
            "IFP_objects": [
                {"IFP": "IFP_A", "genes_in_IFP": ["gene_a", "gene_b"]},
                {"IFP": "IFP_B", "genes_in_IFP": ["gene_a", "gene_b"]},
            ]
        }
    }

    implementation.run_IFP_allocation(
        protein_abundance_df,
        ifp_mapping,
        {"gene_a"},
        apply_trimming=True,
    )

    assert recorded_connected_genes == [(("gene_a", "gene_b"), ("gene_a", "gene_b"))]
    assert sorted(recorded_adjusted_genes[0]) == [
        ("gene_a", "gene_b"),
        ("gene_b",),
    ]


@pytest.mark.integration
@pytest.mark.requires_data
def test_dataset_trimming_changes_ifp_abundance_for_trimmed_ifp() -> None:
    base_dir = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "run_example_output"
        / "NCI_60_human_Human-GEM-2.0.0_run"
        / "outputs"
    )
    protein_abundance_path = base_dir / "protein_abundance_df.csv"
    ifp_mapping_path = base_dir / "adjusted_IFP_mapping.json"
    trimmable_genes_path = base_dir / "trimmable_genes.json"

    required_paths = [
        protein_abundance_path,
        ifp_mapping_path,
        trimmable_genes_path,
    ]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        pytest.skip(
            "Required dataset files are missing for this integration test: "
            f"{', '.join(missing_paths)}"
        )

    protein_abundance_df = pd.read_csv(protein_abundance_path, index_col=0)
    with open(ifp_mapping_path, "r") as file:
        ifp_mapping = json.load(file)
    with open(trimmable_genes_path, "r") as file:
        trimmable_genes = set(json.load(file))

    implementation = object.__new__(FairAllocationImplementation)
    implementation.full_config = SimpleNamespace(
        protein=SimpleNamespace(trim_enable=True),
        allocation=SimpleNamespace(trim_minimum_proteins_in_IFP=7),
    )
    implementation.logger = SimpleNamespace(
        warning=lambda *args, **kwargs: None,
        valid=lambda *args, **kwargs: None,
    )

    trimmed_ifps_per_sample, trimming_output = implementation.trim_IFPs(
        protein_abundance_df,
        ifp_mapping,
        implementation.full_config.allocation.trim_minimum_proteins_in_IFP,
        trimmable_genes,
    )

    trimmed_sample = next(
        (sample for sample, records in trimmed_ifps_per_sample.items() if records),
        None,
    )
    if trimmed_sample is None:
        pytest.skip("No trimmed sample found in dataset for configured trim settings.")

    trimmed_record = trimmed_ifps_per_sample[trimmed_sample][0]
    ifp_name = str(trimmed_record["IFP"])
    remaining_genes = [str(gene) for gene in trimmed_record["remaining_genes_in_IFP"]]
    trimmed_genes = [str(gene) for gene in trimmed_record["trimmed_genes_in_IFP"]]

    assert trimmed_genes
    assert ifp_name in trimming_output
    assert trimmed_sample in trimming_output[ifp_name]["genes_trimmed_per_sample"]
    assert trimming_output[ifp_name]["genes_trimmed_per_sample"][trimmed_sample]

    original_ifp_object = None
    for gpr_data in ifp_mapping.values():
        ifp_objects = gpr_data.get("IFP_objects", [])
        for ifp_object in ifp_objects:
            if ifp_object.get("IFP") == ifp_name:
                original_ifp_object = ifp_object
                break
        if original_ifp_object is not None:
            break

    assert original_ifp_object is not None
    original_genes = [str(gene) for gene in original_ifp_object["genes_in_IFP"]]

    mini_ifp_mapping = {
        "rule_test": {
            "IFP_objects": [
                {
                    "IFP": ifp_name,
                    "genes_in_IFP": original_genes,
                }
            ]
        }
    }
    one_sample_protein_df = protein_abundance_df[[trimmed_sample]]

    (
        _,
        _,
        untrimmed_abundances,
        untrimmed_trimming_output,
        untrimmed_ifps_per_sample,
    ) = implementation.run_IFP_allocation(
        one_sample_protein_df,
        mini_ifp_mapping,
        trimmable_genes,
        apply_trimming=False,
    )
    (
        _,
        _,
        trimmed_abundances,
        _trimmed_trimming_output,
        trimmed_ifps_per_sample_for_run,
    ) = implementation.run_IFP_allocation(
        one_sample_protein_df,
        mini_ifp_mapping,
        trimmable_genes,
        apply_trimming=True,
    )

    untrimmed_value = untrimmed_abundances[trimmed_sample][ifp_name]
    trimmed_value = trimmed_abundances[trimmed_sample][ifp_name]

    expected_untrimmed = float(
        one_sample_protein_df.loc[original_genes, trimmed_sample].min()
    )
    expected_trimmed = float(one_sample_protein_df.loc[remaining_genes, trimmed_sample].min())

    assert untrimmed_trimming_output == {}
    assert untrimmed_ifps_per_sample[trimmed_sample] == []
    assert trimmed_ifps_per_sample_for_run[trimmed_sample]
    assert pytest.approx(expected_untrimmed, rel=0.0, abs=1e-12) == untrimmed_value
    assert pytest.approx(expected_trimmed, rel=0.0, abs=1e-12) == trimmed_value
    assert trimmed_value >= untrimmed_value

    if expected_trimmed > expected_untrimmed:
        assert trimmed_value > untrimmed_value


@pytest.mark.integration
@pytest.mark.requires_data
def test_dataset_trimming_negative_control_no_trimmable_genes_fails_strict_increase() -> None:
    base_dir = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "run_example_output"
        / "NCI_60_human_Human-GEM-2.0.0_run"
        / "outputs"
    )
    protein_abundance_path = base_dir / "protein_abundance_df.csv"
    ifp_mapping_path = base_dir / "adjusted_IFP_mapping.json"

    required_paths = [
        protein_abundance_path,
        ifp_mapping_path,
    ]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        pytest.skip(
            "Required dataset files are missing for this integration test: "
            f"{', '.join(missing_paths)}"
        )

    protein_abundance_df = pd.read_csv(protein_abundance_path, index_col=0)
    with open(ifp_mapping_path, "r") as file:
        ifp_mapping = json.load(file)

    implementation = object.__new__(FairAllocationImplementation)
    implementation.full_config = SimpleNamespace(
        protein=SimpleNamespace(trim_enable=True),
        allocation=SimpleNamespace(trim_minimum_proteins_in_IFP=7),
    )
    implementation.logger = SimpleNamespace(
        warning=lambda *args, **kwargs: None,
        valid=lambda *args, **kwargs: None,
    )

    (
        _,
        _,
        untrimmed_abundances,
        _untrimmed_trimming_output,
        _untrimmed_ifps_per_sample,
    ) = implementation.run_IFP_allocation(
        protein_abundance_df,
        ifp_mapping,
        set(),
        apply_trimming=False,
    )
    (
        _,
        _,
        pseudo_trimmed_abundances,
        pseudo_trimming_output,
        pseudo_trimmed_ifps_per_sample,
    ) = implementation.run_IFP_allocation(
        protein_abundance_df,
        ifp_mapping,
        set(),
        apply_trimming=True,
    )

    assert pseudo_trimming_output == {}
    assert all(len(entries) == 0 for entries in pseudo_trimmed_ifps_per_sample.values())

    sample = next(iter(protein_abundance_df.columns))
    shared_ifps = set(untrimmed_abundances[sample]).intersection(
        pseudo_trimmed_abundances[sample]
    )
    assert shared_ifps

    candidate_ifp = next(iter(shared_ifps))
    untrimmed_value = untrimmed_abundances[sample][candidate_ifp]
    pseudo_trimmed_value = pseudo_trimmed_abundances[sample][candidate_ifp]

    assert pytest.approx(untrimmed_value, rel=0.0, abs=1e-12) == pseudo_trimmed_value

    with pytest.raises(AssertionError):
        assert pseudo_trimmed_value > untrimmed_value


@pytest.mark.integration
@pytest.mark.requires_data
def test_dataset_trimming_changes_affected_connected_component_sum() -> None:
    base_dir = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "run_example_output"
        / "NCI_60_human_Human-GEM-2.0.0_run"
        / "outputs"
    )
    protein_abundance_path = base_dir / "protein_abundance_df.csv"
    ifp_mapping_path = base_dir / "adjusted_IFP_mapping.json"
    trimmable_genes_path = base_dir / "trimmable_genes.json"

    required_paths = [
        protein_abundance_path,
        ifp_mapping_path,
        trimmable_genes_path,
    ]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        pytest.skip(
            "Required dataset files are missing for this integration test: "
            f"{', '.join(missing_paths)}"
        )

    protein_abundance_df = pd.read_csv(protein_abundance_path, index_col=0)
    with open(ifp_mapping_path, "r") as file:
        ifp_mapping = json.load(file)
    with open(trimmable_genes_path, "r") as file:
        trimmable_genes = set(json.load(file))

    implementation = object.__new__(FairAllocationImplementation)
    implementation.full_config = SimpleNamespace(
        protein=SimpleNamespace(trim_enable=True),
        allocation=SimpleNamespace(trim_minimum_proteins_in_IFP=7),
    )
    implementation.logger = SimpleNamespace(
        warning=lambda *args, **kwargs: None,
        valid=lambda *args, **kwargs: None,
    )

    trimmed_ifps_per_sample, trimming_output = implementation.trim_IFPs(
        protein_abundance_df,
        ifp_mapping,
        implementation.full_config.allocation.trim_minimum_proteins_in_IFP,
        trimmable_genes,
    )

    sample = next(
        (sample_name for sample_name, records in trimmed_ifps_per_sample.items() if records),
        None,
    )
    if sample is None:
        pytest.skip("No trimmed sample found in dataset for configured trim settings.")

    trimmed_records_for_sample = trimmed_ifps_per_sample[sample]
    trimmed_ifp_names = {
        str(record["IFP"])
        for record in trimmed_records_for_sample
        if record["trimmed_genes_in_IFP"]
    }
    assert trimmed_ifp_names
    assert any(
        sample in trimming_output[ifp_name]["genes_trimmed_per_sample"]
        and trimming_output[ifp_name]["genes_trimmed_per_sample"][sample]
        for ifp_name in trimmed_ifp_names
        if ifp_name in trimming_output
    )

    connected_components, non_connected_ifps, _ = implementation.get_connected_components(
        ifp_mapping
    )
    affected_component_ifps: set[str] = set(non_connected_ifps).intersection(
        trimmed_ifp_names
    )
    for component in connected_components:
        if component.intersection(trimmed_ifp_names):
            affected_component_ifps.update(component)

    assert affected_component_ifps

    one_sample_protein_df = protein_abundance_df[[sample]]
    (
        _,
        _,
        untrimmed_abundances,
        _,
        _,
    ) = implementation.run_IFP_allocation(
        one_sample_protein_df,
        ifp_mapping,
        trimmable_genes,
        apply_trimming=False,
    )
    (
        _,
        _,
        trimmed_abundances,
        _,
        _,
    ) = implementation.run_IFP_allocation(
        one_sample_protein_df,
        ifp_mapping,
        trimmable_genes,
        apply_trimming=True,
    )

    untrimmed_sample_values = untrimmed_abundances[sample]
    trimmed_sample_values = trimmed_abundances[sample]
    comparable_ifps = affected_component_ifps.intersection(
        untrimmed_sample_values
    ).intersection(trimmed_sample_values)
    assert comparable_ifps

    untrimmed_sum = sum(float(untrimmed_sample_values[ifp]) for ifp in comparable_ifps)
    trimmed_sum = sum(float(trimmed_sample_values[ifp]) for ifp in comparable_ifps)

    changed_trimmed_ifps = [
        ifp_name
        for ifp_name in trimmed_ifp_names
        if ifp_name in untrimmed_sample_values
        and ifp_name in trimmed_sample_values
        and not pytest.approx(
            float(untrimmed_sample_values[ifp_name]),
            rel=0.0,
            abs=1e-12,
        )
        == float(trimmed_sample_values[ifp_name])
    ]

    assert changed_trimmed_ifps
    assert abs(trimmed_sum - untrimmed_sum) > 1e-3
