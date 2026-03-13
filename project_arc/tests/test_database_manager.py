"""Focused tests for DatabaseManager infrastructure behavior."""

from __future__ import annotations

import sqlite3

from src.database import DatabaseManager


def test_database_manager_enforces_row_factory() -> None:
    connection = sqlite3.connect(":memory:")
    assert connection.row_factory is None

    db = DatabaseManager(connection)
    assert connection.row_factory == sqlite3.Row

    db.initialize_schema()
    db.insert_employee(1001, "Ari", "Cole")
    employee = db.fetch_employee(1001)

    assert employee is not None
    assert employee["first_name"] == "Ari"
    connection.close()


def test_initialize_schema_creates_callouts_employee_index() -> None:
    connection = sqlite3.connect(":memory:")
    db = DatabaseManager(connection)

    db.initialize_schema()

    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_call_outs_employee_id'"
    ).fetchone()
    assert row is not None
    connection.close()


def test_upsert_employee_can_defer_commit() -> None:
    connection = sqlite3.connect(":memory:")
    db = DatabaseManager(connection)
    db.initialize_schema()

    db.upsert_employee(2001, "Alex", "Stone", commit=False)
    row = connection.execute(
        "SELECT first_name, last_name FROM employees WHERE employee_id = 2001"
    ).fetchone()
    assert row is not None
    assert row["first_name"] == "Alex"
    assert row["last_name"] == "Stone"

    connection.commit()
    row_after_commit = connection.execute(
        "SELECT first_name, last_name FROM employees WHERE employee_id = 2001"
    ).fetchone()
    assert row_after_commit is not None
    connection.close()
