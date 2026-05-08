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
- Gate 1 result:
  - `frontend/src/views/KoreaPayrollClosing.vue` attempts runtime read via Frappe when available.
  - `frontend/src/data/koreaPayrollClosingRuntime.js` calls `hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime`.
  - static fixture fallback is retained for Vercel/static preview.
  - no save/approve/send/DB mutation was introduced.

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
- Gate 2: Worklist/session runtime bridge.
- Likely branch:
  - `feat/korea-payroll-closing-worklist-runtime-bridge`
- Goal:
  - bind actual payroll closing worklist/session rows to the Korea payroll closing queue/detail UI
  - preserve fixture fallback until bench/browser runtime verification is green
  - keep evidence packet read-only
  - no mutation path in this gate

Useful commands
- Repo status:
  - `cd /home/ubuntu/workspaces/seojaehong-hrms-100h && git status --short --branch`
- Frontend build:
  - `cd /home/ubuntu/workspaces/seojaehong-hrms-100h/frontend && yarn build`
- Gate 1 focused frontend test:
  - `cd /home/ubuntu/workspaces/seojaehong-hrms-100h && node frontend/tests/koreaPayrollClosingRuntime.test.mjs`
- Docker runtime status:
  - `docker compose -f /home/ubuntu/workspaces/seojaehong-hrms-100h/docker/docker-compose.yml ps`

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
