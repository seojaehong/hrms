import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { fileURLToPath, pathToFileURL } from "node:url"
import { dirname, resolve } from "node:path"

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, "..")

const fixtureModule = await import(pathToFileURL(resolve(root, "src/data/koreaPayrollReviewAuditFixture.js")))
const { koreaPayrollReviewAuditFixture } = fixtureModule

assert.equal(koreaPayrollReviewAuditFixture.contract_type, "korea_payroll_review_audit_log_ui_fixture_v1")
assert.equal(koreaPayrollReviewAuditFixture.runtime_action, "preview_only")
assert.equal(koreaPayrollReviewAuditFixture.preview_source, "static_fixture")
assert.equal(koreaPayrollReviewAuditFixture.requires_human_approval, true)
assert.equal(koreaPayrollReviewAuditFixture.ai_role, "assistant_only")
assert.ok(koreaPayrollReviewAuditFixture.summary.total_count >= 3)
assert.ok(koreaPayrollReviewAuditFixture.summary.pending_follow_up_count >= 1)

for (const item of koreaPayrollReviewAuditFixture.items) {
	assert.equal(item.contract_type, "korea_payroll_closing_review_audit_log_runtime_insert_v1")
	assert.equal(item.runtime_action, "runtime_review_audit_log_created")
	assert.equal(item.requires_human_approval, true)
	assert.equal(item.ai_role, "assistant_only")
	assert.ok(item.company)
	assert.ok(item.workplace)
	assert.match(item.period_start, /^\d{4}-\d{2}-\d{2}$/)
	assert.match(item.period_end, /^\d{4}-\d{2}-\d{2}$/)
	assert.ok(["approved", "rejected", "changes_requested"].includes(item.review_status))
	assert.ok(!JSON.stringify(item).match(/risk[_ -]?score|probability|success[_ -]?rate/i))
}

const routerSource = await readFile(resolve(root, "src/router/index.js"), "utf8")
assert.match(routerSource, /KoreaPayrollReviewAuditLogs/)
assert.match(routerSource, /\/dashboard\/korea-payroll-review-audit-logs/)

const homeSource = await readFile(resolve(root, "src/views/Home.vue"), "utf8")
assert.match(homeSource, /Korea Payroll Review Audit Logs/)
assert.match(homeSource, /KoreaPayrollReviewAuditLogs/)

const viewSource = await readFile(resolve(root, "src/views/KoreaPayrollReviewAuditLogs.vue"), "utf8")
assert.match(viewSource, /Human review audit trail/)
assert.match(viewSource, /preview-only/i)
