Installation
============

VmaxBuilder targets Python 3.11.

Recommended setup (uv)
----------------------

.. code-block:: console

   uv venv
   source .venv/bin/activate
   uv sync

If you want the UniKP extras used by the Kcat workflow, install the optional extra:

.. code-block:: console

   uv sync --extra unikp

Solver and license notes
------------------------

The allocation and Vmax stages use Gurobi through ``gurobipy`` in the current project
configuration. Install Gurobi and activate your license before running those stages.

Useful starting points:

- Gurobi installation and downloads: https://www.gurobi.com/downloads/
- Academic license instructions: https://www.gurobi.com/academia/academic-program-and-licenses/

Why ``uv``
----------

The repository is configured for ``uv``-based workflows, so the package metadata,
dependencies, and optional extras are managed from ``pyproject.toml``.

Notes
-----

- Dependency and tool settings are defined in ``pyproject.toml``.
- UniKP is optional and only required for Kcat workflows that use it.
- Some solver backends and scientific packages may still require system-level packages.
