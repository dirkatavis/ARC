# ARC (Attendance Recording Center)

ARC is a desktop application for managing employee call-out tracking and basic attendance-related reporting.

The app is built with:
- Python
- SQLite
- CustomTkinter

Primary workflows:
- Search employees by ID, first name, or last name
- Review call-out history
- Record a new call-out with verification
- View top 10 high-frequency call-out report
- Admin import and sample-data seeding utilities

---

## 1) Repository Layout

- `Launch_ARC.bat`  
  One-click Windows launcher that creates a local virtual environment (if needed), installs runtime dependencies, initializes database schema, and launches the app.

- `project_arc/main.py`  
  Runtime entry point for launching the desktop UI.

- `project_arc/src/`  
  Application code.
  - `ui.py` : Main CustomTkinter app and UI flow orchestration
  - `service.py` : Business logic and domain-level validation
  - `database.py` : SQLite boundary and data access methods
  - `ui_controller.py` : Pure formatting and UI decision helpers
  - `admin_import.py` : Bulk roster import behavior
  - `error_logging.py` : Runtime error log appending

- `project_arc/tools/`  
  Utility scripts.
  - `bootstrap_arc.py` : Runtime setup utility (dependency install, schema init, optional seed, optional launch)
  - `seed_sample_data.py` : Seed realistic demo data (including duplicate first and last name scenarios)
  - `import_roster.py` : CLI wrapper for roster CSV import

- `project_arc/tests/`  
  Test suites.
  - `test_ui_end_to_end.py` : UI workflow contract tests (gated by env flag)
  - `test_ui_simple.py` : UI-adjacent integration tests
  - `test_ui_controller.py` : Pure helper logic tests
  - `test_service.py` : Business layer tests
  - `test_admin_import.py` : Roster import tests
  - `test_ui_smoke.py` : Optional Windows automation smoke test (pywinauto)

- `project_arc/data/`  
  SQLite database location for local runs (`arc_data.db`).

---

## 2) Requirements

- Windows (current project launcher is Windows-oriented)
- Python 3.11+
- PowerShell or Command Prompt

Runtime dependencies are listed in:
- `project_arc/requirements.txt`

Dev/testing dependencies are listed in:
- `project_arc/requirements-dev.txt`

---

## 3) Quick Start (Windows)

From repository root:

1. Run:
   - `Launch_ARC.bat`

What this does:
- Creates `.venv` if missing
- Installs runtime dependencies
- Initializes DB schema
- Launches app

Important note:
- The launcher does not reset or reseed sample data by default.
- It initializes schema only.

---

## 3.1) Build a Customer `setup.exe`

For customer delivery, build a full installer package:

1. Install Inno Setup 6 on the build machine (ensure `iscc.exe` is on `PATH`).
2. From repo root, run:
  - `powershell -ExecutionPolicy Bypass -File project_arc/tools/build_setup.ps1 -Version 1.1.0 -Clean`
3. Deliver artifact:
  - `project_arc/dist/installer/ARC_Setup.exe`

Installer behavior for end users:
- Installs ARC under local user programs folder (no admin required)
- Creates Start Menu shortcut (desktop shortcut optional)
- Leaves ARC ready to launch from Start Menu or desktop shortcut

Runtime data location for installed app:
- Database: `%LOCALAPPDATA%\ARC\data\arc_data.db`
- Log file: `%LOCALAPPDATA%\ARC\error_log.txt`

See `project_arc/tools/INSTALLER_README.md` for full packaging notes.

---

## 4) Manual Setup and Run

From repository root:

1. Create virtual environment:
   - `py -3 -m venv .venv`

2. Activate environment:
   - `\.venv\Scripts\Activate.ps1`

3. Install dependencies:
   - `python -m pip install -r project_arc/requirements-dev.txt`

4. Initialize and launch (without sample seed):
   - `python project_arc/tools/bootstrap_arc.py --launch`

Alternative direct launch:
- `cd project_arc`
- `python main.py`

---

## 5) Database and Seed Data

### Default DB path
- `project_arc/data/arc_data.db`

### Seed sample data (with reset)
From repo root:
- `python project_arc/tools/seed_sample_data.py --db project_arc/data/arc_data.db --reset`

This seed includes:
- Employees with duplicate first names (example: multiple Ari)
- Employees with duplicate last names (example: multiple Smith, multiple Rivera)
- High-frequency call-out data for reporting validation

### Why this matters for QA
Many UI tests and manual repro cases depend on predictable data states.  
If you are validating duplicate-name behavior, reseed before test runs.

---

## 6) Environment Variables

- `ARC_DB_PATH`  
  Override DB location at runtime. Useful for isolated test runs.

- `RUN_UI_E2E=1`  
  Enables UI end-to-end tests that are intentionally gated.

---

## 7) Testing

### Full test suite
From `project_arc`:
- `python -m pytest -q`

### UI end-to-end tests (gated)
From `project_arc`:
- PowerShell:
  - `$env:RUN_UI_E2E='1'`
  - `python -m pytest tests/test_ui_end_to_end.py -q`

### Run one targeted UI test
Example:
- `python -m pytest tests/test_ui_end_to_end.py::test_multiple_matches_shows_selector_without_auto_loading -q`

### Optional Windows UI automation smoke test
- Install optional dependency manually if needed (pywinauto)
- Run with UI flag enabled:
  - `python -m pytest -q tests/test_ui_smoke.py`

---

## 8) Functional Notes for Developers

### Duplicate-name search behavior
When search returns multiple matches:
- The app should not auto-load the first result
- The app should show selector options
- User must explicitly choose the intended employee

This behavior is covered by UI tests for:
- Duplicate first-name paths
- Duplicate last-name paths

### Status messaging
Status label uses semantic coloring:
- Green for normal/success informational messages
- Red for error/exception states

### History box behavior
History display is read-only and supports vertical scrolling when content exceeds visible area.

---

## 9) Admin Roster Import

CLI utility:
- `python project_arc/tools/import_roster.py --db project_arc/data/arc_data.db --csv <path_to_csv>`

CSV header must include:
- employee_id
- first_name
- last_name

Import supports insert-or-update semantics by employee_id.

---

## 10) Troubleshooting

### App launches but expected seed data is missing
Cause:
- `Launch_ARC.bat` does not seed/reset by default.

Fix:
- Run seed script explicitly with reset (see Section 5).

### Duplicate-name behavior not appearing
Cause:
- Active DB does not contain duplicate records for query.

Fix:
- Verify data with a quick SQLite query, then reseed if needed.

### UI tests skip unexpectedly
Cause:
- `RUN_UI_E2E` not set to 1.

Fix:
- Set env var before running UI tests.

### Tkinter/Tcl errors in some environments
Cause:
- Local Python/Tk installation mismatch.

Fix:
- Use repository virtual environment and consistent Python installation.

---

## 11) Suggested Developer Workflow

1. Create a feature branch from main.
2. Reproduce issue with a failing test where possible.
3. Implement fix.
4. Run targeted tests, then broader suite.
5. Commit with focused scope.
6. Push and open PR.
7. After merge, clean up local and remote feature branch.

---

## 12) Reference Documents

For broader product context, see:
- `BusinessRequirements.md`
- `TechnicalSpec.md`
- `Personas/`
