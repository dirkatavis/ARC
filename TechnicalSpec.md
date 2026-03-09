# Project ARC: Technical Specification (POC/MVP)

## 1. System Architecture
ARC uses a modular layered architecture.

- `database.py`: SQLite schema and persistence operations.
- `service.py`: business rules, validation, and reporting logic.
- `ui.py`: `customtkinter` desktop UI and interaction flow.

## 2. Data Schema (SQLite)

### `employees`
- `employee_id` INTEGER PRIMARY KEY UNIQUE
- `first_name` TEXT NOT NULL
- `last_name` TEXT NOT NULL

### `call_outs`
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `employee_id` INTEGER NOT NULL REFERENCES `employees(employee_id)`
- `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP
- `recorded_by` TEXT NOT NULL
- `notes` TEXT NULL

## 3. Functional Requirements

### Search
- Support query by:
  - Employee ID
  - First Name
  - Last Name
- History results are read-only.
- If no call-out history exists, return `NONE`.

### Save and Verification
- Save is enabled only when:
  - `Recorded By` has a value
  - call-out checkbox is checked
- Save action must open a mandatory verification modal.
- Cancel from modal must preserve unsaved input.

### Reporting Navigation
- Top 10 report must be on a separate Reporting screen/view.
- Intake and Reporting navigation should use explicit selection (for example, dropdown).
- Intake screen should not display unnecessary heading text like `Logger Console`.

### Reliability
- SQLite lock/permission failures must show user-friendly UI errors.
- Runtime failures should be appended to `error_log.txt`.

### Admin Policy
- No manager UI edit/delete.
- IT/Admin may manage corrections via SQL and admin scripts.

## 4. TDD and Testing Strategy
- Strict TDD workflow: Red -> Green -> Refactor.
- Service tests use `:memory:` SQLite fixtures.
- UI E2E tests are opt-in (`RUN_UI_E2E=1`) to keep CI stable.

Coverage targets:
- Duplicate Employee ID prevention
- `NONE` state for new employees
- Top 10 frequency sort/limit behavior
- Verification modal before write
- DB lock feedback behavior
- Post-save reset behavior

## 5. Project Structure
```text
/project_arc
├── main.py
├── src/
│   ├── database.py
│   ├── service.py
│   ├── ui.py
│   ├── ui_controller.py
│   ├── admin_import.py
│   └── error_logging.py
├── tests/
│   ├── test_service.py
│   ├── test_ui_controller.py
│   ├── test_ui_end_to_end.py
│   ├── test_ui_simple.py
│   ├── test_ui_smoke.py
│   └── test_admin_import.py
├── tools/
│   └── import_roster.py
└── data/
    └── arc_data.db
```
