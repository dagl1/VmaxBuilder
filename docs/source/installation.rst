Installation
============

VmaxBuilder targets Python 3.11+.

Recommended setup (uv)
----------------------

.. code-block:: console

   uv venv
   .venv\Scripts\activate
   uv sync

Install from package index
--------------------------

.. code-block:: console

   pip install VmaxBuilder

Development install (local repository)
--------------------------------------

.. code-block:: console

   uv sync

Optional extras
---------------

Heavy ML dependencies used by UniKP wrappers are available as optional extra:

.. code-block:: console

   uv sync --extra unikp

Notes
-----

- Dependency and tool settings are defined in ``pyproject.toml``.
- Linting and type checks are enforced through pre-commit and CI.
- Some solver backends or scientific dependencies may require system-level packages.
