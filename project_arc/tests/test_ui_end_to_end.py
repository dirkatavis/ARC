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


def _find_entries(parent) -> list[ctk.CTkEntry]:
    entries: list[ctk.CTkEntry] = []
    for widget in parent.winfo_children():
        if isinstance(widget, ctk.CTkEntry):
            entries.append(widget)
        entries.extend(_find_entries(widget))
    return entries


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


def test_add_new_employee_does_not_log_call_out(ui_gate, app_with_db, monkeypatch) -> None:
    app, connection, _service = app_with_db

    monkeypatch.setattr(messagebox, "askyesno", lambda *_args, **_kwargs: True)

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "2999")
    app._handle_lookup()

    modal = next(modal for modal in _find_toplevels(app) if modal.title() == "Add New Employee")
    entries = _find_entries(modal)
    assert len(entries) >= 2

    entries[0].insert(0, "Robin")
    entries[1].insert(0, "Vale")

    save_employee_btn = _find_button_by_text(modal, "Save Employee")
    assert save_employee_btn is not None
    save_employee_btn.invoke()
    app.update_idletasks()

    row = connection.execute(
        "SELECT employee_id, first_name, last_name FROM employees WHERE employee_id = ?",
        (2999,),
    ).fetchone()
    call_out_count = connection.execute(
        "SELECT COUNT(*) FROM call_outs WHERE employee_id = ?",
        (2999,),
    ).fetchone()[0]

    assert row is not None
    assert row[0] == 2999
    assert row[1] == "Robin"
    assert row[2] == "Vale"
    assert call_out_count == 0


def test_verification_modal_trigger_blocks_write_until_confirm(ui_gate, app_with_db) -> None:
    app, connection, _service = app_with_db

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()

    app.recorded_by_entry.insert(0, "ManagerA")
    app.notes_box.insert("1.0", "Flu")
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
    app._update_save_button_state()

    app._handle_view_change("Reporting")
    app._handle_view_change("Case Entry")

    assert "Ari Cole" in app.employee_label.cget("text")
    assert app.recorded_by_entry.get().strip() == "ManagerPersist"
    assert app.notes_box.get("1.0", "end").strip() == "Keep this input"
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


def test_case_entry_has_no_logger_console_title(ui_gate, app_with_db) -> None:
    app, _connection, _service = app_with_db

    labels = _collect_label_text(app)
    assert "Logger Console" not in labels


def test_navigation_selector_uses_case_entry_label(ui_gate, app_with_db) -> None:
    app, _connection, _service = app_with_db

    nav_values = tuple(app.view_selector.cget("values"))

    assert "Case Entry" in nav_values
    assert "Reporting" in nav_values
    assert "Intake" not in nav_values


def test_search_by_first_or_last_name_loads_employee(ui_gate, app_with_db) -> None:
    app, _connection, service = app_with_db

    service.add_employee(1002, "Nia", "Bishop")

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "Bishop")
    app._handle_lookup()

    assert "Nia Bishop" in app.employee_label.cget("text")


def test_partial_single_match_requires_explicit_selection(ui_gate, app_with_db) -> None:
    app, _connection, service = app_with_db

    service.add_employee(2201, "Mila", "Johnson")

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "John")
    app._handle_lookup()

    assert app.employee_label.cget("text") == "None"
    assert app.match_cards_frame.winfo_manager() == "grid"
    assert app.status_label.cget("text") == "Status: Partial match found. Select employee to confirm."

    johnson_option = next(key for key in app.match_map if key.startswith("2201 - "))
    app._handle_match_selection(johnson_option)

    assert "Mila Johnson" in app.employee_label.cget("text")


def test_multiple_matches_shows_selector_without_auto_loading(ui_gate, app_with_db) -> None:
    app, _connection, service = app_with_db

    service.add_employee(2001, "Alex", "Green")
    service.add_employee(2002, "Alex", "Brown")
    service.log_call_out(
        2001,
        recorded_by="MgrAlpha",
        notes="Alex Green distinct note",
        timestamp="2026-04-01 09:00:00",
    )
    service.log_call_out(
        2002,
        recorded_by="MgrBravo",
        notes="Alex Brown distinct note",
        timestamp="2026-04-02 09:00:00",
    )

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "Alex")
    app._handle_lookup()

    assert app.employee_label.cget("text") == "None"
    assert app.match_cards_frame.winfo_manager() == "grid"
    assert app.status_label.cget("text") == "Status: Multiple matches found. Select employee."

    alex_green_option = next(key for key in app.match_map if key.startswith("2001 - "))
    app._handle_match_selection(alex_green_option)

    assert "Alex Green" in app.employee_label.cget("text")
    history_text = app.history_box.get("1.0", "end")
    assert "MgrAlpha" in history_text
    assert "Alex Green distinct note" in history_text

    alex_brown_option = next(key for key in app.match_map if key.startswith("2002 - "))
    app._handle_match_selection(alex_brown_option)

    assert "Alex Brown" in app.employee_label.cget("text")
    history_text = app.history_box.get("1.0", "end")
    assert "MgrBravo" in history_text
    assert "Alex Brown distinct note" in history_text


def test_multiple_last_name_matches_show_selector_without_auto_loading(ui_gate, app_with_db) -> None:
    app, _connection, service = app_with_db

    service.add_employee(2011, "Jamie", "Smith")
    service.add_employee(2012, "Noah", "Smith")
    service.log_call_out(
        2011,
        recorded_by="MgrSmithA",
        notes="Jamie Smith distinct note",
        timestamp="2026-04-03 09:00:00",
    )
    service.log_call_out(
        2012,
        recorded_by="MgrSmithB",
        notes="Noah Smith distinct note",
        timestamp="2026-04-04 09:00:00",
    )

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "Smith")
    app._handle_lookup()

    assert app.employee_label.cget("text") == "None"
    assert app.match_cards_frame.winfo_manager() == "grid"

    jamie_smith_option = next(key for key in app.match_map if key.startswith("2011 - "))
    app._handle_match_selection(jamie_smith_option)
    assert "Jamie Smith" in app.employee_label.cget("text")
    history_text = app.history_box.get("1.0", "end")
    assert "MgrSmithA" in history_text
    assert "Jamie Smith distinct note" in history_text

    noah_smith_option = next(key for key in app.match_map if key.startswith("2012 - "))
    app._handle_match_selection(noah_smith_option)
    assert "Noah Smith" in app.employee_label.cget("text")
    history_text = app.history_box.get("1.0", "end")
    assert "MgrSmithB" in history_text
    assert "Noah Smith distinct note" in history_text


def test_top10_resides_on_reporting_view(ui_gate, app_with_db) -> None:
    app, _connection, _service = app_with_db

    assert app.current_view.get() == "Case Entry"
    assert app.case_entry_frame.winfo_manager() == "grid"
    assert app.reporting_frame.winfo_manager() == ""

    app._handle_view_change("Reporting")
    app.update_idletasks()

    assert app.current_view.get() == "Reporting"
    assert app.case_entry_frame.winfo_manager() == ""
    assert app.reporting_frame.winfo_manager() == "grid"


def test_action_pane_zero_state_guidance_updates_with_selection(ui_gate, app_with_db) -> None:
    app, _connection, _service = app_with_db

    assert "Please search and select an employee" in app.action_zero_state_label.cget("text")

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()

    assert "Ready to record for:" in app.action_zero_state_label.cget("text")


# ── Section 3: Session identity fixtures and tests ─────────────────────────

@pytest.fixture
def app_with_session(monkeypatch, tmp_path: Path):
    """App fixture with a pre-set session manager so sign-in modal is skipped."""
    db_path = tmp_path / "arc_session_e2e.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    db = DatabaseManager(connection)
    db.initialize_schema()

    service = AttendanceService(db)
    service.add_employee(1001, "Ari", "Cole")

    monkeypatch.setattr(messagebox, "showerror", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(messagebox, "askyesno", lambda *_args, **_kwargs: False)

    app = ArcApp(service, session_manager="TestManager")
    app.withdraw()
    app.update_idletasks()

    yield app, connection, service

    app.destroy()
    connection.close()


def test_session_manager_autofills_recorded_by(ui_gate, app_with_session) -> None:
    app, _connection, _service = app_with_session

    assert app.recorded_by_entry.get() == "TestManager"


def test_recorded_by_is_readonly_with_session(ui_gate, app_with_session) -> None:
    app, _connection, _service = app_with_session

    assert app.recorded_by_entry.cget("state") == "disabled"


def test_change_session_button_visible_with_session(ui_gate, app_with_session) -> None:
    app, _connection, _service = app_with_session

    assert app.change_session_button.winfo_manager() == "grid"


def test_toggle_session_edit_unlocks_and_relocks(ui_gate, app_with_session) -> None:
    app, _connection, _service = app_with_session

    # Clicking Change enters edit mode
    app._toggle_session_edit()
    assert app.recorded_by_entry.cget("state") == "normal"
    assert app.change_session_button.cget("text") == "Confirm"

    # Update name then confirm re-locks
    app.recorded_by_entry.delete(0, "end")
    app.recorded_by_entry.insert(0, "NewManager")
    app._toggle_session_edit()
    assert app.recorded_by_entry.cget("state") == "disabled"
    assert app.recorded_by_entry.get() == "NewManager"
    assert app.session_manager == "NewManager"
    assert app.change_session_button.cget("text") == "(Change)"


def test_session_recorded_by_refills_after_save(ui_gate, app_with_session) -> None:
    app, connection, _service = app_with_session

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()

    app._open_verification_modal()
    modal = next(m for m in _find_toplevels(app) if m.title() == "Verify Call-Out")
    confirm_button = _find_button_by_text(modal, "Confirm")
    assert confirm_button is not None
    confirm_button.invoke()
    app.update_idletasks()

    # Session manager is re-applied after save
    assert app.recorded_by_entry.get() == "TestManager"
    assert app.recorded_by_entry.cget("state") == "disabled"
    assert app.status_label.cget("text") == "Status: Call-out saved"


def test_save_enabled_without_checkbox_when_employee_and_recorded_by_set(ui_gate, app_with_session) -> None:
    app, _connection, _service = app_with_session

    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "1001")
    app._handle_lookup()

    # Session auto-fills Recorded By — save should be ready with no checkbox
    assert "Ready:" in app.save_hint_label.cget("text")

