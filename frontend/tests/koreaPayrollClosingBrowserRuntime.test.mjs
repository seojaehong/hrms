import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { mkdtemp, readFile, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import {
	KOREA_PAYROLL_CLOSING_BROWSER_ROUTE,
	buildKoreaPayrollClosingBrowserProbe,
	assertKoreaPayrollClosingBrowserWalkthrough,
} from "../src/data/koreaPayrollClosingBrowserRuntime.js"
import {
	assertReadOnlyBrowserRuntimeRequests,
	buildBrowserRouteUrl,
	extractDevtoolsPortFromText,
	extractFrappeApiMethodFromUrl,
	normalizeBrowserRuntimeOptions,
	writeBrowserRuntimeReportFile,
} from "../../scripts/verify_korea_payroll_closing_browser_runtime.mjs"

assert.equal(KOREA_PAYROLL_CLOSING_BROWSER_ROUTE, "/hrms/dashboard/korea-payroll-closing")
assert.equal(
	buildBrowserRouteUrl({ baseUrl: "http://hrms.localhost:8000/", company: "노란봉투법 데모" }),
	"http://hrms.localhost:8000/hrms/dashboard/korea-payroll-closing?company=%EB%85%B8%EB%9E%80%EB%B4%89%ED%88%AC%EB%B2%95+%EB%8D%B0%EB%AA%A8",
)

const probeSource = buildKoreaPayrollClosingBrowserProbe({ company: "노란봉투법 데모" })
assert.match(probeSource, /frappe\.call/)
assert.match(probeSource, /window\.fetch\("\/api\/method\/" \+ method/)
assert.match(probeSource, /X-Frappe-CSRF-Token/)
assert.match(probeSource, /credentials: "same-origin"/)
assert.match(probeSource, /frappe\.auth\.get_logged_user/)
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
	domText: "실데이터 마감 목록 연결됨 · 읽기 전용(runtime_action=runtime_read_only) · 변경 없음(requires_runtime_apply=false) · 증적 보존 · AI=assistant_only · human approval required",
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
	() => assertKoreaPayrollClosingBrowserWalkthrough({ ...browserResult, domText: "정적 예시 데이터 미리보기" }),
	/browser DOM did not show the runtime-positive read-only state/,
)
assert.equal(
	assertKoreaPayrollClosingBrowserWalkthrough({ ...browserResult, domText: "실데이터 마감 목록 연결됨 · 증적 보존 · AI is assistant-only" }).runtime_verified,
	true,
)

assert.equal(
	extractFrappeApiMethodFromUrl("http://hrms.localhost:8000/api/method/hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime"),
	"hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime",
)
assert.equal(extractFrappeApiMethodFromUrl("http://hrms.localhost:8000/hrms/dashboard/korea-payroll-closing"), null)

const normalizedOptions = normalizeBrowserRuntimeOptions({
	args: { "base-url": " http://hrms.localhost:8000/ ", company: " 노란봉투법 데모 ", username: " demo.hr.manager@node.pe.kr ", chromium: " chromium-browser " },
	env: { FRAPPE_BROWSER_PASSWORD: " runtime-secret " },
})
assert.equal(normalizedOptions.baseUrl, "http://hrms.localhost:8000")
assert.equal(normalizedOptions.company, "노란봉투법 데모")
assert.equal(normalizedOptions.username, "demo.hr.manager@node.pe.kr")
assert.equal(normalizedOptions.password, "runtime-secret")
assert.equal(normalizedOptions.chromium, "chromium-browser")

for (const [field, args] of [
	["base-url", { "base-url": "  \t\n", company: "노란봉투법 데모", username: "demo.hr.manager@node.pe.kr", chromium: "chromium-browser" }],
	["company", { "base-url": "http://hrms.localhost:8000", company: "  \t\n", username: "demo.hr.manager@node.pe.kr", chromium: "chromium-browser" }],
	["username", { "base-url": "http://hrms.localhost:8000", company: "노란봉투법 데모", username: "  \t\n", chromium: "chromium-browser" }],
	["chromium", { "base-url": "http://hrms.localhost:8000", company: "노란봉투법 데모", username: "demo.hr.manager@node.pe.kr", chromium: "  \t\n" }],
]) {
	assert.throws(
		() => normalizeBrowserRuntimeOptions({ args, env: { FRAPPE_BROWSER_PASSWORD: "runtime-secret" } }),
		new RegExp(`${field} is required`),
	)
}

assert.throws(
	() => normalizeBrowserRuntimeOptions({
		args: { "base-url": "http://hrms.localhost:8000", company: "노란봉투법 데모", username: "demo.hr.manager@node.pe.kr", chromium: "chromium-browser", "report-file": "  \t\n" },
		env: { FRAPPE_BROWSER_PASSWORD: "runtime-secret" },
	}),
	/report-file must be a non-empty string/,
)

assert.throws(
	() => normalizeBrowserRuntimeOptions({
		args: { "base-url": "http://hrms.localhost:8000", company: "노란봉투법 데모", username: "demo.hr.manager@node.pe.kr", chromium: "chromium-browser" },
		env: { FRAPPE_BROWSER_PASSWORD: "  \t\n" },
	}),
	/password is required/,
)

assert.throws(
	() => normalizeBrowserRuntimeOptions({
		args: { "base-url": "http://hrms.localhost:8000", company: "노란봉투법 데모", username: "demo.hr.manager@node.pe.kr", chromium: "chromium-browser" },
		env: { FRAPPE_BROWSER_PASSWORD: "  \t\n", FRAPPE_PASSWORD: "fallback-secret" },
	}),
	/password is required/,
)

assert.equal(
	extractDevtoolsPortFromText("DevTools listening on ws://127.0.0.1:45359/devtools/browser/session-id"),
	45359,
)
assert.equal(extractDevtoolsPortFromText("Chrome stderr without debugger endpoint"), null)

const observed = assertReadOnlyBrowserRuntimeRequests([
	{
		url: "http://hrms.localhost:8000/api/method/frappe.auth.get_logged_user",
		postData: "",
	},
	{
		url: "http://hrms.localhost:8000/api/method/frappe.translate.load_all_translations?lang=ko&hash=0.1",
		postData: "",
	},
	{
		url: "http://hrms.localhost:8000/api/method/hrms.api.are_push_notifications_enabled",
		postData: "",
	},
	{
		url: "http://hrms.localhost:8000/api/method/hrms.api.get_current_employee_info",
		postData: "",
	},
	{
		url: "http://hrms.localhost:8000/api/method/hrms.api.get_current_user_info",
		postData: "",
	},
	{
		url: "http://hrms.localhost:8000/api/method/hrms.api.get_unread_notifications_count",
		postData: "",
	},
	{
		url: "http://hrms.localhost:8000/api/method/notification_relay.api.get_config?project_name=hrms",
		postData: "",
	},
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
	"frappe.auth.get_logged_user",
	"frappe.translate.load_all_translations",
	"hrms.api.are_push_notifications_enabled",
	"hrms.api.get_current_employee_info",
	"hrms.api.get_current_user_info",
	"hrms.api.get_unread_notifications_count",
	"hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime",
	"hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime",
	"notification_relay.api.get_config",
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

const reportTempDir = await mkdtemp(join(tmpdir(), "korea-browser-report-test-"))
try {
	const reportPath = join(reportTempDir, "nested", "browser", "report.json")
	const reportPayload = {
		contract_type: "korea_payroll_closing_browser_runtime_walkthrough_v1",
		runtime_action: "browser_runtime_read_only",
		runtime_verified: false,
		fixture_fallback_required: true,
	}
	await writeBrowserRuntimeReportFile(reportPath, reportPayload)
	assert.deepEqual(JSON.parse(await readFile(reportPath, "utf8")), reportPayload)

	const failedCliReportPath = join(reportTempDir, "cli", "missing-password.json")
	const failedCli = spawnSync(
		process.execPath,
		[
			"scripts/verify_korea_payroll_closing_browser_runtime.mjs",
			"--no-throw",
			"--base-url",
			"http://hrms.localhost:8000",
			"--company",
			"노란봉투법 데모",
			"--username",
			"demo.hr.manager@node.pe.kr",
			"--chromium",
			"chromium-browser",
			"--report-file",
			failedCliReportPath,
		],
		{
			cwd: new URL("../..", import.meta.url),
			env: { ...process.env, FRAPPE_BROWSER_PASSWORD: "", FRAPPE_PASSWORD: "" },
			encoding: "utf8",
		},
	)
	assert.equal(failedCli.status, 0)
	const failedCliPayload = JSON.parse(await readFile(failedCliReportPath, "utf8"))
	assert.equal(failedCliPayload.runtime_verified, false)
	assert.match(failedCliPayload.browser_blockers.join("\n"), /password is required/)
} finally {
	await rm(reportTempDir, { recursive: true, force: true })
}
