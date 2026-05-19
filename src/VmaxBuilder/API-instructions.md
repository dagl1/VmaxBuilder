This document contains API endpoints, and submodules for the different processing steps
in VmaxBuilder. A main class is used for incorperating the submodules, such that a single
interface is used for calling all functions. This includes loading, validation, path-setting,
diagnostics, and running all, or running specific subsets.


The large steps of VmaxBuilder are:

- expression data gets preprocessed
  - inputs: expression data
  - options: [transformations given input scale (log, linear), transcripts/gene level]
  - outputs: [preprocessed expression data, Optional[trimmable genes]]
- model preprocessing
  - inputs: [Cobra model]
  - options: []
  - outputs: [Cobra model]
- protein abundance estimation from PTR + expression or direct proteomics:
  - inputs: [Cobra model, Optional[protein abundance], Optional[PTR data], Optional[preprocessed expression data]]
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
- Kcat estimation
  - inputs: [Cobra model, Optional[additional annotations], Optional[Custom SMILES], Optional[gene/transcript AA
    sequences]]
  - submodules:
    - gene/transcript AA sequence retrieval
      - submodules:
        - Optional[database lookups]
          - inputs: [Optional[AA sequences] |  Optional[gene list, id-type, Optional[database to look in], Optional
            [additional annotations]]
          - options: []
          - outputs: [AA sequences]
        - Optional[AA sequences] (already done)
          - inputs: []
          - outputs [AA sequences]
    - SMILES retrieval
      - inputs: [Optional[SMILES list] | Optional[metabolite list, id-type, Optional[databases], Optional[additional
        annotaitons]]
      - options: []
      - outputs: [SMILES]
    - Kcat estimation
      - inputs: [AA sequences, Optional[EC numbers], [SMILES], Optional[cobra model.reactions]]]
      - options: [UniKP, deepEnzyme, DLKcat]
      - outputs: [Optional[gene-metabolite Kcat pairs] | Optional[gene-reaction Kcat pairs] |
        Optional[IFP-metabolite Kcat pairs] | Optional[IFP-reaction Kcat Pairs]]
    - Kcat processing/resolving (GPR based)
      - inputs: [Optional[gene-metabolite Kcat pairs] | Optional[gene-reaction Kcat pairs] |
        Optional[IFP-metabolite Kcat pairs]]
      - options: [depends on input, gene-accumulation strategy, metabolite-accumulation, strategy]
      - outputs: [IFP-reaction Kcat pair]
  - outputs: [per IFP-reaction Kcat, Optional[metadata]]
- Reaction capacity assignment
  - inputs: [Cobra Model, [protein abundance | preprocessed expression data], Optional[per IFP,reaction Kcat]]
  - submodules:
    - GPR to IFP splitting
      - inputs: [Cobra Model]
      - options: [transcript or gene level]
      - outputs: [IFP splits]
    - IFP allocation (QP)
      - inputs: [IFP splits, [protein abundance | preprocessed expression data], Optional[trimmable genes]]]
      - options: [QP, trimming]
      - outputs: [IFP allocation, Optional[trimmed genes]]
    - reaction capacity calculation
      - inputs: [IFP allocation, Optional[per IFP-reaction Kcat]]
      - options: []
      - outputs: [Reaction capacities]
    - Optional[reaction capacity imputation]
      - inputs: [Reaction capacities]
      - options: [imputation strategies]
      - outputs: [imputed reaction capacity]
  - outputs: [reaction capacity, IFP splits, IFP allocation, Optional[metadata], Optional[imputed reaction capacity]]
