🛰️ Project ARC: Attendance Recording Center (POC)
1. The "Big Six" Data Points
To keep the database lightweight and the UI fast, ARC will capture:

Employee ID: The unique "Primary Key" for all lookups.

First Name: Linked to the ID.

Last Name: Linked to the ID.

Call-Out Timestamp: System-generated YYYY-MM-DD HH:MM:SS.

Recorded By: The name/ID of the manager logging the call.

Manager Notes: Contextual text for the specific occurrence.

2. The Golden Workflow (The "Safety-First" Path)
Search: Manager enters Employee ID.

History Review: ARC displays previous dates + notes (or "NONE" if empty).

Data Intake: Manager enters their name and specific notes, then clicks the "Log Call-Out" checkbox.

Verification Screen: A modal pops up showing exactly what is about to be saved.

Commit: Upon "Confirm," ARC saves to the SQLite database and clears the form.

3. Reporting & Analytics
High-Frequency Attendance Report: A neutral view of the Top 10 employees with the most entries in the system.

Individual Audit: A searchable history by Employee ID, optimized for a "Read-Only" view for managers.

4. Technical Stack (POC Recommendations)
Backend: Python with the sqlite3 library.

Frontend: customtkinter (for a modern Windows look) or tkinter.

Database: A local arc_data.db file.

Admin/IT: Direct database access via SQL for any necessary record corrections.