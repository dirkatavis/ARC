"""Optional Windows UI smoke test using pywinauto.

Run manually on Windows with:
RUN_UI_E2E=1 pytest -q tests/test_ui_smoke.py
"""

# pylint: disable=import-error,unused-variable

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name != "nt", reason="Windows-only UI automation")
def test_verification_modal_smoke_flow(tmp_path: Path) -> None:
    if os.getenv("RUN_UI_E2E") != "1":
        pytest.skip("Set RUN_UI_E2E=1 to run desktop automation tests")

    application_module = pytest.importorskip("pywinauto.application")
    Application = application_module.Application

    db_path = tmp_path / "arc_ui_smoke.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL
        );

        CREATE TABLE call_outs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            recorded_by TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        );

        INSERT INTO employees (employee_id, first_name, last_name)
        VALUES (1001, 'Ari', 'Cole');
        """
    )
    connection.commit()
    connection.close()

    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["ARC_DB_PATH"] = str(db_path)

    process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=project_root,
        env=env,
    )

    try:
        app = Application(backend="uia").connect(title_re="ARC - Attendance Recording Center", timeout=20)
        window = app.window(title_re="ARC - Attendance Recording Center")
        window.wait("ready", timeout=20)

        edit_controls = window.descendants(control_type="Edit")
        assert edit_controls, "Expected edit controls in main window"
        edit_controls[0].type_keys("1001")

        window.child_window(title="Search", control_type="Button").click_input()
        time.sleep(0.6)

        edit_controls = window.descendants(control_type="Edit")
        assert len(edit_controls) >= 2, "Expected Recorded By edit control"
        edit_controls[1].type_keys("ManagerX")

        checkbox = window.child_window(title="Log Call-Out", control_type="CheckBox")
        checkbox.click_input()

        window.child_window(title="Save (Verification Required)", control_type="Button").click_input()

        verify = app.window(title="Verify Call-Out")
        verify.wait("visible", timeout=10)
        assert verify.exists(), "Verification modal should be shown before save"

        verify.child_window(title="Cancel", control_type="Button").click_input()
    finally:
        process.terminate()
        process.wait(timeout=10)
