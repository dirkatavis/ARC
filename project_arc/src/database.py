"""Database layer for ARC.

This module defines the SQLite boundary. Implementations are intentionally
pending while TDD tests drive behavior.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from src.points_engine import build_incremental_award_events, calculate_points


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
                last_name TEXT NOT NULL,
                total_callouts INTEGER NOT NULL DEFAULT 0,
                total_points INTEGER NOT NULL DEFAULT 0,
                points_last_updated TEXT
            );

            CREATE TABLE IF NOT EXISTS call_outs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                recorded_by TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
            );

            CREATE TABLE IF NOT EXISTS points_awards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                awarded_point_number INTEGER NOT NULL,
                callout_count_at_award INTEGER NOT NULL,
                awarded_at TEXT NOT NULL,
                FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
                UNIQUE (employee_id, awarded_point_number)
            );

            CREATE INDEX IF NOT EXISTS idx_call_outs_employee_id
            ON call_outs(employee_id);
            """
        )

        if not self._column_exists("employees", "total_callouts"):
            self.connection.execute(
                "ALTER TABLE employees ADD COLUMN total_callouts INTEGER NOT NULL DEFAULT 0"
            )
        if not self._column_exists("employees", "total_points"):
            self.connection.execute(
                "ALTER TABLE employees ADD COLUMN total_points INTEGER NOT NULL DEFAULT 0"
            )
        if not self._column_exists("employees", "points_last_updated"):
            self.connection.execute(
                "ALTER TABLE employees ADD COLUMN points_last_updated TEXT"
            )

        self.connection.commit()

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        rows = self.connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return any(str(row[1]).lower() == column_name.lower() for row in rows)

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
            """
            SELECT employee_id, first_name, last_name, total_callouts, total_points, points_last_updated
            FROM employees
            WHERE employee_id = ?
            """,
            (employee_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def log_call_out_with_points(
        self,
        employee_id: int,
        recorded_by: str,
        notes: str,
        callouts_per_point: int,
        timestamp: str | None = None,
    ) -> int:
        """Insert call-out, update totals, and persist award history."""
        employee_row = self.connection.execute(
            """
            SELECT total_callouts, total_points
            FROM employees
            WHERE employee_id = ?
            """,
            (employee_id,),
        ).fetchone()
        current_callouts = int(employee_row["total_callouts"]) if employee_row is not None else 0
        current_points = int(employee_row["total_points"]) if employee_row is not None else 0

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

        call_out_id = int(cursor.lastrowid)
        row = self.connection.execute(
            "SELECT timestamp FROM call_outs WHERE id = ?",
            (call_out_id,),
        ).fetchone()
        awarded_at = str(row["timestamp"]) if row else ""

        new_total_callouts = current_callouts + 1
        new_total_points = calculate_points(new_total_callouts, callouts_per_point)

        self.connection.execute(
            """
            UPDATE employees
            SET total_callouts = ?, total_points = ?, points_last_updated = ?
            WHERE employee_id = ?
            """,
            (new_total_callouts, new_total_points, awarded_at, employee_id),
        )

        events = build_incremental_award_events(
            previous_total_points=current_points,
            new_total_points=new_total_points,
            callouts_per_point=callouts_per_point,
            awarded_at=awarded_at,
        )
        for event in events:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO points_awards
                (employee_id, awarded_point_number, callout_count_at_award, awarded_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    employee_id,
                    event.awarded_point_number,
                    event.callout_count_at_award,
                    event.awarded_at,
                ),
            )

        self.connection.commit()
        return call_out_id

    def recalculate_all_employee_points(self, callouts_per_point: int) -> None:
        """Recalculate totals and rebuild award history for all employees."""
        employee_rows = self.connection.execute(
            "SELECT employee_id FROM employees ORDER BY employee_id"
        ).fetchall()

        for employee_row in employee_rows:
            employee_id = int(employee_row["employee_id"])
            summary_row = self.connection.execute(
                """
                SELECT COUNT(*) AS total_callouts, MAX(timestamp) AS last_updated
                FROM call_outs
                WHERE employee_id = ?
                """,
                (employee_id,),
            ).fetchone()

            total_callouts = int(summary_row["total_callouts"]) if summary_row is not None else 0
            total_points = calculate_points(total_callouts, callouts_per_point)
            last_updated = (
                str(summary_row["last_updated"])
                if summary_row is not None and summary_row["last_updated"] is not None
                else None
            )

            self.connection.execute(
                """
                UPDATE employees
                SET total_callouts = ?, total_points = ?, points_last_updated = ?
                WHERE employee_id = ?
                """,
                (total_callouts, total_points, last_updated, employee_id),
            )

            self.connection.execute(
                "DELETE FROM points_awards WHERE employee_id = ?",
                (employee_id,),
            )

            for point_number in range(1, total_points + 1):
                threshold_callouts = point_number * callouts_per_point
                award_row = self.connection.execute(
                    """
                    SELECT timestamp
                    FROM call_outs
                    WHERE employee_id = ?
                    ORDER BY timestamp ASC, id ASC
                    LIMIT 1 OFFSET ?
                    """,
                    (employee_id, threshold_callouts - 1),
                ).fetchone()
                if award_row is None:
                    continue
                award_timestamp = str(award_row["timestamp"])
                self.connection.execute(
                    """
                    INSERT INTO points_awards
                    (employee_id, awarded_point_number, callout_count_at_award, awarded_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (employee_id, point_number, threshold_callouts, award_timestamp),
                )

        self.connection.commit()

    def fetch_employee_points_report(
        self,
        sort_by: str = "employee_name",
        sort_desc: bool = False,
        name_filter: str = "",
    ) -> list[dict[str, Any]]:
        """Return all employees with callout/points summary for reporting."""
        sort_map = {
            "employee_name": "employee_name",
            "employee_id": "e.employee_id",
            "total_callouts": "e.total_callouts",
            "points_earned": "e.total_points",
            "last_updated": "e.points_last_updated",
        }
        sort_column = sort_map.get(sort_by, "employee_name")
        sort_direction = "DESC" if sort_desc else "ASC"

        normalized_filter = f"%{name_filter.strip().lower()}%"
        rows = self.connection.execute(
            f"""
            SELECT
                e.employee_id,
                e.first_name,
                e.last_name,
                (e.first_name || ' ' || e.last_name) AS employee_name,
                e.total_callouts,
                e.total_points AS points_earned,
                e.points_last_updated AS last_updated
            FROM employees e
            WHERE ? = '%%' OR lower(e.first_name || ' ' || e.last_name) LIKE ?
            ORDER BY {sort_column} {sort_direction}, e.employee_id ASC
            """,
            (normalized_filter, normalized_filter),
        ).fetchall()
        return [dict(row) for row in rows]

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

    def fetch_point_award_history(self, employee_id: int) -> list[dict[str, Any]]:
        """Return point award history for an employee."""
        rows = self.connection.execute(
            """
            SELECT id, employee_id, awarded_point_number, callout_count_at_award, awarded_at
            FROM points_awards
            WHERE employee_id = ?
            ORDER BY awarded_point_number ASC
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
