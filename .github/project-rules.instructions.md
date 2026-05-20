# Project Rules



Scope:

- Only modify code inside `src/VmaxBuilder` (see allowed modules), except if specifically asked to modify files outside.

- Ignore legacy or refactor-in-progress code unless explicitly instructed



Testing:

- Tests should mirror the structure of `src/VmaxBuilder`

- Improve coverage when modifying logic



Documentation:

- Do NOT create standalone `.md` documentation files except when specifically asked to

- Only modify inline docstrings, check [architecture.instructions.md](architecture.instructions.md) instructions



Commits:

- Do NOT perform commits

- Instead propose:

  - atomic commit messages (commitizen/commitlint style)

  - list of changed files



Signature changes:

- If a function signature changes:

    → documentation MUST be updated
