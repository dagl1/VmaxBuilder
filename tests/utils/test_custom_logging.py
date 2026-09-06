from __future__ import annotations

from pathlib import Path

import pytest

from VmaxBuilder.utils.custom_logging import (
    CustomLogger,
    PrintLevelFilter,
    decorator_provide_time_information_2,
    parse_log_file,
)


@pytest.mark.unit
def test_parse_log_file_pairs_start_and_finish_entries(tmp_path: Path) -> None:
    log_path = tmp_path / "example.log"
    log_path.write_text(
        (
            "2026-05-19 12:00:00,000 - STARTING - Starting: demo (demo.py:10)\n"
            "2026-05-19 12:00:01,000 - FINISHED - Finished: demo in: 1.0000 seconds "
            "(demo.py:20)\n"
        ),
        encoding="utf-8",
    )

    parsed_frame = parse_log_file(log_path)

    assert len(parsed_frame) == 1
    assert parsed_frame.loc[0, "function"] == "demo"
    assert parsed_frame.loc[0, "calls"] == 1


@pytest.mark.unit
def test_custom_logger_accepts_path_log_directory(tmp_path: Path) -> None:
    log_directory = tmp_path / "logs"

    logger = CustomLogger("unit-test-logger", log_directory, auto_parse=False)

    assert logger.log_file_path.parent == log_directory
    assert logger.log_file_path.name == "unit-test-logger.log"


@pytest.mark.unit
def test_custom_logger_set_print_level(tmp_path: Path) -> None:
    logger = CustomLogger("pl-test", tmp_path, print_level=2, auto_parse=False)
    logger.set_print_level(5)
    assert logger.print_level == 5
    assert logger.filter.print_level == 5


@pytest.mark.unit
def test_custom_logger_set_log_files_location(tmp_path: Path) -> None:
    first_dir = tmp_path / "dir1"
    second_dir = tmp_path / "dir2"
    logger = CustomLogger("relocate-test", first_dir, auto_parse=False)

    logger.set_log_files_location(str(second_dir))

    assert logger.log_file_path.parent == second_dir
    assert second_dir.exists()


@pytest.mark.unit
def test_print_level_filter_passes_low_print_level() -> None:
    filter_ = PrintLevelFilter(print_level=3)
    import logging

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.print_level = 2  # type: ignore[attr-defined]
    assert filter_.filter(record) is True


@pytest.mark.unit
def test_print_level_filter_blocks_high_print_level() -> None:
    filter_ = PrintLevelFilter(print_level=2)
    import logging

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.print_level = 5  # type: ignore[attr-defined]
    assert filter_.filter(record) is False


@pytest.mark.unit
def test_decorator_provide_time_information_2_logs_start_finish(tmp_path: Path) -> None:
    logger = CustomLogger("deco-test", tmp_path, print_level=5, auto_parse=False)

    @decorator_provide_time_information_2(print_level=5, backup_logger=logger)
    def sample_function(x: int) -> int:
        return x * 2

    result = sample_function(21)
    assert result == 42

    log_text = logger.log_file_path.read_text(encoding="utf-8")
    assert "Starting" in log_text
    assert "Finished" in log_text


@pytest.mark.unit
def test_parse_log_file_returns_empty_dataframe_for_malformed_file(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "bad.log"
    log_path.write_text("not a valid log line\n", encoding="utf-8")

    parsed_frame = parse_log_file(log_path)

    assert len(parsed_frame) == 0
