VmaxBuilder Documentation
=========================

**VmaxBuilder** is a modular Python toolbox for converting model, protein, Kcat, and
allocation inputs into condition-specific reaction capacity estimates.

Pipeline overview
-----------------

The pipeline is orchestrated through a fixed stage order:

1. Model preprocessing.
2. Protein preprocessing.
3. Allocation.
4. Kcat estimation and resolution.
5. Vmax calculation.

Start here
----------

- New users: :doc:`getting_started`
- Installation options: :doc:`installation`
- Conceptual overview: :doc:`overview`
- Run tutorial: :doc:`tutorial`
- Stage catalog: :doc:`stages`
- Worked examples: :doc:`examples`
- Practical scenarios: :doc:`use_cases`
- Developer guide: :doc:`developer_guide`
- API details: :doc:`api`

.. note::

   This project is under active development and the docs are intentionally aligned to
   the current orchestrator wiring.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   getting_started
   installation
   overview
   tutorial
   stages
   developer_guide
   examples
   use_cases
   usage
   api
