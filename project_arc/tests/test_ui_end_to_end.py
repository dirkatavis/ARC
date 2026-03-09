"""ARC UI end-to-end contract tests.

These tests mirror the requested acceptance suite. Implemented behaviors are
fully asserted. Features not yet present in the UI are captured as explicit
xfail tests to keep forward progress visible in TDD.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import customtkinter as ctk
import pytest
from tkinter import messagebox

from src.database import DatabaseManager
from src.service import AttendanceService, DatabaseAccessError
from src.ui import ArcApp

pytestmark = [pytest.mark.ui_e2e]


@pytest.fixture
def ui_gate() -> None:
    """Gate desktop UI tests unless explicitly enabled by the user."""
    if os.getenv("RUN_UI_E2E") != "1":
        pytest.skip("Set RUN_UI_E2E=1 to run desktop UI end-to-end tests")


@pytest.fixture
def app_with_db(monkeypatch, tmp_path: Path):
    """Create app instance with isolated sqlite file and deterministic dialogs."""
    db_path = tmp_path / "arc_ui_e2e.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    db = DatabaseManager(connection)
    db.initialize_schema()

    service = AttendanceService(db)
    service.add_employee(1001, "Ari", "Cole")

    monkeypatch.setattr(messagebox, "showerror", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(messagebox, "askyesno", lambda *_args, **_kwargs: False)

    app = ArcApp(service)
    app.withdraw()
    app.update_idletasks()

    yield app, connection, service

    app.destroy()
    connection.close()


def _find_toplevels(app: ArcApp) -> list[ctk.CTkToplevel]:
    return [widget for widget in app.winfo_children() if isinstance(widget, ctk.CTkToplevel)]


def _find_button_by_text(parent, text: str):
    for widget in parent.winfo_children():
        if isinstance(widget, ctk.CTkButton) and widget.cget("text") == text:
            return widget
        found = _find_button_by_text(widget, text)
        if found is not None:
            return found
    return None


def _collect_label_text(parent) -> list[str]:
    texts: list[str] = []
    for widget in parent.winfo_children():
        if isinstance(widget, ctk.CTkLabel):
            texts.append(str(widget.cget("text")))
        texts.extend(_collect_label_text(widget))
    return texts


def test_empty_state_visuals_none_and_add_employee_button(ui_gate, app_with_db, monkeypatch) -> None:
    app, _connection, _service = app_with_db

    monkeypatch.setattr(messagebox, "askyesno", lambda *_args, **_kwargs: False)
    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()

    assert app.history_box._textbox.cget("state") == "disabled"

    # Contract item: reveal dedicated Add Employee button for new ID flow.
    pytest.xfail("Dedicated Add Employee button is not implemented in current UI")


def test_verification_modal_trigger_blocks_write_until_confirm(ui_gate, app_with_db) -> None:
    app, connection, _service = app_with_db

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()

    app.recorded_by_entry.insert(0, "ManagerA")
    app.notes_box.insert("1.0", "Flu")
    app.callout_var.set(True)
    app._update_save_button_state()

    before = connection.execute("SELECT COUNT(*) FROM call_outs").fetchone()[0]
    app._open_verification_modal()
    app.update_idletasks()
    after_open = connection.execute("SELECT COUNT(*) FROM call_outs").fetchone()[0]

    assert after_open == before
    modals = _find_toplevels(app)
    assert any(modal.title() == "Verify Call-Out" for modal in modals)


def test_cross_field_validation_save_button_state(ui_gate, app_with_db) -> None:
    app, _connection, _service = app_with_db

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()

    assert app.save_button.cget("state") == "normal"
    assert "Enter Recorded By" in app.save_hint_label.cget("text")

    app.recorded_by_entry.insert(0, "ManagerB")
    app._update_save_button_state()
    assert app.save_button.cget("state") == "normal"
    assert "Check Log Call-Out" in app.save_hint_label.cget("text")

    app.callout_var.set(True)
    app._update_save_button_state()
    assert app.save_button.cget("state") == "normal"
    assert "Ready:" in app.save_hint_label.cget("text")


def test_roster_to_history_sync_after_admin_add(ui_gate, app_with_db) -> None:
    app, _connection, service = app_with_db

    service.add_employee(2002, "Nia", "Bishop")

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "2002")
    app._handle_lookup()

    assert "Nia Bishop" in app.employee_label.cget("text")
    assert app.history_box.get("1.0", "end").strip() == "NONE"


def test_modal_cancellation_recovery_preserves_input(ui_gate, app_with_db) -> None:
    app, connection, _service = app_with_db

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()

    app.recorded_by_entry.insert(0, "ManagerC")
    app.notes_box.insert("1.0", "Need one day")
    app.callout_var.set(True)
    app._update_save_button_state()

    before = connection.execute("SELECT COUNT(*) FROM call_outs").fetchone()[0]
    app._open_verification_modal()

    modal = next(modal for modal in _find_toplevels(app) if modal.title() == "Verify Call-Out")
    cancel_button = _find_button_by_text(modal, "Cancel")
    assert cancel_button is not None
    cancel_button.invoke()
    app.update_idletasks()

    after = connection.execute("SELECT COUNT(*) FROM call_outs").fetchone()[0]
    assert after == before
    assert app.recorded_by_entry.get().strip() == "ManagerC"
    assert app.notes_box.get("1.0", "end").strip() == "Need one day"


def test_report_refresh_after_commit_and_status_feedback(ui_gate, app_with_db) -> None:
    app, _connection, _service = app_with_db

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()

    app.recorded_by_entry.insert(0, "ManagerD")
    app.notes_box.insert("1.0", "Traffic")
    app.callout_var.set(True)
    app._update_save_button_state()

    app._open_verification_modal()
    modal = next(modal for modal in _find_toplevels(app) if modal.title() == "Verify Call-Out")
    confirm_button = _find_button_by_text(modal, "Confirm")
    assert confirm_button is not None
    confirm_button.invoke()
    app.update_idletasks()

    app._handle_view_change("Reporting")
    report_text = app.top10_box.get("1.0", "end")
    assert "1001" in report_text
    assert "Call-Out Count" in report_text
    assert app.status_label.cget("text") == "Status: Call-out saved"
    assert "Ari Cole" in app.employee_label.cget("text")
    assert app.recorded_by_entry.get().strip() == ""
    assert app.notes_box.get("1.0", "end").strip() == ""
    assert app.callout_var.get() is False
    assert app.save_button.cget("state") == "normal"
    assert "Enter Recorded By" in app.save_hint_label.cget("text")


def test_read_only_integrity_for_history_display(ui_gate, app_with_db) -> None:
    app, _connection, _service = app_with_db

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()

    assert app.history_box._textbox.cget("state") == "disabled"


def test_input_character_stress_notes_layout_stability(ui_gate, app_with_db) -> None:
    app, _connection, _service = app_with_db

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()

    long_notes = "A" * 8000
    app.notes_box.insert("1.0", long_notes)
    app.recorded_by_entry.insert(0, "ManagerE")
    app.callout_var.set(True)
    app._update_save_button_state()
    app.update_idletasks()

    assert app.save_button.cget("state") == "normal"
    width = int(app.save_button.winfo_width())
    assert width > 0


def test_navigation_persistence_between_tabs(ui_gate, app_with_db) -> None:
    app, _connection, _service = app_with_db

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()
    app.recorded_by_entry.insert(0, "ManagerPersist")
    app.notes_box.insert("1.0", "Keep this input")
    app.callout_var.set(True)
    app._update_save_button_state()

    app._handle_view_change("Reporting")
    app._handle_view_change("Intake")

    assert "Ari Cole" in app.employee_label.cget("text")
    assert app.recorded_by_entry.get().strip() == "ManagerPersist"
    assert app.notes_box.get("1.0", "end").strip() == "Keep this input"
    assert app.callout_var.get() is True
    assert app.save_button.cget("state") == "normal"


def test_database_lock_error_feedback(ui_gate, app_with_db, monkeypatch) -> None:
    app, connection, service = app_with_db

    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(messagebox, "showerror", lambda title, msg: errors.append((title, msg)))

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()

    app.recorded_by_entry.insert(0, "ManagerLock")
    app.notes_box.insert("1.0", "Lock simulation")
    app.callout_var.set(True)
    app._update_save_button_state()

    def locked_log_call_out(*_args, **_kwargs):
        raise DatabaseAccessError("Database is unavailable for call-out logging.")

    service.log_call_out = locked_log_call_out  # type: ignore[assignment]

    before = connection.execute("SELECT COUNT(*) FROM call_outs").fetchone()[0]
    app._open_verification_modal()
    modal = next(modal for modal in _find_toplevels(app) if modal.title() == "Verify Call-Out")
    confirm_button = _find_button_by_text(modal, "Confirm")
    assert confirm_button is not None
    confirm_button.invoke()
    app.update_idletasks()
    after = connection.execute("SELECT COUNT(*) FROM call_outs").fetchone()[0]

    assert after == before
    assert errors, "Expected a user-friendly database error message"
    assert errors[-1][0] == "Database Error"
    assert "inaccessible" in errors[-1][1] or "unavailable" in errors[-1][1]
    assert app.status_label.cget("text") == "Status: Database unavailable"


def test_intake_has_no_logger_console_title(ui_gate, app_with_db) -> None:
    app, _connection, _service = app_with_db

    labels = _collect_label_text(app)
    assert "Logger Console" not in labels


def test_search_by_first_or_last_name_loads_employee(ui_gate, app_with_db) -> None:
    app, _connection, service = app_with_db

    service.add_employee(1002, "Nia", "Bishop")

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "Bishop")
    app._handle_lookup()

    assert "Nia Bishop" in app.employee_label.cget("text")


def test_top10_resides_on_reporting_view(ui_gate, app_with_db) -> None:
    app, _connection, _service = app_with_db

    assert app.current_view.get() == "Intake"
    assert app.intake_frame.winfo_manager() == "grid"
    assert app.reporting_frame.winfo_manager() == ""

    app._handle_view_change("Reporting")
    app.update_idletasks()

    assert app.current_view.get() == "Reporting"
    assert app.intake_frame.winfo_manager() == ""
    assert app.reporting_frame.winfo_manager() == "grid"

