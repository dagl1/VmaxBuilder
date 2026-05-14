Usage
=====

.. _installation:

Installation
------------

To use VmaxBuilder, first install it. This can be done in several ways:

**Using pip**: The easiest way to install VmaxBuilder is via pip.
Open your terminal and run:

    .. code-block:: console

        $ pip install VmaxBuilder

We recommend creating a virtual environment before installing to avoid conflicts
with other packages. You can do this using `venv`, `conda <https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html>`_,
or *preferably* `UV <https://docs.astral.sh/uv/getting-started/installation/>`_.

    .. code-block:: console

        (.venv) $ pip install VmaxBuilder

    .. code-block:: console

        (.venv) $ uv add VmaxBuilder


    .. code-block:: console

        (.venv) $ conda install VmaxBuilder


   .. note::
      [\Unverified as of VmaxBUilder v0.1.0]
      VmaxBuilder depends on the MIP package, which in turn requires cffi. This means you
      are required to have C build tools installed on your system. These can be easily found
      at this `link <https://visualstudio.microsoft.com/visual-cpp-build-tools/>`_.
      Installing the C++ desktop development workload is sufficient.


   .. important::

      The :class:`VmaxBuilder.input_preprocessing.PTR_preprocessing.PtrPreprocessor` class
      requires a file containing tissue- or condition-specific PTR values for genes.
      By default VmaxBuilder uses and comes with an n=1 for 29 tissues matched transcriptomic
      and proteomic dataset from `Eraslan et al.,
      2019 <https://www.embopress.org/doi/full/10.15252/msb.20188513>`__
      (created from Table_EV3, last set of columns). If researchers prefer to use their own
      or other datasets, they can do so by providing a file with the same format.


   .. important::

      The :class:`VmaxBuilder.input_preprocessing.Kcat_preprocessing.KcatPreprocessor` class
      requires a file containing Kcat values for gene-substrate pairs, or in (not implemented yet todo)
      the future a file containing Kcat values for reactions. By default, VmaxBuilder uses
      `UniKP <https://pmc.ncbi.nlm.nih.gov/articles/PMC10713628/>`__ for which a custom
      wrapper is provided. This however requires a different Python version/environment and thus
      should be ran separately. It is thererfore possible to slot in reaction Kcat values or gene-substrate
      pairs in the same format as provided in the examples.
