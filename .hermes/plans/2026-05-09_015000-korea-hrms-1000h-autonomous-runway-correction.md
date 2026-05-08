# Korea HRMS 1,000h autonomous runway correction

Status: active source-of-truth correction after Gate 4 landed on `develop`.

## Verified repo state

- Repo: `/home/ubuntu/workspaces/seojaehong-hrms-100h`
- Base branch: `develop`
- Latest product gate commit on `develop`: `b971c3af8 feat(korea): seed realistic demo payroll blockers (#157)`
- Gate 1 is merged to `develop`.
- Gate 2 is merged to `develop`.
- Gate 3 is merged to `develop`.
- Gate 4 is merged to `develop`.
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
   - current priority: Gate 5
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

Status: done and merged.

Goal:
- Bind actual payroll closing worklist/session rows to the Korea payroll closing queue/detail UI.
- Preserve fixture fallback until bench/browser runtime verification is green.
- Keep evidence packet preview read-only.
- Keep session routes stable and route-safe.

Evidence:
- `develop` includes `d14ee6dd2 feat: add Korea payroll closing worklist runtime bridge (#152)`.
- `hrms/regional/south_korea/payroll_closing_worklist_runtime_api.py` reads scoped `Korea Payroll Closing Draft` rows into the existing worklist/session contracts.
- `frontend/src/data/koreaPayrollClosingRuntime.js` normalizes runtime worklist/session payloads for the operator UI.
- `frontend/src/views/KoreaPayrollClosing.vue` uses runtime worklist rows when available and keeps the static fixture fallback otherwise.
- Boundary remains read-only for this gate: no save/approve/send/payroll submission/provider mutation.

Closeout discipline:
- Keep Gate 2 as a read-only/runtime-read bridge.
- Preserve static fixture fallback until positive bench/browser runtime rows are verified.
- Do not reinterpret Gate 2 as a mutation/apply boundary.
- If hardening is needed, add focused tests around the runtime worklist/session normalizer before UI changes.

### Gate 3 — Salary Slip statutory apply hook

Status: done and merged.

Evidence:
- `develop` includes `3fc50a300 feat: add Korea salary slip statutory apply hook (#154)`.
- `payroll_salary_slip_adapter.py` adds `apply_korea_statutory_to_salary_slip()` for idempotent draft Salary Slip deduction-row application.
- `apply_korea_salary_slip_statutory_hook()` is opt-in, KR-scoped, actor-required, and rejects malformed payloads before row mutation.
- `hrms/hooks.py` registers the hook on `Salary Slip.before_validate`.
- Boundary remains row-only: no save/submit/approve/send/provider call.

Closeout discipline:
- Treat Gate 3 as a narrow apply-boundary hook, not payroll submission or approval automation.
- Keep human/operator control around the opt-in flag and actor.
- Runtime/bench verification is still needed before treating this as production payroll close automation.

### Gate 4 — Demo seed blocker realism

Status: done and merged.

Goal:
- Seed blocker-generating transaction data: Attendance absence/unclosed, overtime pending approval, unsettled Expense Claim.
- Keep seed idempotent.
- Preserve fixture/runtime fallback clarity until bench/browser runtime verification is green.

Evidence:
- `develop` includes `b971c3af8 feat(korea): seed realistic demo payroll blockers (#157)`.
- `hrms/regional/south_korea/demo_seed.py` creates realistic demo blocker transactions for the Korea payroll closing operator flow.
- `hrms/tests/test_korea_demo_seed_blockers.py` covers idempotency and the explicit demo-only/no-submit/no-approve/no-send/no-provider boundary.
- Boundary remains demo seed only: no payroll approval/submission/provider automation.

### Gate 5 — Korea test/CI harness

Status: next.

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

Proceed with Gate 5 from `develop`:

```text
ci/korea-regional-smoke-harness
```

Expected deliverables:
- failing direct Python tests first for any harness behavior changes
- a cron/CI-safe Korea regional smoke command that uses the current interpreter and dynamic `test_korea*.py` discovery
- fail-closed behavior when no direct Korea targets are found
- optional bench/runtime probes kept behind explicit flags or availability checks
- commit/push/PR URL
