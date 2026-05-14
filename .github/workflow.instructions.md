\# Workflow Instructions



When generating or modifying code:



1\. Prefer extending existing utilities over creating new ones

2\. Reuse:

&#x20;  - `utils/file\_handling.py`

&#x20;  - `utils/plotting.py`

&#x20;  - `utils/custom\_logging.py`



3\. Logging:

&#x20;  - Always use `CustomLogger`



4\. Plotting:

&#x20;  - Use Plotly graph\_objects only

&#x20;  - Never use matplotlib



5\. Code organization:

&#x20;  - If functionality is reusable:

&#x20;    → place in `utils/`

&#x20;  - Otherwise:

&#x20;    → keep local to module



6\. When unsure:

&#x20;  - Follow patterns already used in `analysis` and `optimization`
