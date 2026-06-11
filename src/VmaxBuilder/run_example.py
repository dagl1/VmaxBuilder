from __future__ import annotations

from pathlib import Path
from pprint import pprint

from VmaxBuilder.api import VmaxOrchestrator, build_default_api_config
from VmaxBuilder.config import ProteinSourceMode, ReactionNotation, ValidationMode
from VmaxBuilder.core.protocols import Scaffold

if __name__ == "__main__":
    print("file")
    # Keep existing model filepath scaffold unchanged.
    # base_dir = Path(r"C:\git\SWaPAM\data\for_SWAMP")
    base_dir = Path("~/git/SWAPAM/data/for_SWAMP/")
    models_dir = base_dir / "models"
    model_name = "model_inhouse_v9_human"
    model_dir = models_dir / model_name
    model_path = model_dir

    # Protein inputs (set whichever mode needs).
    expression_path = base_dir / "expression_datasets" / "NCI_60_human"
    ptr_path = base_dir / "PTR_datasets" / "Eraslan2019_human"
    proteomics_path = base_dir / "proteomics" / "NCI60"
    output_path = Path("~:/git/VmaxBuilder/data/run_example_output")
    create_dynamically_named_results = True

    # Stage/run toggles.
    run_all_stages = False
    run_model_stage = True
    run_protein_stage = True
    config = build_default_api_config()

    # Global/model options.
    config.validation.mode = ValidationMode.STRICT
    config.loading.output_path = output_path
    config.loading.create_dynamically_named_results = create_dynamically_named_results
    config.loading.model_path = model_path
    config.model.reaction_notation = ReactionNotation.STANDARD
    config.model.make_copy = True
    config.model.id_type = "ensembl"
    config.model.level = "gene"

    # Pipeline target granularity.
    config.run_target_transcript_gene_level = "gene"
    config.maximum_transcript_ifp_expansion = 20000

    # Expression option group.
    config.expression.id_type = "ensembl"
    config.expression.level = "gene"
    config.expression.transformation_state = "log2"
    config.expression.data_type = "raw_counts"
    config.expression.thresholding = False
    config.expression.sample_type_map = "heart"

    # PTR option group.
    config.ptr.id_type = "ensembl"
    config.ptr.level = "gene"
    config.ptr.pretransformed_type = "log10"
    config.ptr.partial_missing_imputation_statistic = "median"
    config.ptr.partial_missing_weighted_statistic = "median"
    config.ptr.partial_missing_use_weighted = True
    config.ptr.unobserved_gene_imputation_strategy = "sample_after_imputation"
    config.ptr.unobserved_gene_imputation_statistic = "median"
    config.ptr.use_special_groups_for_unobserved_imputation = True
    config.ptr.special_gene_groups = {
        "transport_reactions": [],
    }
    config.ptr.impute_from_metabolic_genes_only = True

    # Proteomics option group.
    config.proteomics.id_type = "ensembl"
    config.proteomics.level = "gene"
    # config.proteomics.transformation_state = "log"
    # config.proteomics.imputation_strategy = "weighted_gene_median"
    # config.proteomics.fallback_imputation_strategy = "weighted_sample_median"

    # Protein stage mode config.
    config.protein.source_mode = ProteinSourceMode.EXPRESSION_PTR
    config.protein.ptr_method = "ptr_weighted_median"
    config.expression.sample_type_map = "heart"

    # Must-have input paths by mode:
    # - EXPRESSION_PTR: must provide expression + ptr
    # - PROTEOMICS: must provide proteomics
    if config.protein.source_mode is ProteinSourceMode.EXPRESSION_PTR:
        config.loading.expression_path = expression_path
        config.loading.ptr_path = ptr_path
    elif config.protein.source_mode is ProteinSourceMode.PROTEOMICS:
        config.loading.proteomics_path = proteomics_path

    # Optional in-memory usage example (uncomment if you already have tables loaded):
    # config.loading.in_memory_inputs["expression"] = pd.DataFrame(...)
    # config.loading.in_memory_inputs["ptr"] = pd.DataFrame(...)
    # config.loading.in_memory_inputs["proteomics"] = pd.DataFrame(...)

    orchestrator = VmaxOrchestrator(config=config)

    if run_all_stages:
        scaffold = orchestrator.run_all()
    else:
        scaffold: Scaffold = {
            "inputs": {},
            "artifacts": {},
            "outputs": {},
            "metadata": {},
            "diagnostics": {},
            "extras": {},
        }
        if run_model_stage:
            scaffold = orchestrator.run_model(scaffold)
        if run_protein_stage:
            scaffold = orchestrator.run_protein(scaffold)

    print("\n=== Effective key options ===")
    print(f"model_path: {config.loading.model_path}")
    print(f"protein_mode: {config.protein.source_mode.value}")
    print(f"run_target_transcript_gene_level: {config.run_target_transcript_gene_level}")

    print("\n=== Protein required inputs by mode ===")
    print("EXPRESSION_PTR -> expression + ptr")
    print("PROTEOMICS -> proteomics")

    print("\n=== Scaffold artifacts keys ===")
    print(list(scaffold.get("artifacts", {}).keys()))

    orchestrator_metadata = scaffold.get("metadata", {}).get("orchestrator", {})
    print("\n=== Runtime output directories ===")
    pprint(orchestrator_metadata, sort_dicts=False)

    print("\n=== Scaffold metadata ===")
    pprint(scaffold.get("metadata", {}), sort_dicts=False)

    print("some text")
