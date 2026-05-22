from __future__ import annotations

from pathlib import Path
from pprint import pprint

from VmaxBuilder.api import VmaxOrchestrator, build_default_api_config
from VmaxBuilder.config import ProteinSourceMode, ReactionNotation, ValidationMode
from VmaxBuilder.protein.stage_implementation import DefaultProteinStageCoordinator

if __name__ == "__main__":
    # Keep existing model filepath scaffold unchanged.
    base_dir = Path(r"C:\git\SWaPAM\data\for_SWAMP")
    models_dir = base_dir / "models"
    model_name = "HumanGEM_2"
    model_dir = models_dir / model_name
    model_path = model_dir

    # Protein inputs (set whichever mode needs).
    expression_path = base_dir / "expression_datasets" / "NCI60"
    ptr_path = base_dir / "PTR_datasets" / "Eraslan2019_human"
    proteomics_path = base_dir / "proteomics" / "NCI_60_human"

    # Stage/run toggles.
    run_all_stages = False
    run_model_stage = True
    run_protein_stage = True

    # Choose protein implementation mode.
    protein_mode = ProteinSourceMode.EXPRESSION_PTR
    # protein_mode = ProteinSourceMode.PROTEOMICS

    config = build_default_api_config()

    # Global/model options.
    config.validation.mode = ValidationMode.STRICT
    config.loading.model_path = model_path
    config.model.reaction_notation = ReactionNotation.STANDARD
    config.model.make_copy = True
    config.model.target_id_type = "ensembl_gene_id"

    # Pipeline target granularity.
    config.run_target_transcript_gene_level = "gene"

    # Expression option group.
    config.expression.id_type = "ensembl_transcript_id"
    config.expression.transformation_state = "log"
    config.expression.origin_transcript_gene_level = "transcript"
    config.expression.data_type = "TPM"
    config.expression.thresholding = False

    # PTR option group.
    config.ptr.id_type = "ensembl_gene_id"
    config.ptr.transformation_state = "log"
    config.ptr.origin_transcript_gene_level = "gene"

    # Proteomics option group.
    config.proteomics.id_type = "uniprot"
    config.proteomics.origin_transcript_gene_level = "gene"
    config.proteomics.transformation_state = "log"
    config.proteomics.imputation_strategy = "weighted_gene_median"
    config.proteomics.fallback_imputation_strategy = "weighted_sample_median"

    # Protein stage mode config.
    config.protein.source_mode = protein_mode
    config.protein.ptr_method = "ptr_weighted_median"

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

    if run_protein_stage:
        mode_requirements = DefaultProteinStageCoordinator.get_mode_requirements(
            config.protein.source_mode
        )
        missing_paths: list[str] = []
        effective_paths = config.loading.get_effective_exact_paths()
        effective_in_memory = config.loading.get_effective_in_memory_inputs()
        for input_key in mode_requirements["required_inputs"]:
            has_in_memory = input_key in effective_in_memory
            input_path = effective_paths.get(input_key)
            has_path = input_path is not None and Path(input_path).exists()
            if not has_in_memory and not has_path:
                missing_paths.append(input_key)
        if missing_paths:
            raise RuntimeError(
                "Missing required protein inputs for mode "
                f"'{config.protein.source_mode.value}': {missing_paths}. "
                "Set required *_path values to existing files or provide in_memory_inputs."
            )

    if run_all_stages:
        scaffold = orchestrator.run_all()
    else:
        scaffold = {
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

    print("\n=== Scaffold metadata ===")
    pprint(scaffold.get("metadata", {}), sort_dicts=False)
