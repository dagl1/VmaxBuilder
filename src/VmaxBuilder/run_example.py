from __future__ import annotations

from pathlib import Path
from pprint import pprint

from VmaxBuilder.api import VmaxOrchestrator, build_default_api_config
from VmaxBuilder.config import ReactionNotation, ValidationMode

if __name__ == "__main__":
    # Put your model path here. Raw string avoids escaping backslashes on Windows.
    base_dir = Path(r"C:\git\SWaPAM\data\for_SWAMP")
    models_dir = base_dir / "models"
    model_name = "HumanGEM_2"
    model_dir = models_dir / model_name
    # Example alternative paths:
    model_path = model_dir

    # Change options here before each run.
    reaction_notation = ReactionNotation.STANDARD
    validation_mode = ValidationMode.STRICT
    make_copy = True

    # Run only model stage by default. Set True to run full pipeline stages.
    run_all_stages = False

    config = build_default_api_config()

    # Standard usage: assign fields after factory creation.
    config.validation.mode = validation_mode
    config.loading.model_path = model_path
    config.model.reaction_notation = reaction_notation
    config.model.make_copy = make_copy

    # Optional in-memory model usage (uncomment to bypass model_path-based loading):
    # from cobra.io import read_sbml_model
    # loaded_model = read_sbml_model(str(model_path))
    # config.loading.model_object = loaded_model
    # config.loading.model_path = None

    orchestrator = VmaxOrchestrator(config=config)
    scaffold = orchestrator.run_all() if run_all_stages else orchestrator.run_model()

    print("\n=== Effective model options ===")
    print(f"model_path: {config.loading.model_path}")
    print(f"reaction_notation: {config.model.reaction_notation.value}")
    print(f"validation_mode: {config.validation.mode.value}")
    print(f"make_copy: {config.model.make_copy}")

    print("\n=== Scaffold artifacts ===")
    pprint(scaffold.get("artifacts", {}), sort_dicts=False)

    print("\n=== Scaffold metadata ===")
    pprint(scaffold.get("metadata", {}), sort_dicts=False)

    print(f"model_path: {config.loading.model_path}")
    print(f"reaction_notation: {config.model.reaction_notation.value}")
    print(f"validation_mode: {config.validation.mode.value}")
    print(f"make_copy: {config.model.make_copy}")
