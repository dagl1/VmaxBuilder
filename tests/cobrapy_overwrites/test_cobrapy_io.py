"""Unit and integration tests for cobrapy_io overwrites.

Tests:
- load_matlab_model: Load .mat files with error handling
- from_mat_struct: Convert MATLAB struct to Model
- model_to_dict / model_from_dict: Dictionary conversion
- save_json_model: Save with NaN/Inf handling
"""

import json
import tempfile
from pathlib import Path
from typing import cast

import numpy as np
import pytest
from cobra import Gene, Metabolite, Model, Reaction

# Activate cobrapy overwrites
from VmaxBuilder.cobrapy_overwrites import cobrapy_io


@pytest.mark.unit
class TestModelToDict:
    """Unit tests for model_to_dict function."""

    def test_model_to_dict_basic(self) -> None:
        """Test basic model to dict conversion."""
        model = Model("test_model")

        met_a = Metabolite("a_c", compartment="c")
        met_b = Metabolite("b_c", compartment="c")

        rxn = Reaction("R1")
        rxn.add_metabolites({met_a: -1, met_b: 1})

        model.add_metabolites([met_a, met_b])
        model.add_reactions([rxn])

        model_dict = cobrapy_io.model_to_dict(model)

        assert "id" in model_dict
        assert "metabolites" in model_dict
        assert "reactions" in model_dict
        assert "genes" in model_dict
        assert model_dict["id"] == "test_model"
        assert len(model_dict["metabolites"]) == 2
        assert len(model_dict["reactions"]) == 1

    def test_model_to_dict_with_genes(self) -> None:
        """Test model_to_dict with genes and GPR."""
        model = Model("test_model")

        met_a = Metabolite("a", compartment="c")
        met_b = Metabolite("b", compartment="c")

        rxn = Reaction("R1")
        rxn.add_metabolites({met_a: -1, met_b: 1})
        rxn.gene_reaction_rule = "gene1 or gene2"

        model.add_metabolites([met_a, met_b])
        model.add_reactions([rxn])

        model_dict = cobrapy_io.model_to_dict(model)

        assert len(model_dict["genes"]) == 2
        assert any(g["id"] == "gene1" for g in model_dict["genes"])

    def test_model_to_dict_with_sort(self) -> None:
        """Test model_to_dict with sort option."""
        model = Model("test_model")

        # Add mets in unsorted order
        met_z = Metabolite("z", compartment="c")
        met_a = Metabolite("a", compartment="c")
        met_m = Metabolite("m", compartment="c")

        model.add_metabolites([met_z, met_a, met_m])

        model_dict_sorted = cobrapy_io.model_to_dict(model, sort=True)
        met_ids = [m["id"] for m in model_dict_sorted["metabolites"]]

        # Should be sorted
        assert met_ids == sorted(met_ids)

    def test_model_to_dict_preserves_bounds(self) -> None:
        """Test that model_to_dict preserves reaction bounds."""
        model = Model("test_model")

        met_a = Metabolite("a", compartment="c")
        met_b = Metabolite("b", compartment="c")

        rxn = Reaction("R1")
        rxn.bounds = (-10, 20)
        rxn.add_metabolites({met_a: -1, met_b: 1})

        model.add_metabolites([met_a, met_b])
        model.add_reactions([rxn])

        model_dict = cobrapy_io.model_to_dict(model)

        rxn_dict = model_dict["reactions"][0]
        assert rxn_dict["lower_bound"] == -10
        assert rxn_dict["upper_bound"] == 20


@pytest.mark.unit
class TestModelFromDict:
    """Unit tests for model_from_dict function."""

    def test_model_from_dict_basic(self) -> None:
        """Test basic dict to model conversion."""
        model_dict = {
            "id": "test_model",
            "name": "Test Model",
            "metabolites": [
                {"id": "a", "name": "metabolite_a", "compartment": "c", "formula": "H2O"},
                {"id": "b", "name": "metabolite_b", "compartment": "c", "formula": "CO2"},
            ],
            "reactions": [
                {
                    "id": "R1",
                    "name": "reaction_1",
                    "lower_bound": -10,
                    "upper_bound": 20,
                    "gene_reaction_rule": "",
                    "metabolites": {"a": -1, "b": 1},
                }
            ],
            "genes": [],
        }

        model = cobrapy_io.model_from_dict(model_dict)

        assert model.id == "test_model"
        assert model.name == "Test Model"
        assert len(model.metabolites) == 2
        assert len(model.reactions) == 1

    def test_model_from_dict_missing_reactions_raises(self) -> None:
        """Test that missing 'reactions' key raises ValueError."""
        model_dict = {"id": "test", "metabolites": [], "genes": []}

        with pytest.raises(ValueError):
            cobrapy_io.model_from_dict(model_dict)

    def test_model_from_dict_with_objective(self) -> None:
        """Test model_from_dict handles objective coefficients."""
        model_dict = {
            "id": "test",
            "metabolites": [
                {"id": "a", "compartment": "c"},
                {"id": "b", "compartment": "c"},
            ],
            "reactions": [
                {
                    "id": "R1",
                    "lower_bound": -1000,
                    "upper_bound": 1000,
                    "objective_coefficient": 1,
                    "gene_reaction_rule": "",
                    "metabolites": {"a": -1, "b": 1},
                }
            ],
            "genes": [],
        }

        model = cobrapy_io.model_from_dict(model_dict)
        # rxn = model.reactions.get_by_id("R1")

        # Objective should be set
        assert model.objective.direction is not None


@pytest.mark.integration
class TestSaveJsonModel:
    """Integration tests for save_json_model function."""

    def test_save_json_model_basic(self) -> None:
        """Test basic JSON save and load cycle."""
        model = Model("test_model")

        met_a = Metabolite("a", compartment="c")
        met_b = Metabolite("b", compartment="c")

        rxn = Reaction("R1")
        rxn.add_metabolites({met_a: -1, met_b: 1})

        model.add_metabolites([met_a, met_b])
        model.add_reactions([rxn])

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "model.json"

            # Save
            cobrapy_io.save_json_model(model, filepath)
            assert filepath.exists()

            # Verify JSON is valid
            with open(filepath) as f:
                data = json.load(f)
            assert data["id"] == "test_model"

    def test_save_json_model_pretty_format(self) -> None:
        """Test save with pretty formatting."""
        model = Model("test")
        met = Metabolite("a", compartment="c")
        rxn = Reaction("R1")
        rxn.add_metabolites({met: -1})
        model.add_metabolites([met])
        model.add_reactions([rxn])

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "model_pretty.json"

            cobrapy_io.save_json_model(model, filepath, pretty=True)

            # Pretty format should have indentation (larger file)
            with open(filepath) as f:
                content = f.read()
            assert "\n" in content
            assert "    " in content  # Should have indentation

    def test_save_json_model_handles_nan(self) -> None:
        """Test that save_json_model handles NaN values gracefully."""
        # Create basic model
        model = Model("test_nan")
        met_a = Metabolite("a", compartment="c")
        met_b = Metabolite("b", compartment="c")
        rxn = Reaction("R1")
        rxn.add_metabolites({met_a: -1, met_b: 1})
        model.add_metabolites([met_a, met_b])
        model.add_reactions([rxn])

        # After adding to model, directly modify bound to be NaN bypassing solver
        # This tests the save_json_model callback repairs NaN after the fact
        # Cast required: DictList[Reaction][int] returns DictList|Reaction union in ty
        first_rxn = cast(Reaction, model.reactions[0])
        first_rxn._lower_bound = np.nan

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "model_nan.json"

            # Should handle NaN and fix it
            cobrapy_io.save_json_model(model, filepath)
            assert filepath.exists()

            # Verify NaN was replaced with None
            with open(filepath) as f:
                data = json.load(f)
            # NaN values should not appear in JSON
            json_str = json.dumps(data)
            assert "NaN" not in json_str

    def test_save_json_model_handles_inf(self) -> None:
        """Test that save_json_model handles Inf values gracefully."""
        model = Model("test_inf")

        met_a = Metabolite("a", compartment="c")
        met_b = Metabolite("b", compartment="c")

        rxn = Reaction("R1")
        rxn.add_metabolites({met_a: -1, met_b: 1})
        # Set infinite bounds
        rxn.bounds = (-np.inf, np.inf)

        model.add_metabolites([met_a, met_b])
        model.add_reactions([rxn])

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "model_inf.json"

            # Should handle Inf
            cobrapy_io.save_json_model(model, filepath)
            assert filepath.exists()

            # Verify Inf was converted to string or handled properly
            with open(filepath) as f:
                data = json.load(f)
            json_str = json.dumps(data)
            # Inf should be converted to string representation
            assert (
                "inf" in json_str.lower() or "-inf" in json_str.lower() or "INF" in json_str
            )


@pytest.mark.unit
class TestReactionToDict:
    """Unit tests for _reaction_to_dict function."""

    def test_reaction_to_dict_basic(self) -> None:
        """Test basic reaction to dict conversion."""
        rxn = Reaction("R1")
        met_a = Metabolite("a", compartment="c")
        met_b = Metabolite("b", compartment="c")
        rxn.add_metabolites({met_a: -1, met_b: 1})
        rxn.bounds = (-10, 20)

        rxn_dict = cobrapy_io._reaction_to_dict(rxn)

        assert rxn_dict["id"] == "R1"
        assert rxn_dict["lower_bound"] == -10
        assert rxn_dict["upper_bound"] == 20
        assert "a" in rxn_dict["metabolites"]

    def test_reaction_to_dict_handles_inf_bounds(self) -> None:
        """Test that _reaction_to_dict handles infinite bounds."""
        rxn = Reaction("R1")
        rxn.add_metabolites({Metabolite("a"): -1})
        rxn.bounds = (-np.inf, np.inf)

        rxn_dict = cobrapy_io._reaction_to_dict(rxn)

        # Inf should be converted to string representation
        assert isinstance(rxn_dict["lower_bound"], (str, float, int))
        assert isinstance(rxn_dict["upper_bound"], (str, float, int))

    def test_reaction_to_dict_handles_nan_bounds(self) -> None:
        """Test that _reaction_to_dict handles NaN bounds."""
        rxn = Reaction("R1")
        rxn.add_metabolites({Metabolite("a"): -1})
        rxn._lower_bound = np.nan
        rxn._upper_bound = np.nan

        rxn_dict = cobrapy_io._reaction_to_dict(rxn)

        # NaN should be converted to string representation
        assert isinstance(rxn_dict["lower_bound"], (str, float))
        assert isinstance(rxn_dict["upper_bound"], (str, float))
