"""Business logic layer for ARC.

The implementation is intentionally deferred so tests define behavior first.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from src.database import DatabaseManager


class DuplicateEmployeeError(Exception):
    """Raised when an employee_id already exists."""


class AttendanceService:
    """Coordinates ARC business rules between UI and database layers."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def add_employee(self, employee_id: int, first_name: str, last_name: str) -> None:
        """Create an employee record after business validation."""
        try:
            self.db_manager.insert_employee(employee_id, first_name, last_name)
        except sqlite3.IntegrityError as exc:
            raise DuplicateEmployeeError(f"Employee ID {employee_id} already exists") from exc

    def lookup_employee(self, employee_id: int) -> dict[str, Any]:
        """Return employee data and call-out history or explicit NONE state."""
        employee = self.db_manager.fetch_employee(employee_id)
        if employee is None:
            raise ValueError(f"Employee ID {employee_id} not found")

        history = self.db_manager.fetch_call_out_history(employee_id)
        return {
            "employee": employee,
            "history": history if history else "NONE",
        }

    def log_call_out(
        self,
        employee_id: int,
        recorded_by: str,
        notes: str,
        timestamp: str | None = None,
    ) -> int:
        """Log a call-out event and return inserted call-out id."""
        if not recorded_by or not recorded_by.strip():
            raise ValueError("recorded_by is required")

        return self.db_manager.insert_call_out(
            employee_id=employee_id,
            recorded_by=recorded_by.strip(),
            notes=notes,
            timestamp=timestamp,
        )

    def get_top_10_high_frequency(self) -> list[dict[str, Any]]:
        """Return top 10 high-frequency call-out report rows."""
        return self.db_manager.fetch_top_10_high_frequency()
