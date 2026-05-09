# Korea HRMS 1,000h autonomous runway correction

Status: active source-of-truth correction after Gate 9 runtime handoff evidence path landed on `develop`.

## Verified repo state

- Repo: `/home/ubuntu/workspaces/seojaehong-hrms-100h`
- Base branch: `develop`
- Latest product gate commit on `develop`: `0da583aea test: add Korea runtime handoff evidence path (#167)`
- Gate 1 is merged to `develop`.
- Gate 2 is merged to `develop`.
- Gate 3 is merged to `develop`.
- Gate 4 is merged to `develop`.
- Gate 5 is merged to `develop`.
- Gate 6 is merged to `develop`.
- Gate 7 closeout hardening is merged to `develop`.
- Gate 8 runtime ownership evidence is merged to `develop`.
- Gate 9 runtime handoff evidence path is merged to `develop`.
- Runtime bridge files are tracked:
  - `frontend/src/data/koreaPayrollClosingRuntime.js`
  - `frontend/tests/koreaPayrollClosingRuntime.test.mjs`
- Gate 1 snapshot is tracked:
  - `.hermes/plans/2026-05-08_162000-gate-1-runtime-read-ui-bridge-snapshot.md`

## Correction from earlier plan branches

Previous roadmap/grill plan work existed on a plan branch and not all plan notes were present on `develop`. `HERMES_WORKSPACE.md` on `develop` was also stale and still referenced `/home/ubuntu/workspaces/frappe-hrms` as the primary repo.

The original correction made `develop` the operational source of truth after Gate 1; this update advances the same runway after Gate 9 runtime handoff evidence-path work and aligns cron with the Gate 10 next action.

## Autonomous operating model

Two cron jobs remain the main autonomous runway:

1. `frappe-hrms-1000h-saas-agentic-productization-runway`
   - cadence: every 30 minutes
   - role: implementation, tests, commit, push, PR URL
   - current priority: Gate 10
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

Status: blocked pending authoritative runtime handoff or running local Bench/Frappe runtime.

Goal:
- Supply or expose a real authoritative Bench/Frappe runtime target for this workspace, then run the existing Gate 9 handoff-aware read-only checkpoint against it.
- Use an explicit runtime handoff contract rather than environment guessing.
- Verify scoped `Korea Payroll Closing Draft` rows through the read-only worklist/session path and record only redacted evidence.
- Preserve fixture fallback and clear fallback labeling while runtime rows are absent or unverified.
- Keep evidence/session views read-only: no save/approve/send/payroll submit/provider calls.

Current cron-host evidence:
- 2026-05-09 Gate 10 checkpoint from `/home/ubuntu/workspaces/seojaehong-hrms-100h` ran `scripts/verify_korea_payroll_closing_runtime.py --report-file /tmp/korea-payroll-closing-runtime-report.json`.
- Focused Gate 2/Gate 10 health checks passed: `python3 hrms/tests/test_korea_payroll_closing_worklist_runtime_api.py`, `node frontend/tests/koreaPayrollClosingRuntime.test.mjs`, and `python3 scripts/run_korea_regional_smoke.py` with 60 direct targets.
- `docker compose -f docker/docker-compose.yml up -d` successfully started `docker-frappe-1`, `docker-mariadb-1`, and `docker-redis-1`, and `hrms.localhost` installed successfully.
- The started Docker runtime is not authoritative for this runway yet: `docker/init.sh` clones upstream `https://github.com/frappe/hrms.git` into the bench, so `/home/frappe/frappe-bench/apps/hrms` is upstream `hrms 17.0.0-dev develop`, not this `seojaehong/hrms` `develop` worktree with the Korea runtime bridge modules.
- A direct bench execute probe against `hrms.regional.south_korea.payroll_closing_worklist_runtime_api...` failed because the runtime app source does not expose the Korea module path from this fork.
- The checkpoint correctly remains `runtime_verified: false`; positive scoped row capture is blocked until the runtime app source is switched to, mounted from, or otherwise deployed from the canonical fork/branch.
- Boundary remained read-only: no save/submit/approve/send/provider/payroll document mutation.

## Guardrails

- Korean business logic stays under `hrms/regional/south_korea/`.
- Do not modify `hrms/__init__.py` to bypass Frappe imports.
- AI is assistant-only.
- AI must not directly mutate DB.
- Runtime mutation paths must follow preview/read-only -> human approval -> apply.
- Do not store full resident-registration numbers or secrets.
- Avoid numeric AI confidence for HR/legal decisions; use evidence status and human review requirements instead.

## Next action

Proceed with Gate 10 from `develop`:

```text
ops/korea-payroll-closing-runtime-positive-row-capture
```

Expected deliverables:
- authoritative Bench/Frappe runtime handoff executed through the Gate 9 checkpoint path
- ensure the runtime app source is this canonical `seojaehong/hrms` fork/branch, not upstream `frappe/hrms`, before claiming positive Gate 10 evidence
- explicit runtime handoff contract inputs kept out of reports except for redacted booleans/counts
- read-only runtime verification checkpoint run against that runtime when available and explicitly scoped
- positive scoped `Korea Payroll Closing Draft` row evidence only if the runtime actually returns rows through the worklist/session path
- precise environmental blocker report if Docker/Bench/runtime access remains unavailable or points at the wrong app source
- fixture fallback remains visible and labeled when runtime data is absent or unverified
- no save/approve/send/payroll submit/provider mutation in the verification gate
- commit/push/PR URL
