# Coding Style

Follow:
- PEP 8 and the Zen of Python

Naming:
- `normalise` not `normalize` (British English)
- Use fully descriptive names (e.g. `reaction`, not `rxn`)
- Avoid abbreviations and acronyms except:
  - index variables: `idx`, `rxn_idx`, `gene_idx`
- Never use single-letter variables (`i`, `j`, `k`)

Constants:
- No magic numbers → assign to named variables

Typing:
- All functions must:
  - be fully type hinted
  - pass type checking using `ty` (astral)
- Variables, when necessary, should be typed
  - If applicable (upon type error), cast types to ensure correct typing

Paths:
- Always use `pathlib`
- Never use `os` when `pathlib` can replace it

Formatting:
- Code must pass `ruff` (format + lint)

Checking
- Code must pass `ruff` check

Package management:
- Use `uv` only -> pyproject.toml for specific project settings
- Never use `pip`
