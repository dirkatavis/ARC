"""Seed ARC SQLite database with demo data for UI testing."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from project_arc.src.database import DatabaseManager


EMPLOYEES = [
    (1001, "Ari", "Cole"),
    (1002, "Nia", "Bishop"),
    (1003, "Jordan", "Miles"),
    (1004, "Riley", "Hart"),
    (1005, "Sam", "Howard"),
    (1006, "Taylor", "Mills"),
    (1007, "Mina", "Park"),
    (1008, "Chris", "Stone"),
    (1009, "Alex", "Rivera"),
    (1010, "Jamie", "Fox"),
    (1011, "Casey", "Lane"),
    (1012, "Drew", "King"),
    (1099, "Morgan", "Test"),
    (1100, "Ari", "Johnson"),
    (1101, "Ari", "Smith"),
    (1102, "Taylor", "Green"),
    (1103, "Jamie", "Smith"),
    (1104, "Noah", "Smith"),
    (1105, "Maya", "Rivera"),
]

CALL_OUT_PLAN = {
    1001: ["Flu symptoms", "Doctor follow-up", "Childcare issue"],
    1002: ["Weather delay"],
    1003: ["Vehicle issue", "Transit delay"],
    1004: ["Family emergency", "School closure", "Medical appointment", "Migraine"],
    1005: [],
    1006: ["Flu", "Flu", "Flu", "Flu", "Flu"],
    1007: ["Shift conflict", "Shift conflict"],
    1008: ["Unexpected overtime rest"],
    1009: ["Power outage", "Power outage", "Power outage"],
    1010: ["Car trouble", "Car trouble"],
    1011: ["Weather delay", "Weather delay", "Weather delay", "Weather delay"],
    1012: ["Family care"],
    1099: [
        "Sick leave", "Sick leave", "Sick leave", "Sick leave", "Sick leave",
        "Medical appointment", "Medical appointment", "Medical appointment",
        "Childcare issue", "Childcare issue", "Childcare issue", "Childcare issue",
        "Car trouble", "Car trouble", "Car trouble", "Car trouble", "Car trouble",
        "Family emergency", "Family emergency", "Family emergency",
        "Weather delay", "Weather delay", "Weather delay", "Weather delay", "Weather delay",
        "Personal day", "Personal day", "Personal day",
        "Appointment", "Appointment", "Appointment",
        "Transit delay", "Transit delay", "Transit delay",
        "School closure", "School closure",
        "Unexpected shift conflict", "Unexpected shift conflict",
        "Migraine", "Migraine", "Migraine",
        "Doctor follow-up", "Doctor follow-up",
        "Dental appointment", "Dental appointment",
        "Flu symptoms", "Flu symptoms",
        "Post-op follow-up",
    ],
}


def seed_database(db_path: Path, reset: bool) -> dict[str, int]:
    """Seed demo employees/call-outs and return seeding + total counts."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    db = DatabaseManager(connection)
    db.initialize_schema()

    if reset:
        connection.execute("DELETE FROM call_outs")
        connection.execute("DELETE FROM employees")
        connection.commit()

    inserted_employees = 0
    inserted_call_outs = 0

    for employee_id, first_name, last_name in EMPLOYEES:
        connection.execute(
            """
            INSERT INTO employees (employee_id, first_name, last_name)
            VALUES (?, ?, ?)
            ON CONFLICT(employee_id) DO UPDATE SET
                first_name = excluded.first_name,
                last_name = excluded.last_name
            """,
            (employee_id, first_name, last_name),
        )
        inserted_employees += 1

    day_counter = 1
    for employee_id, notes_list in CALL_OUT_PLAN.items():
        for note in notes_list:
            timestamp = f"2026-03-{day_counter:02d} 08:00:00"
            recorded_by = f"Mgr{(employee_id % 7) + 1}"
            connection.execute(
                """
                INSERT INTO call_outs (employee_id, timestamp, recorded_by, notes)
                VALUES (?, ?, ?, ?)
                """,
                (employee_id, timestamp, recorded_by, note),
            )
            inserted_call_outs += 1
            day_counter = 1 if day_counter >= 28 else day_counter + 1

    connection.commit()

    employee_count = connection.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    call_out_count = connection.execute("SELECT COUNT(*) FROM call_outs").fetchone()[0]
    connection.close()

    return {
        "seeded_employees": inserted_employees,
        "seeded_call_outs": inserted_call_outs,
        "total_employees": int(employee_count),
        "total_call_outs": int(call_out_count),
    }


def main() -> int:
    """Parse args and seed the specified ARC SQLite database."""
    parser = argparse.ArgumentParser(description="Seed ARC database with sample data")
    parser.add_argument("--db", required=True, help="Path to SQLite database file")
    parser.add_argument("--reset", action="store_true", help="Clear employees/call_outs before seeding")
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    result = seed_database(db_path=db_path, reset=args.reset)
    print(
        "Seed complete: "
        f"seeded_employees={result['seeded_employees']} "
        f"seeded_call_outs={result['seeded_call_outs']} "
        f"total_employees={result['total_employees']} "
        f"total_call_outs={result['total_call_outs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
