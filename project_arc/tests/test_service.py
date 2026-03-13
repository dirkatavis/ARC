"""TDD contract tests for ARC AttendanceService.

All tests use in-memory SQLite fixtures to guarantee isolated execution.
"""

# pylint: disable=redefined-outer-name,missing-function-docstring,missing-class-docstring,too-few-public-methods

from __future__ import annotations

from datetime import date, datetime, timedelta
import sqlite3
from typing import Any

import pytest

from src.database import DatabaseManager
from src.service import AttendanceService, DatabaseAccessError, DuplicateEmployeeError, TrialExpiredError

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


@pytest.fixture
def arc_context() -> dict[str, Any]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_SQL)

    db_manager = DatabaseManager(connection)
    service = AttendanceService(db_manager)

    yield {
        "connection": connection,
        "db_manager": db_manager,
        "service": service,
    }

    connection.close()


def seed_employee(connection: sqlite3.Connection, employee_id: int, first_name: str, last_name: str) -> None:
    connection.execute(
        "INSERT INTO employees (employee_id, first_name, last_name) VALUES (?, ?, ?)",
        (employee_id, first_name, last_name),
    )
    connection.commit()


def seed_call_out(
    connection: sqlite3.Connection,
    employee_id: int,
    recorded_by: str,
    notes: str,
    timestamp: str,
) -> None:
    connection.execute(
        """
        INSERT INTO call_outs (employee_id, timestamp, recorded_by, notes)
        VALUES (?, ?, ?, ?)
        """,
        (employee_id, timestamp, recorded_by, notes),
    )
    connection.commit()


def test_successful_employee_lookup_returns_history(arc_context: dict[str, Any]) -> None:
    connection = arc_context["connection"]
    service: AttendanceService = arc_context["service"]

    seed_employee(connection, 1001, "Ari", "Cole")
    seed_call_out(connection, 1001, "MgrA", "Flu", "2026-03-01 08:00:00")
    seed_call_out(connection, 1001, "MgrB", "Family emergency", "2026-03-05 09:30:00")

    result = service.lookup_employee(1001)

    assert result["employee"]["employee_id"] == 1001
    assert result["employee"]["first_name"] == "Ari"
    assert isinstance(result["history"], list)
    assert len(result["history"]) == 2
    assert result["history"][0]["recorded_by"] == "MgrB"
    assert result["history"][1]["notes"] == "Flu"


def test_lookup_returns_none_state_for_new_employee(arc_context: dict[str, Any]) -> None:
    connection = arc_context["connection"]
    service: AttendanceService = arc_context["service"]

    seed_employee(connection, 1002, "Nia", "Bishop")

    result = service.lookup_employee(1002)

    assert result["employee"]["employee_id"] == 1002
    assert result["history"] == "NONE"


def test_search_employees_by_id(arc_context: dict[str, Any]) -> None:
    connection = arc_context["connection"]
    service: AttendanceService = arc_context["service"]

    seed_employee(connection, 1101, "Mina", "Park")

    matches = service.search_employees("1101")

    assert len(matches) == 1
    assert matches[0]["employee_id"] == 1101


def test_search_employees_by_first_name(arc_context: dict[str, Any]) -> None:
    connection = arc_context["connection"]
    service: AttendanceService = arc_context["service"]

    seed_employee(connection, 1201, "Jordan", "Miles")
    seed_employee(connection, 1202, "Jori", "Stone")

    matches = service.search_employees("jOr")
    matched_ids = {row["employee_id"] for row in matches}

    assert matched_ids == {1201, 1202}


def test_search_employees_by_last_name(arc_context: dict[str, Any]) -> None:
    connection = arc_context["connection"]
    service: AttendanceService = arc_context["service"]

    seed_employee(connection, 1301, "Sam", "Howard")
    seed_employee(connection, 1302, "Ari", "Cole")

    matches = service.search_employees("how")

    assert len(matches) == 1
    assert matches[0]["employee_id"] == 1301


def test_duplicate_employee_id_is_prevented(arc_context: dict[str, Any]) -> None:
    service: AttendanceService = arc_context["service"]

    service.add_employee(2001, "Ada", "Lovelace")

    with pytest.raises(DuplicateEmployeeError):
        service.add_employee(2001, "Ada", "Lovelace")


def test_top_10_high_frequency_report_sorts_and_limits(arc_context: dict[str, Any]) -> None:
    connection = arc_context["connection"]
    service: AttendanceService = arc_context["service"]

    base_employee_id = 1000
    for frequency in range(1, 16):
        employee_id = base_employee_id + frequency
        seed_employee(connection, employee_id, f"First{frequency}", f"Last{frequency}")
        for occurrence in range(frequency):
            day = (occurrence % 28) + 1
            seed_call_out(
                connection,
                employee_id,
                f"Mgr{frequency}",
                f"Call-out {occurrence + 1}",
                f"2026-02-{day:02d} 07:00:00",
            )

    report = service.get_top_10_high_frequency()

    assert len(report) == 10
    counts = [row["call_out_count"] for row in report]
    assert counts == sorted(counts, reverse=True)
    employee_ids = [row["employee_id"] for row in report]
    assert employee_ids == [1015, 1014, 1013, 1012, 1011, 1010, 1009, 1008, 1007, 1006]


def test_log_call_out_persists_recorded_by_and_notes(arc_context: dict[str, Any]) -> None:
    connection = arc_context["connection"]
    service: AttendanceService = arc_context["service"]

    seed_employee(connection, 3001, "Jordan", "Miles")

    service.log_call_out(3001, recorded_by="ManagerX", notes="Vehicle issue")

    row = connection.execute(
        """
        SELECT recorded_by, notes
        FROM call_outs
        WHERE employee_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (3001,),
    ).fetchone()

    assert row is not None
    assert row["recorded_by"] == "ManagerX"
    assert row["notes"] == "Vehicle issue"


def test_log_call_out_honors_explicit_timestamp(arc_context: dict[str, Any]) -> None:
    connection = arc_context["connection"]
    service: AttendanceService = arc_context["service"]

    seed_employee(connection, 3002, "Riley", "Hart")
    expected_timestamp = "2026-03-09 06:45:00"

    service.log_call_out(
        3002,
        recorded_by="ManagerY",
        notes="Weather delay",
        timestamp=expected_timestamp,
    )

    row = connection.execute(
        """
        SELECT timestamp
        FROM call_outs
        WHERE employee_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (3002,),
    ).fetchone()

    assert row is not None
    assert row["timestamp"] == expected_timestamp


def test_log_call_out_uses_local_time_when_timestamp_not_provided(
    arc_context: dict[str, Any],
) -> None:
    connection = arc_context["connection"]
    service: AttendanceService = arc_context["service"]

    seed_employee(connection, 3003, "Casey", "Lane")
    before = datetime.now()
    service.log_call_out(3003, recorded_by="ManagerQ", notes="Family care")
    after = datetime.now()

    row = connection.execute(
        """
        SELECT timestamp
        FROM call_outs
        WHERE employee_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (3003,),
    ).fetchone()

    assert row is not None
    logged_at = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
    assert (before - timedelta(seconds=1)) <= logged_at <= (after + timedelta(seconds=1))


def test_log_call_out_raises_database_access_error_on_sqlite_failure(arc_context: dict[str, Any]) -> None:
    service: AttendanceService = arc_context["service"]

    class FailingDb:
        def log_call_out_with_points(self, **_kwargs: Any) -> int:
            raise sqlite3.OperationalError("database is locked")

    service.db_manager = FailingDb()  # type: ignore[assignment]

    with pytest.raises(DatabaseAccessError, match="unavailable"):
        service.log_call_out(1001, recorded_by="ManagerZ", notes="test")


# ── Entitlement-aware write protection ─────────────────────────────────────


def _make_expired_service(connection: sqlite3.Connection) -> AttendanceService:
    """Build an AttendanceService wired to an expired entitlement engine."""
    from src.entitlement import TRIAL_DAYS, EntitlementEngine

    entitlement = EntitlementEngine(connection, machine_id="TRIAL-MACHINE-TEST")
    past_date = (date.today() - timedelta(days=TRIAL_DAYS + 1)).isoformat()
    connection.execute(
        "UPDATE sys_entitlement SET install_date = ? WHERE id = 1",
        (past_date,),
    )
    connection.commit()

    db_manager = DatabaseManager(connection)
    return AttendanceService(db_manager, entitlement=entitlement)


def test_expired_trial_blocks_add_employee() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)

    service = _make_expired_service(conn)
    with pytest.raises(TrialExpiredError):
        service.add_employee(9001, "Blocked", "User")

    conn.close()


def test_expired_trial_blocks_log_call_out() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)

    service = _make_expired_service(conn)
    with pytest.raises(TrialExpiredError):
        service.log_call_out(9001, recorded_by="ManagerX", notes="blocked")

    conn.close()


def test_expired_trial_still_allows_reads() -> None:
    """Read-only operations must succeed even when the trial is expired."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)

    # Insert an employee directly so lookup is possible without going through service writes.
    conn.execute("INSERT INTO employees (employee_id, first_name, last_name) VALUES (9002, 'Read', 'Only')")
    conn.commit()

    service = _make_expired_service(conn)

    # search and top-10 must not raise
    result = service.search_employees("Read")
    assert len(result) == 1

    top10 = service.get_top_10_high_frequency()
    assert isinstance(top10, list)

    conn.close()


def test_no_entitlement_engine_allows_all_writes(arc_context: dict[str, Any]) -> None:
    """AttendanceService without an entitlement engine must behave as before."""
    service: AttendanceService = arc_context["service"]
    assert service.entitlement is None

    # Must not raise – backward-compatible with existing test infrastructure.
    service.add_employee(8001, "Free", "Write")
    service.log_call_out(8001, recorded_by="AnyMgr", notes="no entitlement guard")
