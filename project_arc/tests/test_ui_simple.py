"""Simple UI-adjacent integration tests.

These tests validate the `src.ui` bootstrap path and ensure the default
file-backed runtime service can be exercised safely via a temp database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from tkinter import messagebox

import src.ui as ui_module
from src.ui import build_default_service


def test_build_default_service_initializes_required_tables(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "arc_ui_simple.db"
    monkeypatch.setenv("ARC_DB_PATH", str(db_path))

    service = build_default_service()
    connection = service.db_manager.connection

    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    table_names = {row[0] for row in rows}

    assert "employees" in table_names
    assert "call_outs" in table_names

    connection.close()


def test_build_default_service_supports_employee_lookup_flow(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "arc_lookup_flow.db"
    monkeypatch.setenv("ARC_DB_PATH", str(db_path))

    service = build_default_service()

    service.add_employee(4501, "Jamie", "Fox")
    result = service.lookup_employee(4501)

    assert result["employee"]["employee_id"] == 4501
    assert result["history"] == "NONE"

    service.db_manager.connection.close()


def test_build_default_service_supports_call_out_persistence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "arc_callout_flow.db"
    monkeypatch.setenv("ARC_DB_PATH", str(db_path))

    service = build_default_service()

    service.add_employee(4601, "Taylor", "Mills")
    service.log_call_out(4601, recorded_by="Mgr77", notes="Shift conflict")

    conn: sqlite3.Connection = service.db_manager.connection
    row = conn.execute(
        """
        SELECT recorded_by, notes
        FROM call_outs
        WHERE employee_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (4601,),
    ).fetchone()

    assert row is not None
    assert row[0] == "Mgr77"
    assert row[1] == "Shift conflict"

    conn.close()


def test_run_ui_handles_filesystem_error_during_startup(
    monkeypatch,
    tmp_path: Path,
) -> None:
    errors: list[tuple[str, str]] = []
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(
        ui_module,
        "build_default_service",
        lambda: (_ for _ in ()).throw(OSError("access denied")),
    )
    monkeypatch.setattr(messagebox, "showerror", lambda title, msg: errors.append((title, msg)))

    ui_module.run_ui()

    assert errors
    assert errors[-1][0] == "Startup Error"
