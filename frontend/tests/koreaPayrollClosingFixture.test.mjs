import assert from "node:assert/strict"
import { koreaPayrollClosingOperatorFixture } from "../src/data/koreaPayrollClosingFixture.js"

assert.equal(koreaPayrollClosingOperatorFixture.contract_type, "korea_payroll_closing_worklist_preview_v1")
assert.equal(koreaPayrollClosingOperatorFixture.runtime_action, "preview_only")
assert.equal(koreaPayrollClosingOperatorFixture.preview_source, "static_fixture")
assert.equal(koreaPayrollClosingOperatorFixture.requires_runtime_apply, false)
assert.equal(koreaPayrollClosingOperatorFixture.requires_human_approval, true)
assert.equal(koreaPayrollClosingOperatorFixture.ai_role, "assistant_only")
assert.ok(koreaPayrollClosingOperatorFixture.summary.total_count >= 3)
assert.ok(koreaPayrollClosingOperatorFixture.summary.blocked_count >= 1)
assert.ok(koreaPayrollClosingOperatorFixture.summary.review_ready_count >= 1)

for (const item of koreaPayrollClosingOperatorFixture.items) {
	assert.equal(item.company, koreaPayrollClosingOperatorFixture.company)
	assert.ok(item.workplace)
	assert.match(item.route, /^korea-payroll-closing-session\//)
	assert.equal(item.primary_action.requires_runtime_apply, false)
	assert.equal(item.requires_human_approval, true)
	assert.equal(item.ai_role, "assistant_only")
	assert.ok(["blocked", "review_ready"].includes(item.status))
	assert.ok(Array.isArray(item.readiness_cards))
	assert.ok(item.readiness_cards.length >= 4)
}

const blockedSession = koreaPayrollClosingOperatorFixture.items.find((item) => item.status === "blocked")
assert.ok(blockedSession, "fixture should include a blocked workplace")
assert.ok(blockedSession.blocker_codes.includes("attendance_not_ready") || blockedSession.blocker_codes.includes("kakao_queue_not_ready"))

const readySession = koreaPayrollClosingOperatorFixture.items.find((item) => item.status === "review_ready")
assert.ok(readySession, "fixture should include a review-ready workplace")
assert.equal(readySession.blocker_codes.length, 0)

function walk(value) {
	if (Array.isArray(value)) return value.forEach(walk)
	if (!value || typeof value !== "object") return
	for (const [key, child] of Object.entries(value)) {
		assert.ok(!/(risk|probability|success\s*rate|success_rate)/i.test(key), `forbidden numeric-score key: ${key}`)
		walk(child)
	}
}
walk(koreaPayrollClosingOperatorFixture)
