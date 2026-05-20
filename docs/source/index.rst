.. VmaxBuilder documentation master file, created by
   sphinx-quickstart on Sun Jun  8 16:04:05 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

VmaxBuilder documentation
====================================================================

**VmaxBuilder** is a Python library to integrate transcriptomics data into Genome-Scale
metabolic models (GEMs) to predict maximum reaction rates (Vmax) in a condition- and
tissue-specific manner. It is a modular pipeline that consists of three main steps:
1. Estimation of protein abundance from transcriptomics data using the protein-to-RNA ratios.
2. Allocation of the estimated protein abundance to reactions using gene-protein-reaction (GPR)
   rules and quadratic programming allocation strategy, which aims to allocate proteins as
   to evenly distribute them to as many independently functioning proteins (IFPs)
   while remaining constrained by each individual's protein abundance - see publication
   <link> for more information.
3. Estimation of Vmax values for each reaction by multiplying the allocated protein abundance
   with the each IFP's reaction-specific Kcat value, predicted through one of several
   Kcat-prediciton algorithms such as UniKP (<link>), or directly fetched from databases
   such as Brenda or Sabio-RK.

.. note::

   For information on how to get started see the
   :doc:`usage` page, including a guide on :ref:`installing <installation>`
   VmaxBuilder.

.. note::

   This project is under active development.


..  toctree::
    :caption: Contents

    usage
    VmaxBuilder (API)
