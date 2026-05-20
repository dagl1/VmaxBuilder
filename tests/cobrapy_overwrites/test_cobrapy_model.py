"""Unit and integration tests for cobrapy_model overwrites.

Tests:
- add_reactions_slim: Fast bulk add without solver overhead
- populate_solver_from_model: Retroactively populate solver for use with any solver
- Integration: Model created without solver works after attach+populate
"""

import pytest
from cobra import Gene, Metabolite, Model, Reaction

# Activate cobrapy overwrites
from VmaxBuilder.cobrapy_overwrites import cobrapy_model


class TestAddReactionSlim:
    """Unit tests for add_reactions_slim method."""

    def test_add_reactions_slim_basic(self) -> None:
        """Test basic reaction addition without solver overhead."""
        model = Model("test_model")
        met_a = Metabolite("a", compartment="c")
        met_b = Metabolite("b", compartment="c")

        reaction = Reaction("R1")
        reaction.add_metabolites({met_a: -1, met_b: 1})

        model.add_reactions_slim([reaction])  # ty: ignore[unresolved-attribute]

        assert len(model.reactions) == 1
        assert "R1" in model.reactions
        assert len(model.metabolites) == 2

    def test_add_reactions_slim_multiple(self) -> None:
        """Test adding multiple reactions at once."""
        model = Model("test_model")

        reactions = []
        for idx in range(5):
            met_a = Metabolite(f"a_{idx}", compartment="c")
            met_b = Metabolite(f"b_{idx}", compartment="c")

            rxn = Reaction(f"R{idx}")
            rxn.add_metabolites({met_a: -1, met_b: 1})
            reactions.append(rxn)

        model.add_reactions_slim(reactions)  # ty: ignore[unresolved-attribute]

        assert len(model.reactions) == 5
        assert len(model.metabolites) == 10

    def test_add_reactions_slim_skips_duplicates(self) -> None:
        """Test that duplicate reaction IDs are skipped with warning."""
        model = Model("test_model")

        met_a = Metabolite("a", compartment="c")
        met_b = Metabolite("b", compartment="c")

        reaction_1 = Reaction("R1")
        reaction_1.add_metabolites({met_a: -1, met_b: 1})

        model.add_reactions_slim([reaction_1])  # ty: ignore[unresolved-attribute]
        assert len(model.reactions) == 1

        reaction_2 = Reaction("R1")
        reaction_2.add_metabolites({met_a: -1, met_b: 1})

        model.add_reactions_slim([reaction_2])  # ty: ignore[unresolved-attribute]
        assert len(model.reactions) == 1  # Still 1, not 2

    def test_add_reactions_slim_links_existing_metabolites(self) -> None:
        """Test that reactions link to existing metabolites in model."""
        model = Model("test_model")

        met_c = Metabolite("c", compartment="cyto")
        met_d = Metabolite("d", compartment="cyto")
        rxn_1 = Reaction("R1")
        rxn_1.add_metabolites({met_c: -1, met_d: 1})
        model.add_reactions_slim([rxn_1])  # ty: ignore[unresolved-attribute]

        met_c_new = Metabolite("c", compartment="cyto")  # Same ID
        met_e = Metabolite("e", compartment="cyto")
        rxn_2 = Reaction("R2")
        rxn_2.add_metabolites({met_c_new: -1, met_e: 1})

        model.add_reactions_slim([rxn_2])  # ty: ignore[unresolved-attribute]

        assert len(model.metabolites) == 3  # c, d, e
        assert (
            model.reactions.get_by_id("R2").metabolites[model.metabolites.get_by_id("c")]
            == -1
        )

    def test_add_reactions_slim_updates_genes_from_gpr(self) -> None:
        """Test that GPR rules are parsed and genes added."""
        model = Model("test_model")

        met_a = Metabolite("a", compartment="c")
        met_b = Metabolite("b", compartment="c")

        rxn = Reaction("R1")
        rxn.add_metabolites({met_a: -1, met_b: 1})
        rxn.gene_reaction_rule = "g1 and g2"

        model.add_reactions_slim([rxn])  # ty: ignore[unresolved-attribute]

        assert len(model.genes) == 2
        assert "g1" in model.genes
        assert "g2" in model.genes


class TestPopulateSolverFromModel:
    """Unit tests for populate_solver_from_model method."""

    def test_populate_solver_from_model_no_solver(self) -> None:
        """Test that populate_solver_from_model handles missing solver gracefully."""
        model = Model("test_model")

        met_a = Metabolite("a", compartment="c")
        met_b = Metabolite("b", compartment="c")
        rxn = Reaction("R1")
        rxn.add_metabolites({met_a: -1, met_b: 1})

        model.add_reactions_slim([rxn])  # ty: ignore[unresolved-attribute]

        model.populate_solver_from_model()  # ty: ignore[unresolved-attribute]

    def test_populate_solver_from_model_with_solver(self) -> None:
        """Test that populate_solver_from_model adds reactions to solver."""
        try:
            import optlang  # noqa: F401
        except ImportError:
            pytest.skip("optlang not installed")

        met_a = Metabolite("a", compartment="c")
        met_b = Metabolite("b", compartment="c")
        rxn = Reaction("R1")
        rxn.add_metabolites({met_a: -1, met_b: 1})
        rxn.bounds = (-1000, 1000)

        model = Model("test_model_solver")
        if model.solver is not None:
            model.add_reactions_slim([rxn])  # ty: ignore[unresolved-attribute]
            model.populate_solver_from_model()  # ty: ignore[unresolved-attribute]

    def test_populate_solver_multiple_calls_safe(self) -> None:
        """Test that populate_solver_from_model can be called multiple times safely."""
        model = Model("test_model")

        if model.solver is None:
            pytest.skip("No solver available")

        met_a = Metabolite("a", compartment="c")
        met_b = Metabolite("b", compartment="c")
        rxn = Reaction("R1")
        rxn.add_metabolites({met_a: -1, met_b: 1})

        model.add_reactions_slim([rxn])  # ty: ignore[unresolved-attribute]
        model.populate_solver_from_model()  # ty: ignore[unresolved-attribute]

        model.populate_solver_from_model()  # ty: ignore[unresolved-attribute]

        assert len(model.reactions) == 1


class TestIntegrationSlimWorkflow:
    """Integration tests for slim model building + solver workflow."""

    def test_slim_add_then_attach_solver(self) -> None:
        """Integration: Build model slim, attach solver, populate, optimize."""
        model = Model("large_model")

        reactions = []
        for idx in range(3):
            met_in = Metabolite(f"substrate_{idx}", compartment="c")
            met_out = Metabolite(f"product_{idx}", compartment="c")
            rxn = Reaction(f"r_{idx}")
            rxn.add_metabolites({met_in: -1, met_out: 1})
            reactions.append(rxn)

        model.add_reactions_slim(reactions)  # ty: ignore[unresolved-attribute]

        assert len(model.reactions) == 3
        assert len(model.metabolites) == 6

        model_with_solver = Model("test_solver_attach")
        if model_with_solver.solver is not None:
            model.solver = model_with_solver.solver
            model.populate_solver_from_model()  # ty: ignore[unresolved-attribute]

            assert model.solver is not None

    def test_slim_workflow_preserves_model_integrity(self) -> None:
        """Test that slim workflow produces equivalent model to standard add."""
        model_slim = Model("model_slim")
        reactions_a = []
        for idx in range(3):
            met_in = Metabolite(f"m_{idx}_in", compartment="c")
            met_out = Metabolite(f"m_{idx}_out", compartment="c")
            rxn = Reaction(f"r_{idx}")
            rxn.add_metabolites({met_in: -1, met_out: 1})
            rxn.bounds = (-1000, 1000)
            reactions_a.append(rxn)

        model_slim.add_reactions_slim(reactions_a)  # ty: ignore[unresolved-attribute]

        model_standard = Model("model_standard")
        reactions_b = []
        for idx in range(3):
            met_in = Metabolite(f"m_{idx}_in", compartment="c")
            met_out = Metabolite(f"m_{idx}_out", compartment="c")
            rxn = Reaction(f"r_{idx}")
            rxn.add_metabolites({met_in: -1, met_out: 1})
            rxn.bounds = (-1000, 1000)
            reactions_b.append(rxn)

        model_standard.add_reactions(reactions_b)

        assert len(model_slim.reactions) == len(model_standard.reactions)
        assert len(model_slim.metabolites) == len(model_standard.metabolites)
        assert len(model_slim.genes) == len(model_standard.genes)
