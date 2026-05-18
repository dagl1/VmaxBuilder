This document contains API endpoints, and submodules for the different processing steps
in VmaxBuilder. A main class is used for incorperating the submodules, such that a single
interface is used for calling all functions. This includes loading, validation, path-setting,
diagnostics, and running all, or running specific subsets.

The large steps of VmaxBuilder are:

- expression data gets preprocessed
  - inputs: expression data
  - options: transformations given input scale (log, linear)
  - outputs: preprocessed expression data
- protein abundance estimation from PTR + expression or direct proteomics:
  - inputs: [Optional[protein abundance], Optional[PTR data], Optional[preprocessed expression data]]
  - submodules:
    - estimating protein abundance
      - submodules:
        - expression data gets preprocessed
          - inputs: expression data
          - options: transformations given input scale (log, linear)
          - outputs: preprocessed expression data
        - PTR data gets preprocessed and imputed
          - inputs: [PTR dataset, metabolic_genes]
          - options: use metabolic genes only
          - submodules:
            - PTR imputation
                - inputs: PTR data
                - options: imputation strategies
                - outputs: imputed PTR data
          - outputs: imputed PTR dataset
        - integrating PTR + expression data
          - inputs: [imputed PTR dataset, preprocessed expresssion data, sample_type]
          - options: [simple multiplication, linear regression]
          - outputs: [protein_abundance]
    - direct integration of proteomics data
      - inputs: [proteomics data]
      - submodules:
        - Optional[proteomics preprocessing/imputation]
          - inputs: [proteomics data]
          - options: [preprocessing strategies, imputation strategies]
          - outputs: [preprocessed proteomics data]
        - Proteomics to protein abundance
          - inputs: [proteomics data]
          - outputs [protein abundance]
      - outputs: [protein_abundance]
