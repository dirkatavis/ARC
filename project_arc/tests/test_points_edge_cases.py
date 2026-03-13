"""Edge and boundary tests for ARC points system."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from src.database import DatabaseManager
from src.points_config import DEFAULT_CALLOUTS_PER_POINT, load_points_config
from src.points_engine import PointsConfigError, calculate_points
from src.service import AttendanceService


SCHEMA_SQL = """
CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    total_callouts INTEGER NOT NULL DEFAULT 0,
    total_points INTEGER NOT NULL DEFAULT 0,
    points_last_updated TEXT
);

CREATE TABLE call_outs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recorded_by TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

CREATE TABLE points_awards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    awarded_point_number INTEGER NOT NULL,
    callout_count_at_award INTEGER NOT NULL,
    awarded_at TEXT NOT NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    UNIQUE (employee_id, awarded_point_number)
);
"""


def _build_service() -> tuple[sqlite3.Connection, AttendanceService]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_SQL)

    db = DatabaseManager(connection)
    service = AttendanceService(db)
    return connection, service


def test_n_equals_one_awards_point_per_callout() -> None:
    assert calculate_points(total_callouts=1, callouts_per_point=1) == 1
    assert calculate_points(total_callouts=5, callouts_per_point=1) == 5


def test_large_callout_count_calculates_correctly() -> None:
    assert calculate_points(total_callouts=10_000, callouts_per_point=3) == 3333


def test_employee_with_no_callout_history() -> None:
    connection, service = _build_service()
    service.add_employee(1010, "No", "History")

    payload = service.lookup_employee(1010)

    assert payload["history"] == "NONE"
    assert payload["employee"]["total_callouts"] == 0
    assert payload["employee"]["total_points"] == 0
    connection.close()


def test_invalid_ini_value_raises_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text("[PointsSystem]\ncallouts_per_point = 0\n", encoding="utf-8")

    with pytest.raises(PointsConfigError):
        load_points_config(config_path)


def test_missing_ini_section_falls_back_to_default(tmp_path: Path) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text("[General]\napp_name = ARC\n", encoding="utf-8")

    config = load_points_config(config_path)

    assert config.callouts_per_point == DEFAULT_CALLOUTS_PER_POINT
