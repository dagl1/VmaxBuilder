from __future__ import annotations

from pathlib import Path

import pandas as pd

from VmaxBuilder.utils.file_handling import (
    check_for_existing_files,
    get_project_root,
    load_existing_file_based_on_extension,
    save_with_tries,
)


def test_get_project_root_finds_parent_with_project_name(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    nested_directory = project_root / "src" / "nested"
    nested_directory.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n',
        encoding="utf-8",
    )

    assert get_project_root(nested_directory) == project_root


def test_check_for_existing_files_returns_matching_path(tmp_path: Path) -> None:
    matching_file = tmp_path / "Example_Result.TXT"
    matching_file.write_text("content", encoding="utf-8")

    found_path = check_for_existing_files(tmp_path, ["example"], [".txt"])

    assert found_path == str(matching_file)


def test_load_existing_file_based_on_extension_reads_csv(tmp_path: Path) -> None:
    input_frame = pd.DataFrame({"value": [1, 2], "name": ["a", "b"]})
    csv_path = tmp_path / "data.csv"
    input_frame.to_csv(csv_path, index=False)

    loaded_frame = load_existing_file_based_on_extension(csv_path)

    pd.testing.assert_frame_equal(loaded_frame, input_frame)


def test_save_with_tries_writes_string_and_creates_directory(tmp_path: Path) -> None:
    save_directory = tmp_path / "nested" / "output"

    save_with_tries(
        data="hello",
        filename="greeting",
        extension="txt",
        save_dir=save_directory,
        overwrite=False,
    )

    saved_file = save_directory / "greeting.txt"
    assert saved_file.exists()
    assert saved_file.read_text(encoding="utf-8") == "hello"
