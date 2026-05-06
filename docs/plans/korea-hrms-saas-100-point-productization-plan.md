# Korea HRMS SaaS 100-Point Productization Plan

> **For Hermes:** Execute this as a 100-hour productization runway. Use `frappe-hrms-rapid-delivery`, `github-pr-workflow`, `test-driven-development`, and focused subagents when useful. Ship one small reviewable PR per run unless a blocker requires closeout instead.

**Goal:** Move `seojaehong/hrms` from a tested Korea regional HRMS core toward a commercially demonstrable SaaS for multi-location Korean SME/franchise HR, payroll close, approvals, Kakao notices, and labor operations.

**Architecture:** Keep `frappe/hrms` as the base application in our fork (`seojaehong/hrms`). Korea-specific functionality lives under `hrms/regional/south_korea` and must move from framework-free/preview-only contracts toward real Frappe runtime flows, screens, permissions, draft persistence, approval, audit logs, and demo tenant readiness. AI remains assistant-only: checklist, comparison, review, draft support; never numeric legal/probability prediction.

**Canonical workspace:** `/home/ubuntu/workspaces/seojaehong-hrms-100h`

**Canonical remote:** `https://github.com/seojaehong/hrms.git`

**Base branch:** `develop`

---

## Current Baseline

As of this plan, the project has strong Korea regional domain coverage but is not yet a commercial SaaS.

- SaaS readiness estimate: `38 / 100`
- Strengths:
  - Korea payroll/statutory/social-insurance core groundwork
  - Salary Slip and Payroll Entry preview adapters
  - Kakao notification queue/template/audit/dispatch contracts
  - Closing Center, Admin Dashboard, Approval Inbox, Mobile ESS/MSS contracts
  - Employment Contract, Leave Allocation, Attendance Closing, Expense Settlement
  - Regional smoke harness with direct no-bench tests
- Main gaps:
  - Too much preview-only behavior
  - Weak runtime persistence and mutation flows
  - Weak actual user-facing UI
  - Weak role/tenant/permission verification
  - No complete payroll-close end-to-end path
  - Demo tenant / pilot story not yet product-grade

---

## 100-Point SaaS Scorecard

Use this scorecard in every PDCA briefing. Do not game it with helper count; score only customer-visible product readiness.

### 1. Payroll Closing E2E — 25 points

Commercial user question: “Can one workplace close one month of payroll safely?”

- 0-5: pure helper/preview payloads only
- 6-10: API previews connect Salary Slip/Payroll Entry/statutory rows
- 11-15: draft close state can be created and reviewed in runtime
- 16-20: approval, blockers, audit log, and notification previews are connected
- 21-25: end-to-end demo workplace can close a payroll period with visible status, review, approval, and send/print-ready artifacts

### 2. Operations UI / Admin Home — 15 points

Commercial user question: “When I log in, do I know what is blocked and what to do next?”

- Closing Center cards
- workplace/month filters
- missing attendance, approval queue, contract/Kakao/payroll blockers
- route/action cards
- mobile-aware layout where relevant

### 3. Runtime Integration & Persistence — 15 points

Commercial user question: “Is this actually saved and controlled by Frappe, not just a preview function?”

- whitelisted APIs are still useful but not enough
- introduce safe draft records, runtime lookups, DocType/custom field integration, and explicit no-mutation boundaries where not yet ready
- every mutation must have approval/audit semantics

### 4. Role, Workplace, Tenant, and Audit Safety — 15 points

Commercial user question: “Can HQ, branch managers, employees, and external labor advisors see only what they should?”

- workplace-scoped queries
- role-aware action availability
- masked personal data
- audit events for payroll/contract/approval/notification actions
- no raw PII in provider/dedupe/log identifiers

### 5. Demo Tenant / Pilot Readiness — 10 points

Commercial user question: “Can we see this with realistic data in five minutes?”

Minimum demo data:
- HQ + 3 workplaces
- 50 employees
- monthly/salaried/hourly mix
- joiners/leavers
- overtime/night/holiday work
- missing attendance
- pending approvals
- unsigned contracts
- Kakao notice queue
- payroll close blockers

### 6. Payroll/Compliance Correctness Depth — 10 points

Commercial user question: “Does this behave like a Korean payroll/labor operations system?”

- policy/version basis
- statutory basis visibility
- evidence and manual review
- no public API dependency as default
- paid/partner/vendor/manual verification adapters as optional evidence layer

### 7. SaaS Operations — 10 points

Commercial user question: “Can this be operated without heroics?”

- smoke/regression harness
- deployment/runtime checks
- monitoring/logging hooks
- migration/backfill discipline
- onboarding docs
- rollback-safe small PRs

---

## Execution Rules

1. **No upstream distraction.** Work against `seojaehong/hrms`, not `frappe/hrms` upstream.
2. **One small PR per run.** If a PR is already open, close it out before starting another.
3. **E2E first.** Prefer PRs that move payroll closing from helper/preview toward customer-visible workflow.
4. **Stop random hardening unless it blocks E2E.** Hardening is still required for payroll/PII/permissions, but every hardening PR must say which product flow it unblocks.
5. **Preview-only is not a destination.** Every preview API should either feed a visible review screen, draft record, approval, audit event, or demo flow.
6. **Human approval is final authority.** AI and adapters can review, compare, summarize, and prepare drafts; they cannot finalize payroll or legal conclusions alone.
7. **No numeric legal/probability predictions.** Compliance diagnosis is qualitative, evidence-based, and human-review oriented.
8. **TDD required.** Red → Green → focused tests → Korea smoke harness when relevant → py_compile where useful.
9. **Report evidence.** Every run must report path, branch, HEAD, PR number, tests, score movement, blocker, and next target.

---

## Phase Plan to 100

### Phase 1 — 38 → 55: Close one Payroll Closing E2E demo path

**Outcome:** One workplace can run a visible payroll closing review flow for one period.

Priority PR slices:
1. Add payroll closing session/read model that aggregates workplace, period, attendance, payroll entry, salary slips, statutory rows, approvals, Kakao notices, and blockers.
2. Add draft close state contract/API with explicit `preview`, `draft`, `approved`, `ready_to_send`, `closed` statuses.
3. Add approval action contract for payroll close review with audit event payloads.
4. Connect Kakao/payslip preview artifacts to the closing session.
5. Add no-bench tests and include them in Korea smoke harness.

Acceptance:
- A single JSON/API response can explain the payroll close state for a workplace/month.
- It includes blockers, next actions, approver requirements, and artifact readiness.
- Tests prove invalid period/workplace/cross-company data fails closed.

### Phase 2 — 55 → 68: Product home and operator UX

**Outcome:** User can see what to do next without reading API docs.

Priority PR slices:
1. Admin Home/Closing Center cards for payroll close, missing attendance, pending approvals, unsigned contracts, Kakao queue.
2. Workplace/month filters and drilldown targets.
3. Mobile ESS/MSS review cards for manager approvals.
4. Empty/loading/error state contracts.

Acceptance:
- A demo dashboard payload has customer-readable cards and CTA routes.
- Cards are role-aware and workplace-scoped.

### Phase 3 — 68 → 78: Runtime persistence and approval/audit

**Outcome:** Preview payloads start becoming controlled runtime workflows.

Priority PR slices:
1. Introduce safe draft records or DocType/custom-field integration for payroll close sessions.
2. Add audit log event helpers for close preview, draft creation, approval, rejection, notice dispatch preview.
3. Add permission guards for HQ/admin/branch manager/external advisor/employee roles.
4. Add migration-safe setup/install hooks only when direct tests and rollback plan exist.

Acceptance:
- Mutation boundaries are explicit.
- Audit events are deterministic, PII-safe, and tested.

### Phase 4 — 78 → 88: Demo tenant and pilot story

**Outcome:** Five-minute commercial demo becomes possible.

Priority PR slices:
1. Demo seed for HQ + 3 workplaces + 50 employees.
2. Scenario data: missing attendance, overtime/night/holiday, joiner/leaver, unsigned contract, approval queue, Kakao queue.
3. Demo payroll close scenario report.
4. One command/script to generate or validate demo state.

Acceptance:
- Demo seed can produce a realistic payroll close blocker board.
- Pilot script explains exactly what the user can click/review.

### Phase 5 — 88 → 95: Security, tenant isolation, and operational hardening

**Outcome:** Pilot risk is reduced enough for controlled customer use.

Priority PR slices:
1. Workplace-scoped permission tests.
2. PII masking and print/log guards.
3. Audit trail completeness tests.
4. Runtime smoke/deployment checks.
5. Error reporting and rollback docs.

Acceptance:
- Sensitive flows do not leak employee identifiers/phone/RRN-like values in logs/provider keys.
- Role/workplace boundaries fail closed.

### Phase 6 — 95 → 100: Commercial readiness polish

**Outcome:** A controlled pilot customer can use the system with operator support.

Priority PR slices:
1. Onboarding checklist and setup wizard contract.
2. Pilot runbook for first payroll close.
3. Known limitations and human-review boundaries.
4. Demo/video script or guided walkthrough.
5. Production readiness checklist.

Acceptance:
- A non-developer operator can follow the pilot runbook.
- Remaining risks are known, bounded, and visible.

---

## Next Immediate PR Target

Start with Phase 1, PR 1:

**Title:** `feat: add Korea payroll closing session read model`

**Goal:** Create a framework-free read model under `hrms/regional/south_korea` that aggregates workplace/month payroll close readiness into one customer-visible session payload.

**Likely files:**
- Create: `hrms/regional/south_korea/payroll_closing_session.py`
- Create: `hrms/tests/test_korea_payroll_closing_session.py`
- Verify smoke harness discovers the new test file dynamically.

**Minimum output fields:**
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

**TDD acceptance:**
- happy path produces review-ready session with next actions
- missing attendance creates blocker
- missing approver creates blocker
- cross-workplace/cross-company items are rejected or excluded explicitly
- invalid period fails closed
- no numeric probability/risk score appears

---

## PDCA Briefing Format

Every briefing must include:

1. **Conclusion** — current score and whether runway is on track
2. **Evidence** — repo path, branch, HEAD, PRs, tests, cron status
3. **Score movement** — old score → new score, and why
4. **Gap to 100** — top 3 blockers only
5. **Next PR** — exact slice, files, tests
6. **/grill me** — blunt critique: what is still not a product

