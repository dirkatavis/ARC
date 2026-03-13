"""Integration tests for callout -> points -> persistence pipeline."""

from __future__ import annotations

import sqlite3

from src.database import DatabaseManager
from src.points_config import PointsConfig
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


def _build_service(callouts_per_point: int = 3) -> tuple[sqlite3.Connection, AttendanceService]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_SQL)

    db = DatabaseManager(connection)
    service = AttendanceService(db, points_config=PointsConfig(callouts_per_point=callouts_per_point))
    return connection, service


def test_callout_triggers_point_award_at_threshold() -> None:
    connection, service = _build_service(callouts_per_point=3)
    service.add_employee(1001, "Ari", "Cole")

    service.log_call_out(1001, "Mgr", "one")
    service.log_call_out(1001, "Mgr", "two")
    service.log_call_out(1001, "Mgr", "three")

    row = connection.execute(
        "SELECT total_callouts, total_points FROM employees WHERE employee_id = 1001"
    ).fetchone()
    assert row is not None
    assert row["total_callouts"] == 3
    assert row["total_points"] == 1

    awards = connection.execute(
        "SELECT awarded_point_number, callout_count_at_award FROM points_awards WHERE employee_id = 1001"
    ).fetchall()
    assert len(awards) == 1
    assert awards[0]["awarded_point_number"] == 1
    assert awards[0]["callout_count_at_award"] == 3

    connection.close()


def test_callout_below_threshold_does_not_award_point() -> None:
    connection, service = _build_service(callouts_per_point=3)
    service.add_employee(1002, "Nia", "Bishop")

    service.log_call_out(1002, "Mgr", "one")
    service.log_call_out(1002, "Mgr", "two")

    row = connection.execute(
        "SELECT total_callouts, total_points FROM employees WHERE employee_id = 1002"
    ).fetchone()
    assert row is not None
    assert row["total_callouts"] == 2
    assert row["total_points"] == 0

    awards = connection.execute("SELECT COUNT(*) FROM points_awards WHERE employee_id = 1002").fetchone()
    assert awards is not None
    assert awards[0] == 0

    connection.close()


def test_multiple_employees_tracked_independently() -> None:
    connection, service = _build_service(callouts_per_point=2)
    service.add_employee(1003, "Alex", "Green")
    service.add_employee(1004, "Alex", "Brown")

    service.log_call_out(1003, "Mgr", "one")
    service.log_call_out(1003, "Mgr", "two")
    service.log_call_out(1004, "Mgr", "one")

    row_a = connection.execute(
        "SELECT total_callouts, total_points FROM employees WHERE employee_id = 1003"
    ).fetchone()
    row_b = connection.execute(
        "SELECT total_callouts, total_points FROM employees WHERE employee_id = 1004"
    ).fetchone()

    assert row_a is not None and row_b is not None
    assert (row_a["total_callouts"], row_a["total_points"]) == (2, 1)
    assert (row_b["total_callouts"], row_b["total_points"]) == (1, 0)

    connection.close()


def test_points_persist_correctly_to_database() -> None:
    connection, service = _build_service(callouts_per_point=3)
    service.add_employee(1005, "Jordan", "Miles")

    for i in range(6):
        service.log_call_out(1005, "Mgr", f"callout-{i}")

    row = connection.execute(
        "SELECT total_callouts, total_points, points_last_updated FROM employees WHERE employee_id = 1005"
    ).fetchone()
    assert row is not None
    assert row["total_callouts"] == 6
    assert row["total_points"] == 2
    assert row["points_last_updated"] is not None

    awards = connection.execute(
        "SELECT awarded_point_number FROM points_awards WHERE employee_id = 1005 ORDER BY awarded_point_number"
    ).fetchall()
    assert [r["awarded_point_number"] for r in awards] == [1, 2]

    connection.close()


def test_reporting_screen_reflects_updated_points() -> None:
    connection, service = _build_service(callouts_per_point=3)
    service.add_employee(1006, "Riley", "Hart")
    for i in range(3):
        service.log_call_out(1006, "Mgr", f"callout-{i}")

    rows = service.get_employee_points_report(sort_by="employee_name")
    target = next(row for row in rows if row["employee_id"] == 1006)

    assert target["employee_name"] == "Riley Hart"
    assert target["total_callouts"] == 3
    assert target["points_earned"] == 1
    assert target["last_updated"] is not None

    connection.close()
