# Documentation Style

Use Google-style docstrings with required extensions.


## Required sections:

- Description

- Args:

- Returns:

- Raises: (if applicable)

- Requires: (for dependencies on instance attributes)

- Modifies: (for side effects or state changes)



## Rules:

- All parameters must include type hints in docstring

- Must match function signature exactly

### Example:

- param_name (dict\[str, pd.DataFrame | int]): description



## Additional requirements:

- Include usage example when helpful

- Update documentation whenever signature changes

- Add documentation to functions that lack it, if function is modified



## Important:

All generated or modified docstrings must start with:

"Generated: validation needed"


## Sphinx

ALL generated docstrings much be compatible with Sphinx for read-the-docs
