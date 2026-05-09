import assert from "node:assert/strict"
import {
	KOREA_PAYROLL_CLOSING_BROWSER_ROUTE,
	buildKoreaPayrollClosingBrowserProbe,
	assertKoreaPayrollClosingBrowserWalkthrough,
} from "../src/data/koreaPayrollClosingBrowserRuntime.js"
import {
	assertReadOnlyBrowserRuntimeRequests,
	extractDevtoolsPortFromText,
	extractFrappeApiMethodFromUrl,
} from "../../scripts/verify_korea_payroll_closing_browser_runtime.mjs"

assert.equal(KOREA_PAYROLL_CLOSING_BROWSER_ROUTE, "/hrms/dashboard/korea-payroll-closing")

const probeSource = buildKoreaPayrollClosingBrowserProbe({ company: "노란봉투법 데모" })
assert.match(probeSource, /frappe\.call/)
assert.match(probeSource, /window\.fetch\("\/api\/method\/" \+ method/)
assert.match(probeSource, /X-Frappe-CSRF-Token/)
assert.match(probeSource, /credentials: "same-origin"/)
assert.match(probeSource, /browser runtime probe only allows Korea payroll closing read-only methods/)
assert.match(probeSource, /list_korea_payroll_closing_worklist_runtime/)
assert.match(probeSource, /get_korea_admin_dashboard_runtime/)
assert.match(probeSource, /노란봉투법 데모/)
assert.doesNotMatch(probeSource, /save\(/i)
assert.doesNotMatch(probeSource, /submit\(/i)
assert.doesNotMatch(probeSource, /approve\(/i)

const browserResult = {
	url: "http://hrms.localhost:8000/hrms/dashboard/korea-payroll-closing",
	authenticated: true,
	dashboard: {
		contract_type: "korea_admin_dashboard_runtime_api_v1",
		runtime_action: "runtime_read_only",
		requires_runtime_apply: false,
		metrics: { blocked_payroll_closings: 1 },
	},
	worklist: {
		contract_type: "korea_payroll_closing_worklist_runtime_api_v1",
		runtime_action: "runtime_read_only",
		requires_runtime_apply: false,
		requires_human_approval: true,
		ai_role: "assistant_only",
		items: [{ name: "KPCS-1", runtime_action: "runtime_read_only", requires_runtime_apply: false, requires_human_approval: true, ai_role: "assistant_only" }],
	},
	domText: "Runtime worklist loaded · runtime_action=runtime_read_only · requires_runtime_apply=false · evidence remains read-only · AI=assistant_only · human approval required",
	calledMethods: [
		"hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime",
		"hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime",
	],
}
const positive = assertKoreaPayrollClosingBrowserWalkthrough(browserResult)
assert.equal(positive.runtime_verified, true)
assert.equal(positive.fixture_fallback_required, false)
assert.equal(positive.runtime_action, "browser_runtime_read_only")
assert.equal(positive.requires_runtime_apply, false)
assert.equal(positive.requires_human_approval, true)
assert.equal(positive.ai_role, "assistant_only")
assert.deepEqual(positive.dashboard, {
	contract_type: "korea_admin_dashboard_runtime_api_v1",
	runtime_action: "runtime_read_only",
	requires_runtime_apply: false,
	metric_keys: ["blocked_payroll_closings"],
})
assert.deepEqual(positive.worklist, {
	contract_type: "korea_payroll_closing_worklist_runtime_api_v1",
	runtime_action: "runtime_read_only",
	requires_runtime_apply: false,
	requires_human_approval: true,
	ai_role: "assistant_only",
	item_count: 1,
})

assert.throws(
	() => assertKoreaPayrollClosingBrowserWalkthrough({ ...browserResult, authenticated: false }),
	/authenticated browser session is required/,
)
assert.throws(
	() => assertKoreaPayrollClosingBrowserWalkthrough({ ...browserResult, worklist: { ...browserResult.worklist, items: [] } }),
	/positive runtime worklist rows/,
)
assert.throws(
	() => assertKoreaPayrollClosingBrowserWalkthrough({ ...browserResult, worklist: { ...browserResult.worklist, runtime_action: "save" } }),
	/Unexpected Korea payroll closing worklist runtime action/,
)
assert.throws(
	() => assertKoreaPayrollClosingBrowserWalkthrough({ ...browserResult, worklist: { ...browserResult.worklist, items: [{ ...browserResult.worklist.items[0], legalRiskScore: 0.8 }] } }),
	/score keys are not allowed/,
)
assert.throws(
	() => assertKoreaPayrollClosingBrowserWalkthrough({ ...browserResult, domText: "Static fixture preview" }),
	/browser DOM did not show the runtime-positive read-only state/,
)

assert.equal(
	extractFrappeApiMethodFromUrl("http://hrms.localhost:8000/api/method/hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime"),
	"hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime",
)
assert.equal(extractFrappeApiMethodFromUrl("http://hrms.localhost:8000/hrms/dashboard/korea-payroll-closing"), null)

assert.equal(
	extractDevtoolsPortFromText("DevTools listening on ws://127.0.0.1:45359/devtools/browser/session-id"),
	45359,
)
assert.equal(extractDevtoolsPortFromText("Chrome stderr without debugger endpoint"), null)

const observed = assertReadOnlyBrowserRuntimeRequests([
	{
		url: "http://hrms.localhost:8000/api/method/hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime",
		postData: "company=%EB%85%B8%EB%9E%80%EB%B4%89%ED%88%AC%EB%B2%95+%EB%8D%B0%EB%AA%A8",
	},
	{
		url: "http://hrms.localhost:8000/api/method/hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime",
		postData: "company=%EB%85%B8%EB%9E%80%EB%B4%89%ED%88%AC%EB%B2%95+%EB%8D%B0%EB%AA%A8",
	},
])
assert.deepEqual(observed.sort(), [
	"hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime",
	"hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime",
])

assert.throws(
	() => assertReadOnlyBrowserRuntimeRequests([
		{ url: "http://hrms.localhost:8000/api/method/frappe.client.save", postData: "doc={}" },
	]),
	/browser runtime observed non-read-only Frappe method/,
)
assert.throws(
	() => assertReadOnlyBrowserRuntimeRequests([
		{
			url: "http://hrms.localhost:8000/api/method/hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime",
			postData: "action=approve_draft",
		},
	]),
	/browser runtime observed mutation marker/,
)
