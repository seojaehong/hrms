# Korea HRMS SaaS 500-Hour Productization Runway

> **For Hermes:** Run this as a slow-but-relentless 500-hour productization runway. Use `frappe-hrms-rapid-delivery`, `github-pr-workflow`, `test-driven-development`, and focused subagents. Keep one small reviewable PR per run where possible. Do not chase a big-bang rewrite.

**Goal:** Build `seojaehong/hrms` into a commercially pilotable Korean HRMS SaaS for multi-location SME/franchise operators by steadily stacking product capabilities, tests, runtime integration, UI, permissions, demo data, and operating runbooks.

**Canonical workspace:** `/home/ubuntu/workspaces/seojaehong-hrms-100h`

**Canonical remote:** `https://github.com/seojaehong/hrms.git`

**Base branch:** `develop`

**Runway length:** `500 hours = 1,000 half-hour cycles`

**Daily target:** raise commercial SaaS readiness by about `+10 points/day` when enough verified product-layer evidence exists. From the current 38/100 baseline, the arithmetic gap is 62 points, so +10/day implies roughly 7 days / 168 hours / 336 half-hour cycles to reach 100 if the team is converting stack work into real product readiness. The remaining 500-hour runway is still useful for consolidation, pilot hardening, and not faking readiness.

**Live test surface:** keep a Vercel deployment available for operator testing. Current public static preview URL: `https://hrms-vercel-static.vercel.app`. This is a built frontend/static preview, not a full Frappe backend runtime. Any UI/runtime work must state whether it is visible on this URL, requires backend APIs, or needs Docker/Bench.

**Operating philosophy:** Do not force a fake 100-point sprint. Build the stack correctly. Keep the current 100-point SaaS scorecard, but treat it as a long-horizon product score, not a promise that every 30-minute run must visibly increase the score.

---

## Starting Position

Current SaaS readiness estimate remains:

```text
38 / 100
```

Meaning:
- Good Korea regional domain core and test discipline.
- Many preview-only/API/helper contracts exist.
- Commercial SaaS readiness still depends on E2E payroll closing, UI, runtime persistence, role/tenant safety, demo tenant, and operational readiness.

This 500-hour runway keeps the same destination but changes the pacing:

```text
100-hour pressure mode: rush toward E2E product proof
500-hour stack mode: build the commercial stack layer by layer without losing E2E direction
```

---

## 100-Point SaaS Scorecard

Use this scorecard for PDCA, but do not inflate it because helper count increased.

1. **Payroll Closing E2E — 25 pts**
   - One workplace/month can close payroll safely with blockers, review, approval, audit, and payslip/Kakao readiness.
2. **Operations UI / Admin Home — 15 pts**
   - Operator sees what is blocked and what to do next.
3. **Runtime Integration & Persistence — 15 pts**
   - Drafts, state transitions, controlled Frappe runtime flows, explicit mutation boundaries.
4. **Role / Workplace / Tenant / Audit Safety — 15 pts**
   - HQ, branch manager, employee, external advisor roles; workplace-scoped access; PII masking; audit logs.
5. **Demo Tenant / Pilot Readiness — 10 pts**
   - Realistic HQ + branches + employees + payroll blockers + approval/Kakao/contract scenarios.
6. **Payroll / Compliance Correctness Depth — 10 pts**
   - Policy/version basis, statutory basis visibility, evidence/manual review, paid/vendor/manual verification as optional evidence layer.
7. **SaaS Operations — 10 pts**
   - Smoke/regression, runtime checks, monitoring/logging, migration/rollback, onboarding docs.

---

## 500-Hour Milestones

### Milestone A — Hours 0-50: Stabilize runway and product spine

Target score: `38 -> 43`

Purpose:
- Keep function stacking, but organize it around one product spine: payroll closing.
- Avoid random helper drift.

Deliverables:
1. Payroll closing session read model.
2. Payroll closing preview API.
3. Readiness cards that aggregate existing modules.
4. Smoke harness includes all new closing tests.
5. PDCA reports score, latest PR, and product gap every cycle.

Exit criteria:
- One payload can explain workplace/month close readiness with blockers and next actions.

### Milestone B — Hours 50-120: Close the read-only E2E demo path

Target score: `43 -> 52`

Deliverables:
1. Attendance, payroll, statutory, approval, Kakao, contract, and expense blockers visible in closing session.
2. Payroll artifacts grouped into customer-readable sections.
3. Approval readiness and human-review gates.
4. Demo fixture/helper for a single workplace/month.
5. Negative tests for cross-company/workplace leakage.

Exit criteria:
- We can demo “what blocks this month’s payroll close” without manual JSON spelunking.

### Milestone C — Hours 120-200: Runtime preview and first operator screens

Target score: `52 -> 62`

Deliverables:
1. Frappe-facing whitelisted preview APIs for closing center.
2. Admin Home / Closing Center route/action contracts aligned to actual screens.
3. First Vue/Frappe UI slice or server-rendered review endpoint where practical.
4. Empty/loading/error state contracts.
5. Role-aware CTA availability.

Exit criteria:
- Operator has a visible “what to do next” surface, even if final mutations remain guarded.

### Milestone D — Hours 200-300: Draft state, approval, audit, and guarded mutation

Target score: `62 -> 74`

Deliverables:
1. Draft payroll close state.
2. State transitions: preview -> draft -> reviewed -> approved -> ready_to_send -> closed.
3. Approval/rejection action payloads.
4. Audit event creation and PII-safe log identifiers.
5. Permission guard tests.
6. Explicit rollback/migration discipline for any DocType/custom-field changes.

Exit criteria:
- Payroll close is no longer just preview; it can become a controlled reviewed draft with audit.

### Milestone E — Hours 300-380: Demo tenant and pilot narrative

Target score: `74 -> 84`

Deliverables:
1. HQ + 3 workplaces + 50 employees demo seed.
2. Salaried/hourly/joiner/leaver/overtime/night/holiday scenarios.
3. Missing attendance, unsigned contract, approval queue, Kakao queue, payroll blockers.
4. One-command demo validation.
5. Pilot walkthrough script.

Exit criteria:
- A non-developer can understand the product value in five minutes.

### Milestone F — Hours 380-450: Security, role scope, and operational hardening

Target score: `84 -> 93`

Deliverables:
1. HQ/branch/employee/external advisor permission matrix.
2. Workplace-scoped data tests.
3. PII masking and no-leak tests for logs/provider keys/audit IDs.
4. Runtime smoke checks.
5. Monitoring/logging hooks and failure runbooks.
6. Backup/restore and rollback notes for pilot.

Exit criteria:
- Controlled pilot risk is bounded and visible.

### Milestone G — Hours 450-500: Commercial pilot readiness

Target score: `93 -> 100`

Deliverables:
1. Onboarding checklist.
2. First payroll close runbook.
3. Known limitations and human-review boundaries.
4. Demo script and acceptance checklist.
5. Operator/admin docs.
6. Final `/grill me` gap review.

Exit criteria:
- The product is ready for a controlled, operator-supported pilot; not necessarily fully self-serve public SaaS.

---

## PR Selection Rule

Every PR must declare one of these stack layers:

1. `domain-core`
2. `closing-e2e`
3. `runtime-api`
4. `ui-operator`
5. `approval-audit`
6. `permissions-tenant`
7. `demo-pilot`
8. `ops-hardening`
9. `docs-runbook`

A PR is valid if it does at least one of the following:
- Moves a payroll closing E2E path forward.
- Turns a preview/helper into a runtime/API/UI/draft/approval/audit step.
- Reduces pilot risk around permission, PII, payroll correctness, or operations.
- Adds demo data or runbook content needed to sell/validate the product.

A PR is low priority if it only hardens an isolated helper without linking to a customer-visible flow or safety blocker.

---

## Per-Cycle Procedure

1. Verify canonical workdir, branch, origin, status, HEAD.
2. Sync `develop` with `origin/develop`.
3. Check whether any open runway PR needs closeout first.
4. Pick exactly one PR slice from the nearest milestone.
5. Write failing test first.
6. Implement minimal code.
7. Run focused tests.
8. Run `python3 scripts/run_korea_regional_smoke.py` when Korea tests changed.
9. Run `python3 -m py_compile` for touched Python files where useful.
10. Commit and push.
11. If frontend/UI changed, build and deploy or explain why Vercel preview cannot show the change. Verify the public URL with HTTP 200 and critical asset checks.
12. Create PR if tooling allows; otherwise report compare/new PR URL.
13. Report score movement conservatively against the +10/day target.

---

## PDCA Briefing Format

Every PDCA briefing must answer:

1. **결론** — current score, daily +10 target status, current milestone, on/off track.
2. **근거** — repo path, branch, HEAD, latest commits/PRs, tests, cron status.
3. **리스크** — top 3 product risks, not generic engineering worries.
4. **다음 행동** — exact next PR slice, files, tests.
5. **/grill me** — what still does not look like a product.

Scoring rule:
- Helper-only change: +0 to +1 at most.
- Closing read model/API: can move +2 to +5 if it connects modules.
- Runtime state/approval/audit: can move +5 to +10 across a milestone.
- UI/demo tenant/permission safety drive most movement above 60.

---

## Immediate Next Slice

Milestone A, PR 1:

```text
feat: add Korea payroll closing session read model
```

Files:
- Create: `hrms/regional/south_korea/payroll_closing_session.py`
- Create: `hrms/tests/test_korea_payroll_closing_session.py`

Required output fields:
- `contract_type: korea_payroll_closing_session_v1`
- `company`
- `workplace`
- `period_start`
- `period_end`
- `status`
- `blockers[]`
- `next_actions[]`
- `readiness_cards[]`
- `payroll_artifacts`
- `approval_state`
- `notification_state`
- `audit_preview`
- `requires_human_approval: true`
- `ai_role: assistant_only`

Acceptance tests:
- happy path produces review-ready session.
- missing attendance creates blocker.
- missing approver creates blocker.
- invalid period fails closed.
- cross-company/workplace data is rejected or explicitly excluded.
- no numeric legal/probability score appears.

---

## Operator Warning

The purpose of extending to 500 hours is not to relax into vague motion. It is to avoid false urgency while keeping direction strict.

Bad 500-hour behavior:
- adding helpers forever;
- hardening random edge cases with no product path;
- reporting PR count as progress;
- ignoring UI/runtime/permission/demo work.

Good 500-hour behavior:
- steady stack building;
- each layer connects to payroll close, operator UX, pilot safety, or demo readiness;
- every 30-minute run leaves a small, reviewable artifact or a verified blocker;
- every briefing says what is still not product-grade.
