"""CustomTkinter UI for ARC.

This module provides employee search, read-only history review, verified
call-out logging, dedicated reporting navigation, and license management.
"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import sys
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

import customtkinter as ctk

from src.database import DatabaseManager
from src.entitlement import EntitlementEngine, EntitlementState
from src.error_logging import append_error_log
from src.points_config import ensure_config_file, load_points_config
from src.points_engine import PointsConfigError
from src.service import AttendanceService, DatabaseAccessError, DuplicateEmployeeError, TrialExpiredError
from src.ui_controller import UiController


VIEW_SELECTOR_WIDTH = 180
SEARCH_ROW_WIDTH = 560
SEARCH_ENTRY_WIDTH = 260
SEARCH_BUTTON_WIDTH = 120
CONTEXT_PANE_WIDTH = 620
ACTION_PANE_WIDTH = 360
DETAILS_PANEL_WIDTH = 420
MATCH_SELECTOR_WIDTH = 420
MATCH_CARDS_WIDTH = 420
HISTORY_BOX_WIDTH = 420
HISTORY_BOX_HEIGHT = 200
HISTORY_MAX_ENTRIES = 10
RECORDED_BY_WIDTH = 300
NOTES_BOX_WIDTH = 320
NOTES_BOX_HEIGHT = 90
NOTES_FONT_FAMILY = "Courier New"
NOTES_FONT_SIZE = 13
SAVE_BUTTON_HEIGHT = 40
REPORT_FILTER_WIDTH = 260
REPORT_SORT_WIDTH = 180
REPORT_SORT_LABEL_TO_KEY = {
    "Employee Name": "employee_name",
    "Employee ID": "employee_id",
    "Total Callouts": "total_callouts",
    "Points Earned": "points_earned",
    "Last Updated": "last_updated",
}
REPORT_SORT_KEY_TO_LABEL = {value: key for key, value in REPORT_SORT_LABEL_TO_KEY.items()}
REPORT_SORT_ASC_SYMBOL = " ▲"
REPORT_SORT_DESC_SYMBOL = " ▼"


class ArcApp(ctk.CTk):
    """Main ARC application window."""

    def __init__(
        self,
        service: AttendanceService,
        session_manager: str | None = None,
        entitlement: EntitlementEngine | None = None,
        error_log_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.entitlement = entitlement
        self.error_log_path = error_log_path or _resolve_default_log_path()
        self.current_employee_id: int | None = None
        self.current_employee_name: str = ""
        self.session_manager: str | None = session_manager
        self.current_view = tk.StringVar(value="Case Entry")
        self.match_map: dict[str, int] = {}
        self._suppress_match_selection = False
        self._trial_notice_shown = False

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.title("ARC - Attendance Recording Center")
        self.geometry("1180x760")
        self.minsize(980, 680)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_navigation()
        self._build_case_entry_view()
        self._build_reporting_view()
        self._build_status_bar()
        self._handle_view_change("Case Entry")
        self._set_status("Ready")

        if session_manager is not None:
            self._apply_session_manager()
        else:
            self.after(50, self._show_sign_in_modal)

        # Show the trial-expired blocking modal after the main window is ready.
        if self.entitlement is not None:
            self.after(100, self._check_entitlement_on_startup)

    def _build_navigation(self) -> None:
        nav = ctk.CTkFrame(self)
        nav.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        nav.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(nav, text="View").grid(row=0, column=0, padx=(12, 8), pady=10, sticky="w")
        self.view_selector = ctk.CTkOptionMenu(
            nav,
            values=["Case Entry", "Reporting"],
            variable=self.current_view,
            command=self._handle_view_change,
            width=VIEW_SELECTOR_WIDTH,
        )
        self.view_selector.grid(row=0, column=1, sticky="w", padx=8, pady=10)

        self.session_header_label = ctk.CTkLabel(
            nav,
            text="Not signed in",
            anchor="e",
            text_color=("#64748b", "#94a3b8"),
            font=ctk.CTkFont(size=12),
        )
        self.session_header_label.grid(row=0, column=2, sticky="e", padx=(8, 12), pady=10)

        # Trial / license status banner (column 3).
        self.trial_banner_label = ctk.CTkLabel(
            nav,
            text="",
            anchor="e",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.trial_banner_label.grid(row=0, column=3, sticky="e", padx=(4, 4), pady=10)

        activate_btn = ctk.CTkButton(
            nav,
            text="Activate License",
            width=130,
            height=28,
            command=self._open_license_modal,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            corner_radius=6,
            font=ctk.CTkFont(size=12),
        )
        activate_btn.grid(row=0, column=4, sticky="e", padx=(4, 12), pady=10)

        self._refresh_trial_banner()

    # ── Entitlement helpers ────────────────────────────────────────────────

    def _get_entitlement_state(self) -> EntitlementState | None:
        if self.entitlement is None:
            return None
        return self.entitlement.get_state()

    def _refresh_trial_banner(self) -> None:
        """Update the trial status banner in the navigation bar."""
        if self.entitlement is None:
            self.trial_banner_label.configure(text="")
            return

        state = self.entitlement.get_state()
        if state == EntitlementState.LICENSED:
            self.trial_banner_label.configure(
                text="✓ Licensed",
                text_color=("#16A34A", "#4ade80"),
            )
        elif state == EntitlementState.TRIAL:
            days = self.entitlement.days_remaining()
            self.trial_banner_label.configure(
                text=f"🔓 Trial – {days} day{'s' if days != 1 else ''} remaining",
                text_color=("#d97706", "#fbbf24"),
            )
        else:  # EXPIRED
            self.trial_banner_label.configure(
                text="⛔ Trial Expired",
                text_color=("#EF4444", "#EF4444"),
            )

    def _check_entitlement_on_startup(self) -> None:
        """Show entitlement state messaging at startup."""
        if self.entitlement is None:
            return

        state = self.entitlement.get_state()
        if state == EntitlementState.EXPIRED:
            self._show_trial_expired_modal()
        elif state == EntitlementState.TRIAL and not self._trial_notice_shown:
            self._trial_notice_shown = True
            self._show_trial_active_modal()

    def _show_trial_active_modal(self) -> None:
        """Inform users they are in trial mode while allowing full access."""
        if self.entitlement is None:
            return

        days = self.entitlement.days_remaining()

        modal = ctk.CTkToplevel(self)
        modal.title("Trial Active")
        modal.geometry("500x250")
        modal.grab_set()
        modal.resizable(False, False)

        ctk.CTkLabel(
            modal,
            text="ARC Trial Mode",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(20, 6))

        ctk.CTkLabel(
            modal,
            text=(
                f"You have {days} day{'s' if days != 1 else ''} remaining in your trial.\n"
                "All features are currently enabled during the trial period."
            ),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkButton(
            modal,
            text="Continue",
            command=modal.destroy,
            fg_color=("#2563eb", "#1d4ed8"),
            hover_color=("#1d4ed8", "#1e40af"),
        ).pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkButton(
            modal,
            text="Activate License…",
            command=lambda: (modal.destroy(), self._open_license_modal()),
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
        ).pack(fill="x", padx=20, pady=(0, 20))

    def _show_trial_expired_modal(self) -> None:
        """Block the main window and present activation options."""
        modal = ctk.CTkToplevel(self)
        modal.title("Trial Expired")
        modal.geometry("460x240")
        modal.grab_set()
        modal.resizable(False, False)
        modal.protocol("WM_DELETE_WINDOW", lambda: None)

        ctk.CTkLabel(
            modal,
            text="Your 15-day trial has expired.",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(20, 6))

        ctk.CTkLabel(
            modal,
            text=(
                "ARC is now in read-only mode. Purchase a license and\n"
                "enter your activation key to restore full access."
            ),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=20, pady=(0, 16))

        def open_activation() -> None:
            modal.destroy()
            self._open_license_modal()

        ctk.CTkButton(
            modal,
            text="Activate License…",
            command=open_activation,
            fg_color=("#2563eb", "#1d4ed8"),
            hover_color=("#1d4ed8", "#1e40af"),
        ).pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkButton(
            modal,
            text="Continue in Read-Only Mode",
            command=modal.destroy,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
        ).pack(fill="x", padx=20, pady=(0, 20))

    def _open_license_modal(self) -> None:
        """Open the License Management dialog."""
        machine_id = self.entitlement.machine_id if self.entitlement else "N/A"

        modal = ctk.CTkToplevel(self)
        modal.title("License Management")
        modal.geometry("500x340")
        modal.grab_set()
        modal.resizable(False, False)

        ctk.CTkLabel(
            modal,
            text="License Activation",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(20, 4))

        # Machine ID section.
        ctk.CTkLabel(modal, text="Machine ID (share this with the developer to get a key):", anchor="w").pack(
            fill="x", padx=20, pady=(10, 2)
        )
        mid_row = ctk.CTkFrame(modal, fg_color="transparent")
        mid_row.pack(fill="x", padx=20, pady=(0, 14))
        mid_row.grid_columnconfigure(0, weight=1)

        mid_entry = ctk.CTkEntry(mid_row, width=340)
        mid_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        mid_entry.insert(0, machine_id)
        mid_entry.configure(state="disabled")

        def copy_machine_id() -> None:
            self.clipboard_clear()
            self.clipboard_append(machine_id)
            copy_btn.configure(text="Copied!")
            self.after(1500, lambda: copy_btn.configure(text="Copy"))

        copy_btn = ctk.CTkButton(mid_row, text="Copy", width=80, command=copy_machine_id)
        copy_btn.grid(row=0, column=1)

        # Key entry section.
        ctk.CTkLabel(modal, text="* Activation Key (format: XXXX-XXXX-XXXX):", anchor="w").pack(
            fill="x", padx=20, pady=(0, 2)
        )
        key_entry = ctk.CTkEntry(modal, placeholder_text="e.g. A1B2-C3D4-E5F6", width=340)
        key_entry.pack(fill="x", padx=20, pady=(0, 6))

        feedback_label = ctk.CTkLabel(modal, text="", anchor="w")
        feedback_label.pack(fill="x", padx=20, pady=(0, 10))

        def attempt_activation() -> None:
            if self.entitlement is None:
                feedback_label.configure(
                    text="No entitlement engine configured.",
                    text_color=("#EF4444", "#EF4444"),
                )
                return

            key = key_entry.get().strip()
            if not key:
                feedback_label.configure(
                    text="Please enter an activation key.",
                    text_color=("#EF4444", "#EF4444"),
                )
                return

            if self.entitlement.activate(key):
                feedback_label.configure(
                    text="✓ Activation successful! ARC is now fully licensed.",
                    text_color=("#16A34A", "#4ade80"),
                )
                self._refresh_trial_banner()
                self._update_save_button_state()
                activate_btn.configure(state="disabled")
            else:
                feedback_label.configure(
                    text="Invalid Key. Please verify and try again.",
                    text_color=("#EF4444", "#EF4444"),
                )

        activate_btn = ctk.CTkButton(
            modal,
            text="Activate",
            command=attempt_activation,
            fg_color=("#2563eb", "#1d4ed8"),
            hover_color=("#1d4ed8", "#1e40af"),
        )
        activate_btn.pack(fill="x", padx=20, pady=(0, 16))

        key_entry.bind("<Return>", lambda _e: attempt_activation())

    def _build_case_entry_view(self) -> None:
        self.case_entry_frame = ctk.CTkFrame(self)
        self.case_entry_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        self.case_entry_frame.grid_columnconfigure(0, weight=1)
        self.case_entry_frame.grid_columnconfigure(1, weight=0)
        self.case_entry_frame.grid_rowconfigure(0, weight=1)

        self.context_pane = ctk.CTkFrame(self.case_entry_frame, width=CONTEXT_PANE_WIDTH)
        self.context_pane.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=(16, 12))
        self.context_pane.grid_columnconfigure(0, weight=1)

        self.action_pane = ctk.CTkFrame(self.case_entry_frame, width=ACTION_PANE_WIDTH)
        self.action_pane.grid(row=0, column=1, sticky="nsw", padx=(8, 16), pady=(16, 12))
        self.action_pane.grid_columnconfigure(0, weight=1)

        search_row = ctk.CTkFrame(self.context_pane, width=SEARCH_ROW_WIDTH)
        search_row.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        ctk.CTkLabel(search_row, text="* Search (ID / First / Last)").grid(
            row=0, column=0, padx=(12, 8), pady=12
        )
        self.search_entry = ctk.CTkEntry(
            search_row,
            placeholder_text="e.g. 1001, Ari, Bishop",
            width=SEARCH_ENTRY_WIDTH,
        )
        self.search_entry.grid(row=0, column=1, sticky="w", padx=8, pady=12)
        self.search_entry.bind("<Return>", lambda _event: self._handle_lookup())
        self.employee_id_entry = self.search_entry

        self.search_button = ctk.CTkButton(
            search_row,
            text="Search",
            command=self._handle_lookup,
            width=SEARCH_BUTTON_WIDTH,
        )
        self.search_button.grid(row=0, column=2, padx=(8, 12), pady=12)

        self.match_selector = ctk.CTkOptionMenu(
            self.context_pane,
            values=["No matches"],
            command=self._handle_match_selection,
            width=MATCH_SELECTOR_WIDTH,
        )
        self.match_selector.grid_remove()

        self.match_cards_frame = ctk.CTkFrame(self.context_pane, width=MATCH_CARDS_WIDTH)
        self.match_cards_frame.grid(row=2, column=0, sticky="w", padx=16, pady=(8, 4))
        self.match_cards_frame.grid_remove()

        details = ctk.CTkFrame(self.context_pane, width=DETAILS_PANEL_WIDTH)
        details.grid(row=3, column=0, sticky="w", padx=16, pady=8)
        details.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(details, text="Selected Employee", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=12, pady=(8, 2), sticky="w"
        )
        self.employee_label = ctk.CTkLabel(details, text="None", anchor="w")
        self.employee_label.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

        ctk.CTkLabel(self.context_pane, text="Past Call-Outs").grid(
            row=4, column=0, sticky="w", padx=16, pady=(12, 4)
        )
        self.history_box = ctk.CTkTextbox(
            self.context_pane,
            width=HISTORY_BOX_WIDTH,
            height=HISTORY_BOX_HEIGHT,
            wrap="none",
        )
        self.history_box.grid(row=5, column=0, sticky="w", padx=16, pady=(0, 10))
        self.history_box.configure(state="disabled")

        self.action_zero_state_label = ctk.CTkLabel(
            self.action_pane,
            text="Please search and select an employee to begin.",
            anchor="w",
            justify="left",
            wraplength=ACTION_PANE_WIDTH - 32,
            font=ctk.CTkFont(weight="bold"),
            text_color=("#64748b", "#94a3b8"),
        )
        self.action_zero_state_label.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        recorded_by_header = ctk.CTkFrame(self.action_pane, fg_color="transparent")
        recorded_by_header.grid(row=1, column=0, sticky="w", padx=16, pady=(8, 4))
        ctk.CTkLabel(recorded_by_header, text="* Recorded By").grid(row=0, column=0, sticky="w")
        self.change_session_button = ctk.CTkButton(
            recorded_by_header,
            text="(Change)",
            width=80,
            height=24,
            command=self._toggle_session_edit,
            fg_color="transparent",
            text_color=("#2563eb", "#60a5fa"),
            hover_color=("#e2e8f0", "#334155"),
            corner_radius=6,
        )
        self.change_session_button.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.change_session_button.grid_remove()
        self.recorded_by_entry = ctk.CTkEntry(
            self.action_pane,
            placeholder_text="Manager name or ID",
            width=RECORDED_BY_WIDTH,
        )
        self.recorded_by_entry.grid(row=2, column=0, sticky="w", padx=16)
        self.recorded_by_entry.bind("<KeyRelease>", lambda _event: self._update_save_button_state())

        self.recorded_by_hint_label = ctk.CTkLabel(
            self.action_pane,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=("#64748b", "#94a3b8"),
        )
        self.recorded_by_hint_label.grid(row=3, column=0, sticky="w", padx=16, pady=(1, 0))

        ctk.CTkLabel(self.action_pane, text="Manager Notes (optional)").grid(
            row=4, column=0, sticky="w", padx=16, pady=(8, 4)
        )
        self.notes_box = ctk.CTkTextbox(
            self.action_pane,
            width=NOTES_BOX_WIDTH,
            height=NOTES_BOX_HEIGHT,
            font=ctk.CTkFont(family=NOTES_FONT_FAMILY, size=NOTES_FONT_SIZE),
        )
        self.notes_box.grid(row=5, column=0, sticky="w", padx=16)

        self.save_button = ctk.CTkButton(
            self.action_pane,
            text="Record Call-Out",
            command=self._open_verification_modal,
            fg_color=("#2563eb", "#1d4ed8"),
            hover_color=("#1d4ed8", "#1e40af"),
            text_color=("#ffffff", "#ffffff"),
            text_color_disabled=("#94a3b8", "#94a3b8"),
            height=SAVE_BUTTON_HEIGHT,
            corner_radius=8,
        )
        self.save_button.grid(row=6, column=0, sticky="ew", padx=16, pady=(12, 16))

        self.save_hint_label = ctk.CTkLabel(
            self.action_pane,
            text="Tip: Select an employee and enter Recorded By to record a call-out.",
            anchor="w",
            wraplength=DETAILS_PANEL_WIDTH,
        )
        self.save_hint_label.grid(row=7, column=0, sticky="w", padx=16, pady=(0, 12))

        self._update_action_zero_state()

    def _build_reporting_view(self) -> None:
        self.reporting_frame = ctk.CTkFrame(self)
        self.reporting_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        self.reporting_frame.grid_columnconfigure(0, weight=1)
        self.reporting_frame.grid_rowconfigure(2, weight=1)

        title = ctk.CTkLabel(
            self.reporting_frame,
            text="Employee Points Report",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

        controls = ctk.CTkFrame(self.reporting_frame)
        controls.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        controls.grid_columnconfigure(6, weight=1)

        ctk.CTkLabel(controls, text="Filter Name").grid(row=0, column=0, sticky="w", padx=(10, 6), pady=10)
        self.report_filter_entry = ctk.CTkEntry(controls, width=REPORT_FILTER_WIDTH, placeholder_text="Type employee name")
        self.report_filter_entry.grid(row=0, column=1, sticky="w", padx=(0, 8), pady=10)
        self.report_filter_entry.bind("<KeyRelease>", lambda _event: self._refresh_points_report())

        ctk.CTkLabel(controls, text="Sort By").grid(row=0, column=2, sticky="w", padx=(8, 6), pady=10)
        self.report_sort_by = ctk.CTkOptionMenu(
            controls,
            values=["Employee Name", "Employee ID", "Total Callouts", "Points Earned", "Last Updated"],
            width=REPORT_SORT_WIDTH,
            command=lambda _value: self._refresh_points_report(),
        )
        self.report_sort_by.grid(row=0, column=3, sticky="w", padx=(0, 8), pady=10)
        self.report_sort_by.set("Employee Name")

        self.report_sort_direction = ctk.CTkOptionMenu(
            controls,
            values=["Ascending", "Descending"],
            width=130,
            command=lambda _value: self._refresh_points_report(),
        )
        self.report_sort_direction.grid(row=0, column=4, sticky="w", padx=(0, 8), pady=10)
        self.report_sort_direction.set("Ascending")

        refresh = ctk.CTkButton(controls, text="Refresh", command=self._refresh_points_report)
        refresh.grid(row=0, column=5, sticky="w", padx=(0, 10), pady=10)

        table_frame = ctk.CTkFrame(self.reporting_frame)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        columns = ("employee_name", "employee_id", "total_callouts", "points_earned", "last_updated")
        self.points_report_tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self._update_report_header_indicators()
        self.points_report_tree.column("employee_name", width=240, anchor="w")
        self.points_report_tree.column("employee_id", width=120, anchor="center")
        self.points_report_tree.column("total_callouts", width=140, anchor="center")
        self.points_report_tree.column("points_earned", width=120, anchor="center")
        self.points_report_tree.column("last_updated", width=180, anchor="center")
        self.points_report_tree.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.points_report_tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.points_report_tree.configure(yscrollcommand=scroll.set)

        self._refresh_points_report()

    def _handle_report_header_click(self, sort_key: str) -> None:
        selected_label = REPORT_SORT_KEY_TO_LABEL.get(sort_key, "Employee Name")
        current_label = self.report_sort_by.get()
        current_direction = self.report_sort_direction.get()

        if current_label == selected_label:
            next_direction = "Descending" if current_direction == "Ascending" else "Ascending"
            self.report_sort_direction.set(next_direction)
        else:
            self.report_sort_by.set(selected_label)
            self.report_sort_direction.set("Ascending")

        self._refresh_points_report()

    def _update_report_header_indicators(self) -> None:
        sort_key = REPORT_SORT_LABEL_TO_KEY.get(self.report_sort_by.get(), "employee_name")
        is_desc = self.report_sort_direction.get() == "Descending"

        def header_text(label: str, column_key: str) -> str:
            if sort_key != column_key:
                return label
            return label + (REPORT_SORT_DESC_SYMBOL if is_desc else REPORT_SORT_ASC_SYMBOL)

        self.points_report_tree.heading(
            "employee_name",
            text=header_text("Employee Name", "employee_name"),
            command=lambda: self._handle_report_header_click("employee_name"),
        )
        self.points_report_tree.heading(
            "employee_id",
            text=header_text("Employee ID", "employee_id"),
            command=lambda: self._handle_report_header_click("employee_id"),
        )
        self.points_report_tree.heading(
            "total_callouts",
            text=header_text("Total Callouts", "total_callouts"),
            command=lambda: self._handle_report_header_click("total_callouts"),
        )
        self.points_report_tree.heading(
            "points_earned",
            text=header_text("Points Earned", "points_earned"),
            command=lambda: self._handle_report_header_click("points_earned"),
        )
        self.points_report_tree.heading(
            "last_updated",
            text=header_text("Last Updated", "last_updated"),
            command=lambda: self._handle_report_header_click("last_updated"),
        )

    def _build_status_bar(self) -> None:
        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        status_frame.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="",
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
            text_color=("#EF4444", "#EF4444"),
        )
        self.status_label.grid(row=0, column=0, sticky="ew", padx=12, pady=10)

    def _handle_view_change(self, view_name: str) -> None:
        self.current_view.set(view_name)
        if view_name == "Reporting":
            self.case_entry_frame.grid_remove()
            self.reporting_frame.grid()
            self._refresh_points_report()
        else:
            self.reporting_frame.grid_remove()
            self.case_entry_frame.grid()

    def _set_status(self, message: str, is_error: bool = False) -> None:
        text_color = ("#EF4444", "#EF4444") if is_error else ("#16A34A", "#16A34A")
        self.status_label.configure(text=f"Status: {message}", text_color=text_color)

    def _flash_save_success(self) -> None:
        self.save_button.configure(
            text="✓ Saved!",
            fg_color=("#16A34A", "#15803d"),
            hover_color=("#15803d", "#166534"),
        )
        self.after(1500, self._restore_save_button)

    def _restore_save_button(self) -> None:
        self.save_button.configure(
            text="Record Call-Out",
            fg_color=("#2563eb", "#1d4ed8"),
            hover_color=("#1d4ed8", "#1e40af"),
        )

    def _handle_runtime_error(self, user_message: str, context: str, exc: Exception) -> None:
        append_error_log(self.error_log_path, context, exc)
        messagebox.showerror("Database Error", user_message)
        self._set_status("Database unavailable", is_error=True)

    def _update_history_text(self, text: str) -> None:
        self.history_box.configure(state="normal")
        self.history_box.delete("1.0", "end")
        self.history_box.insert("1.0", text)
        self.history_box.configure(state="disabled")

    def _clear_match_cards(self) -> None:
        for widget in self.match_cards_frame.winfo_children():
            widget.destroy()

    def _render_match_cards(self, options: list[str]) -> None:
        self._clear_match_cards()
        ctk.CTkLabel(
            self.match_cards_frame,
            text="Select from matching employees:",
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 4))
        for idx, option in enumerate(options, start=1):
            ctk.CTkButton(
                self.match_cards_frame,
                text=option,
                command=lambda selected=option: self._handle_match_selection(selected),
                width=MATCH_CARDS_WIDTH - 24,
                anchor="w",
            ).grid(row=idx, column=0, sticky="w", padx=8, pady=2)

    def _show_sign_in_modal(self) -> None:
        modal = ctk.CTkToplevel(self)
        modal.title("Manager Sign In")
        modal.geometry("380x185")
        modal.grab_set()
        modal.resizable(False, False)
        modal.protocol("WM_DELETE_WINDOW", lambda: None)

        ctk.CTkLabel(modal, text="Sign in to begin your session:", anchor="w").pack(
            fill="x", padx=16, pady=(16, 8)
        )
        name_entry = ctk.CTkEntry(modal, placeholder_text="Your name")
        name_entry.pack(fill="x", padx=16, pady=(0, 4))
        error_label = ctk.CTkLabel(modal, text="", text_color=("#EF4444", "#EF4444"))
        error_label.pack(fill="x", padx=16)

        def sign_in() -> None:
            name = name_entry.get().strip()
            if not name:
                error_label.configure(text="Name is required to continue.")
                return
            self.session_manager = name
            modal.destroy()
            self._apply_session_manager()

        name_entry.bind("<Return>", lambda _event: sign_in())
        ctk.CTkButton(modal, text="Sign In", command=sign_in).pack(
            fill="x", padx=16, pady=(8, 16)
        )

    def _apply_session_manager(self) -> None:
        self.recorded_by_entry.configure(state="normal")
        self.recorded_by_entry.delete(0, "end")
        self.recorded_by_entry.insert(0, self.session_manager or "")
        self.recorded_by_entry.configure(state="disabled")
        self.change_session_button.configure(text="(Change)")
        self.change_session_button.grid()
        self.session_header_label.configure(text=f"Signed in as: {self.session_manager}")
        self._update_save_button_state()

    def _toggle_session_edit(self) -> None:
        current_state = self.recorded_by_entry.cget("state")
        if current_state == "disabled":
            self.recorded_by_entry.configure(state="normal")
            self.recorded_by_entry.focus()
            self.change_session_button.configure(text="Confirm")
        else:
            name = self.recorded_by_entry.get().strip()
            if not name:
                return
            self.session_manager = name
            self.recorded_by_entry.configure(state="disabled")
            self.change_session_button.configure(text="(Change)")
            self.session_header_label.configure(text=f"Signed in as: {self.session_manager}")
            self._update_save_button_state()

    def _update_action_zero_state(self) -> None:
        if self.current_employee_id is None:
            self.action_zero_state_label.configure(text="Please search and select an employee to begin.")
        else:
            self.action_zero_state_label.configure(text=f"Ready to record for: {self.current_employee_name}")

    @staticmethod
    def _is_exact_search_match(employee: dict[str, object], query: str) -> bool:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return False

        employee_id = str(employee.get("employee_id", "")).strip().lower()
        first_name = str(employee.get("first_name", "")).strip().lower()
        last_name = str(employee.get("last_name", "")).strip().lower()
        full_name = f"{first_name} {last_name}".strip()

        return normalized_query in {employee_id, first_name, last_name, full_name}

    def _refresh_points_report(self) -> None:
        sort_by = REPORT_SORT_LABEL_TO_KEY.get(self.report_sort_by.get(), "employee_name")
        sort_desc = self.report_sort_direction.get() == "Descending"
        name_filter = self.report_filter_entry.get()
        self._update_report_header_indicators()

        try:
            rows = self.service.get_employee_points_report(
                sort_by=sort_by,
                sort_desc=sort_desc,
                name_filter=name_filter,
            )
        except DatabaseAccessError as exc:
            self._handle_runtime_error(
                "Unable to load report because the database is unavailable.",
                "get_employee_points_report",
                exc,
            )
            rows = []

        for item_id in self.points_report_tree.get_children():
            self.points_report_tree.delete(item_id)

        for row in rows:
            self.points_report_tree.insert(
                "",
                "end",
                values=(
                    row["employee_name"],
                    row["employee_id"],
                    row["total_callouts"],
                    row["points_earned"],
                    row["last_updated"] or "",
                ),
            )

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
            self._set_status("Employee not found", is_error=True)
            return

        employee = payload["employee"]
        self.current_employee_id = employee["employee_id"]
        self.current_employee_name = f"{employee['first_name']} {employee['last_name']}"
        self.employee_label.configure(text=f"{self.current_employee_name} (ID: {self.current_employee_id})")
        self.match_selector.grid_remove()
        self.match_cards_frame.grid_remove()
        self._clear_match_cards()
        self._update_history_text(UiController.format_history(payload["history"], max_entries=HISTORY_MAX_ENTRIES))
        self._update_action_zero_state()
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
            self.match_map = {}
            self.match_selector.grid_remove()
            self.match_cards_frame.grid_remove()
            self._clear_match_cards()
            self.current_employee_id = None
            self.current_employee_name = ""
            self.employee_label.configure(text="None")
            self._update_action_zero_state()
            self._set_status("No employee matches found", is_error=True)
            if query.isdigit():
                should_add = messagebox.askyesno(
                    "Employee Not Found",
                    "Employee ID was not found. Add a new employee now?",
                )
                if should_add:
                    self._open_add_employee_modal(int(query))
            return

        if len(matches) == 1 and self._is_exact_search_match(matches[0], query):
            self.match_map = {}
            self.match_selector.grid_remove()
            self.match_cards_frame.grid_remove()
            self._clear_match_cards()
            self._load_employee(int(matches[0]["employee_id"]))
            return

        self.match_map = {
            f"{row['first_name']} {row['last_name']}  (ID: {row['employee_id']})": int(row["employee_id"])
            for row in matches
        }
        options = list(self.match_map.keys())
        self._render_match_cards(options)
        self.match_cards_frame.grid()
        self.current_employee_id = None
        self.current_employee_name = ""
        self.employee_label.configure(text="None")
        self._update_history_text("NONE")
        self._update_action_zero_state()
        self._update_save_button_state()
        if len(matches) == 1:
            self._set_status("Partial match found. Select employee to confirm.", is_error=True)
        else:
            self._set_status("Multiple matches found. Select employee.", is_error=True)

    def _handle_match_selection(self, selected: str) -> None:
        if self._suppress_match_selection:
            return

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
            except TrialExpiredError:
                messagebox.showerror(
                    "License Required",
                    "Your trial has expired. Please activate a license to add employees.",
                )
                return
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
        # Block writes when the trial has expired.
        state = self._get_entitlement_state()
        if state == EntitlementState.EXPIRED:
            self.save_button.configure(state="disabled")
            self.save_hint_label.configure(
                text="Trial expired. Activate a license to record call-outs."
            )
            self.recorded_by_hint_label.configure(text="", text_color=("#64748b", "#94a3b8"))
            return

        can_save = UiController.can_enable_save(
            current_employee_id=self.current_employee_id,
            recorded_by=self.recorded_by_entry.get(),
        )
        recorded_by_value = self.recorded_by_entry.get().strip()
        if recorded_by_value:
            self.recorded_by_hint_label.configure(
                text="✓ Set", text_color=("#16A34A", "#4ade80")
            )
        else:
            self.recorded_by_hint_label.configure(
                text="Required", text_color=("#EF4444", "#f87171")
            )
        if can_save:
            self.save_hint_label.configure(text="Ready: click Record Call-Out to open the verification modal.")
        else:
            if self.current_employee_id is None:
                self.save_hint_label.configure(text="Required action: Search and select an employee first.")
            elif not recorded_by_value:
                self.save_hint_label.configure(text="Required action: Enter Recorded By before saving.")
            else:
                self.save_hint_label.configure(text="Required action: complete all required fields.")

    def _open_verification_modal(self) -> None:
        if self.current_employee_id is None:
            self.save_hint_label.configure(text="Required action: Search and select an employee first.")
            return

        if not self.recorded_by_entry.get().strip():
            self.save_hint_label.configure(text="Required action: Enter Recorded By before saving.")
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
            except TrialExpiredError:
                modal.destroy()
                messagebox.showerror(
                    "License Required",
                    "Your trial has expired. Please activate a license to record call-outs.",
                )
                self._update_save_button_state()
                return
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
            self.recorded_by_entry.configure(state="normal")
            self.recorded_by_entry.delete(0, "end")
            self.notes_box.delete("1.0", "end")
            self._handle_lookup()
            self._refresh_points_report()
            if self.session_manager:
                self._apply_session_manager()
            else:
                self._update_save_button_state()
            self._set_status("Call-out saved")
            self._flash_save_success()

        ctk.CTkButton(button_row, text="Confirm", command=confirm_save).grid(
            row=0, column=0, sticky="ew", padx=(0, 8), pady=8
        )
        ctk.CTkButton(button_row, text="Cancel", command=modal.destroy).grid(
            row=0, column=1, sticky="ew", padx=(8, 0), pady=8
        )

def build_default_service() -> AttendanceService:
    """Build a file-backed service for desktop runtime usage."""
    override_path = os.getenv("ARC_DB_PATH")
    if override_path:
        db_path = Path(override_path)
    else:
        db_path = _resolve_default_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    db_manager = DatabaseManager(connection)
    db_manager.initialize_schema()

    override_config_path = os.getenv("ARC_CONFIG_PATH")
    if override_config_path:
        config_path = Path(override_config_path)
    else:
        config_path = _resolve_default_config_path()
    ensure_config_file(config_path)
    points_config = load_points_config(config_path)

    entitlement = EntitlementEngine(connection)
    return AttendanceService(db_manager, entitlement=entitlement, points_config=points_config)


def _resolve_app_storage_root() -> Path:
    """Resolve writable root directory for ARC runtime files."""
    if getattr(sys, "frozen", False):
        local_appdata = os.getenv("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "ARC"
        return Path.home() / "AppData" / "Local" / "ARC"

    return Path(__file__).resolve().parents[1]


def _resolve_default_db_path() -> Path:
    """Return default database path for source and packaged runtime modes."""
    return _resolve_app_storage_root() / "data" / "arc_data.db"


def _resolve_default_config_path() -> Path:
    """Return default runtime config path."""
    return _resolve_app_storage_root() / "config.ini"


def _resolve_default_log_path() -> Path:
    """Return default runtime error log path."""
    return _resolve_app_storage_root() / "error_log.txt"


def run_ui() -> None:
    """Launch the ARC desktop UI."""
    log_path = _resolve_default_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        service = build_default_service()
    except sqlite3.Error as exc:
        append_error_log(log_path, "build_default_service", exc)
        messagebox.showerror(
            "Startup Error",
            "ARC could not open the database file. Please check permissions and try again.",
        )
        return
    except PointsConfigError as exc:
        append_error_log(log_path, "load_points_config", exc)
        messagebox.showerror(
            "Configuration Error",
            "ARC configuration is invalid. Please update config.ini and restart.",
        )
        return

    app = ArcApp(service, entitlement=service.entitlement, error_log_path=log_path)
    app.mainloop()
