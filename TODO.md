# ARC UX/UI Improvement TODO

This TODO tracks implementation of UI/UX architecture feedback in incremental, testable slices.

## Guiding Principle
Move from a form-first layout to a workflow-first layout while preserving existing behavior and test coverage.

## Backlog

### 1) Two-pane Case Entry layout (Context + Action)
- [x] Split current single-column Case Entry view into:
  - Left pane: Search, selected employee context, call-out history
  - Right pane: New call-out action form
- [x] Keep existing widget ids/variables where possible to avoid breaking tests.
- [x] Keep duplicate-match selection flow behavior unchanged.
- [x] Validate with UI e2e tests.

### 2) Search UX enhancements
- [x] Replace passive selected text with richer "selected employee card" presentation.
- [x] Add duplicate-result resolution cards/list with clickable options (ID + name; department later if available).
- [x] Add no-selection zero-state guidance in action pane.

### 3) Recording form workflow improvements
- [x] Add session-level manager identity (sign-in once per app session).
- [x] Auto-fill Recorded By from session.
- [x] Make Recorded By read-only by default; enable controlled edit mode.
- [x] Evaluate replacement of Log Call-Out checkbox with validation-driven Confirm & Save enablement.

### 4) Visual hierarchy and feedback refinements
- [ ] Reposition status indicator to top-right header or standardized footer treatment.
- [ ] Improve notes entry readability (font sizing/monospace evaluation).
- [ ] Normalize primary action button sizing and completed-state feedback color.

### 5) Information architecture alignment
- [ ] Global header with view selector + manager session info.
- [ ] Search result list optimized for duplicate-name disambiguation.
- [ ] History panel constrained to recent entries, with scroll.
- [ ] Action form with top-aligned labels and auto-validation messaging.

## Delivery Strategy
- Implement one section at a time.
- Keep each section as a focused PR.
- Ensure targeted tests pass before moving to next section.
