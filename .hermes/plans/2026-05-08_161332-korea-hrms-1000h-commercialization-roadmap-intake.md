# Korea HRMS SaaS — 1,000h commercialization roadmap intake

Source document
- Uploaded file: `/home/ubuntu/.hermes/cache/documents/doc_479308287a89_Korea_HRMS_SaaS_—_1,000시간_상용화_및_AI_에이전트화_완성_가이드.md`
- Repository baseline at intake: `seojaehong/hrms` `develop`
- Intake timestamp: `2026-05-08_161332` from server `date +%F_%H%M%S`

## Operating conclusion

The 500-hour SaaS runway is superseded by the 1,000-hour commercialization and agentic HR runway.

Immediate execution focus is Phase 1: connect the already-built Korea backend contracts to real UI/runtime flows while preserving the existing rules:
- TDD first for backend/domain/runtime changes.
- Small stacked PRs.
- Framework-free Korea domain logic under `hrms/regional/south_korea/`.
- AI remains `assistant_only`; no direct DB mutation by AI.
- Human approval remains mandatory for apply/mutation paths.
- No full resident registration number storage.

## Phase structure

1. Phase 1: E2E pipeline connection, 100h → 300h
   - Vue frontend ↔ runtime API connection.
   - Salary Slip statutory deduction pipeline.
   - Demo seed blocker data.
   - pytest CI stabilization.

2. Phase 2: Core HR commercialization, 300h → 600h
   - Work-time engine.
   - Statutory payroll edge cases.
   - e-contract pipeline.
   - legal payslip PDF/distribution.

3. Phase 3: Enterprise scale, 600h → 800h
   - Multi-workplace payroll closing.
   - RBAC/row-level access.
   - EDI file generation readiness.
   - year-end settlement support.

4. Phase 4: Agentic HR platform, 800h → 1,000h+
   - compliance monitoring agent.
   - payroll anomaly detection assistant.
   - function-calling HR assistant.
   - AI governance/audit framework.

## Current repo facts verified during intake

- Current branch before intake branch: `develop`
- Current develop HEAD: `71925bd18 feat: extend Korea admin runtime operational counts (#150)`
- `.hermes/plans/` exists.
- `HERMES_WORKSPACE.md` exists.
- `frontend/src/views/KoreaPayrollClosing.vue` exists and still contains `Preview-only static fixture`.
- `hrms/regional/south_korea/admin_dashboard_runtime_api.py` exists and exposes `get_korea_admin_dashboard_runtime`.
- `hrms/regional/south_korea/payroll_salary_slip_adapter.py` exists.
- `hrms/regional/south_korea/demo_seed.py` exists.
- `hrms/regional/south_korea/statutory_payroll.py` exists.

## Phase 1 execution order

### Slice 1-A1 — UI runtime-read client boundary

Goal: introduce a small frontend runtime client/fallback boundary without removing the static fixture yet.

Acceptance:
- `KoreaPayrollClosing.vue` can represent `loading`, `runtime_read_only`, and `error/fallback` states.
- Static fixture remains available as fallback for Vercel/static preview.
- No DB mutation.
- `yarn build` passes.

### Slice 1-A2 — bind runtime dashboard cards

Goal: bind `dashboard.cards` from `get_korea_admin_dashboard_runtime` to existing UI cards.

Acceptance:
- Runtime response contract is mapped in one adapter function.
- Existing demo fixture still works when `frappe.call` is unavailable.
- Browser/bench verification is performed when runtime is available.

### Slice 1-B — Salary Slip adapter TDD

Goal: complete `apply_korea_statutory_to_salary_slip(salary_slip_doc)`.

Acceptance:
- Test proves gross pay is converted into Korea statutory snapshot input.
- Test proves employee deductions are appended/mapped to the Salary Slip deductions table.
- Hook registration is isolated and reversible.
- No mutation by AI path.

### Slice 1-C — demo seed blockers

Goal: seed realistic payroll-closing blocker records.

Acceptance:
- Attendance absence blocker data.
- Pending overtime request blocker data.
- Unsettled expense claim blocker data.
- Read-only dashboard/closing preview can expose these blockers.

### Slice 1-D — pytest CI stabilization

Goal: stabilize batch Korea test execution and add CI.

Acceptance:
- `python3 -m pytest hrms/tests/test_korea_*` succeeds or documented known failures are reduced with isolated root cause.
- `pyproject.toml` pytest config added only if compatible with upstream project layout.
- GitHub Actions Korea workflow added.

## Guardrails

- Do not edit `hrms/__init__.py` to work around Frappe imports.
- Do not write Korea business logic outside `hrms/regional/south_korea/`.
- Do not create AI code paths that directly mutate DB rows.
- Keep preview/apply separation explicit in contracts.
- Mask or avoid sensitive identifiers.
- Every phase/slice completion should update `.hermes/plans/` and, when materially useful, `HERMES_WORKSPACE.md`.

## Next implementation target

Start with Slice 1-A1 because it directly addresses the current bottleneck: backend runtime contracts exist, but `KoreaPayrollClosing.vue` still renders a static fixture boundary.
