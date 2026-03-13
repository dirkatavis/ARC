"""Database layer for ARC.

This module defines the SQLite boundary. Implementations are intentionally
pending while TDD tests drive behavior.
"""

from __future__ import annotations

import sqlite3
from typing import Any


class DatabaseManager:
    """Wraps SQLite operations for employees and call-out data."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        connection.row_factory = sqlite3.Row
        self.connection = connection

    def initialize_schema(self) -> None:
        """Create required ARC tables when absent."""
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                employee_id INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS call_outs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                recorded_by TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
            );

            CREATE INDEX IF NOT EXISTS idx_call_outs_employee_id
            ON call_outs(employee_id);
            """
        )
        self.connection.commit()

    def insert_employee(self, employee_id: int, first_name: str, last_name: str) -> None:
        """Insert a new employee record."""
        self.connection.execute(
            "INSERT INTO employees (employee_id, first_name, last_name) VALUES (?, ?, ?)",
            (employee_id, first_name, last_name),
        )
        self.connection.commit()

    def upsert_employee(
        self,
        employee_id: int,
        first_name: str,
        last_name: str,
        commit: bool = True,
    ) -> None:
        """Insert or update an employee by employee_id."""
        self.connection.execute(
            """
            INSERT INTO employees (employee_id, first_name, last_name)
            VALUES (?, ?, ?)
            ON CONFLICT(employee_id) DO UPDATE SET
                first_name = excluded.first_name,
                last_name = excluded.last_name
            """,
            (employee_id, first_name, last_name),
        )
        if commit:
            self.connection.commit()

    def fetch_employee(self, employee_id: int) -> dict[str, Any] | None:
        """Return employee data for a specific employee id."""
        row = self.connection.execute(
            "SELECT employee_id, first_name, last_name FROM employees WHERE employee_id = ?",
            (employee_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def search_employees(self, query: str) -> list[dict[str, Any]]:
        """Return employees matching ID, first name, or last name."""
        q = query.strip()
        if not q:
            return []

        if q.isdigit():
            rows = self.connection.execute(
                """
                SELECT employee_id, first_name, last_name
                FROM employees
                WHERE employee_id = ?
                ORDER BY employee_id ASC
                """,
                (int(q),),
            ).fetchall()
            return [dict(row) for row in rows]

        like_pattern = f"%{q.lower()}%"
        rows = self.connection.execute(
            """
            SELECT employee_id, first_name, last_name
            FROM employees
            WHERE lower(first_name) LIKE ? OR lower(last_name) LIKE ?
            ORDER BY last_name ASC, first_name ASC, employee_id ASC
            """,
            (like_pattern, like_pattern),
        ).fetchall()
        return [dict(row) for row in rows]

    def insert_call_out(
        self,
        employee_id: int,
        recorded_by: str,
        notes: str,
        timestamp: str | None = None,
    ) -> int:
        """Insert a call-out record and return the inserted row id."""
        if timestamp is None:
            cursor = self.connection.execute(
                """
                INSERT INTO call_outs (employee_id, timestamp, recorded_by, notes)
                VALUES (?, DATETIME('now', 'localtime'), ?, ?)
                """,
                (employee_id, recorded_by, notes),
            )
        else:
            cursor = self.connection.execute(
                """
                INSERT INTO call_outs (employee_id, timestamp, recorded_by, notes)
                VALUES (?, ?, ?, ?)
                """,
                (employee_id, timestamp, recorded_by, notes),
            )
        self.connection.commit()
        return int(cursor.lastrowid)

    def fetch_call_out_history(self, employee_id: int) -> list[dict[str, Any]]:
        """Return call-out history for an employee."""
        rows = self.connection.execute(
            """
            SELECT id, employee_id, timestamp, recorded_by, notes
            FROM call_outs
            WHERE employee_id = ?
            ORDER BY timestamp DESC, id DESC
            """,
            (employee_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def fetch_top_10_high_frequency(self) -> list[dict[str, Any]]:
        """Return top 10 employees by call-out volume."""
        rows = self.connection.execute(
            """
            SELECT
                e.employee_id,
                e.first_name,
                e.last_name,
                COUNT(c.id) AS call_out_count
            FROM employees AS e
            JOIN call_outs AS c ON c.employee_id = e.employee_id
            GROUP BY e.employee_id, e.first_name, e.last_name
            ORDER BY call_out_count DESC, e.employee_id ASC
            LIMIT 10
            """
        ).fetchall()
        return [dict(row) for row in rows]
