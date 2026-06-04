"""Tests for VmaxBuilder.model.preprocessing."""

from __future__ import annotations

from typing import cast

import pytest
from cobra import Metabolite, Model, Reaction

from VmaxBuilder.config.dataclasses import ModelConfig
from VmaxBuilder.model.preprocessing import (
    _BACKWARD_SUFFIX,
    _FORWARD_SUFFIX,
    IrreversibleModelMode,
    create_irreversible_model,
    preprocess_model,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_simple_model() -> Model:
    """Build a minimal test model with reversible and boundary reactions.
    Reactions:
        - r_rev: reversible (-10, 10), A -> B
        - r_irrev_fwd: irreversible (0, 10), B -> C
        - ex_A: exchange/boundary (-1000, 1000), A <->
        - r_forced_fwd: forced-positive bounds (2, 10), C -> D
        - r_forced_rev: forced-negative bounds (-10, -1), D -> E
    """
    model = Model("test_model")
    metabolite_a = Metabolite("A")
    metabolite_b = Metabolite("B")
    metabolite_c = Metabolite("C")
    metabolite_d = Metabolite("D")
    metabolite_e = Metabolite("E")
    r_rev = Reaction("r_rev")
    r_rev.add_metabolites({metabolite_a: -1, metabolite_b: 1})
    r_rev.bounds = (-10.0, 10.0)
    r_irrev_fwd = Reaction("r_irrev_fwd")
    r_irrev_fwd.add_metabolites({metabolite_b: -1, metabolite_c: 1})
    r_irrev_fwd.bounds = (0.0, 10.0)
    ex_a = Reaction("ex_A")
    ex_a.add_metabolites({metabolite_a: -1})
    ex_a.bounds = (-1000.0, 1000.0)
    r_forced_fwd = Reaction("r_forced_fwd")
    r_forced_fwd.add_metabolites({metabolite_c: -1, metabolite_d: 1})
    r_forced_fwd.bounds = (2.0, 10.0)
    r_forced_rev = Reaction("r_forced_rev")
    r_forced_rev.add_metabolites({metabolite_d: -1, metabolite_e: 1})
    r_forced_rev.bounds = (-10.0, -1.0)
    model.add_reactions([r_rev, r_irrev_fwd, ex_a, r_forced_fwd, r_forced_rev])
    return model


# ---------------------------------------------------------------------------
# create_irreversible_model
# ---------------------------------------------------------------------------
class TestCreateIrreversibleModel:
    def test_reversible_reaction_split_into_two(self) -> None:
        model = _make_simple_model()
        irrev_model, rev2irrev = create_irreversible_model(
            model, mode=IrreversibleModelMode.SAFE
        )
        reaction_ids = [r.id for r in irrev_model.reactions]
        assert "r_rev_f" in reaction_ids
        assert "r_rev_r" in reaction_ids

    def test_split_reactions_have_non_negative_lower_bound(self) -> None:
        model = _make_simple_model()
        irrev_model, _ = create_irreversible_model(model, mode=IrreversibleModelMode.SAFE)
        split_reactions = [
            r
            for r in irrev_model.reactions
            if r.id.endswith(_FORWARD_SUFFIX) or r.id.endswith(_BACKWARD_SUFFIX)
        ]
        assert all(r.lower_bound >= 0 for r in split_reactions)

    def test_backward_reaction_has_flipped_metabolites(self) -> None:
        model = _make_simple_model()
        irrev_model, _ = create_irreversible_model(model, mode=IrreversibleModelMode.SAFE)
        r_rev_r = irrev_model.reactions.get_by_id("r_rev_r")
        coeffs = {met.id: coeff for met, coeff in r_rev_r.metabolites.items()}
        assert coeffs["B"] < 0
        assert coeffs["A"] > 0

    def test_rev2irrev_has_two_entries_for_reversible(self) -> None:
        model = _make_simple_model()
        original_ids = [r.id for r in model.reactions]
        irrev_model, rev2irrev = create_irreversible_model(
            model, mode=IrreversibleModelMode.SAFE
        )
        rev_idx = original_ids.index("r_rev")
        assert len(rev2irrev[rev_idx]) == 2

    def test_rev2irrev_has_one_entry_for_irreversible(self) -> None:
        model = _make_simple_model()
        original_ids = [r.id for r in model.reactions]
        irrev_model, rev2irrev = create_irreversible_model(
            model, mode=IrreversibleModelMode.SAFE
        )
        irrev_idx = original_ids.index("r_irrev_fwd")
        assert len(rev2irrev[irrev_idx]) == 1

    def test_already_irreversible_model_returns_unchanged(self) -> None:
        model = Model("irrev")
        r = Reaction("r1")
        r.add_metabolites({Metabolite("A"): -1, Metabolite("B"): 1})
        r.bounds = (0.0, 10.0)
        model.add_reactions([r])
        irrev_model, rev2irrev = create_irreversible_model(
            model, mode=IrreversibleModelMode.SAFE
        )
        assert rev2irrev == []
        assert "r1" in [r.id for r in irrev_model.reactions]

    def test_model_mutated_inplace(self) -> None:
        model = _make_simple_model()
        irrev_model, _ = create_irreversible_model(model, mode=IrreversibleModelMode.SAFE)
        # create_irreversible_model mutates the model in-place (does not copy)
        assert irrev_model is model

    def test_fast_mode_splits_reversible_reactions(self) -> None:
        model = _make_simple_model()

        irrev_model, rev2irrev = create_irreversible_model(
            model,
            mode=IrreversibleModelMode.FAST,
        )

        reaction_ids = {reaction.id for reaction in irrev_model.reactions}
        assert "r_rev_f" in reaction_ids
        assert "r_rev_r" in reaction_ids
        assert rev2irrev

    def test_fast_mode_restores_default_bounds_setter_after_exit(self) -> None:
        model = _make_simple_model()

        create_irreversible_model(model, mode=IrreversibleModelMode.FAST)

        reaction = Reaction("restored_bounds")
        with pytest.raises(ValueError, match="too many values to unpack"):
            reaction.bounds = (0.0, 1.0, True)  # type: ignore[assignment]

    def test_raises_on_invalid_mode(self) -> None:
        model = _make_simple_model()
        with pytest.raises(ValueError, match="Unknown IrreversibleModelMode"):
            create_irreversible_model(
                model,
                mode=cast(IrreversibleModelMode, "invalid_mode"),
            )


# ---------------------------------------------------------------------------
# preprocess_model (integration)
# ---------------------------------------------------------------------------
class TestPreprocessModel:
    def test_result_has_required_keys(self) -> None:
        model = _make_simple_model()
        config = ModelConfig(make_copy=True)
        result = preprocess_model(model, config)
        assert "irreversible_model" in result
        assert "rev2irrev" in result

    def test_result_does_not_contain_reversible_model(self) -> None:
        model = _make_simple_model()
        config = ModelConfig(make_copy=True)
        result = preprocess_model(model, config)
        assert "reversible_model" not in result

    def test_boundary_reactions_closed_in_output(self) -> None:
        model = _make_simple_model()
        config = ModelConfig(make_copy=True)
        result = preprocess_model(model, config)
        boundary_reactions = [r for r in result["irreversible_model"].reactions if r.boundary]
        assert all(r.bounds == (0.0, 0.0) for r in boundary_reactions)

    def test_split_reactions_have_non_negative_bounds(self) -> None:
        model = _make_simple_model()
        config = ModelConfig(make_copy=True)
        result = preprocess_model(model, config)
        split_reactions = [
            r
            for r in result["irreversible_model"].reactions
            if r.id.endswith(_FORWARD_SUFFIX) or r.id.endswith(_BACKWARD_SUFFIX)
        ]
        assert all(r.lower_bound >= 0 for r in split_reactions)

    def test_result_is_copy_when_make_copy_true(self) -> None:
        model = _make_simple_model()
        config = ModelConfig(make_copy=True)
        result = preprocess_model(model, config)
        assert result["irreversible_model"] is not model

    def test_result_mutates_original_when_make_copy_false(self) -> None:
        model = _make_simple_model()
        config = ModelConfig(make_copy=False)
        result = preprocess_model(model, config)
        # With make_copy=False, returned model is same object (boundary reactions mutated)
        assert result["irreversible_model"] is model
