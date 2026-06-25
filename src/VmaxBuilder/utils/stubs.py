import os
from collections import defaultdict
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any


def extract_schema(cls: type) -> dict[str, type]:
    schema = {}
    if not is_dataclass(cls):
        return schema  # ty: ignore [invalid-return-type]
    for f in fields(cls):
        schema[f.name] = f.type

    return schema  # ty: ignore [invalid-return-type]


def resolve_type(typ, imports):
    if typ is Any:
        return "Any"

    module = getattr(typ, "__module__", None)
    name = getattr(typ, "__name__", None)

    if module and module != "builtins":
        imports[module].add(name)
        return name

    return name or "Any"


def generate_stub(stage: str, impl_name: str, schema: dict[str, type]) -> str:
    class_name = f"{impl_name.capitalize()}Config"

    imports = defaultdict(set)

    protocol_import_lines = ["from typing import Protocol", ""]
    lines = []

    lines.append(f"class {class_name}(Protocol):")

    if not schema:
        lines.append("    pass")

    for name, typ in schema.items():
        type_name = resolve_type(typ, imports)
        lines.append(f"    {name}: {type_name}")

    # add imports at top
    import_lines = []
    for module, names in imports.items():
        import_lines.append(f"from {module} import {', '.join(sorted(names))}")

    return "\n".join(import_lines + [""] + protocol_import_lines + lines)


def _update_stub_for_implementation(stage, name, config_cls):
    schema = extract_schema(config_cls)

    stub = generate_stub(stage, impl_name=name, schema=schema)

    path = Path("src/VmaxBuilder/typing_stubs/")
    print(f"Writing stub for {name} to {path}")
    path.mkdir(parents=True, exist_ok=True)
    if not (path / "__init__.py").exists():
        init_path = path / "__init__.py"
        init_path.write_text(
            "# This file is auto-generated to make the directory a package.\n"
        )
    stage_path = path / stage
    stage_path.mkdir(parents=True, exist_ok=True)
    if not (stage_path / "__init__.py").exists():
        init_path = stage_path / "__init__.py"
        init_path.write_text(
            "# This file is auto-generated to make the directory a package.\n"
        )
    implementation_path = stage_path / name
    implementation_path.mkdir(parents=True, exist_ok=True)
    if not (implementation_path / "__init__.py").exists():
        init_path = implementation_path / "__init__.py"
        init_path.write_text(
            "# This file is auto-generated to make the directory a package.\n"
        )
    #
    stub_file_path = implementation_path / "implementation.py"
    stub_file_path.write_text(stub)
