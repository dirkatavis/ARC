"""Unit tests for pure UI controller logic."""

from __future__ import annotations

import pytest

from src.ui_controller import UiController


def test_parse_employee_id_accepts_numeric_input() -> None:
    assert UiController.parse_employee_id(" 1001 ") == 1001


def test_parse_employee_id_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="required"):
        UiController.parse_employee_id("   ")


def test_parse_employee_id_rejects_non_numeric_input() -> None:
    with pytest.raises(ValueError, match="numeric"):
        UiController.parse_employee_id("abc")


def test_can_enable_save_requires_employee_and_recorded_by() -> None:
    assert UiController.can_enable_save(1001, "mgr") is True
    assert UiController.can_enable_save(None, "mgr") is False
    assert UiController.can_enable_save(1001, "  ") is False


def test_format_history_supports_none_state() -> None:
    assert UiController.format_history("NONE") == "NONE"


def test_format_history_renders_rows() -> None:
    result = UiController.format_history(
        [
            {
                "timestamp": "2026-03-09 06:45:00",
                "recorded_by": "ManagerY",
                "notes": "Weather delay",
            }
        ]
    )
    assert "2026-03-09 06:45:00 | ManagerY | Weather delay" in result


def test_format_history_max_entries_limits_output() -> None:
    # rows in descending order (newest first) matching service return order
    rows = [
        {"timestamp": f"2026-01-{i:02d}", "recorded_by": f"Mgr{i:02d}", "notes": ""}
        for i in range(15, 0, -1)
    ]
    result = UiController.format_history(rows, max_entries=10)
    assert "Mgr15" in result    # newest entry present
    assert "| Mgr05 |" not in result  # oldest entries excluded
    assert "most recent" in result


def test_format_top_10_empty_message() -> None:
    assert UiController.format_top_10([]) == "No call-out data yet."


def test_format_top_10_renders_ranked_table() -> None:
    text = UiController.format_top_10(
        [
            {
                "employee_id": 1015,
                "first_name": "First15",
                "last_name": "Last15",
                "call_out_count": 15,
            },
            {
                "employee_id": 1014,
                "first_name": "First14",
                "last_name": "Last14",
                "call_out_count": 14,
            },
        ]
    )
    assert "Rank | Employee ID | Name | Call-Out Count" in text
    assert "1015" in text
    assert "First15 Last15" in text


def test_build_verification_summary_uses_fallback_for_empty_notes() -> None:
    summary = UiController.build_verification_summary(
        employee_name="Jordan Miles",
        employee_id=3001,
        recorded_by="ManagerX",
        notes="",
    )
    assert "Employee: Jordan Miles" in summary
    assert "ID: 3001" in summary
    assert "Recorded By: ManagerX" in summary
    assert "Notes: (none)" in summary
