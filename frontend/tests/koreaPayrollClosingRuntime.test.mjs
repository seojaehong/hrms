import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { resolve } from "node:path"
import {
	getKoreaPayrollClosingRuntimeCompany,
	isFrappeRuntimeAvailable,
	loadKoreaAdminDashboardRuntime,
} from "../src/data/koreaPayrollClosingRuntime.js"

const method = "hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime"

assert.equal(isFrappeRuntimeAvailable({}), false)
assert.equal(isFrappeRuntimeAvailable({ frappe: {} }), false)
assert.equal(isFrappeRuntimeAvailable({ frappe: { call: () => {} } }), true)

assert.equal(
	getKoreaPayrollClosingRuntimeCompany({ frappe: { boot: { sysdefaults: { company: "Runtime Co" } } } }, "Fallback Co"),
	"Runtime Co",
)
assert.equal(
	getKoreaPayrollClosingRuntimeCompany({ frappe: { defaults: { get_default: () => "Default Co" } } }, "Fallback Co"),
	"Default Co",
)
assert.equal(getKoreaPayrollClosingRuntimeCompany({}, "Fallback Co"), "Fallback Co")

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

const viewSource = await readFile(resolve("frontend/src/views/KoreaPayrollClosing.vue"), "utf8")
assert.match(viewSource, /loadKoreaAdminDashboardRuntime/)
assert.match(viewSource, /runtime_read_only/)
assert.match(viewSource, /static fixture fallback is active/i)
assert.match(viewSource, /runtime_action=\{\{ runtimeDashboard\.runtime_action \}\}/)
