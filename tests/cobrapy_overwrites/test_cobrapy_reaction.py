"""Unit tests for cobrapy_reaction overwrites.

Tests:
- bounds setter: 3-tuple slim mode support
- update_variable_bounds_slim: No-op for slim mode
"""

import pytest
from cobra import Metabolite, Model, Reaction

# Activate cobrapy overwrites
from VmaxBuilder.cobrapy_overwrites import cobrapy_reaction


@pytest.mark.unit
class TestBoundsSetter:
    """Test updated bounds setter with slim mode support."""

    def test_bounds_setter_standard_tuple(self) -> None:
        """Test standard 2-tuple bounds setting."""
        model = Model("test")
        rxn = Reaction("R1")
        rxn.add_metabolites({Metabolite("a"): -1})
        model.add_reactions([rxn])

        # Standard 2-tuple should work
        rxn.bounds = (-10, 20)
        assert rxn.lower_bound == -10
        assert rxn.upper_bound == 20

    def test_bounds_setter_standard_list(self) -> None:
        """Test standard list bounds setting."""
        model = Model("test")
        rxn = Reaction("R1")
        rxn.add_metabolites({Metabolite("a"): -1})
        model.add_reactions([rxn])

        # List should work
        rxn.bounds = [-5, 15]
        assert rxn.lower_bound == -5
        assert rxn.upper_bound == 15

    def test_bounds_setter_slim_mode_3tuple(self) -> None:
        """Test 3-tuple slim mode (no solver sync)."""
        model = Model("test")
        rxn = Reaction("R1")
        rxn.add_metabolites({Metabolite("a"): -1})
        model.add_reactions([rxn])

        # 3-tuple with is_slim=True
        rxn.bounds = (-10, 20, True)
        assert rxn.lower_bound == -10
        assert rxn.upper_bound == 20

    def test_bounds_setter_slim_mode_false(self) -> None:
        """Test 3-tuple with is_slim=False (normal sync)."""
        model = Model("test")
        rxn = Reaction("R1")
        rxn.add_metabolites({Metabolite("a"): -1})
        model.add_reactions([rxn])

        # 3-tuple with is_slim=False should work like 2-tuple
        rxn.bounds = (-10, 20, False)
        assert rxn.lower_bound == -10
        assert rxn.upper_bound == 20

    def test_bounds_setter_validates_bounds(self) -> None:
        """Test that invalid bounds (lower > upper) raise ValueError."""
        model = Model("test")
        rxn = Reaction("R1")
        rxn.add_metabolites({Metabolite("a"): -1})
        model.add_reactions([rxn])

        # Invalid bounds should raise
        with pytest.raises(ValueError):
            rxn.bounds = (20, 10)

        # Invalid bounds in 3-tuple should also raise
        with pytest.raises(ValueError):
            rxn.bounds = (20, 10, True)

    def test_bounds_setter_slim_mode_no_solver_update(self) -> None:
        """Test that slim mode avoids solver update overhead."""
        # Create model without solver for performance test
        model = Model("test_no_solver")
        rxn = Reaction("R1")
        rxn.add_metabolites({Metabolite("a"): -1})

        # Add without solver
        model.reactions.append(rxn)
        rxn._model = model

        # Should not raise even without solver (slim mode skips sync)
        rxn.bounds = (-10, 20, True)
        assert rxn.lower_bound == -10


@pytest.mark.unit
class TestUpdateVariableBoundsSlim:
    """Test update_variable_bounds_slim no-op method."""

    def test_update_variable_bounds_slim_no_model(self) -> None:
        """Test that method handles reaction without model gracefully."""
        rxn = Reaction("orphan")
        # Should not raise when reaction not in model
        rxn.update_variable_bounds_slim()  # ty: ignore[unresolved-attribute]

    def test_update_variable_bounds_slim_is_noop(self) -> None:
        """Test that update_variable_bounds_slim is safely a no-op."""
        model = Model("test")
        rxn = Reaction("R1")
        rxn.add_metabolites({Metabolite("a"): -1})
        model.add_reactions([rxn])

        # Calling the slim method should not raise
        rxn.update_variable_bounds_slim()  # ty: ignore[unresolved-attribute]

        # Model should still be intact
        assert len(model.reactions) == 1
        assert "R1" in model.reactions
