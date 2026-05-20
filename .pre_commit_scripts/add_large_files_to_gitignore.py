#!/usr/bin/env python3
"""Pre-commit hook: append any files >99 MB that are not already covered by
.gitignore to the ignore file, keeping the file clean and deduplicated.

Features
--------
* Skips files already ignored by git (exact or via existing patterns).
* Deduplicates all entries in .gitignore on every run (case-insensitive on
  Windows, case-sensitive elsewhere).
* Strips trailing whitespace from every line.
* Removes blank lines that appear consecutively (max one blank line between
  sections).
* Appends new large-file entries under a clearly labelled section.
* Re-stages .gitignore automatically so the update is part of the commit.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_MAX_BYTES = 99 * 1024 * 1024  # 99 MB
_ROOT = Path(__file__).resolve().parent.parent
_GITIGNORE = _ROOT / ".gitignore"
_SECTION_HEADER = "# Auto-added by pre-commit (files >99 MB)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=_ROOT,
    )


def _is_ignored(path: Path) -> bool:
    """Return True if git already considers this path ignored."""
    return _git("check-ignore", "-q", str(path)).returncode == 0


def _staged_added_files() -> list[Path]:
    """Return staged added file paths (A) relative to repository root."""
    result = _git("diff", "--cached", "--name-only", "--diff-filter=A", "-z")
    if result.returncode != 0:
        return []

    files: list[Path] = []
    for rel_path in result.stdout.split("\0"):
        if not rel_path:
            continue
        files.append(Path(rel_path))
    return files


# ---------------------------------------------------------------------------
# .gitignore cleaning helpers
# ---------------------------------------------------------------------------


def _clean_lines(lines: list[str]) -> list[str]:
    """Strip trailing whitespace and collapse consecutive blank lines."""
    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        line = line.rstrip()
        is_blank = line == ""
        if is_blank and prev_blank:
            continue  # collapse consecutive blanks
        cleaned.append(line)
        prev_blank = is_blank
    # Remove a single trailing blank line if present
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    return cleaned


def _pattern_set(lines: list[str]) -> set[str]:
    """Return the set of non-comment, non-blank patterns already present."""
    return {
        line.strip() for line in lines if line.strip() and not line.strip().startswith("#")
    }


def _deduplicate(lines: list[str]) -> list[str]:
    """Remove duplicate patterns, keeping the first occurrence."""
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        is_pattern = stripped and not stripped.startswith("#")
        if is_pattern:
            key = stripped.lower() if sys.platform == "win32" else stripped
            if key in seen:
                continue
            seen.add(key)
        result.append(line)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:  # noqa: C901
    # ── 1. Collect staged large files that are not already ignored ─────────
    large_files: list[str] = []
    for rel_path in _staged_added_files():
        f = _ROOT / rel_path
        if not f.is_file():
            continue
        try:
            size = f.stat().st_size
        except OSError:
            continue
        if size <= _MAX_BYTES:
            continue
        if _is_ignored(rel_path):
            continue
        large_files.append(rel_path.as_posix())

    # ── 2. Read and normalise existing .gitignore ───────────────────────────
    raw: str = _GITIGNORE.read_text(encoding="utf-8") if _GITIGNORE.exists() else ""
    lines = raw.splitlines()
    lines = _clean_lines(lines)
    lines = _deduplicate(lines)
    existing_patterns = _pattern_set(lines)

    # ── 3. Determine which large files are genuinely new ───────────────────
    new_entries = [p for p in large_files if p not in existing_patterns]

    # ── 4. Append new entries under a labelled section ─────────────────────
    if new_entries:
        # Avoid duplicating the section header itself
        if _SECTION_HEADER not in (line_item.strip() for line_item in lines):
            lines.append("")
            lines.append(_SECTION_HEADER)
        for entry in new_entries:
            lines.append(entry)

    # ── 5. Write back (always, to apply cleaning even if no new entries) ───
    new_content = "\n".join(lines) + "\n"
    old_content = raw

    if new_content != old_content:
        _GITIGNORE.write_text(new_content, encoding="utf-8")
        _git("add", ".gitignore")

    # ── 6. Report ───────────────────────────────────────────────────────────
    if new_entries:
        print(
            f"[add-large-files] Appended {len(new_entries)} large file(s) to .gitignore:",
            file=sys.stderr,
        )
        for entry in new_entries:
            print(f"  + {entry}", file=sys.stderr)
    elif new_content != old_content:
        print(
            "[add-large-files] Cleaned up .gitignore (deduplication / whitespace).",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
