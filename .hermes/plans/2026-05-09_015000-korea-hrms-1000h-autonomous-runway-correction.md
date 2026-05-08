# Korea HRMS 1,000h autonomous runway correction

Status: active source-of-truth correction after Gate 1 landed on `develop`.

## Verified repo state

- Repo: `/home/ubuntu/workspaces/seojaehong-hrms-100h`
- Base branch: `develop`
- Current `develop` head: `4226bc967 feat: add Korea payroll closing runtime read UI bridge (#151)`
- Gate 1 is merged to `develop`.
- Runtime bridge files are tracked:
  - `frontend/src/data/koreaPayrollClosingRuntime.js`
  - `frontend/tests/koreaPayrollClosingRuntime.test.mjs`
- Gate 1 snapshot is tracked:
  - `.hermes/plans/2026-05-08_162000-gate-1-runtime-read-ui-bridge-snapshot.md`

## Correction from earlier plan branches

Previous roadmap/grill plan work existed on a plan branch and not all plan notes were present on `develop`. `HERMES_WORKSPACE.md` on `develop` was also stale and still referenced `/home/ubuntu/workspaces/frappe-hrms` as the primary repo.

This correction makes `develop` the operational source of truth again and aligns cron with the already-merged Gate 1 state.

## Autonomous operating model

Two cron jobs remain the main autonomous runway:

1. `frappe-hrms-1000h-saas-agentic-productization-runway`
   - cadence: every 30 minutes
   - role: implementation, tests, commit, push, PR URL
   - current priority: Gate 2
2. `frappe-hrms-1000h-pdca-briefing-grill`
   - cadence: every 30 minutes
   - role: grill/checkpoint against docs, risks, stale assumptions, next gate

Live Telegram work can override or accelerate the cron, but the cron should continue from the same gate queue without inventing a different roadmap.

## Current gate status

### Gate 1 — Runtime-read UI bridge

Status: done and merged.

Evidence:
- `develop` includes `4226bc967 feat: add Korea payroll closing runtime read UI bridge (#151)`.
- Bridge calls `hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime` when Frappe runtime is available.
- Static fixture fallback is retained for Vercel/static preview.
- Boundary remains read-only: no save/approve/send/database mutation.

### Gate 2 — Worklist/session runtime bridge

Status: next.

Goal:
- Bind actual payroll closing worklist/session rows to the Korea payroll closing queue/detail UI.
- Preserve fixture fallback until bench/browser runtime verification is green.
- Keep evidence packet preview read-only.
- Keep session routes stable and route-safe.

Implementation discipline:
- Start from clean `develop`.
- Create PR-sized branch, likely `feat/korea-payroll-closing-worklist-runtime-bridge`.
- Write tests first where possible for data normalization/contract validation.
- Do not remove static fixtures until runtime worklist is verified.
- Do not add mutation paths in this gate.

### Gate 3 — Salary Slip statutory apply hook

Status: after Gate 2.

Notes:
- Existing preview adapter exists in `payroll_salary_slip_adapter.py`.
- Missing piece is idempotent `apply_korea_statutory_to_salary_slip` and scoped hook registration.
- This is a real mutation path; TDD and small PR are mandatory.

### Gate 4 — Demo seed blocker realism

Status: after Gate 3 or parallel only if isolated.

Goal:
- Seed blocker-generating transaction data: Attendance absence/unclosed, overtime pending approval, unsettled Expense Claim.
- Keep seed idempotent.

### Gate 5 — Korea test/CI harness

Status: after core Gate 2/3 boundaries or earlier if test execution blocks progress.

Known issue:
- The active Hermes Python previously lacked `pytest`; test execution environment must be explicit rather than assumed.

## Guardrails

- Korean business logic stays under `hrms/regional/south_korea/`.
- Do not modify `hrms/__init__.py` to bypass Frappe imports.
- AI is assistant-only.
- AI must not directly mutate DB.
- Runtime mutation paths must follow preview/read-only -> human approval -> apply.
- Do not store full resident-registration numbers or secrets.
- Avoid numeric AI confidence for HR/legal decisions; use evidence status and human review requirements instead.

## Next action

Proceed with Gate 2 from `develop`:

```text
feat/korea-payroll-closing-worklist-runtime-bridge
```

Expected deliverables:
- runtime worklist/session data adapter or normalizer
- UI binding with runtime primary + fixture fallback
- focused frontend/unit test
- `yarn build` verification
- commit/push/PR URL
