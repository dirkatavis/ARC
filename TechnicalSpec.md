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
- Save action must open a mandatory verification modal.
- Cancel from modal must preserve unsaved input.
- Trial mode is fully functional and displays clear trial-status messaging.
- Expired trial mode blocks write operations while preserving read-only access.

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

## 5. Licensing Architecture (Module 07)

### Overview

ARC uses a **hardware-locked challenge-response** licensing model implemented in `src/entitlement.py`. The engine manages three states: `TRIAL`, `EXPIRED`, and `LICENSED`.

### License States

| State | Condition | User Impact |
|---|---|---|
| `TRIAL` | Within 15 days of first launch | Full read/write access; trial banner shown |
| `EXPIRED` | More than 15 days since first launch, no valid key | Read-only mode; blocking modal on startup |
| `LICENSED` | Valid activation key stored and verified against machine ID | Full read/write access; "✓ Licensed" banner |

### Machine Fingerprinting

`get_machine_id()` produces a stable identifier for each machine:
- **Windows**: reads `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`
- **Other platforms**: generates and persists a UUID at `~/.arc_machine_id`

The machine ID is stored in the `sys_entitlement` table at first launch and re-validated on every startup to detect database copying.

### Database Schema

The entitlement row lives in the same SQLite database as application data (`arc_data.db`):

```sql
CREATE TABLE sys_entitlement (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    install_date  TEXT    NOT NULL,   -- ISO date of first launch
    machine_id    TEXT    NOT NULL,   -- hardware fingerprint at install time
    is_licensed   INTEGER NOT NULL DEFAULT 0,
    license_key   TEXT               -- stored in XXXX-XXXX-XXXX format
);
```

### Key Generation Algorithm

Activation keys are deterministic HMAC-SHA256 derivations:

1. Input: `machine_id` (uppercased) + internal `_SALT` constant
2. Output: first 12 hex characters of the HMAC digest, formatted as `XXXX-XXXX-XXXX`
3. Verification uses `hmac.compare_digest` to prevent timing attacks

The same machine ID always produces the same key. Keys are machine-specific and cannot be shared between installations.

### State Transitions

```
First launch  → TRIAL
TRIAL (>15d)  → EXPIRED
EXPIRED + valid key → LICENSED
TRIAL + valid key   → LICENSED
LICENSED (DB moved to different machine) → EXPIRED
```

### Runtime Wiring

`run_ui()` in `ui.py` constructs `EntitlementEngine(connection)` using the same SQLite connection as `DatabaseManager`, then passes it to both `AttendanceService` (write-gate enforcement) and `ArcApp` (UI state display). The entitlement check at startup fires 100 ms after window creation via `self.after(100, self._check_entitlement_on_startup)`.

### Developer Key Generation

To generate a license key for a customer machine, use the `generate_license_key` function in `src/entitlement.py`:

```python
from src.entitlement import generate_license_key
key = generate_license_key("<MACHINE-ID-FROM-CUSTOMER>")
print(key)  # e.g. A1B2-C3D4-E5F6
```

Run from the repository root with the virtual environment active:

```powershell
.venv\Scripts\python.exe -c "from src.entitlement import generate_license_key; print(generate_license_key('PASTE-MACHINE-ID-HERE'))"
```

The `_SALT` constant in `entitlement.py` must remain unchanged after production deployment. Changing it invalidates all previously issued keys.

### Manual Activation Test Procedure

Because the activation key is bound to the specific machine being tested, the tester must generate the correct key before starting either scenario.

**Prerequisite — Generate the key for the test machine**

On the developer machine, run from the repository root, substituting the Machine ID shown in the ARC License Management dialog on the test machine:

```powershell
.venv\Scripts\python.exe -c "from src.entitlement import generate_license_key; print(generate_license_key('PASTE-MACHINE-ID-HERE'))"
```

The output is the activation key for that machine, e.g. `A1B2-C3D4-E5F6`. Keep this ready for both scenarios below.

---

#### Scenario A — Activate during the trial period

Start with a fresh install where the trial has not yet expired (install date is within the last 15 days).

| # | Action | Expected Result |
|---|---|---|
| 1 | Launch ARC | Orange trial status text visible in nav bar with days remaining |
| 2 | Click **Activate License** | License Management dialog opens |
| 3 | Confirm **Machine ID** field is populated | Machine ID shown and cannot be edited |
| 4 | Click **Copy** | Machine ID copied to clipboard; button briefly shows "Copied!" |
| 5 | Enter a wrong key (e.g. `XXXX-XXXX-XXXX`) and click **Activate** | Red text: "Invalid Key. Please verify and try again." |
| 6 | Enter the correct key and click **Activate** | Green text: "✓ Activation successful! ARC is now fully licensed." |
| 7 | Close the dialog | Nav bar status text changes to green **✓ Licensed** |
| 8 | Close and relaunch ARC | App starts without any trial dialog; nav bar shows **✓ Licensed** |

---

#### Scenario B — Activate after the trial has expired

To simulate an expired trial without waiting 15 days, use the PowerShell test utility:

```powershell
powershell -ExecutionPolicy Bypass -File project_arc/tools/ArcTrialPeriodAdjuster.ps1 -Days 16
```

If `sqlite3.exe` is not on `PATH`, provide it explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File project_arc/tools/ArcTrialPeriodAdjuster.ps1 -Days 16 -SqliteExe "C:\path\to\sqlite3.exe"
```

Then relaunch ARC and proceed:

| # | Action | Expected Result |
|---|---|---|
| 1 | Launch ARC | Blocking "Trial Expired" dialog appears; main window is inaccessible |
| 2 | Click **Continue in Read-Only Mode** | Dialog closes; app is usable but write actions are blocked |
| 3 | Attempt to log a call-out | Error or save button is disabled — write is blocked |
| 4 | Click **Activate License** in the nav bar | License Management dialog opens |
| 5 | Enter the correct key and click **Activate** | Green text: "✓ Activation successful! ARC is now fully licensed." |
| 6 | Close the dialog | Nav bar status text changes to green **✓ Licensed**; write operations re-enabled |
| 7 | Close and relaunch ARC | App starts without any trial dialog; nav bar shows **✓ Licensed** |

## 6. Project Structure
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
