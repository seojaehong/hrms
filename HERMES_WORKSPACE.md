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
- Gate 7: Phase 1 runtime blocker closeout / positive bench evidence.
- Likely branch:
  - `test/korea-payroll-closing-runtime-positive-evidence`
- Goal:
  - resolve or document the concrete runtime blockers found by Gate 6: no running Frappe Docker Compose service rows and no `bench` executable in the cron environment
  - run the read-only verification checkpoint against an available Bench/Docker runtime when safe
  - confirm seeded demo blocker rows surface through the read-only payroll closing worklist/session UI only after positive runtime rows exist
  - keep fixture fallback visible and explicitly labeled when runtime rows remain absent
  - preserve the no-bench smoke harness and direct tests as the baseline regression net
  - preserve read-only/evidence-only boundaries: no save/approve/send/payroll submit/provider calls

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
