# Korea HRMS SaaS — /grill with docs: revised 1,000h development plan

Source documents and inspected evidence
- Source guide: `/home/ubuntu/.hermes/cache/documents/doc_479308287a89_Korea_HRMS_SaaS_—_1,000시간_상용화_및_AI_에이전트화_완성_가이드.md`
- Prior intake: `.hermes/plans/2026-05-08_161332-korea-hrms-1000h-commercialization-roadmap-intake.md`
- Repository/workdir: `/home/ubuntu/workspaces/seojaehong-hrms-100h`
- Inspected branch: `plan/korea-hrms-1000h-roadmap-intake`
- Inspected HEAD: `1d3730e8e docs: adopt Korea HRMS 1000h commercialization roadmap`
- Upstream develop ref observed: `71925bd18c6cefdf4d4f7645f155898a58135c61 refs/heads/develop`

## 1. 결론

The guide is directionally correct: the real bottleneck is not more isolated Korea domain logic; it is connecting existing Korea backend contracts to runtime UI, DB rows, hooks, seed data, and CI.

The plan is revised as follows:

1. Phase 1 is no longer a broad “E2E” label. It is split into five enforceable release gates:
   - Gate 1: Runtime-read UI bridge.
   - Gate 2: Payroll closing worklist/session runtime bridge.
   - Gate 3: Salary Slip statutory apply hook.
   - Gate 4: Demo seed blocker realism.
   - Gate 5: Korea test/CI harness.
2. Static fixture is not deleted immediately. It becomes an explicit fallback until runtime bench verification passes.
3. `Salary Slip` integration is treated as a mutation path and therefore must be TDD + hook-gated + reversible.
4. AI-agent work is deferred until Phase 4, but every API added from now on must remain function-calling-ready: dict contract, explicit `contract_type`, explicit runtime action, explicit human approval boundary.
5. The guide’s “AI confidence_score” recommendation is modified: for this project, avoid numeric AI confidence in HR decisions. Use evidence completeness/status labels instead unless a future governance policy explicitly approves a non-predictive scoring field.

## 2. /grill findings against the uploaded guide

### Finding A — The guide’s main diagnosis is correct

Evidence:
- `frontend/src/views/KoreaPayrollClosing.vue` still contains `Preview-only static fixture`.
- `hrms/regional/south_korea/admin_dashboard_runtime_api.py` exists and exposes `get_korea_admin_dashboard_runtime`.
- This means backend read contracts exist, but the operator UI is not yet using them as the primary data source.

Decision:
- Phase 1 starts with UI runtime-read bridging, not new payroll math.

### Finding B — Some guide assumptions are stale or only partially true

Evidence:
- The guide says “Vue router Korea path unregistered”; actual `frontend/src/router/index.js` already registers:
  - `/dashboard/korea-payroll-closing`
  - `/korea-payroll-closing-session/:name`
  - `/dashboard/korea-payroll-review-audit-logs`
- The guide says “383 tests pass”; current shell cannot verify because `python3 -m pytest` fails with `No module named pytest`.
- `pyproject.toml` exists but has no `[tool.pytest.ini_options]` yet.
- `.github/workflows/korea_tests.yml` is absent.

Decision:
- Do not blindly implement stale checklist items. Each guide item must be revalidated against files before work.
- CI/harness work must include environment dependency discovery, not only pytest config.

### Finding C — Salary Slip adapter is more complete than guide says, but not apply-ready

Evidence:
- `hrms/regional/south_korea/payroll_salary_slip_adapter.py` already has:
  - `build_korea_salary_slip_statutory_payload`
  - `build_korea_salary_slip_verification_request`
- It intentionally does not mutate Salary Slip documents.
- `apply_korea_statutory_to_salary_slip(salary_slip_doc)` is not present.
- Hook registration for Korea Salary Slip apply is not verified/present.

Decision:
- Treat current adapter as preview/review payload layer.
- Add apply function only after tests prove idempotent deduction mapping and no duplicate rows.

### Finding D — Demo seed has base data, but not blocker transactions

Evidence:
- `demo_seed.py` creates company, users, employees, salary components, salary structure, salary structure assignments.
- No inspected section creates blocker transactions for:
  - absent Attendance records,
  - pending overtime requests,
  - unsettled Expense Claims.

Decision:
- Demo seed work must create actual blocker rows, not just more static frontend data.

### Finding E — AI-agent phase needs stricter HR governance than uploaded doc

Evidence:
- Uploaded doc suggests `confidence_score` on AI proposals.
- Existing project/user policy forbids AI probability/success prediction style outputs in HR/labor contexts.

Decision:
- Replace `confidence_score` with safer fields unless later approved:
  - `evidence_status`: `complete | partial | missing`
  - `source_count`
  - `requires_human_review: true`
  - `sensitive_data_redacted: true`

## 3. Revised Phase 1 plan: 100h → 300h

### Gate 1 — Runtime-read UI bridge

Purpose:
- Make `KoreaPayrollClosing.vue` runtime-aware without breaking Vercel/static demo.

Scope:
- Add a frontend data adapter/client for `frappe.call`.
- On mount, call:
  - `hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime`
- Use `company` from current user/session/default company if available; otherwise use demo company fallback only in static preview.
- Add UI states:
  - loading
  - runtime_read_only loaded
  - runtime error with static fallback
  - no data

Acceptance:
- `yarn build` passes.
- Static Vercel route still works.
- Runtime API call is primary when `window.frappe.call` exists.
- UI clearly labels whether data source is runtime or fixture.
- No save/approve/send mutation is added.

Suggested PR:
- Branch: `feat/korea-payroll-closing-runtime-read-ui`
- Files likely touched:
  - `frontend/src/views/KoreaPayrollClosing.vue`
  - optionally `frontend/src/data/koreaPayrollClosingRuntime.js`

### Gate 2 — Worklist/session runtime bridge

Purpose:
- The user should see actual payroll closing session/worklist rows, not only admin dashboard summary cards.

Scope:
- Inspect existing worklist/session runtime APIs before adding anything.
- Bind actual runtime rows to queue/session screen.
- Keep route-safe session IDs.
- Keep evidence packet preview as read-only.

Acceptance:
- Browser/bench route shows real DB-derived sessions when seeded.
- Static fixture fallback remains available.
- Runtime response has `contract_type` and explicit `runtime_action`.
- No session apply mutation happens from this gate.

Suggested PR:
- Branch: `feat/korea-payroll-closing-worklist-runtime-ui`

### Gate 3 — Salary Slip statutory apply hook

Purpose:
- Convert existing preview adapter into controlled Salary Slip deduction application.

Scope:
- Add tests first for:
  - gross/earning extraction,
  - deduction row mapping,
  - idempotency/no duplicate statutory deductions,
  - preservation of non-Korea/non-statutory existing rows,
  - missing policy/invalid gross handling.
- Add `apply_korea_statutory_to_salary_slip(salary_slip_doc, *, policy)` or equivalent.
- Add Frappe wrapper/hook only after pure adapter passes.
- Hook must be scoped to Korea company/country/policy so upstream/global Salary Slip behavior is not changed.

Acceptance:
- Direct-run adapter tests pass.
- Hook registration is isolated and reversible.
- `Salary Slip` before_save or equivalent applies statutory employee deductions only under Korea policy.
- Audit/review boundary remains clear: calculation is deterministic statutory apply, not AI decisioning.

Suggested PRs:
- `test: cover Korea salary slip statutory apply adapter`
- `feat: apply Korea statutory deductions to salary slip`
- `feat: register Korea salary slip hook behind scoped guard`

### Gate 4 — Demo seed blocker realism

Purpose:
- Demo data must exercise the closing blocker logic, not merely populate master data.

Scope:
- Add idempotent seed helpers for:
  - absent/unclosed Attendance rows,
  - pending overtime request rows or nearest existing overtime DocType equivalent,
  - unsettled Expense Claim rows.
- Do not store full RRN or real bank/account data.
- Seed rows should be clearly demo-labeled.

Acceptance:
- Running demo seed twice does not duplicate blocker rows.
- Dashboard/worklist APIs can count or expose blockers.
- UI shows blockers from runtime data after seed.

Suggested PR:
- Branch: `feat/korea-demo-seed-payroll-blockers`

### Gate 5 — Korea test/CI harness

Purpose:
- Make the 1,000h runway safe enough for continuous PR stacking.

Scope:
- First resolve current local test runner issue:
  - current `python3` is `/home/ubuntu/.hermes/hermes-agent/venv/bin/python3`
  - `python3 -m pytest` currently fails: `No module named pytest`
- Decide whether tests run via bench env, repo venv, or installed dev dependency.
- Add pytest config only after confirming it does not break upstream HRMS/Frappe test layout.
- Add `.github/workflows/korea_tests.yml` only after command is known-good locally or documented as bench-only.

Acceptance:
- A reproducible command exists for direct-run Korea tests.
- CI workflow uses the same command or a documented equivalent.
- Known Frappe-runtime tests are separated from pure direct-run tests if needed.

Suggested PRs:
- `chore: document Korea test harness command`
- `ci: add Korea regional tests workflow`

## 4. Revised Phase 2 plan: 300h → 600h

### Gate 6 — Work-time engine

Purpose:
- Build the foundation for flex-level time/payroll differentiation.

Scope:
- New pure module: `hrms/regional/south_korea/work_time_engine.py`.
- Inputs: work logs, holiday calendar, policy from `KOREA_LEGAL_RULES_INPUT.yaml`.
- Outputs: ordinary/overtime/night/holiday buckets and statutory premium flags.

Acceptance:
- Pure Python tests for standard, flexible, selective, night, holiday, and edge cases.
- No Frappe import in the core engine.

### Gate 7 — Statutory payroll edge cases

Purpose:
- Reduce manual correction burden for real payroll operators.

Scope sequence:
1. 60+ national pension exclusion.
2. Joiner/leaver proration.
3. tax/non-tax allowance caps.
4. foreign employee employment insurance handling.
5. probation/minimum-wage guard.
6. simplified withholding table expansion.

Acceptance:
- Add `employee_profile` or equivalent typed input to `build_statutory_payroll_snapshot` without breaking existing callers.
- One edge case per PR with RED → GREEN tests.

### Gate 8 — e-contract and payslip documents

Purpose:
- Commercial user value: contract creation, delivery, signed state, payslip legal form.

Scope:
- Start with preview PDF/template generation, then notification, then signed/apply state.
- Use existing Kakao notification module only after preview output is verified.

Acceptance:
- Human approval before send.
- Audit record for send/sign events.
- No sensitive full identifiers in generated/test artifacts.

## 5. Revised Phase 3 plan: 600h → 800h

Priority order:
1. Multi-workplace closing pipeline and consolidated payroll report.
2. Row-level access policy using existing Frappe permissions/user permissions.
3. EDI file generation preview/export with validation report.
4. Year-end settlement aggregation and PDF/export artifacts.

Acceptance across Phase 3:
- Branch/workplace/company scope is explicit in every query.
- Read/write permissions tested separately.
- Export files are previewed/validated before user download or submission.

## 6. Revised Phase 4 plan: 800h → 1,000h+

Priority order:
1. Function-calling schema generator for existing safe `*_api.py` read/preview APIs.
2. Compliance monitoring assistant that drafts legal-rule updates for human review.
3. Payroll anomaly assistant as deterministic rules first, LLM explanation second.
4. Conversational HR assistant for read-only employee/admin questions.
5. Governance/audit extension for AI actor events.

Modified governance fields:
- Use `ai_role: assistant_only`.
- Use `runtime_action: preview_only` or `runtime_read_only`.
- Use `requires_human_approval: true` for recommendations/actions.
- Prefer `evidence_status` and `source_count` over numeric confidence.
- Redact sensitive fields before LLM calls.

## 7. Execution rules from now on

- One gate = multiple small PRs, not one large PR.
- Before each PR:
  1. inspect branch/status,
  2. inspect target files,
  3. write or update tests first for backend/runtime changes,
  4. keep fallback paths for UI until runtime is verified.
- After each PR:
  1. run smallest relevant tests/build,
  2. commit/push,
  3. update `.hermes/plans/` snapshot if state changed,
  4. provide PR URL if `gh` is unavailable.
- Do not change `hrms/__init__.py` for tests.
- Do not put Korea-specific business logic outside `hrms/regional/south_korea/`.
- Do not let AI write/apply DB mutations directly.
- Do not store full resident-registration numbers or secrets.

## 8. Immediate next PR queue

1. `feat/korea-payroll-closing-runtime-read-ui`
   - Runtime-read boundary for `KoreaPayrollClosing.vue`.
   - Static fixture fallback retained.
   - `yarn build` required.

2. `feat/korea-payroll-closing-worklist-runtime-ui`
   - Bind actual worklist/session runtime rows.
   - Bench/browser verification when runtime is available.

3. `test/korea-salary-slip-apply-adapter`
   - RED tests for statutory apply/idempotency.

4. `feat/korea-salary-slip-apply-adapter`
   - Implement pure adapter apply function.

5. `feat/korea-demo-seed-payroll-blockers`
   - Seed attendance/overtime/expense blockers.

6. `chore/korea-test-harness`
   - Resolve pytest runner dependency/environment and document CI command.

## 9. Current blockers

- Current shell Python has no pytest installed, so “383 tests pass” cannot be accepted as verified in this environment.
- The current working branch is a plan branch, not `develop`; next implementation should branch from updated `develop` after this plan PR is either merged or consciously left as a planning branch.
- Runtime/bench availability has not been verified in this grill pass; UI runtime work must include actual bench/browser verification when possible.

## 10. Decision record

- Adopt guide as strategic direction.
- Correct stale assumptions before implementation.
- Preserve static fixture as fallback until runtime path passes.
- Move AI-agent features to Phase 4 only, while making contracts function-calling-ready from Phase 1.
- Replace numeric AI confidence recommendation with evidence-status governance for HR/labor safety.
