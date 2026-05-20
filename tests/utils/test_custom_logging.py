from __future__ import annotations

from pathlib import Path

from VmaxBuilder.utils.custom_logging import CustomLogger, parse_log_file


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


def test_custom_logger_accepts_path_log_directory(tmp_path: Path) -> None:
    log_directory = tmp_path / "logs"

    logger = CustomLogger("unit-test-logger", log_directory, auto_parse=False)

    assert logger.log_file_path.parent == log_directory
    assert logger.log_file_path.name == "unit-test-logger.log"
