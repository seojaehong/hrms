import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import {
	getKoreaPayrollClosingRuntimeCompany,
	hasKoreaAdminDashboardRuntimeData,
	hasKoreaPayrollClosingRuntimeWorklistData,
	isFrappeRuntimeAvailable,
	loadKoreaAdminDashboardRuntime,
	loadKoreaPayrollClosingRuntimeWorklist,
	assertKoreaPayrollClosingRuntimeWorklist,
	getKoreaPayrollClosingRuntimeUiState,
	ensureKoreaPayrollClosingFrappeCallRuntime,
} from "../src/data/koreaPayrollClosingRuntime.js"

const method = "hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime"
const worklistMethod = "hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime"
const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, "..")

assert.equal(isFrappeRuntimeAvailable({}), false)
assert.equal(isFrappeRuntimeAvailable({ frappe: {} }), false)
assert.equal(isFrappeRuntimeAvailable({ frappe: { call: () => {} } }), true)

const browserFetchCalls = []
const browserWindowWithoutCall = {
	csrf_token: "csrf-token",
	frappe: { session: { user: "Administrator" } },
	fetch: async (url, options) => {
		browserFetchCalls.push({ url, options })
		return {
			ok: true,
			status: 200,
			json: async () => ({ message: { contract_type: "korea_admin_dashboard_runtime_api_v1", runtime_action: "runtime_read_only", requires_runtime_apply: false } }),
		}
	},
}
assert.equal(ensureKoreaPayrollClosingFrappeCallRuntime(browserWindowWithoutCall), true)
assert.equal(isFrappeRuntimeAvailable(browserWindowWithoutCall), true)
const browserCallResponse = await browserWindowWithoutCall.frappe.call({ method, args: { company: "Runtime Co" } })
assert.equal(browserFetchCalls[0].url, `/api/method/${method}`)
assert.equal(browserFetchCalls[0].options.method, "POST")
assert.equal(browserFetchCalls[0].options.headers["X-Frappe-CSRF-Token"], "csrf-token")
assert.match(String(browserFetchCalls[0].options.body), /company=Runtime\+Co/)
assert.equal(browserCallResponse.message.runtime_action, "runtime_read_only")
await assert.rejects(
	browserWindowWithoutCall.frappe.call({ method: "frappe.client.insert", args: { doc: "blocked" } }),
	/read-only runtime methods/,
)
assert.equal(browserFetchCalls.length, 1)
assert.equal(ensureKoreaPayrollClosingFrappeCallRuntime({ frappe: {}, fetch: null }), false)

assert.equal(
	getKoreaPayrollClosingRuntimeCompany({ frappe: { boot: { user: { company: "User Co" }, sysdefaults: { company: "Runtime Co" } } } }, "Fallback Co"),
	"User Co",
)
assert.equal(
	getKoreaPayrollClosingRuntimeCompany({ frappe: { boot: { sysdefaults: { company: "Runtime Co" } } } }, "Fallback Co"),
	"Runtime Co",
)
assert.equal(
	getKoreaPayrollClosingRuntimeCompany({ frappe: { session: { company: "Session Co" } } }, "Fallback Co"),
	"Session Co",
)
assert.equal(
	getKoreaPayrollClosingRuntimeCompany({ frappe: { defaults: { get_default: () => "Default Co" } } }, "Fallback Co"),
	"Default Co",
)
assert.equal(getKoreaPayrollClosingRuntimeCompany({}, "Fallback Co"), "Fallback Co")

// 폴백 미지정 + boot 후보 없음 → undefined (loader가 company 파라미터를 생략해 서버 Global Defaults 폴백을 태운다)
assert.equal(getKoreaPayrollClosingRuntimeCompany({}), undefined)

// company 미해결 시 loader는 args에서 company를 생략한다 (서버 기본값 위임)
{
	const calls = []
	const win = {
		location: { origin: "https://noho.safeclaw.kr" },
		frappe: {
			call: async ({ method, args }) => {
				calls.push({ method, args })
				return { message: { contract_type: "korea_admin_dashboard_runtime_api_v1", runtime_action: "runtime_read_only", requires_runtime_apply: false, company: "노호", workplaces: [], metrics: {}, dashboard: {} } }
			},
		},
	}
	const r = await loadKoreaAdminDashboardRuntime({ win })
	assert.equal(r.data.company, "노호")
	assert.ok(!("company" in calls[0].args), "company must be omitted when unresolved")
}


const calls = []
const runtimeWindow = {
	frappe: {
		boot: { sysdefaults: { company: "Runtime Co" } },
		call: async (payload) => {
			calls.push(payload)
			return {
				message: {
					contract_type: "korea_admin_dashboard_runtime_api_v1",
					runtime_action: "runtime_read_only",
					requires_runtime_apply: false,
					company: payload.args.company,
					workplaces: [],
					metrics: { blocked_payroll_closings: 2, payroll_review_audit_logs: 3, pending_payslips: 4, unclosed_attendance: 5 },
					dashboard: { cards: [{ key: "blocked_payroll_closings", count: 2 }] },
				},
			}
		},
	},
}

const result = await loadKoreaAdminDashboardRuntime({ win: runtimeWindow, fallbackCompany: "Fallback Co" })
assert.equal(calls.length, 1)
assert.equal(calls[0].method, method)
assert.deepEqual(calls[0].args, { company: "Runtime Co" })
assert.equal(result.source, "runtime_read_only")
assert.equal(result.data.contract_type, "korea_admin_dashboard_runtime_api_v1")
assert.equal(result.data.runtime_action, "runtime_read_only")
assert.equal(result.data.requires_runtime_apply, false)
assert.equal(result.data.metrics.blocked_payroll_closings, 2)
assert.equal(hasKoreaAdminDashboardRuntimeData(result.data), true)
assert.equal(
	hasKoreaAdminDashboardRuntimeData({
		contract_type: "korea_admin_dashboard_runtime_api_v1",
		runtime_action: "runtime_read_only",
		requires_runtime_apply: false,
		metrics: { blocked_payroll_closings: 0, payroll_review_audit_logs: 0, pending_payslips: 0, unclosed_attendance: 0 },
		dashboard: { cards: [{ key: "blocked_payroll_closings", count: 0 }] },
	}),
	false,
)

const worklistCalls = []
const runtimeWorklistWindow = {
	frappe: {
		boot: { sysdefaults: { company: "Runtime Co" } },
		call: async (payload) => {
			worklistCalls.push(payload)
			return {
				message: {
					contract_type: "korea_payroll_closing_worklist_runtime_api_v1",
					worklist_contract_type: "korea_payroll_closing_worklist_v1",
					runtime_action: "runtime_read_only",
					requires_runtime_apply: false,
					requires_human_approval: true,
					ai_role: "assistant_only",
					company: payload.args.company,
					workplaces: ["Seoul HQ"],
					summary: { total_count: 1, blocked_count: 1, review_ready_count: 0 },
					items: [
						{
							name: "KPCS/서울 001",
							company: payload.args.company,
							workplace: "Seoul HQ",
							period_start: "2026-05-01",
							period_end: "2026-05-31",
							status: "blocked",
							blocker_codes: ["attendance_not_ready"],
							primary_action: { action: "review_blockers", label: "Review blockers", requires_runtime_apply: false },
							route: "korea-payroll-closing-session/KPCS%2F%EC%84%9C%EC%9A%B8%20001",
							payroll_entry: "PAY-ENTRY-2026-05",
							employee_count: 22,
							readiness_cards: [{ key: "attendance", label: "Attendance", state: "blocked", summary: "1 open day" }],
							audit_preview: { runtime_action: "preview_only", requires_runtime_apply: false, blocker_codes: ["attendance_not_ready"] },
							source_session: { contract_type: "korea_payroll_closing_session_v1" },
							runtime_action: "runtime_read_only",
							requires_runtime_apply: false,
							requires_human_approval: true,
							ai_role: "assistant_only",
						},
					],
				},
			}
		},
	},
}

const worklistResult = await loadKoreaPayrollClosingRuntimeWorklist({ win: runtimeWorklistWindow, fallbackCompany: "Fallback Co", workplaces: ["Seoul HQ"] })
assert.equal(worklistCalls.length, 1)
assert.equal(worklistCalls[0].method, worklistMethod)
assert.deepEqual(worklistCalls[0].args, { company: "Runtime Co", workplaces: JSON.stringify(["Seoul HQ"]) })
assert.equal(worklistResult.source, "runtime_read_only")
assert.equal(worklistResult.data.contract_type, "korea_payroll_closing_worklist_runtime_api_v1")
assert.equal(worklistResult.data.runtime_action, "runtime_read_only")
assert.equal(worklistResult.data.requires_runtime_apply, false)
assert.equal(worklistResult.data.items[0].route, "korea-payroll-closing-session/KPCS%2F%EC%84%9C%EC%9A%B8%20001")
assert.equal(worklistResult.data.items[0].runtime_action, "runtime_read_only")
assert.equal(worklistResult.data.items[0].requires_runtime_apply, false)
assert.equal(hasKoreaPayrollClosingRuntimeWorklistData(worklistResult.data), true)
assert.equal(hasKoreaPayrollClosingRuntimeWorklistData({ contract_type: "korea_payroll_closing_worklist_runtime_api_v1", runtime_action: "runtime_read_only", requires_runtime_apply: false, items: [] }), false)

const runtimePositiveUiState = getKoreaPayrollClosingRuntimeUiState({
	runtimeDashboard: result.data,
	runtimeWorklist: worklistResult.data,
})
assert.equal(runtimePositiveUiState.dataSourceLabel, "Runtime read-only worklist")
assert.equal(runtimePositiveUiState.dataSourceBadge, "runtime worklist")
assert.equal(runtimePositiveUiState.showFixtureFallbackCopy, false)
assert.equal(runtimePositiveUiState.showRuntimePositiveCopy, true)
assert.match(runtimePositiveUiState.worklistBanner, /Runtime worklist loaded/i)
assert.match(runtimePositiveUiState.worklistBanner, /evidence remains read-only/i)
assert.doesNotMatch(runtimePositiveUiState.worklistBanner, /Gate 2/i)
assert.doesNotMatch(runtimePositiveUiState.worklistBanner, /fixture worklist remains visible/i)

const runtimeDashboardOnlyUiState = getKoreaPayrollClosingRuntimeUiState({
	runtimeDashboard: result.data,
	runtimeWorklist: { contract_type: "korea_payroll_closing_worklist_runtime_api_v1", runtime_action: "runtime_read_only", requires_runtime_apply: false, items: [] },
})
assert.equal(runtimeDashboardOnlyUiState.dataSourceLabel, "Runtime read-only dashboard")
assert.equal(runtimeDashboardOnlyUiState.showFixtureFallbackCopy, true)
assert.equal(runtimeDashboardOnlyUiState.showRuntimePositiveCopy, false)
assert.match(runtimeDashboardOnlyUiState.worklistBanner, /실데이터 워크리스트가 비어 있어/)
assert.match(runtimeDashboardOnlyUiState.worklistBanner, /정적 예시 데이터가 유지됩니다/)
assert.doesNotMatch(runtimeDashboardOnlyUiState.worklistBanner, /Gate 2/i)

await assert.rejects(
	() => loadKoreaAdminDashboardRuntime({ win: {}, fallbackCompany: "Fallback Co" }),
	/Frappe runtime is not available/,
)

await assert.rejects(
	() =>
		loadKoreaAdminDashboardRuntime({
			win: {
				frappe: {
					call: async () => ({ message: { contract_type: "wrong", runtime_action: "preview_only" } }),
				},
			},
			fallbackCompany: "Fallback Co",
		}),
	/Unexpected Korea admin dashboard runtime contract/,
)

await assert.rejects(
	() =>
		loadKoreaAdminDashboardRuntime({
			win: {
				frappe: {
					call: async () => ({ message: { contract_type: "korea_admin_dashboard_runtime_api_v1", runtime_action: "save" } }),
				},
			},
			fallbackCompany: "Fallback Co",
		}),
	/Unexpected Korea admin dashboard runtime action/,
)

await assert.rejects(
	() =>
		loadKoreaPayrollClosingRuntimeWorklist({
			win: {
				frappe: {
					call: async () => ({ message: { contract_type: "korea_payroll_closing_worklist_runtime_api_v1", runtime_action: "save", requires_runtime_apply: true } }),
				},
			},
			fallbackCompany: "Fallback Co",
		}),
	/Unexpected Korea payroll closing worklist runtime action/,
)

await assert.rejects(
	() =>
		loadKoreaPayrollClosingRuntimeWorklist({
			win: {
				frappe: {
					call: async () => ({
						message: {
							contract_type: "korea_payroll_closing_worklist_runtime_api_v1",
							runtime_action: "runtime_read_only",
							requires_runtime_apply: false,
							requires_human_approval: true,
							ai_role: "assistant_only",
							items: [{ runtime_action: "runtime_read_only", requires_runtime_apply: false, requires_human_approval: true, ai_role: "assistant_only", legalRiskScore: 0.9 }],
						},
					}),
				},
			},
			fallbackCompany: "Fallback Co",
		}),
	/score keys are not allowed/,
)

assert.throws(
	() =>
		assertKoreaPayrollClosingRuntimeWorklist({
			contract_type: "korea_payroll_closing_worklist_runtime_api_v1",
			runtime_action: "runtime_read_only",
			requires_runtime_apply: false,
			requires_human_approval: true,
			ai_role: "assistant_only",
			items: [{ runtime_action: "runtime_read_only", requires_runtime_apply: false, requires_human_approval: true, ai_role: "assistant_only", riskRating: "high" }],
		}),
	/score keys are not allowed/,
)

const viewSource = await readFile(resolve(frontendRoot, "src/views/KoreaPayrollClosing.vue"), "utf8")
assert.match(viewSource, /loadKoreaAdminDashboardRuntime/)
assert.match(viewSource, /loadKoreaPayrollClosingRuntimeWorklist/)
assert.match(viewSource, /runtime_read_only/)
assert.match(viewSource, /정적 예시 데이터로 표시 중입니다/)
assert.match(viewSource, /runtime_action=\{\{ runtimeDashboard\.runtime_action \}\}/)
assert.match(viewSource, /실데이터 대시보드 행이 없어/)
assert.match(viewSource, /runtime worklist/i)
assert.match(viewSource, /runtimeDashboard && !runtimeHasData && !runtimeHasWorklistData/)
assert.match(viewSource, /runtimeUiState\.worklistBanner/)
assert.doesNotMatch(viewSource, /Gate 2 runtime worklist bridge/i)
assert.match(viewSource, /runtimeWorklistError/)
assert.match(viewSource, /Runtime worklist read failed; fixture worklist fallback is active/i)
assert.match(viewSource, /runtimeWorklistError\.value = worklistResult\.reason/)
assert.match(viewSource, /summaryCards\.total_employees \?\? 'runtime'/)
assert.match(viewSource, /item\.employee_count \?\? 'runtime'/)
assert.match(viewSource, /findActiveSessionItem\(route\.params\.name\)/)
assert.match(viewSource, /Loading read-only Frappe runtime data/i)
