# Documentation Style

Use Google-style docstrings with required extensions.

## Required sections

- Description (always required)

- Args: (only if function/class has parameters)

- Returns: (only if function returns a non-None value)

- Raises: (only if exceptions are raised)

- Requires: (only if there are instance attribute dependencies)

- Modifies: (only if there are side effects or state changes)

## Omission rule

**Do not include a section if it has no content.**

- No `Args: None.` — omit `Args:` entirely if there are no parameters.
- No `Returns: None.` — omit `Returns:` if the return is `None` or there is nothing meaningful to document.
- No `Raises: None.` — omit `Raises:` if no exceptions are raised.
- No `Requires: None.` — omit `Requires:` if there are no attribute dependencies.
- No `Modifies: None.` — omit `Modifies:` if there are no side effects.

Only the **Description** is always required. Every other section is conditional on having actual content.

Applies to both function and class/module-level docstrings.

## Rules

- All parameters must include type hints in docstring

- Must match function signature exactly

### Example

- param_name (dict\[str, pd.DataFrame | int]): description

## Additional requirements

- Include usage example when helpful

- Update documentation whenever signature changes

- Add documentation to functions that lack it, if function is modified

## Important

All generated or modified docstrings must start with:

"Generated: validation needed"

## Sphinx

ALL generated docstrings much be compatible with Sphinx for read-the-docs
