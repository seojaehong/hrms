# Korea HRMS 1,000h autonomous runway correction

Status: active source-of-truth correction after Gate 13 demo credential handoff landed on `develop`; next implementation gate is human-approved demo credential apply plus authenticated browser runtime proof.

## Verified repo state

- Repo: `/home/ubuntu/workspaces/seojaehong-hrms-100h`
- Base branch: `develop`
- Latest product gate commit on `develop`: `15f9c24a7 test: add Korea demo browser credential handoff (#185)`.
- Latest source-of-truth alignment commit on `develop`: `9db012fa4 docs: align Gate 13 credential handoff state (#186)`.
- Gate 1 is merged to `develop`.
- Gate 2 is merged to `develop`.
- Gate 3 is merged to `develop`.
- Gate 4 is merged to `develop`.
- Gate 5 is merged to `develop`.
- Gate 6 is merged to `develop`.
- Gate 7 closeout hardening is merged to `develop`.
- Gate 8 runtime ownership evidence is merged to `develop`.
- Gate 9 runtime handoff evidence path is merged to `develop`.
- Gate 10 Docker source-alignment, runtime-probe hardening, and positive scoped runtime-row capture are merged to `develop`.
- Gate 11 runtime-positive operator UI/browser closeout is merged to `develop`.
- Gate 12 browser runtime verifier is merged to `develop`.
- Gate 13 demo employee browser credential handoff is merged to `develop`.
- Runtime bridge files are tracked:
  - `frontend/src/data/koreaPayrollClosingRuntime.js`
  - `frontend/tests/koreaPayrollClosingRuntime.test.mjs`
- Gate 1 snapshot is tracked:
  - `.hermes/plans/2026-05-08_162000-gate-1-runtime-read-ui-bridge-snapshot.md`

## Correction from earlier plan branches

Previous roadmap/grill plan work existed on a plan branch and not all plan notes were present on `develop`. `HERMES_WORKSPACE.md` on `develop` was also stale and still referenced `/home/ubuntu/workspaces/frappe-hrms` as the primary repo.

The original correction made `develop` the operational source of truth after Gate 1; this update advances the same runway after Gate 13 demo credential handoff closeout and aligns cron with Gate 14 human-approved credential apply plus authenticated browser runtime proof.

## Autonomous operating model

Two cron jobs remain the main autonomous runway:

1. `frappe-hrms-1000h-saas-agentic-productization-runway`
   - cadence: every 30 minutes
   - role: implementation, tests, commit, push, PR URL
   - current priority: Gate 14 human-approved demo credential apply plus authenticated browser runtime proof
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

Status: done and merged.

Evidence:
- `develop` includes `17c4bc7e5 ci: harden Korea regional smoke reporting (#159)`.
- `scripts/run_korea_regional_smoke.py` discovers Korea direct-run tests dynamically, excludes the harness self-test, uses the current interpreter for subprocess commands, and fails closed when no direct targets are found.
- The harness can write a JSON report artifact via `--report-file`, including `python_executable`, direct target count, per-command results, and pass/fail state for cron/CI diagnostics.
- Optional bench smoke remains behind explicit `--include-bench --site ...`; no-bench direct coverage is not weakened.

Closeout discipline:
- Treat Gate 5 as harness/reporting hardening, not proof of bench/browser runtime health.
- Keep using direct file execution for framework-free Korea tests in cron/no-bench environments.
- Runtime verification remains a separate gate.

### Gate 6 — Phase 1 runtime/bench verification checkpoint

Status: done and merged.

Goal:
- Verify the payroll closing runtime-read/worklist path against a real Bench/Docker runtime when available.
- Confirm seeded demo blocker rows surface through the read-only operator worklist/session UI.
- Preserve static fixture fallback when positive runtime rows are absent.
- Document runtime prerequisites and blockers without weakening the no-bench smoke harness.
- Keep evidence/session views read-only: no save/approve/send/payroll submit/provider calls.

Evidence:
- `develop` includes `7c4dd63c2 test: add Korea payroll closing runtime verification checkpoint (#161)`.
- `scripts/verify_korea_payroll_closing_runtime.py` records Docker Compose status and optionally bench-executes the read-only payroll closing worklist runtime API.
- `hrms/tests/test_korea_runtime_verification_checkpoint.py` covers no-bench direct behavior, missing executables, Docker Compose parsing, bench command safety/redaction, and fail-closed skipped-command semantics.
- PR #161 runtime evidence: Docker Compose returned no running Frappe service rows and `bench` was unavailable in the cron environment. Therefore runtime verification is still not green and fixture fallback remains required until positive runtime rows are proven.
- Safety boundary remains read-only: no save/submit/approve/send/provider/payroll document mutation.

Closeout discipline:
- Treat Gate 6 as a checkpoint/evidence gate, not a runtime success claim.
- Do not remove static fixture fallback until a real Bench/Docker runtime returns positive scoped `Korea Payroll Closing Draft` rows through the read-only worklist/session path.
- Keep runtime reports redacted; do not leak payroll/HR row payloads into cron artifacts.

### Gate 7 — Phase 1 runtime blocker closeout / positive bench evidence hardening

Status: done and merged.

Goal:
- Resolve or document the Gate 6 blockers: no running Frappe Docker Compose service rows and no `bench` executable in the cron environment.
- Prevent skipped runtime commands or malformed runtime output from being reported as green.
- Run the read-only runtime verification checkpoint against an available Bench/Docker runtime when safe.
- Confirm seeded demo blocker rows surface through the read-only payroll closing worklist/session UI only after positive runtime rows exist.
- Preserve fixture fallback and clear fallback labeling while runtime rows remain absent.
- Preserve no-bench direct tests and the Korea regional smoke harness as the baseline regression net.
- Keep evidence/session views read-only: no save/approve/send/payroll submit/provider calls.

Evidence:
- `develop` includes `2f1cc60b5 test: harden payroll closing runtime evidence gate (#163)`.
- `scripts/verify_korea_payroll_closing_runtime.py` distinguishes skipped command checks from passed checks, parses Docker Compose service state, summarizes closeout blockers, and only marks the gate passed when positive runtime worklist rows are verified.
- `hrms/tests/test_korea_runtime_verification_checkpoint.py` covers running/stopped/non-Frappe Docker service output, missing bench, bench command failure, positive runtime rows, and malformed runtime rows.
- Focused test and Korea regional smoke passed after merge.
- Live positive Bench/Docker row evidence is still not proven on this cron host; fixture fallback remains required until an authoritative runtime returns scoped `Korea Payroll Closing Draft` rows.

Closeout discipline:
- Treat Gate 7 as false-green/runtime-evidence hardening, not full live runtime completion.
- Do not remove static fixture fallback until a real Bench/Docker runtime returns positive scoped rows through the read-only worklist/session path.
- Keep runtime reports redacted; do not leak payroll/HR row payloads into cron artifacts.

### Gate 8 — Phase 1 live runtime evidence / Bench environment ownership

Status: done and merged.

Goal:
- Establish which runtime is authoritative for the 100h workspace: local Docker Compose, an existing Bench site, or a separate operator-provided runtime.
- Make the runtime verification checkpoint executable against that runtime without weakening no-bench cron tests.
- Produce positive read-only evidence only when scoped `Korea Payroll Closing Draft` rows are actually returned through the runtime worklist/session path.
- Preserve fixture fallback and clear fallback labeling while runtime rows remain absent or unverified.
- Keep evidence/session views read-only: no save/approve/send/payroll submit/provider calls.

Evidence:
- `develop` includes `b5926a910 test: add Korea payroll closing runtime ownership evidence (#165)`.
- `scripts/verify_korea_payroll_closing_runtime.py` returns a report-safe `runtime_ownership` decision with `authoritative_runtime`, `decision_status`, evidence, and next actions.
- `hrms/tests/test_korea_runtime_verification_checkpoint.py` covers blocked `operator_provided_runtime_required` ownership when Docker/Bench are absent and verified `local_docker_compose_bench` ownership when Docker plus positive read-only worklist rows are available.
- Current cron-host evidence after #165 remained blocked: Docker Compose had no running Frappe service rows, `bench` was unavailable, and no positive scoped runtime rows were returned.
- Fixture fallback remained required until an authoritative runtime returned scoped `Korea Payroll Closing Draft` rows through the read-only worklist/session path.

Closeout discipline:
- Treat Gate 8 as ownership/evidence decision hardening, not positive live runtime completion.
- Do not remove static fixture fallback until a real Bench/Frappe runtime returns positive scoped rows through the read-only worklist/session path.
- Keep runtime reports redacted; do not leak payroll/HR row payloads into cron artifacts.

### Gate 9 — Runtime handoff / positive row evidence path

Status: done and merged.

Goal:
- Connect the verification checkpoint to an explicit authoritative runtime handoff target without relying on cron-host guessing.
- Run the existing read-only worklist/session probe when handoff data is supplied.
- Preserve no-bench direct tests and redacted report artifacts.
- Produce positive runtime-row evidence only when the runtime API actually returns scoped rows through the read-only worklist path.
- Preserve fixture fallback and clear fallback labeling while runtime rows remain absent or unverified.
- Keep evidence/session views read-only: no save/approve/send/payroll submit/provider calls.

Evidence:
- `develop` includes `0da583aea test: add Korea runtime handoff evidence path (#167)`.
- `scripts/verify_korea_payroll_closing_runtime.py` accepts a report-safe `runtime_handoff` contract for `operator_provided_bench` or `local_docker_compose_bench`, forces `include_bench` with supplied site/company scope, and redacts sensitive command arguments.
- `hrms/tests/test_korea_runtime_verification_checkpoint.py` covers handoff validation, invalid handoff rejection, and a mocked positive operator-provided bench path where `fixture_fallback_required_until_positive_runtime_rows` becomes false only after positive scoped rows are verified.
- Verified in this PDCA run: focused runtime checkpoint test passed, Korea regional smoke passed with 60 direct targets, and GitHub PR #167 is merged into `develop`.
- Current cron-host live evidence without an actual handoff remains blocked: Docker Compose has no running Frappe service rows and the default checkpoint still reports `runtime_verified: false` / fixture fallback required.

Closeout discipline:
- Treat Gate 9 as the handoff/evidence path, not proof that this cron host has live payroll-closing runtime rows.
- Do not remove static fixture fallback until the explicit handoff is executed against a real Bench/Frappe runtime and returns positive scoped rows.
- Keep runtime reports redacted; do not leak payroll/HR row payloads into cron artifacts.

### Gate 10 — Authoritative runtime handoff execution / positive row capture

Status: done and merged; local Docker Compose Bench checkpoint is green after PR #179 and `frappe` source sync.

Goal:
- Supply or expose a real authoritative Bench/Frappe runtime target for this workspace, then run the existing Gate 9 handoff-aware read-only checkpoint against it.
- Use an explicit runtime handoff contract rather than environment guessing.
- Verify scoped `Korea Payroll Closing Draft` rows through the read-only worklist/session path and record only redacted evidence.
- Preserve fixture fallback and clear fallback labeling while runtime rows are absent or unverified.
- Keep evidence/session views read-only: no save/approve/send/payroll submit/provider calls.

Evidence:
- Gate 10 source-alignment/runtime-probe hardening PRs #171-#177 landed Docker source mounting/sync, Docker Bench execution, stale-source fail-closed behavior, and positive-row-required runtime verification.
- `develop` includes `9dd80e49d feat: seed Korea payroll closing runtime rows (#179)`.
- `hrms/regional/south_korea/demo_seed.py` now creates a scoped, draft-only `Korea Payroll Closing Draft` row for human review, while `ensure_doc` respects caller filters before insert and does not mutate out-of-scope name collisions.
- `hrms/tests/test_korea_demo_seed_blockers.py` covers draft-row idempotency, scoped blocker filters, invalid company rejection, and out-of-scope name-collision protection.
- 2026-05-09 post-merge verification restarted the `frappe` container, which synced app source to `9dd80e49d`.
- `scripts/verify_korea_payroll_closing_runtime.py --include-bench --site hrms.localhost --company '노란봉투법 데모'` returned `runtime_verified: true`, `source_matches_mounted_workspace: true`, `positive_runtime_rows_verified: true`, `fixture_fallback_required_until_positive_runtime_rows: false`, and no runtime blockers.
- Safety boundary remains controlled: the seed creates demo-scoped draft evidence only; the verification/worklist path remains read-only and does not save/submit/approve/send/payroll-submit/call providers.

Closeout discipline:
- Treat Gate 10 as positive runtime-row evidence for the local Docker/Bench runtime, not full SaaS readiness.
- Do not remove fixture fallback for static/no-runtime previews.
- Next gate should verify the operator UI/browser route with runtime-positive rows and make fallback/banner copy conditional on actual runtime data.

### Gate 11 — Runtime-positive operator UI/browser closeout

Status: done and merged; local Docker Compose Bench checkpoint is green after PR #181 and `frappe` source sync.

Goal:
- Verify the Korea payroll closing operator route against the local Docker/Bench runtime after positive scoped rows are present.
- Prove the UI chooses runtime rows when available and preserves fixture fallback for static/no-runtime contexts.
- Keep evidence/session views read-only: no save/approve/send/payroll submit/provider mutation.
- Keep human-approval and `assistant_only` boundaries visible.

Evidence:
- `develop` includes `d603fffa5 feat: close runtime-positive payroll closing UI state (#181)`.
- `frontend/src/data/koreaPayrollClosingRuntime.js` now centralizes the runtime UI-state normalizer so positive runtime worklist rows win over dashboard-only/static fallback copy.
- `frontend/src/views/KoreaPayrollClosing.vue` uses the normalizer to keep fallback/banner copy conditional while preserving read-only evidence, human approval, and assistant-only copy.
- 2026-05-09 post-merge verification restarted the `frappe` container and synced runtime source to `d603fffa5`.
- `scripts/verify_korea_payroll_closing_runtime.py --include-bench --site hrms.localhost --company '노란봉투법 데모'` returned `runtime_verified: true`, `source_matches_mounted_workspace: true`, `positive_runtime_rows_verified: true`, `fixture_fallback_required_until_positive_runtime_rows: false`, and no runtime blockers.
- Static route/chunk smoke returned HTTP 200 for `http://127.0.0.1:8000/hrms/dashboard/korea-payroll-closing` and the served `KoreaPayrollClosing-oazgujqG.js` lazy chunk; the chunk contains runtime-positive, read-only evidence, fixture fallback, and `assistant_only` copy.
- `node frontend/tests/koreaPayrollClosingRuntime.test.mjs`, `python3 scripts/run_korea_regional_smoke.py`, and `cd frontend && yarn build` passed.

Closeout discipline:
- Treat Gate 11 as runtime-positive UI-state and route/chunk smoke evidence, not a full authenticated browser/session walkthrough.
- Do not remove fixture fallback for static/no-runtime previews.
- Next gate should verify a real authenticated browser/session path where the loaded UI executes `frappe.call` and receives the runtime worklist from the local Docker/Bench site.

### Gate 12 — Browser runtime verifier / authenticated walkthrough harness

Status: done and merged as verifier infrastructure; live employee-session browser closeout remains blocked pending credential apply/browser proof.

Goal:
- Add an authenticated browser/CDP verifier for the Korea payroll closing route.
- Prove the verifier executes only the approved read-only Frappe methods and requires positive runtime worklist rows.
- Preserve read-only evidence, human approval, and `assistant_only` boundaries.
- Fail closed and report blockers rather than mutating runtime data.

Evidence:
- `develop` includes `e7e0aedc5 test: add Korea payroll closing browser runtime verifier (#183)`.
- `frontend/src/data/koreaPayrollClosingBrowserRuntime.js` builds a browser-side probe for the payroll closing route and validates runtime-positive/read-only/assistant-only DOM and payload state.
- `scripts/verify_korea_payroll_closing_browser_runtime.mjs` logs in through Frappe, drives headless Chromium through CDP, observes browser API requests, and rejects non-read-only Frappe methods, mutation markers, and score/risk/probability keys.
- Snap Chromium on this cron host did not write `DevToolsActivePort`; PR #183 added stderr port parsing and a focused regression test.
- Verification before merge: `node frontend/tests/koreaPayrollClosingRuntime.test.mjs`, `node frontend/tests/koreaPayrollClosingBrowserRuntime.test.mjs`, `python3 scripts/run_korea_regional_smoke.py`, and `cd frontend && yarn build` passed.
- Verification after merge: focused JS tests and Korea regional smoke passed on `develop`.
- Live browser run with Administrator and the documented local Docker password failed closed on the HRMS "No active employee" page; no secret/demo employee password was printed or stored.

Closeout discipline:
- Treat Gate 12 as the browser-runtime verifier landing, not full positive authenticated browser proof.
- Do not remove fixture fallback for static/no-runtime previews.
- Gate 13 establishes a report-safe employee-linked credential handoff/apply path, but browser proof remains a separate next gate until the operator-supplied secret is applied and verified.

### Gate 13 — Demo employee browser credential handoff

Status: done and merged as report-safe handoff/apply boundary; live authenticated browser proof remains pending.

Goal:
- Establish a report-safe way to hand off or apply the employee-linked demo browser credential without printing or storing secrets in repo/cron output.
- Keep the default path handoff-only.
- Require explicit human approval before any credential update.
- Preserve payroll/evidence boundaries: no save/approve/send/payroll submit/provider mutation.

Evidence:
- `develop` includes `15f9c24a7 test: add Korea demo browser credential handoff (#185)`.
- `hrms/regional/south_korea/demo_seed.py` emits `korea_demo_browser_credential_handoff_v1` in the demo seed summary with a redacted verifier command and `password_env_var: FRAPPE_BROWSER_PASSWORD`.
- `ensure_demo_browser_credential()` requires `human_approved=True` before reading the password or calling `update_password`, verifies the approved demo username and active Employee link, and returns no password value.
- Reviewer-requested fix landed before merge: the apply helper now fails closed before mutation, uses the same `FRAPPE_BROWSER_PASSWORD` env var as the handoff, and returns `human_approval_verified` only after the approved boundary.
- Verification before merge: `python3 hrms/tests/test_korea_demo_seed_blockers.py`, `python3 -m py_compile hrms/regional/south_korea/demo_seed.py hrms/tests/test_korea_demo_seed_blockers.py`, `node frontend/tests/koreaPayrollClosingBrowserRuntime.test.mjs`, `python3 scripts/run_korea_regional_smoke.py`, and `cd frontend && yarn build` passed.
- Verification after merge: focused demo-seed test and Korea regional smoke passed on `develop`.

Closeout discipline:
- Treat Gate 13 as credential handoff/apply-boundary readiness, not positive authenticated browser proof.
- Do not print, commit, or report the demo employee password.
- The next gate must only apply the credential with an operator-provided `FRAPPE_BROWSER_PASSWORD` and explicit human approval, then run the browser verifier to a positive read-only result.

## Guardrails

- Korean business logic stays under `hrms/regional/south_korea/`.
- Do not modify `hrms/__init__.py` to bypass Frappe imports.
- AI is assistant-only.
- AI must not directly mutate DB.
- Runtime mutation paths must follow preview/read-only -> human approval -> apply.
- Do not store full resident-registration numbers or secrets.
- Avoid numeric AI confidence for HR/legal decisions; use evidence status and human review requirements instead.

## Next action

Proceed with Gate 14 human-approved demo credential apply and authenticated browser runtime proof from `develop`:

```text
test/korea-payroll-closing-browser-runtime-positive-credential
```

Expected deliverables:
- use an operator-provided `FRAPPE_BROWSER_PASSWORD` value from the runtime environment without printing, committing, or summarizing the secret
- apply only the approved demo employee credential boundary with `ensure_demo_browser_credential(..., human_approved=True)`
- rerun `scripts/verify_korea_payroll_closing_browser_runtime.mjs` against local Docker/Bench until it returns `runtime_verified: true`
- prove the loaded UI executes only the allowed read-only Frappe methods and receives positive runtime worklist rows
- preserve fixture fallback for static/no-runtime contexts
- keep evidence/session views read-only: no save/approve/send/payroll submit/provider mutation
- keep human-approval and `assistant_only` boundaries visible
- run focused browser/runtime tests, the runtime verification checkpoint, Korea regional smoke, and frontend build
- commit/push/PR URL
