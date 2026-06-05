"""Cobrapy overwrites: explicit imports required.

.. important::

    This module requires explicit import to activate patches.

This package provides bug fixes and performance enhancements to cobrapy_fork
for VmaxBuilder.  The patches are **not** applied automatically — you must
explicitly import them to avoid interfering with other cobrapy usage.

Why explicit imports?
---------------------

By default, importing VmaxBuilder does **not** modify cobrapy behaviour.  This
ensures:

- No silent patches affect other projects using cobrapy_fork.
- Clear code intent: patches are deliberate, not accidental.
- Easy to debug: patches only active when explicitly imported.

What to import
--------------

Import specific patches based on your use case.

**Option 1 — All patches (recommended for VmaxBuilder usage)**::

    from VmaxBuilder.cobrapy_overwrites import (
        cobrapy_io,
        cobrapy_model,
        cobrapy_reaction,
    )
    # Now all patches are active
    model = Model()
    model.add_reactions_slim(reactions)   # Fast (no solver sync)
    model.populate_solver_from_model()    # Prepare solver before optimise

**Option 2 — Selective patches**::

    from VmaxBuilder.cobrapy_overwrites import cobrapy_model
    # Only Model patches active

    from VmaxBuilder.cobrapy_overwrites import cobrapy_io
    # Use IO functions for MATLAB/JSON I/O

**Option 3 — Minimal (just I/O helpers)**::

    from VmaxBuilder.cobrapy_overwrites.cobrapy_io import load_matlab_model
    model = load_matlab_model("model.mat")

Modules
-------

cobrapy_io
    Fixes for model I/O (MATLAB, JSON):

    - ``load_matlab_model()`` — load ``.mat`` with better error handling.
    - ``from_mat_struct()`` — MATLAB struct → Model conversion.
    - ``model_to_dict()`` / ``model_from_dict()`` — dict serialisation.
    - ``save_json_model()`` — JSON save with NaN/Inf handling.

cobrapy_model
    Model method enhancements:

    - ``add_reactions_slim()`` — bulk add without solver population (↑10×).
    - ``populate_solver_from_model()`` — retroactively populate solver.

cobrapy_reaction
    Reaction method enhancements:

    - bounds setter — supports slim mode (no optlang sync).
    - ``update_variable_bounds_slim()`` — no-op for slim mode.

Use case: Building large models
--------------------------------

::

    from VmaxBuilder.cobrapy_overwrites import cobrapy_model, cobrapy_io
    from cobrapy_fork import Model

    # Create model WITHOUT solver (fast)
    model = Model('large_model')

    # Bulk add reactions (10x faster than standard add_reactions)
    model.add_reactions_slim(reactions)

    # Save without intermediate solver overhead
    cobrapy_io.save_json_model(model, 'model.json')

    # Later: Load and prepare for optimisation
    model.solver = get_gurobi_interface()   # or CPLEX, GLPK, etc.
    model.populate_solver_from_model()      # CRITICAL before optimize()

    # Now ready to use
    solution = model.optimize()

Testing patches
---------------

Patches are tested via:

- ``tests/cobrapy_overwrites/test_cobrapy_io.py`` — I/O functions.
- ``tests/cobrapy_overwrites/test_cobrapy_model.py`` — Model methods.
- ``tests/cobrapy_overwrites/test_cobrapy_reaction.py`` — Reaction methods.

See test files for usage examples.
"""

# Explicitly list what can be imported (but don't import automatically)
__all__ = [
    "cobrapy_io",
    "cobrapy_model",
    "cobrapy_reaction",
]

# Allow explicit imports only
# Users MUST do: from VmaxBuilder.cobrapy_overwrites import cobrapy_io
# NOT: from VmaxBuilder.cobrapy_overwrites import *  (will fail silently)
