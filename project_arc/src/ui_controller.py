"""Testable UI decision/formatting logic for ARC desktop workflows."""

from __future__ import annotations


class UiController:
    """Pure helper logic used by the desktop UI layer."""

    @staticmethod
    def parse_employee_id(raw_value: str) -> int:
        value = raw_value.strip()
        if not value:
            raise ValueError("Employee ID is required.")
        if not value.isdigit():
            raise ValueError("Employee ID must be numeric.")
        return int(value)

    @staticmethod
    def can_enable_save(
        current_employee_id: int | None,
        recorded_by: str,
    ) -> bool:
        return current_employee_id is not None and bool(recorded_by.strip())

    @staticmethod
    def format_history(history: str | list[dict[str, object]]) -> str:
        if history == "NONE":
            return "NONE"

        lines: list[str] = []
        for row in history:
            timestamp = str(row.get("timestamp", ""))
            recorded_by = str(row.get("recorded_by", ""))
            notes = str(row.get("notes", "") or "")
            lines.append(f"{timestamp} | {recorded_by} | {notes}")
        return "\n".join(lines)

    @staticmethod
    def format_top_10(rows: list[dict[str, object]]) -> str:
        if not rows:
            return "No call-out data yet."

        lines = ["Rank | Employee ID | Name | Call-Out Count", "-" * 50]
        for idx, row in enumerate(rows, start=1):
            employee_id = int(row["employee_id"])
            first_name = str(row["first_name"])
            last_name = str(row["last_name"])
            count = int(row["call_out_count"])
            name = f"{first_name} {last_name}"
            lines.append(f"{idx:>4} | {employee_id:>11} | {name:<20} | {count:>3}")
        return "\n".join(lines)

    @staticmethod
    def build_verification_summary(
        employee_name: str,
        employee_id: int,
        recorded_by: str,
        notes: str,
    ) -> str:
        notes_value = notes.strip() or "(none)"
        return (
            "Please verify before commit:\n\n"
            f"Employee: {employee_name}\n"
            f"ID: {employee_id}\n"
            f"Recorded By: {recorded_by.strip()}\n"
            f"Notes: {notes_value}"
        )
