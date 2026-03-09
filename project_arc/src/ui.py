"""CustomTkinter UI for ARC.

This module provides a manager-first workflow for employee lookup, history
review, verified call-out logging, and Top 10 high-frequency reporting.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from src.database import DatabaseManager
from src.service import AttendanceService, DuplicateEmployeeError


class ArcApp(ctk.CTk):
	"""Main ARC application window."""

	def __init__(self, service: AttendanceService) -> None:
		super().__init__()
		self.service = service
		self.current_employee_id: int | None = None
		self.current_employee_name: str = ""
		self.callout_var = tk.BooleanVar(value=False)

		ctk.set_appearance_mode("system")
		ctk.set_default_color_theme("blue")

		self.title("ARC - Attendance Recording Center")
		self.geometry("1180x760")
		self.minsize(980, 680)

		self.grid_columnconfigure(0, weight=3)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		self._build_manager_panel()
		self._build_report_panel()
		self._set_status("Ready")

	def _build_manager_panel(self) -> None:
		panel = ctk.CTkFrame(self)
		panel.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)
		panel.grid_columnconfigure(0, weight=1)

		title = ctk.CTkLabel(
			panel,
			text="Logger Console",
			font=ctk.CTkFont(size=24, weight="bold"),
		)
		title.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

		search_row = ctk.CTkFrame(panel)
		search_row.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
		search_row.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(search_row, text="Employee ID").grid(row=0, column=0, padx=(12, 8), pady=12)
		self.employee_id_entry = ctk.CTkEntry(search_row, placeholder_text="ex: 1001")
		self.employee_id_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=12)
		self.employee_id_entry.bind("<Return>", lambda _event: self._handle_lookup())

		self.search_button = ctk.CTkButton(search_row, text="Search", command=self._handle_lookup)
		self.search_button.grid(row=0, column=2, padx=(8, 12), pady=12)

		details = ctk.CTkFrame(panel)
		details.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
		details.grid_columnconfigure(1, weight=1)
		ctk.CTkLabel(details, text="Selected Employee:").grid(row=0, column=0, padx=12, pady=8, sticky="w")
		self.employee_label = ctk.CTkLabel(details, text="None")
		self.employee_label.grid(row=0, column=1, padx=12, pady=8, sticky="w")

		ctk.CTkLabel(panel, text="History (Read-Only)").grid(row=3, column=0, sticky="w", padx=16, pady=(12, 4))
		self.history_box = ctk.CTkTextbox(panel, height=230)
		self.history_box.grid(row=4, column=0, sticky="nsew", padx=16, pady=(0, 10))
		self.history_box.configure(state="disabled")

		ctk.CTkLabel(panel, text="Recorded By").grid(row=5, column=0, sticky="w", padx=16, pady=(8, 4))
		self.recorded_by_entry = ctk.CTkEntry(panel, placeholder_text="Manager name or ID")
		self.recorded_by_entry.grid(row=6, column=0, sticky="ew", padx=16)
		self.recorded_by_entry.bind("<KeyRelease>", lambda _event: self._update_save_button_state())

		ctk.CTkLabel(panel, text="Manager Notes").grid(row=7, column=0, sticky="w", padx=16, pady=(12, 4))
		self.notes_box = ctk.CTkTextbox(panel, height=120)
		self.notes_box.grid(row=8, column=0, sticky="ew", padx=16)

		self.callout_check = ctk.CTkCheckBox(
			panel,
			text="Log Call-Out",
			variable=self.callout_var,
			command=self._update_save_button_state,
		)
		self.callout_check.grid(row=9, column=0, sticky="w", padx=16, pady=(12, 8))

		self.save_button = ctk.CTkButton(
			panel,
			text="Save (Verification Required)",
			command=self._open_verification_modal,
			state="disabled",
		)
		self.save_button.grid(row=10, column=0, sticky="ew", padx=16, pady=(0, 16))

	def _build_report_panel(self) -> None:
		panel = ctk.CTkFrame(self)
		panel.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
		panel.grid_columnconfigure(0, weight=1)
		panel.grid_rowconfigure(2, weight=1)

		title = ctk.CTkLabel(
			panel,
			text="Top 10 High-Frequency",
			font=ctk.CTkFont(size=22, weight="bold"),
		)
		title.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

		refresh = ctk.CTkButton(panel, text="Refresh Report", command=self._render_top_10)
		refresh.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

		self.top10_box = ctk.CTkTextbox(panel)
		self.top10_box.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
		self.top10_box.configure(state="disabled")

		self.status_label = ctk.CTkLabel(panel, text="", anchor="w")
		self.status_label.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))

		self._render_top_10()

	def _set_status(self, message: str) -> None:
		self.status_label.configure(text=f"Status: {message}")

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

	def _parse_employee_id(self) -> int | None:
		raw_value = self.employee_id_entry.get().strip()
		if not raw_value:
			messagebox.showerror("Validation", "Employee ID is required.")
			return None
		if not raw_value.isdigit():
			messagebox.showerror("Validation", "Employee ID must be numeric.")
			return None
		return int(raw_value)

	def _handle_lookup(self) -> None:
		employee_id = self._parse_employee_id()
		if employee_id is None:
			return

		try:
			payload = self.service.lookup_employee(employee_id)
		except ValueError:
			should_add = messagebox.askyesno(
				"Employee Not Found",
				"Employee ID was not found. Add a new employee now?",
			)
			if should_add:
				self._open_add_employee_modal(employee_id)
			else:
				self._set_status("Employee not found")
			return

		employee = payload["employee"]
		self.current_employee_id = employee["employee_id"]
		self.current_employee_name = f"{employee['first_name']} {employee['last_name']}"
		self.employee_label.configure(text=f"{self.current_employee_name} (ID: {self.current_employee_id})")

		history = payload["history"]
		if history == "NONE":
			self._update_history_text("NONE")
		else:
			lines = []
			for row in history:
				lines.append(f"{row['timestamp']} | {row['recorded_by']} | {row['notes'] or ''}")
			self._update_history_text("\n".join(lines))

		self._update_save_button_state()
		self._set_status("Employee loaded")

	def _open_add_employee_modal(self, employee_id: int) -> None:
		modal = ctk.CTkToplevel(self)
		modal.title("Add New Employee")
		modal.geometry("400x230")
		modal.grab_set()

		ctk.CTkLabel(modal, text=f"Employee ID: {employee_id}").pack(anchor="w", padx=16, pady=(16, 8))
		ctk.CTkLabel(modal, text="First Name").pack(anchor="w", padx=16)
		first_name_entry = ctk.CTkEntry(modal)
		first_name_entry.pack(fill="x", padx=16, pady=(0, 10))

		ctk.CTkLabel(modal, text="Last Name").pack(anchor="w", padx=16)
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

			modal.destroy()
			self.employee_id_entry.delete(0, "end")
			self.employee_id_entry.insert(0, str(employee_id))
			self._handle_lookup()
			self._set_status("New employee added")

		ctk.CTkButton(modal, text="Save Employee", command=save_new_employee).pack(
			fill="x", padx=16, pady=(0, 16)
		)

	def _update_save_button_state(self) -> None:
		can_save = (
			self.current_employee_id is not None
			and bool(self.recorded_by_entry.get().strip())
			and self.callout_var.get()
		)
		self.save_button.configure(state="normal" if can_save else "disabled")

	def _open_verification_modal(self) -> None:
		if self.current_employee_id is None:
			return

		recorded_by = self.recorded_by_entry.get().strip()
		notes = self.notes_box.get("1.0", "end").strip()

		modal = ctk.CTkToplevel(self)
		modal.title("Verify Call-Out")
		modal.geometry("540x330")
		modal.grab_set()

		summary = (
			"Please verify before commit:\n\n"
			f"Employee: {self.current_employee_name}\n"
			f"ID: {self.current_employee_id}\n"
			f"Recorded By: {recorded_by}\n"
			f"Notes: {notes or '(none)'}"
		)
		ctk.CTkLabel(modal, text=summary, justify="left", anchor="w").pack(
			fill="x", padx=16, pady=(16, 14)
		)

		button_row = ctk.CTkFrame(modal)
		button_row.pack(fill="x", padx=16, pady=(0, 16))
		button_row.grid_columnconfigure((0, 1), weight=1)

		def confirm_save() -> None:
			self.service.log_call_out(
				self.current_employee_id,
				recorded_by=recorded_by,
				notes=notes,
			)
			modal.destroy()
			self.callout_var.set(False)
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
		rows = self.service.get_top_10_high_frequency()
		if not rows:
			self._update_top10_text("No call-out data yet.")
			return

		lines = ["Rank | Employee ID | Name | Call-Out Count", "-" * 50]
		for idx, row in enumerate(rows, start=1):
			name = f"{row['first_name']} {row['last_name']}"
			lines.append(f"{idx:>4} | {row['employee_id']:>11} | {name:<20} | {row['call_out_count']:>3}")
		self._update_top10_text("\n".join(lines))


def build_default_service() -> AttendanceService:
	"""Build a file-backed service for desktop runtime usage."""
	project_root = Path(__file__).resolve().parents[1]
	data_dir = project_root / "data"
	data_dir.mkdir(parents=True, exist_ok=True)

	db_path = data_dir / "arc_data.db"
	connection = sqlite3.connect(db_path)
	connection.row_factory = sqlite3.Row

	db_manager = DatabaseManager(connection)
	db_manager.initialize_schema()
	return AttendanceService(db_manager)


def run_ui() -> None:
	"""Launch the ARC desktop UI."""
	app = ArcApp(build_default_service())
	app.mainloop()
