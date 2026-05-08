# Gate 1 snapshot — Korea payroll closing runtime-read UI bridge

Status: implemented and locally verified

Branch
- `feat/korea-payroll-closing-runtime-read-ui`

Purpose
- Make `frontend/src/views/KoreaPayrollClosing.vue` runtime-aware while keeping the existing static fixture as a safe fallback for Vercel/static preview.

Changed files
- `frontend/src/data/koreaPayrollClosingRuntime.js`
  - Adds `KOREA_ADMIN_DASHBOARD_RUNTIME_METHOD` for `hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime`.
  - Detects `window.frappe.call` availability.
  - Resolves current company from Frappe boot/defaults with fixture fallback.
  - Validates `contract_type`, `runtime_action`, and `requires_runtime_apply`.
- `frontend/src/views/KoreaPayrollClosing.vue`
  - Adds loading/error/runtime/fixture source states.
  - Calls runtime read on mount.
  - Keeps static fixture fallback active when runtime is unavailable or fails.
  - Displays `runtime_action` and `requires_runtime_apply` when runtime data loads.
- `frontend/tests/koreaPayrollClosingRuntime.test.mjs`
  - Covers runtime availability detection, company resolution, method call payload, contract validation, runtime-unavailable failure, and view wiring strings.

Verification
- `node frontend/tests/koreaPayrollClosingRuntime.test.mjs`: PASS
- `cd frontend && yarn build`: PASS
- Vercel deployment: `dpl_2ogjdXrE7avzkaZsLujfHGirfFyf` Ready
- Public route: `https://hrms-vercel-static.vercel.app/hrms/dashboard/korea-payroll-closing` returned HTTP 200
- Built chunk contains runtime bridge markers:
  - `Runtime read-only dashboard loaded`
  - `static fixture fallback is active`
  - `get_korea_admin_dashboard_runtime`
  - `runtime_read_only`

Known warnings
- Existing build warnings remain:
  - `caniuse-lite` data is old.
  - Ionic/Stencill pure annotation warning.
  - large chunk warning for existing bundles.

Boundary
- No DB mutation.
- No save/approve/send action.
- `runtime_action` remains `runtime_read_only`.
- Static fixture fallback intentionally retained.

Next gate
- Gate 2: bind actual worklist/session runtime rows to the queue/session UI after this PR is reviewed/merged.
