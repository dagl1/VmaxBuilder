from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from VmaxBuilder.utils.file_handling import (
    check_for_existing_files,
    get_project_root,
    load_existing_file_based_on_extension,
    save_with_tries,
)


@pytest.mark.unit
def test_get_project_root_finds_parent_with_project_name(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    nested_directory = project_root / "src" / "nested"
    nested_directory.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n',
        encoding="utf-8",
    )

    assert get_project_root(nested_directory) == project_root


@pytest.mark.unit
def test_get_project_root_falls_back_to_src_parent(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "package"
    src_dir.mkdir(parents=True)

    root = get_project_root(src_dir)
    assert root == tmp_path


@pytest.mark.unit
def test_get_project_root_raises_when_nothing_found(tmp_path: Path) -> None:
    isolated = tmp_path / "isolated"
    isolated.mkdir()

    with pytest.raises(RuntimeError, match="Could not find"):
        get_project_root(isolated)


@pytest.mark.unit
def test_check_for_existing_files_returns_matching_path(tmp_path: Path) -> None:
    matching_file = tmp_path / "Example_Result.TXT"
    matching_file.write_text("content", encoding="utf-8")

    found_path = check_for_existing_files(tmp_path, ["example"], [".txt"])

    assert found_path == str(matching_file)


@pytest.mark.unit
def test_check_for_existing_files_returns_false_when_missing(tmp_path: Path) -> None:
    result = check_for_existing_files(tmp_path, ["missing"], [".csv"])
    assert result is False


@pytest.mark.unit
def test_check_for_existing_files_returns_false_for_nonexistent_dir(tmp_path: Path) -> None:
    result = check_for_existing_files(tmp_path / "ghost", ["x"], [".csv"])
    assert result is False


@pytest.mark.unit
def test_load_existing_file_based_on_extension_reads_csv(tmp_path: Path) -> None:
    input_frame = pd.DataFrame({"value": [1, 2], "name": ["a", "b"]})
    csv_path = tmp_path / "data.csv"
    input_frame.to_csv(csv_path, index=False)

    loaded_frame = load_existing_file_based_on_extension(csv_path)

    pd.testing.assert_frame_equal(loaded_frame, input_frame)


@pytest.mark.unit
def test_load_existing_file_based_on_extension_reads_json(tmp_path: Path) -> None:
    data = [{"a": 1}, {"a": 2}]
    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_existing_file_based_on_extension(json_path)
    assert isinstance(loaded, pd.DataFrame)
    assert list(loaded["a"]) == [1, 2]


@pytest.mark.unit
def test_load_existing_file_based_on_extension_raises_on_unsupported(
    tmp_path: Path,
) -> None:
    weird_file = tmp_path / "data.xyz"
    weird_file.write_text("content")

    with pytest.raises(ValueError, match="Unsupported"):
        load_existing_file_based_on_extension(weird_file)


@pytest.mark.unit
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


@pytest.mark.unit
def test_save_with_tries_overwrites_existing_file(tmp_path: Path) -> None:
    file_path = tmp_path / "output.txt"
    file_path.write_text("old content", encoding="utf-8")

    save_with_tries(
        data="new content",
        filename="output",
        extension="txt",
        save_dir=tmp_path,
        overwrite=True,
    )

    assert file_path.read_text(encoding="utf-8") == "new content"


@pytest.mark.unit
def test_save_with_tries_dataframe_csv(tmp_path: Path) -> None:
    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})

    save_with_tries(
        data=df, filename="frame", extension="csv", save_dir=tmp_path, overwrite=True
    )

    loaded = pd.read_csv(tmp_path / "frame.csv")
    pd.testing.assert_frame_equal(loaded, df)


@pytest.mark.unit
def test_save_with_tries_dict_json(tmp_path: Path) -> None:
    data = {"key": "value", "number": 42}

    save_with_tries(
        data=data, filename="data", extension="json", save_dir=tmp_path, overwrite=True
    )

    with (tmp_path / "data.json").open(encoding="utf-8") as fh:
        loaded = json.load(fh)
    assert loaded == data


@pytest.mark.unit
def test_save_with_tries_raises_on_unsupported_type(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        save_with_tries(data=12345, filename="bad", extension="csv", save_dir=tmp_path)  # type: ignore[arg-type]


@pytest.mark.unit
def test_save_with_tries_raises_on_invalid_extension_for_type(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not valid"):
        save_with_tries(data="text", filename="bad", extension="csv", save_dir=tmp_path)
