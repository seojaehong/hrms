# Hermes HRMS Workspace Notes

Workspace
- Repo: `/home/ubuntu/workspaces/seojaehong-hrms-100h`
- Remote: `seojaehong/hrms`
- Primary base branch: `develop`
- Operating model: 1,000-hour Korea HRMS SaaS commercialization + Agentic HR runway.
- Runtime baseline: Docker/Bench runtime when needed; static Vercel preview is used only for frontend/UI smoke checks.

Current source of truth
- Uploaded guide: Korea HRMS SaaS 1,000h commercialization and AI-agentization roadmap.
- Active correction snapshot: `.hermes/plans/2026-05-09_015000-korea-hrms-1000h-autonomous-runway-correction.md`
- Gate 1 completion snapshot: `.hermes/plans/2026-05-08_162000-gate-1-runtime-read-ui-bridge-snapshot.md`

Current verified state
- `develop` includes Gate 1:
  - `4226bc967 feat: add Korea payroll closing runtime read UI bridge (#151)`
- `develop` includes Gate 2:
  - `d14ee6dd2 feat: add Korea payroll closing worklist runtime bridge (#152)`
- `develop` includes Gate 3:
  - `3fc50a300 feat: add Korea salary slip statutory apply hook (#154)`
- `develop` includes Gate 4:
  - `b971c3af8 feat(korea): seed realistic demo payroll blockers (#157)`
- `develop` includes Gate 5:
  - `17c4bc7e5 ci: harden Korea regional smoke reporting (#159)`
- `develop` includes Gate 6:
  - `7c4dd63c2 test: add Korea payroll closing runtime verification checkpoint (#161)`
- `develop` includes Gate 7 closeout hardening:
  - `2f1cc60b5 test: harden payroll closing runtime evidence gate (#163)`
- Gate 1 result:
  - `frontend/src/views/KoreaPayrollClosing.vue` attempts runtime read via Frappe when available.
  - `frontend/src/data/koreaPayrollClosingRuntime.js` calls `hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime`.
  - static fixture fallback is retained for Vercel/static preview.
  - no save/approve/send/DB mutation was introduced.
- Gate 2 result:
  - `hrms/regional/south_korea/payroll_closing_worklist_runtime_api.py` exposes a read-only runtime worklist/session bridge over `Korea Payroll Closing Draft` rows.
  - `frontend/src/data/koreaPayrollClosingRuntime.js` and `frontend/src/views/KoreaPayrollClosing.vue` bind runtime worklist/session rows when present.
  - static fixture fallback remains in place when runtime worklist data is unavailable.
  - evidence packet/session display remains read-only; no save/approve/send/DB mutation was added in the UI bridge.
- Gate 3 result:
  - `hrms.regional.south_korea.payroll_salary_slip_adapter.apply_korea_statutory_to_salary_slip` applies Korea statutory deduction rows idempotently to draft Salary Slip-shaped documents.
  - `hrms.regional.south_korea.payroll_salary_slip_adapter.apply_korea_salary_slip_statutory_hook` is opt-in via operator-set Korea statutory fields and rejects non-KR/malformed inputs.
  - `hrms/hooks.py` registers a narrow `Salary Slip.before_validate` hook.
  - mutation boundary remains row-only: no save/submit/approve/send/provider call was introduced.
- Gate 4 result:
  - `hrms/regional/south_korea/demo_seed.py` seeds realistic Korea demo blocker transactions for the payroll closing operator flow.
  - `hrms/tests/test_korea_demo_seed_blockers.py` covers idempotent blocker seed behavior and the no-submit/no-approve/no-send/no-provider mutation boundary.
  - seed output remains explicitly demo-scoped with `ai_role: assistant_only` and no approval/submission/provider automation.
- Gate 5 result:
  - `scripts/run_korea_regional_smoke.py` now reports the current Python executable, writes optional JSON reports for CI/cron artifacts, and continues to discover `hrms/tests/test_korea*.py` dynamically while excluding the harness self-test.
  - `hrms/tests/test_korea_regional_smoke_harness.py` covers report-file output, current-interpreter command construction, fail-closed zero-target behavior, and dry-run reporting.
  - optional bench probes remain explicit (`--include-bench --site ...`) and skipped safely when `bench` is unavailable.
- Gate 6 result:
  - `scripts/verify_korea_payroll_closing_runtime.py` records a cron-safe read-only runtime/bench verification checkpoint for the payroll closing worklist path.
  - `hrms/tests/test_korea_runtime_verification_checkpoint.py` covers no-bench direct behavior, Docker Compose parsing, optional bench command construction, output redaction, and fail-closed skipped-command semantics.
  - Current cron evidence from PR #161: Docker Compose returned no running Frappe service rows and `bench` was unavailable, so runtime verification is not green yet; fixture fallback remains required until positive runtime rows are proven.
  - Boundary remains read-only: no save/submit/approve/send/provider/payroll document mutation.
- Gate 7 closeout result:
  - `scripts/verify_korea_payroll_closing_runtime.py` now distinguishes skipped command checks from passed checks, parses Docker Compose service state safely, summarizes Gate 6 blocker closeout state, and only closes the runtime gate when positive read-only worklist rows are verified.
  - `hrms/tests/test_korea_runtime_verification_checkpoint.py` covers running/stopped/non-Frappe Docker services, missing bench, bench failure, positive bench worklist rows, and malformed bench rows.
  - PR #163 closed the false-positive evidence gap but did not prove live runtime rows on this cron host; fixture fallback remains required until Docker/Bench runtime plus positive `Korea Payroll Closing Draft` rows are verified.
  - Boundary remains read-only: no save/submit/approve/send/provider/payroll document mutation.
- Gate 8 runtime ownership evidence result:
  - `develop` includes `b5926a910 test: add Korea payroll closing runtime ownership evidence (#165)`.
  - `scripts/verify_korea_payroll_closing_runtime.py` now returns a report-safe `runtime_ownership` decision with `authoritative_runtime`, `decision_status`, evidence, and next actions.
  - Current cron-host evidence remains blocked: Docker Compose has no running Frappe service rows and `bench` is unavailable, so `authoritative_runtime` is `operator_provided_runtime_required` and fixture fallback remains required.
  - Boundary remains read-only: no save/submit/approve/send/provider/payroll document mutation.
- Gate 9 runtime handoff evidence-path result:
  - `develop` includes `0da583aea test: add Korea runtime handoff evidence path (#167)`.
  - `scripts/verify_korea_payroll_closing_runtime.py` now accepts an explicit report-safe runtime handoff contract for `operator_provided_bench` or `local_docker_compose_bench`, forces the read-only bench probe when handoff data is supplied, and redacts site/company/workplace command details.
  - `hrms/tests/test_korea_runtime_verification_checkpoint.py` covers handoff normalization, invalid handoff rejection, and a positive mocked operator-provided bench path.
  - Current cron-host evidence remains blocked when no handoff is supplied: Docker Compose has no running Frappe service rows and `bench` is unavailable, so fixture fallback remains required until an actual runtime handoff plus positive scoped rows are available.
  - Boundary remains read-only: no save/submit/approve/send/provider/payroll document mutation.
- Gate 10 source-alignment, runtime-probe, and positive-row capture result:
  - `develop` includes `be2806d40 test: align Korea Docker runtime source (#171)`.
  - `develop` includes `f949ae1dc fix: trust mounted HRMS source in Docker init (#172)`.
  - `develop` includes `74b58e450 fix: run Korea runtime probe through Docker bench (#173)`.
  - `develop` includes `d63d0e1a7 fix: require positive rows for Korea runtime verification (#174)`.
  - `develop` includes `12a37c4e8 docs: align Gate 10 runtime checkpoint state (#175)`.
  - `develop` includes `2f276f0b5 fix: fail closed on stale Korea runtime source (#176)`.
  - `develop` includes `51f0e3d2 fix: sync existing Docker HRMS runtime source (#177)`.
  - `develop` includes `9dd80e49d feat: seed Korea payroll closing runtime rows (#179)`.
  - Docker Compose mounts this repo at `/workspace/hrms-source`, `docker/init.sh` installs/syncs HRMS from that mounted workspace even when an existing bench checkout is present, and the checkpoint can execute Bench inside the `frappe` container without requiring host `bench`.
  - The demo seed now creates a scoped, draft-only `Korea Payroll Closing Draft` row for human review without submit/approve/send/payroll-submit/provider calls.
  - 2026-05-09 post-merge Docker/Bench verification after restarting `frappe` returned `runtime_verified: true`, `source_matches_mounted_workspace: true`, `positive_runtime_rows_verified: true`, and `fixture_fallback_required_until_positive_runtime_rows: false`.
- Gate 11 runtime-positive operator UI/browser closeout result:
  - `develop` includes `d603fffa5 feat: close runtime-positive payroll closing UI state (#181)`.
  - `frontend/src/data/koreaPayrollClosingRuntime.js` now centralizes runtime UI-state decisions so positive read-only worklist rows win over dashboard-only/static fallback copy.
  - `frontend/src/views/KoreaPayrollClosing.vue` keeps fallback copy conditional and preserves read-only evidence, human-approval, and `assistant_only` boundaries.
  - 2026-05-09 post-merge cron verification restarted the `frappe` container, synced runtime source to `d603fffa5`, and the read-only runtime checkpoint returned `runtime_verified: true`, `source_matches_mounted_workspace: true`, `positive_runtime_rows_verified: true`, and `fixture_fallback_required_until_positive_runtime_rows: false`.
  - Route smoke: `http://127.0.0.1:8000/hrms/dashboard/korea-payroll-closing` returned HTTP 200 and the served lazy chunk `KoreaPayrollClosing-oazgujqG.js` returned HTTP 200 with runtime-positive/read-only/assistant-only copy present.

Autonomous cron runway
- Implementation cron:
  - `0fabfbb750ac frappe-hrms-1000h-saas-agentic-productization-runway`
  - cadence: every 30 minutes
  - role: implement next PR-sized gate with tests/build/commit/push/PR URL
- PDCA/grill cron:
  - `995e2065fd60 frappe-hrms-1000h-pdca-briefing-grill`
  - cadence: every 30 minutes
  - role: check plan/doc alignment, stale assumptions, risks, and next action

Next gate
- Gate 12: Authenticated browser/runtime operator walkthrough closeout.
- Current status: Gate 11 is merged and local Docker Compose Bench runtime is green after restart/source sync. Static route/chunk HTTP smoke is green, but a fully authenticated browser-executed runtime read still needs an explicit closeout before calling the UI runtime path production-demo ready.
- Latest checkpoint evidence:
  - 2026-05-09 implementation-cron verified PR #181 (`d603fffa5 feat: close runtime-positive payroll closing UI state`) is merged into `develop`.
  - Docker Compose has running `frappe`, `mariadb`, and `redis` services.
  - After restarting `frappe`, logs showed `HEAD is now at d603fffa5 feat: close runtime-positive payroll closing UI state (#181)`.
  - `scripts/verify_korea_payroll_closing_runtime.py --include-bench --site hrms.localhost --company '노란봉투법 데모'` returned `runtime_verified: true`, `source_matches_mounted_workspace: true`, `positive_runtime_rows_verified: true`, and `fixture_fallback_required_until_positive_runtime_rows: false`.
  - `node frontend/tests/koreaPayrollClosingRuntime.test.mjs`, `python3 scripts/run_korea_regional_smoke.py`, and `cd frontend && yarn build` passed.
- Likely branch:
  - `test/korea-payroll-closing-authenticated-browser-closeout`
- Goal:
  - verify the Korea payroll closing operator route in an authenticated browser/session context where `frappe.call` actually reads the runtime worklist
  - keep static/no-runtime fixture fallback intact
  - keep evidence/session views read-only and human-review-only
  - preserve `runtime_action=runtime_read_only`, `requires_runtime_apply=false`, `requires_human_approval=true`, and `ai_role=assistant_only`

Useful commands
- Repo status:
  - `cd /home/ubuntu/workspaces/seojaehong-hrms-100h && git status --short --branch`
- Frontend build:
  - `cd /home/ubuntu/workspaces/seojaehong-hrms-100h/frontend && yarn build`
- Gate 1 focused frontend test:
  - `cd /home/ubuntu/workspaces/seojaehong-hrms-100h && node frontend/tests/koreaPayrollClosingRuntime.test.mjs`
- Korea regional smoke harness:
  - `cd /home/ubuntu/workspaces/seojaehong-hrms-100h && python3 scripts/run_korea_regional_smoke.py`
- Docker runtime status:
  - `docker compose -f /home/ubuntu/workspaces/seojaehong-hrms-100h/docker/docker-compose.yml ps`
- Runtime verification checkpoint:
  - `cd /home/ubuntu/workspaces/seojaehong-hrms-100h && python3 scripts/verify_korea_payroll_closing_runtime.py --report-file /tmp/korea-payroll-closing-runtime-report.json || true`

Key paths
- Korea runtime APIs and domain logic:
  - `hrms/regional/south_korea/`
- Korea payroll closing UI:
  - `frontend/src/views/KoreaPayrollClosing.vue`
  - `frontend/src/data/koreaPayrollClosingRuntime.js`
  - `frontend/src/data/koreaPayrollClosingFixture.js`
- Runtime API:
  - `hrms/regional/south_korea/admin_dashboard_runtime_api.py`
- Salary Slip adapter:
  - `hrms/regional/south_korea/payroll_salary_slip_adapter.py`
- Demo seed:
  - `hrms/regional/south_korea/demo_seed.py`
- Runtime verification checkpoint:
  - `scripts/verify_korea_payroll_closing_runtime.py`

Guardrails
- Korean business logic stays under `hrms/regional/south_korea/`.
- Do not modify `hrms/__init__.py` to bypass Frappe imports.
- AI remains assistant-only.
- AI must not directly mutate DB.
- Runtime mutation paths must follow preview/read-only -> human approval -> apply.
- Do not store full resident-registration numbers or secrets.
- Avoid numeric AI confidence for HR/legal decisions; use evidence status and human-review flags.

Notes
- `import hrms` alone can fail outside a Bench/Frappe runtime because `frappe` may not be installed in the active system Python.
- Use isolated/direct tests for pure JS/Python adapters first, then Bench/Docker runtime checks for actual Frappe execution.
- If cron or a live session has an active feature branch, inspect branch/status before switching or editing. Prefer clean `develop` for the next PR-sized branch.
