Workflow Instructions

When generating or modifying code:

1. Prefer extending existing utilities over creating new ones

2. Reuse:

  - `utils/file\_handling.py`

  - `utils/plotting.py`

  - `utils/custom\_logging.py`



3. Logging:

  - Always use `CustomLogger`



4. Plotting:

  - Use Plotly graph\_objects only

  - Never use matplotlib



5. Code organization:

  - If functionality is reusable:

    → place in `utils/`

  - Otherwise:

    → keep local to module



6. When unsure:

 - Follow patterns already used in `analysis` and `optimization`
