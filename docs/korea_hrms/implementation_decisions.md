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
