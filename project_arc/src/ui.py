"""CustomTkinter UI for ARC.

This module provides employee search, read-only history review, verified
call-out logging, and dedicated reporting navigation.
"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from src.database import DatabaseManager
from src.error_logging import append_error_log
from src.service import AttendanceService, DatabaseAccessError, DuplicateEmployeeError
from src.ui_controller import UiController


class ArcApp(ctk.CTk):
    """Main ARC application window."""

    def __init__(self, service: AttendanceService) -> None:
        super().__init__()
        self.service = service
        self.error_log_path = Path(__file__).resolve().parents[1] / "error_log.txt"
        self.current_employee_id: int | None = None
        self.current_employee_name: str = ""
        self.callout_var = tk.BooleanVar(value=False)
        self.current_view = tk.StringVar(value="Intake")
        self.match_map: dict[str, int] = {}

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.title("ARC - Attendance Recording Center")
        self.geometry("1180x760")
        self.minsize(980, 680)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_navigation()
        self._build_intake_view()
        self._build_reporting_view()
        self._build_status_bar()
        self._handle_view_change("Intake")
        self._set_status("Ready")

    def _build_navigation(self) -> None:
        nav = ctk.CTkFrame(self)
        nav.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        nav.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(nav, text="View").grid(row=0, column=0, padx=(12, 8), pady=10, sticky="w")
        self.view_selector = ctk.CTkOptionMenu(
            nav,
            values=["Intake", "Reporting"],
            variable=self.current_view,
            command=self._handle_view_change,
        )
        self.view_selector.grid(row=0, column=1, sticky="w", padx=8, pady=10)

    def _build_intake_view(self) -> None:
        self.intake_frame = ctk.CTkFrame(self)
        self.intake_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        self.intake_frame.grid_columnconfigure(0, weight=1)

        search_row = ctk.CTkFrame(self.intake_frame)
        search_row.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        search_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(search_row, text="* Search (ID / First / Last)").grid(
            row=0, column=0, padx=(12, 8), pady=12
        )
        self.search_entry = ctk.CTkEntry(search_row, placeholder_text="e.g. 1001, Ari, Bishop")
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=12)
        self.search_entry.bind("<Return>", lambda _event: self._handle_lookup())
        self.employee_id_entry = self.search_entry

        self.search_button = ctk.CTkButton(search_row, text="Search", command=self._handle_lookup)
        self.search_button.grid(row=0, column=2, padx=(8, 12), pady=12)

        self.match_selector = ctk.CTkOptionMenu(
            self.intake_frame,
            values=["No matches"],
            command=self._handle_match_selection,
        )
        self.match_selector.grid(row=1, column=0, sticky="ew", padx=16)
        self.match_selector.grid_remove()

        details = ctk.CTkFrame(self.intake_frame)
        details.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        details.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(details, text="Selected Employee:").grid(row=0, column=0, padx=12, pady=8, sticky="w")
        self.employee_label = ctk.CTkLabel(details, text="None")
        self.employee_label.grid(row=0, column=1, padx=12, pady=8, sticky="w")

        ctk.CTkLabel(self.intake_frame, text="Past Call-Outs").grid(
            row=3, column=0, sticky="w", padx=16, pady=(12, 4)
        )
        self.history_box = ctk.CTkTextbox(self.intake_frame, height=230)
        self.history_box.grid(row=4, column=0, sticky="nsew", padx=16, pady=(0, 10))
        self.history_box.configure(state="disabled")

        ctk.CTkLabel(self.intake_frame, text="* Recorded By").grid(
            row=5, column=0, sticky="w", padx=16, pady=(8, 4)
        )
        self.recorded_by_entry = ctk.CTkEntry(self.intake_frame, placeholder_text="Manager name or ID")
        self.recorded_by_entry.grid(row=6, column=0, sticky="ew", padx=16)
        self.recorded_by_entry.bind("<KeyRelease>", lambda _event: self._update_save_button_state())

        ctk.CTkLabel(self.intake_frame, text="Manager Notes (optional)").grid(
            row=7, column=0, sticky="w", padx=16, pady=(12, 4)
        )
        self.notes_box = ctk.CTkTextbox(self.intake_frame, height=120)
        self.notes_box.grid(row=8, column=0, sticky="ew", padx=16)

        self.callout_check = ctk.CTkCheckBox(
            self.intake_frame,
            text="* Log Call-Out",
            variable=self.callout_var,
            command=self._update_save_button_state,
        )
        self.callout_check.grid(row=9, column=0, sticky="w", padx=16, pady=(12, 8))

        self.save_button = ctk.CTkButton(
            self.intake_frame,
            text="Save (Verification Required)",
            command=self._open_verification_modal,
            fg_color=("#2563eb", "#1d4ed8"),
            hover_color=("#1d4ed8", "#1e40af"),
            text_color=("#ffffff", "#ffffff"),
            text_color_disabled=("#94a3b8", "#94a3b8"),
            width=320,
            height=44,
            corner_radius=10,
        )
        self.save_button.grid(row=10, column=0, sticky="w", padx=16, pady=(0, 16))

        self.save_hint_label = ctk.CTkLabel(
            self.intake_frame,
            text="Tip: Enter Recorded By and check Log Call-Out to enable Save.",
            anchor="w",
        )
        self.save_hint_label.grid(row=11, column=0, sticky="ew", padx=16, pady=(0, 12))

    def _build_reporting_view(self) -> None:
        self.reporting_frame = ctk.CTkFrame(self)
        self.reporting_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        self.reporting_frame.grid_columnconfigure(0, weight=1)
        self.reporting_frame.grid_rowconfigure(2, weight=1)

        title = ctk.CTkLabel(
            self.reporting_frame,
            text="Top 10 High-Frequency",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

        refresh = ctk.CTkButton(self.reporting_frame, text="Refresh Report", command=self._render_top_10)
        refresh.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        self.top10_box = ctk.CTkTextbox(self.reporting_frame)
        self.top10_box.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        self.top10_box.configure(state="disabled")

        self._render_top_10()

    def _build_status_bar(self) -> None:
        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        status_frame.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(status_frame, text="", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=12, pady=10)

    def _handle_view_change(self, view_name: str) -> None:
        self.current_view.set(view_name)
        if view_name == "Reporting":
            self.intake_frame.grid_remove()
            self.reporting_frame.grid()
            self._render_top_10()
        else:
            self.reporting_frame.grid_remove()
            self.intake_frame.grid()

    def _set_status(self, message: str) -> None:
        self.status_label.configure(text=f"Status: {message}")

    def _handle_runtime_error(self, user_message: str, context: str, exc: Exception) -> None:
        append_error_log(self.error_log_path, context, exc)
        messagebox.showerror("Database Error", user_message)
        self._set_status("Database unavailable")

    def _update_history_text(self, text: str) -> None:
        self.history_box.configure(state="normal")
        self.history_box.delete("1.0", "end")
        self.history_box.insert("1.0", text)
        self.history_box.configure(state="disabled")

    def _update_top10_text(self, text: str) -> None:
        self.top10_box.configure(state="normal")
        self.top10_box.delete("1.0", "end")
        self.top10_box.insert("1.0", text)
        self.top10_box.configure(state="disabled")

    def _load_employee(self, employee_id: int) -> None:
        try:
            payload = self.service.lookup_employee(employee_id)
        except DatabaseAccessError as exc:
            self._handle_runtime_error(
                "Database is unavailable right now. Please try again in a moment.",
                "lookup_employee",
                exc,
            )
            return
        except ValueError:
            self._set_status("Employee not found")
            return

        employee = payload["employee"]
        self.current_employee_id = employee["employee_id"]
        self.current_employee_name = f"{employee['first_name']} {employee['last_name']}"
        self.employee_label.configure(text=f"{self.current_employee_name} (ID: {self.current_employee_id})")
        self._update_history_text(UiController.format_history(payload["history"]))
        self._update_save_button_state()
        self._set_status("Employee loaded")

    def _handle_lookup(self) -> None:
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showerror("Validation", "Search input is required.")
            return

        try:
            matches = self.service.search_employees(query)
        except DatabaseAccessError as exc:
            self._handle_runtime_error(
                "Database is unavailable right now. Please try again in a moment.",
                "search_employees",
                exc,
            )
            return

        if not matches:
            if query.isdigit():
                should_add = messagebox.askyesno(
                    "Employee Not Found",
                    "Employee ID was not found. Add a new employee now?",
                )
                if should_add:
                    self._open_add_employee_modal(int(query))
            else:
                self._set_status("No employee matches found")
            return

        if len(matches) == 1:
            self.match_selector.grid_remove()
            self._load_employee(int(matches[0]["employee_id"]))
            return

        self.match_map = {
            f"{row['employee_id']} - {row['first_name']} {row['last_name']}": int(row["employee_id"])
            for row in matches
        }
        options = list(self.match_map.keys())
        self.match_selector.configure(values=options)
        self.match_selector.set(options[0])
        self.match_selector.grid()
        self._load_employee(self.match_map[options[0]])
        self._set_status("Multiple matches found. Select employee.")

    def _handle_match_selection(self, selected: str) -> None:
        employee_id = self.match_map.get(selected)
        if employee_id is not None:
            self._load_employee(employee_id)

    def _open_add_employee_modal(self, employee_id: int) -> None:
        modal = ctk.CTkToplevel(self)
        modal.title("Add New Employee")
        modal.geometry("400x230")
        modal.grab_set()

        ctk.CTkLabel(modal, text=f"Employee ID: {employee_id}").pack(anchor="w", padx=16, pady=(16, 8))
        ctk.CTkLabel(modal, text="* First Name").pack(anchor="w", padx=16)
        first_name_entry = ctk.CTkEntry(modal)
        first_name_entry.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(modal, text="* Last Name").pack(anchor="w", padx=16)
        last_name_entry = ctk.CTkEntry(modal)
        last_name_entry.pack(fill="x", padx=16, pady=(0, 14))

        def save_new_employee() -> None:
            first = first_name_entry.get().strip()
            last = last_name_entry.get().strip()
            if not first or not last:
                messagebox.showerror("Validation", "First and last name are required.")
                return
            try:
                self.service.add_employee(employee_id, first, last)
            except DuplicateEmployeeError:
                messagebox.showerror("Duplicate", "Employee ID already exists.")
                return
            except DatabaseAccessError as exc:
                self._handle_runtime_error(
                    "Unable to add employee because the database is unavailable.",
                    "add_employee",
                    exc,
                )
                return

            modal.destroy()
            self.search_entry.delete(0, "end")
            self.search_entry.insert(0, str(employee_id))
            self._handle_lookup()
            self._set_status("New employee added")

        ctk.CTkButton(modal, text="Save Employee", command=save_new_employee).pack(
            fill="x", padx=16, pady=(0, 16)
        )

    def _update_save_button_state(self) -> None:
        can_save = UiController.can_enable_save(
            current_employee_id=self.current_employee_id,
            recorded_by=self.recorded_by_entry.get(),
            callout_checked=self.callout_var.get(),
        )
        if can_save:
            self.save_hint_label.configure(text="Ready: click Save to open the verification modal.")
        else:
            if self.current_employee_id is None:
                self.save_hint_label.configure(text="Required action: Search and select an employee first.")
            elif not self.recorded_by_entry.get().strip():
                self.save_hint_label.configure(text="Required action: Enter Recorded By before saving.")
            elif not self.callout_var.get():
                self.save_hint_label.configure(text="Required action: Check Log Call-Out before saving.")
            else:
                self.save_hint_label.configure(text="Required action: complete all required fields.")

    def _open_verification_modal(self) -> None:
        if self.current_employee_id is None:
            self.save_hint_label.configure(text="Required action: Search and select an employee first.")
            return

        if not self.recorded_by_entry.get().strip():
            self.save_hint_label.configure(text="Required action: Enter Recorded By before saving.")
            return

        if not self.callout_var.get():
            self.save_hint_label.configure(text="Required action: Check Log Call-Out before saving.")
            return

        recorded_by = self.recorded_by_entry.get().strip()
        notes = self.notes_box.get("1.0", "end").strip()

        modal = ctk.CTkToplevel(self)
        modal.title("Verify Call-Out")
        modal.geometry("540x330")
        modal.grab_set()

        summary = UiController.build_verification_summary(
            employee_name=self.current_employee_name,
            employee_id=self.current_employee_id,
            recorded_by=recorded_by,
            notes=notes,
        )
        ctk.CTkLabel(modal, text=summary, justify="left", anchor="w").pack(
            fill="x", padx=16, pady=(16, 14)
        )

        button_row = ctk.CTkFrame(modal)
        button_row.pack(fill="x", padx=16, pady=(0, 16))
        button_row.grid_columnconfigure((0, 1), weight=1)

        def confirm_save() -> None:
            try:
                self.service.log_call_out(
                    self.current_employee_id,
                    recorded_by=recorded_by,
                    notes=notes,
                )
            except DatabaseAccessError as exc:
                self._handle_runtime_error(
                    "Could not save call-out because the database file is currently inaccessible.",
                    "log_call_out",
                    exc,
                )
                return
            except ValueError as exc:
                messagebox.showerror("Validation", str(exc))
                return
            modal.destroy()
            self.callout_var.set(False)
            self.recorded_by_entry.delete(0, "end")
            self.notes_box.delete("1.0", "end")
            self._handle_lookup()
            self._render_top_10()
            self._update_save_button_state()
            self._set_status("Call-out saved")

        ctk.CTkButton(button_row, text="Confirm", command=confirm_save).grid(
            row=0, column=0, sticky="ew", padx=(0, 8), pady=8
        )
        ctk.CTkButton(button_row, text="Cancel", command=modal.destroy).grid(
            row=0, column=1, sticky="ew", padx=(8, 0), pady=8
        )

    def _render_top_10(self) -> None:
        try:
            rows = self.service.get_top_10_high_frequency()
        except DatabaseAccessError as exc:
            self._handle_runtime_error(
                "Unable to load report because the database is unavailable.",
                "get_top_10_high_frequency",
                exc,
            )
            self._update_top10_text("Report unavailable while database is inaccessible.")
            return
        self._update_top10_text(UiController.format_top_10(rows))


def build_default_service() -> AttendanceService:
    """Build a file-backed service for desktop runtime usage."""
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    override_path = os.getenv("ARC_DB_PATH")
    db_path = Path(override_path) if override_path else data_dir / "arc_data.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    db_manager = DatabaseManager(connection)
    db_manager.initialize_schema()
    return AttendanceService(db_manager)


def run_ui() -> None:
    """Launch the ARC desktop UI."""
    try:
        service = build_default_service()
    except sqlite3.Error as exc:
        log_path = Path(__file__).resolve().parents[1] / "error_log.txt"
        append_error_log(log_path, "build_default_service", exc)
        messagebox.showerror(
            "Startup Error",
            "ARC could not open the database file. Please check permissions and try again.",
        )
        return

    app = ArcApp(service)
    app.mainloop()
