# Project Rules



Scope:

- Only modify code inside `src/SWAMP` (see allowed modules)

- Ignore legacy or refactor-in-progress code unless explicitly instructed



Testing:

- Tests should mirror the structure of `src/SWAMP`

- Improve coverage when modifying logic



Documentation:

- Do NOT create standalone `.md` documentation files

- Only modify inline docstrings



Commits:

- Do NOT perform commits

- Instead propose:

  - atomic commit messages (commitizen/commitlint style)

  - list of changed files



Signature changes:

- If a function signature changes:

    → documentation MUST be updated
