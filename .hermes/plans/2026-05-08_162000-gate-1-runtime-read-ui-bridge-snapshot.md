# Gate 1 snapshot — Korea payroll closing runtime-read UI bridge

Status: implemented, locally verified, PR opened

Branch
- `feat/korea-payroll-closing-runtime-read-ui`

Purpose
- Make `frontend/src/views/KoreaPayrollClosing.vue` runtime-aware while keeping the existing static fixture as a safe fallback for Vercel/static preview.

Changed files
- `frontend/src/data/koreaPayrollClosingRuntime.js`
  - Adds `KOREA_ADMIN_DASHBOARD_RUNTIME_METHOD` for `hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime`.
  - Detects `window.frappe.call` availability.
  - Resolves current company from Frappe user/session/boot defaults with fixture fallback.
  - Validates `contract_type`, `runtime_action`, and `requires_runtime_apply`.
  - Treats all-zero runtime metrics as a no-data state even when dashboard cards are structurally present.
- `frontend/src/views/KoreaPayrollClosing.vue`
  - Adds loading/error/runtime/fixture source states.
  - Calls runtime read on mount.
  - Keeps static fixture fallback active when runtime is unavailable or fails.
  - Displays `runtime_action` and `requires_runtime_apply` when runtime data loads.
- `frontend/tests/koreaPayrollClosingRuntime.test.mjs`
  - Covers runtime availability detection, user/session/default company resolution, method call payload, contract validation, runtime-unavailable failure, all-zero runtime no-data detection, and view wiring strings.

Verification
- `node frontend/tests/koreaPayrollClosingRuntime.test.mjs`: PASS
- `(cd frontend && node tests/koreaPayrollClosingRuntime.test.mjs)`: PASS
- `for test in frontend/tests/*.mjs; do node "$test"; done`: PASS
- `yarn --cwd frontend build`: PASS
- Subagent spec re-review after hardening: PASS
- Subagent quality review: APPROVED
- Vercel redeploy was not run in this PR closeout; static route remains a fallback target and should be redeployed after merge if public preview freshness is required.

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
