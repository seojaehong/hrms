import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { fileURLToPath, pathToFileURL } from "node:url"
import { dirname, resolve } from "node:path"

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, "..")

const fixtureModule = await import(pathToFileURL(resolve(root, "src/data/koreaPayrollReviewAuditFixture.js")))
const { koreaPayrollReviewAuditFixture, getKoreaPayrollReviewAuditDetail } = fixtureModule

assert.equal(koreaPayrollReviewAuditFixture.contract_type, "korea_payroll_review_audit_log_ui_fixture_v1")
assert.equal(koreaPayrollReviewAuditFixture.runtime_action, "preview_only")
assert.equal(koreaPayrollReviewAuditFixture.preview_source, "static_fixture")
assert.equal(koreaPayrollReviewAuditFixture.requires_human_approval, true)
assert.equal(koreaPayrollReviewAuditFixture.ai_role, "assistant_only")
assert.ok(koreaPayrollReviewAuditFixture.summary.total_count >= 3)
assert.ok(koreaPayrollReviewAuditFixture.summary.pending_follow_up_count >= 1)

const allowedStatusByAction = {
	approve_draft: "draft_human_approved",
	reject_draft: "draft_human_rejected",
	request_changes: "draft_changes_requested",
}

for (const item of koreaPayrollReviewAuditFixture.items) {
	assert.equal(item.contract_type, "korea_payroll_closing_review_audit_log_runtime_insert_v1")
	assert.equal(item.source_audit_log_contract_type, "korea_payroll_closing_draft_review_audit_log_v1")
	assert.equal(item.runtime_action, "runtime_review_audit_log_created")
	assert.equal(item.requires_runtime_apply, false)
	assert.equal(item.mutation_boundary, "audit_log_only_no_submit_no_send_no_provider_call")
	assert.equal(item.doctype, "Korea Payroll Closing Review Audit Log")
	assert.equal(item.previous_status, "draft_pending_human_approval")
	assert.equal(item.status, allowedStatusByAction[item.action])
	assert.ok(item.draft_name)
	assert.ok(item.source_payroll_entry)
	assert.ok(item.review_actor)
	assert.ok(item.audit_actor)
	assert.equal(item.docstatus, 0)
	assert.equal(item.requires_human_approval, true)
	assert.equal(item.ai_role, "assistant_only")
	assert.ok(item.company)
	assert.ok(item.workplace)
	assert.match(item.period_start, /^\d{4}-\d{2}-\d{2}$/)
	assert.match(item.period_end, /^\d{4}-\d{2}-\d{2}$/)
	assert.ok(item.route)
	assert.match(item.route, /^\/korea-payroll-review-audit-logs\//)
	assert.ok(!("source_draft" in item))
	assert.ok(!("review_status" in item))
	assert.ok(!("review_action" in item))
	assert.ok(!JSON.stringify(item).match(/risk[_ -]?score|probability|success[_ -]?rate/i))
}

const routerSource = await readFile(resolve(root, "src/router/index.js"), "utf8")
assert.match(routerSource, /KoreaPayrollReviewAuditLogs/)
assert.match(routerSource, /KoreaPayrollReviewAuditLogDetail/)
assert.match(routerSource, /\/dashboard\/korea-payroll-review-audit-logs/)
assert.match(routerSource, /\/korea-payroll-review-audit-logs\/:name/)

const detail = getKoreaPayrollReviewAuditDetail("KPCRAL-2026-05-BUSAN-BRANCH-001")
assert.equal(detail.contract_type, "korea_payroll_review_audit_log_detail_ui_fixture_v1")
assert.equal(detail.source_audit_log.contract_type, "korea_payroll_closing_review_audit_log_runtime_insert_v1")
assert.equal(detail.name, "KPCRAL-2026-05-BUSAN-BRANCH-001")
assert.equal(detail.status, "draft_changes_requested")
assert.equal(detail.runtime_action, "preview_only")
assert.equal(detail.preview_source, "static_fixture")
assert.equal(detail.requires_runtime_apply, false)
assert.equal(detail.requires_human_approval, true)
assert.equal(detail.ai_role, "assistant_only")
assert.ok(!JSON.stringify(detail).match(/risk[_ -]?score|probability|success[_ -]?rate/i))
assert.throws(() => getKoreaPayrollReviewAuditDetail("UNKNOWN"), /audit log fixture not found/)

const homeSource = await readFile(resolve(root, "src/views/Home.vue"), "utf8")
assert.match(homeSource, /Korea Payroll Review Audit Logs/)
assert.match(homeSource, /KoreaPayrollReviewAuditLogs/)

const viewSource = await readFile(resolve(root, "src/views/KoreaPayrollReviewAuditLogs.vue"), "utf8")
assert.match(viewSource, /Human review audit trail/)
assert.match(viewSource, /preview-only/i)
assert.match(viewSource, /item\.route/)

const detailViewSource = await readFile(resolve(root, "src/views/KoreaPayrollReviewAuditLogDetail.vue"), "utf8")
assert.match(detailViewSource, /Audit log detail/)
assert.match(detailViewSource, /source_runtime_apply/i)
assert.match(detailViewSource, /No submit · no send · no provider call/)
