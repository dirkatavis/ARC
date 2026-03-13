# Project ARC: Business Requirements (POC)

## 1. Core Data Points
ARC must capture the following data:
- Employee ID (primary lookup key)
- First Name
- Last Name
- Call-Out Timestamp (system generated: `YYYY-MM-DD HH:MM:SS`)
- Recorded By (manager name/ID)
- Manager Notes

## 2. Golden Workflow (Safety-First)
1. Manager searches by employee criteria.
2. ARC displays employee history in read-only form.
3. If history is empty, ARC explicitly displays `NONE`.
4. Manager enters `Recorded By` and Notes.
5. ARC displays mandatory verification summary modal before commit.
6. On confirm, ARC writes call-out and resets intake fields.

## 2.1 Trial and Licensing Workflow
- During active trial, ARC remains fully functional and visibly indicates trial status.
- If trial expires, ARC shifts to read-only mode until a valid license is activated.

## 3. Search Requirements
- Search must support:
  - Employee ID
  - First Name
  - Last Name
- Search should remain fast and keyboard-friendly for shift operations.

## 4. UI/Navigation Requirements
- Remove intake header text labeled `Logger Console`; no title is required there.
- `Top 10 High-Frequency` must be on a separate Reporting view/screen.
- Navigation between Intake and Reporting must be explicit (for example, dropdown selector).

## 5. Reporting and Analytics
- High-Frequency Report: Top 10 employees by call-out count.
- Individual Audit: searchable employee history in read-only format.

## 6. Admin and Governance
- No manager-facing UI support for edit/delete.
- IT/Admin performs corrections via direct SQL or approved admin scripts.
- IT/Admin monitors runtime `error_log.txt` entries.

## 7. Technology Stack
- Backend: Python + `sqlite3`
- Frontend: `customtkinter`
- Storage: local SQLite file (`arc_data.db`)
