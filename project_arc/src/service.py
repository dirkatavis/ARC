"""Business logic layer for ARC.

The implementation is intentionally deferred so tests define behavior first.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

from src.database import DatabaseManager
from src.points_config import PointsConfig

if TYPE_CHECKING:
    from src.entitlement import EntitlementEngine


class DuplicateEmployeeError(Exception):
    """Raised when an employee_id already exists."""


class DatabaseAccessError(Exception):
    """Raised when the backing SQLite database is unavailable."""


class TrialExpiredError(Exception):
    """Raised when a write operation is attempted after the trial period has ended."""


class AttendanceService:
    """Coordinates ARC business rules between UI and database layers."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        entitlement: EntitlementEngine | None = None,
        points_config: PointsConfig | None = None,
    ) -> None:
        self.db_manager = db_manager
        self.entitlement = entitlement
        self.points_config = points_config or PointsConfig()

    def synchronize_points_from_history(self) -> None:
        """Recalculate points from history when writes are allowed."""
        if self.entitlement is not None:
            from src.entitlement import EntitlementState  # noqa: PLC0415

            if self.entitlement.get_state() == EntitlementState.EXPIRED:
                return

        self.db_manager.recalculate_all_employee_points(self.points_config.callouts_per_point)

    def _assert_write_allowed(self) -> None:
        """Raise TrialExpiredError if the entitlement state blocks writes."""
        if self.entitlement is None:
            return
        from src.entitlement import EntitlementState  # noqa: PLC0415

        state = self.entitlement.get_state()
        if state == EntitlementState.EXPIRED:
            raise TrialExpiredError(
                "The trial period has expired. Please activate a license to continue."
            )

    def add_employee(self, employee_id: int, first_name: str, last_name: str) -> None:
        """Create an employee record after business validation."""
        self._assert_write_allowed()
        try:
            self.db_manager.insert_employee(employee_id, first_name, last_name)
        except sqlite3.IntegrityError as exc:
            raise DuplicateEmployeeError(f"Employee ID {employee_id} already exists") from exc
        except sqlite3.DatabaseError as exc:
            raise DatabaseAccessError("Database is unavailable for employee updates.") from exc

    def lookup_employee(self, employee_id: int) -> dict[str, Any]:
        """Return employee data and call-out history or explicit NONE state."""
        try:
            employee = self.db_manager.fetch_employee(employee_id)
            history = self.db_manager.fetch_call_out_history(employee_id)
        except sqlite3.DatabaseError as exc:
            raise DatabaseAccessError("Database is unavailable for employee lookup.") from exc

        if employee is None:
            raise ValueError(f"Employee ID {employee_id} not found")

        return {
            "employee": employee,
            "history": history if history else "NONE",
        }

    def search_employees(self, query: str) -> list[dict[str, Any]]:
        """Search employees by ID, first name, or last name."""
        try:
            return self.db_manager.search_employees(query)
        except sqlite3.DatabaseError as exc:
            raise DatabaseAccessError("Database is unavailable for employee search.") from exc

    def log_call_out(
        self,
        employee_id: int,
        recorded_by: str,
        notes: str,
        timestamp: str | None = None,
    ) -> int:
        """Log a call-out event and return inserted call-out id."""
        self._assert_write_allowed()
        if not recorded_by or not recorded_by.strip():
            raise ValueError("recorded_by is required")

        try:
            return self.db_manager.log_call_out_with_points(
                employee_id=employee_id,
                recorded_by=recorded_by.strip(),
                notes=notes,
                callouts_per_point=self.points_config.callouts_per_point,
                timestamp=timestamp,
            )
        except sqlite3.DatabaseError as exc:
            raise DatabaseAccessError("Database is unavailable for call-out logging.") from exc

    def get_employee_points_report(
        self,
        sort_by: str = "employee_name",
        sort_desc: bool = False,
        name_filter: str = "",
    ) -> list[dict[str, Any]]:
        """Return employee points report rows for reporting UI."""
        try:
            return self.db_manager.fetch_employee_points_report(
                sort_by=sort_by,
                sort_desc=sort_desc,
                name_filter=name_filter,
            )
        except sqlite3.DatabaseError as exc:
            raise DatabaseAccessError("Database is unavailable for reporting.") from exc

    def get_point_award_history(self, employee_id: int) -> list[dict[str, Any]]:
        """Return point award history rows for an employee."""
        try:
            return self.db_manager.fetch_point_award_history(employee_id)
        except sqlite3.DatabaseError as exc:
            raise DatabaseAccessError("Database is unavailable for reporting.") from exc

    def get_top_10_high_frequency(self) -> list[dict[str, Any]]:
        """Return top 10 high-frequency call-out report rows."""
        try:
            return self.db_manager.fetch_top_10_high_frequency()
        except sqlite3.DatabaseError as exc:
            raise DatabaseAccessError("Database is unavailable for reporting.") from exc
