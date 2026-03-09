"""Shared error logging utilities for ARC runtime failures."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import traceback


def append_error_log(log_path: Path, context: str, exc: Exception) -> None:
    """Append a structured error entry to the ARC error log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now().isoformat(timespec='seconds')}] {context}\n")
        handle.write(f"{type(exc).__name__}: {exc}\n")
        handle.write(traceback.format_exc())
        handle.write("\n")
