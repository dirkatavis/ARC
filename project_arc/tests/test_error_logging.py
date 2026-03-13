"""Regression tests for runtime error logging utilities."""

from __future__ import annotations

from pathlib import Path

from src.error_logging import append_error_log


def test_append_error_log_uses_provided_exception_traceback(tmp_path: Path) -> None:
    log_path = tmp_path / "arc_error.log"

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        append_error_log(log_path, "unit-test", exc)

    text = log_path.read_text(encoding="utf-8")

    assert "unit-test" in text
    assert "RuntimeError: boom" in text
    assert "Traceback" in text
