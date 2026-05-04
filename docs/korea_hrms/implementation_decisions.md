# Korea HRMS Implementation Decisions

## PR-1 Workplace & Employment Profile

Decision: native DocType scaffold under `hrms/hr/doctype`.

Reason: PR-1 needs a stable Korean domain layer that downstream leave, payroll, attendance, contract, dashboard, and approval features can reference without overloading upstream `Employee`, `Company`, or `Branch` semantics.

Scope:
- Add schema-only `Korea Workplace Profile`.
- Add schema-only `Korea Employment Profile`.
- Add isolated schema tests that do not require a running Frappe bench.

Reversibility:
- Remove the two DocType directories.
- Remove `tests/test_korea_hrms_profiles.py`.
- Remove this decision note if no longer needed.

Downstream users:
- Korea annual leave engine
- Korea attendance summary and monthly closing
- Korea payroll rule engine
- Korea employment contract generation
- Unified approval inbox
- Admin dashboard

## PR-3 Attendance Summary & Monthly Closing

Decision: keep the Korea attendance closing core framework-free first.

Reason: PR-3 establishes the monthly attendance closing contract that downstream payroll, admin dashboard, and notification features can consume. It should not depend on a running Frappe bench, UI workspace, workflow state, or Salary Slip posting yet.

Scope:
- Add `hrms/regional/south_korea/attendance_summary.py` as a pure Python core.
- Calculate Korea workplace cutoff-based attendance closing periods.
- Summarize normalized attendance records by employee.
- Preserve late, early-exit, overtime, holiday-work, weekly-off-work, half-day, and unresolved half-day signals for downstream payroll/compliance use.
- Build deterministic side-effect-free closing snapshot payloads.
- Add direct-run tests under `hrms/tests/test_korea_attendance_summary.py`.

Non-goals:
- No new DocType, migration, Workspace, workflow, or Salary Slip posting in this PR.
- No Korean overtime premium, night-work, holiday-work pay calculation in this PR.
- No Frappe adapter/query layer until the pure closing contract is stable.

Reversibility:
- Remove `hrms/regional/south_korea/attendance_summary.py`.
- Remove `hrms/tests/test_korea_attendance_summary.py`.
- Remove this PR-3 decision note.
