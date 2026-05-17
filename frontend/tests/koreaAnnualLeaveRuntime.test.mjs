/**
 * Node unit tests for koreaAnnualLeaveRuntime.js
 *
 * Follows the pattern of koreaPayrollClosingRuntime.test.mjs:
 * - no external test runner needed; run with: node frontend/tests/koreaAnnualLeaveRuntime.test.mjs
 * - all assertions throw on failure (node:assert/strict)
 */

import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import {
	isFrappeRuntimeAvailable,
	ensureKoreaAnnualLeaveFrappeCallRuntime,
	getKoreaAnnualLeaveRuntimeCompany,
	fetchKoreaAnnualLeavePreview,
	fetchKoreaAnnualLeaveWithRatio,
	applyKoreaLeaveAllocation,
	assertKoreaAnnualLeavePreview,
	assertKoreaAnnualLeaveRatioPreview,
	assertKoreaLeaveAllocationApplyResult,
	hasKoreaAnnualLeavePreviewData,
	hasKoreaAnnualLeaveRatioData,
	buildKoreaAnnualLeaveDisplayData,
	KOREA_LEAVE_PREVIEW_METHOD,
	KOREA_LEAVE_RATIO_METHOD,
	KOREA_LEAVE_APPLY_METHOD,
} from "../src/data/koreaAnnualLeaveRuntime.js"

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, "..")

// ---------------------------------------------------------------------------
// isFrappeRuntimeAvailable
// ---------------------------------------------------------------------------
assert.equal(isFrappeRuntimeAvailable({}), false)
assert.equal(isFrappeRuntimeAvailable({ frappe: {} }), false)
assert.equal(isFrappeRuntimeAvailable({ frappe: { call: () => {} } }), true)

// ---------------------------------------------------------------------------
// ensureKoreaAnnualLeaveFrappeCallRuntime — polyfill install
// ---------------------------------------------------------------------------
const fetchCalls = []
const browserWindowWithoutCall = {
	csrf_token: "csrf-test",
	frappe: { session: { user: "Administrator" } },
	fetch: async (url, options) => {
		fetchCalls.push({ url, options })
		return {
			ok: true,
			status: 200,
			json: async () => ({
				message: {
					contract_type: "korea_leave_allocation_preview_v1",
					runtime_action: "preview_only",
					requires_runtime_apply: true,
					draft: {},
				},
			}),
		}
	},
}

assert.equal(ensureKoreaAnnualLeaveFrappeCallRuntime(browserWindowWithoutCall), true)
assert.equal(isFrappeRuntimeAvailable(browserWindowWithoutCall), true)

const callResp = await browserWindowWithoutCall.frappe.call({
	method: KOREA_LEAVE_PREVIEW_METHOD,
	args: { employee: JSON.stringify({ name: "EMP-001", date_of_joining: "2020-01-01" }), as_of_date: "2026-05-01" },
})
assert.equal(fetchCalls[0].url, `/api/method/${KOREA_LEAVE_PREVIEW_METHOD}`)
assert.equal(fetchCalls[0].options.method, "POST")
assert.equal(fetchCalls[0].options.headers["X-Frappe-CSRF-Token"], "csrf-test")
assert.match(String(fetchCalls[0].options.body), /as_of_date=2026-05-01/)
assert.equal(callResp.message.runtime_action, "preview_only")

// blocked method must be rejected
await assert.rejects(
	browserWindowWithoutCall.frappe.call({ method: "frappe.client.insert", args: {} }),
	/read-only runtime methods/,
)
assert.equal(fetchCalls.length, 1)

// no-fetch env returns false
assert.equal(ensureKoreaAnnualLeaveFrappeCallRuntime({ frappe: {}, fetch: null }), false)

// ---------------------------------------------------------------------------
// getKoreaAnnualLeaveRuntimeCompany
// ---------------------------------------------------------------------------
assert.equal(
	getKoreaAnnualLeaveRuntimeCompany({ frappe: { boot: { user: { company: "User Co" } } } }, "Fallback"),
	"User Co",
)
assert.equal(
	getKoreaAnnualLeaveRuntimeCompany({ frappe: { boot: { sysdefaults: { company: "Sys Co" } } } }, "Fallback"),
	"Sys Co",
)
assert.equal(
	getKoreaAnnualLeaveRuntimeCompany({ frappe: { session: { company: "Session Co" } } }, "Fallback"),
	"Session Co",
)
assert.equal(
	getKoreaAnnualLeaveRuntimeCompany({ frappe: { defaults: { get_default: () => "Default Co" } } }, "Fallback"),
	"Default Co",
)
assert.equal(getKoreaAnnualLeaveRuntimeCompany({}, "Fallback"), "Fallback")

// ---------------------------------------------------------------------------
// fetchKoreaAnnualLeavePreview — happy path
// ---------------------------------------------------------------------------
const previewCalls = []
const previewWindow = {
	frappe: {
		boot: { sysdefaults: { company: "Preview Co" } },
		call: async (payload) => {
			previewCalls.push(payload)
			return {
				message: {
					contract_type: "korea_leave_allocation_preview_v1",
					runtime_action: "preview_only",
					requires_runtime_apply: true,
					draft: {
						contract_type: "korea_leave_allocation_draft_v1",
						employee: "EMP-001",
						employee_name: "홍길동",
						from_date: "2026-01-01",
						to_date: "2026-12-31",
						new_leaves_allocated: 15,
						total_reference_entitlement: 15,
						existing_allocated_days: 0,
						requires_runtime_apply: true,
						entitlement_reference: {
							basis: "Hire Date",
							hire_date: "2021-01-01",
							as_of_date: "2026-05-01",
							service_years: 5,
							monthly_accrual_days: 0,
							annual_entitlement_days: 15,
							total_entitlement_days: 15,
						},
					},
				},
			}
		},
	},
}

const previewResult = await fetchKoreaAnnualLeavePreview({
	employee: { name: "EMP-001", date_of_joining: "2021-01-01" },
	asOfDate: "2026-05-01",
	win: previewWindow,
})
assert.equal(previewCalls.length, 1)
assert.equal(previewCalls[0].method, KOREA_LEAVE_PREVIEW_METHOD)
assert.match(previewCalls[0].args.employee, /EMP-001/)
assert.equal(previewCalls[0].args.as_of_date, "2026-05-01")
assert.equal(previewResult.source, "runtime_read_only")
assert.equal(previewResult.data.contract_type, "korea_leave_allocation_preview_v1")
assert.equal(previewResult.data.runtime_action, "preview_only")
assert.equal(previewResult.data.requires_runtime_apply, true)

// ---------------------------------------------------------------------------
// fetchKoreaAnnualLeavePreview — wrong contract_type
// ---------------------------------------------------------------------------
await assert.rejects(
	() =>
		fetchKoreaAnnualLeavePreview({
			employee: { name: "EMP-001", date_of_joining: "2021-01-01" },
			asOfDate: "2026-05-01",
			win: {
				frappe: {
					call: async () => ({ message: { contract_type: "wrong_type", runtime_action: "preview_only", requires_runtime_apply: true, draft: {} } }),
				},
			},
		}),
	/Unexpected Korea annual leave preview contract_type/,
)

// ---------------------------------------------------------------------------
// fetchKoreaAnnualLeavePreview — no frappe runtime
// ---------------------------------------------------------------------------
await assert.rejects(
	() =>
		fetchKoreaAnnualLeavePreview({
			employee: { name: "EMP-001", date_of_joining: "2021-01-01" },
			asOfDate: "2026-05-01",
			win: {},
		}),
	/Frappe runtime is not available/,
)

// ---------------------------------------------------------------------------
// fetchKoreaAnnualLeaveWithRatio — happy path
// ---------------------------------------------------------------------------
const ratioCalls = []
const ratioWindow = {
	frappe: {
		call: async (payload) => {
			ratioCalls.push(payload)
			return {
				message: {
					contract_type: "korea_annual_leave_attendance_ratio_preview_v1",
					runtime_action: "preview_only",
					requires_runtime_apply: true,
					draft: {
						basis: "Hire Date",
						hire_date: "2021-01-01",
						as_of_date: "2026-05-01",
						attendance_ratio: 0.75,
						threshold: 0.8,
						below_threshold: true,
						annual_entitlement_days: 0,
						monthly_accrual_days: 11,
						total_entitlement_days: 11,
					},
					meta: { employee: "EMP-001", as_of_date: "2026-05-01", attendance_ratio: 0.75, threshold: 0.8 },
				},
			}
		},
	},
}

const ratioResult = await fetchKoreaAnnualLeaveWithRatio({
	employee: { name: "EMP-001", date_of_joining: "2021-01-01" },
	asOfDate: "2026-05-01",
	attendanceRatio: 0.75,
	win: ratioWindow,
})
assert.equal(ratioCalls.length, 1)
assert.equal(ratioCalls[0].method, KOREA_LEAVE_RATIO_METHOD)
assert.equal(ratioCalls[0].args.attendance_ratio, "0.75")
assert.equal(ratioResult.source, "runtime_read_only")
assert.equal(ratioResult.data.contract_type, "korea_annual_leave_attendance_ratio_preview_v1")

// ---------------------------------------------------------------------------
// applyKoreaLeaveAllocation — fail-closed when humanApproved !== true
// ---------------------------------------------------------------------------
const draftPayload = {
	contract_type: "korea_leave_allocation_draft_v1",
	employee: "EMP-001",
	leave_type: "Annual Leave",
	from_date: "2026-01-01",
	to_date: "2026-12-31",
	new_leaves_allocated: 15,
	requires_runtime_apply: true,
}

// false → must throw (fail-closed)
await assert.rejects(
	() =>
		applyKoreaLeaveAllocation({
			draft: draftPayload,
			humanApproved: false,
			win: { frappe: { call: async () => ({}) } },
		}),
	/humanApproved must be strictly true/,
)

// null → must throw
await assert.rejects(
	() =>
		applyKoreaLeaveAllocation({
			draft: draftPayload,
			humanApproved: null,
			win: { frappe: { call: async () => ({}) } },
		}),
	/humanApproved must be strictly true/,
)

// "true" string → must throw (strict true required)
await assert.rejects(
	() =>
		applyKoreaLeaveAllocation({
			draft: draftPayload,
			humanApproved: "true",
			win: { frappe: { call: async () => ({}) } },
		}),
	/humanApproved must be strictly true/,
)

// ---------------------------------------------------------------------------
// applyKoreaLeaveAllocation — success when humanApproved === true
// ---------------------------------------------------------------------------
const applyCalls = []
const applyWindow = {
	frappe: {
		call: async (payload) => {
			applyCalls.push(payload)
			return {
				message: {
					contract_type: "korea_leave_allocation_runtime_apply_v1",
					applied: true,
					leave_allocation_name: "LA-2026-0001",
				},
			}
		},
	},
}

const applyResult = await applyKoreaLeaveAllocation({
	draft: draftPayload,
	humanApproved: true,
	actor: "Administrator",
	win: applyWindow,
})
assert.equal(applyCalls.length, 1)
assert.equal(applyCalls[0].method, KOREA_LEAVE_APPLY_METHOD)
assert.equal(applyCalls[0].args.human_approved, "true")
assert.match(applyCalls[0].args.draft, /EMP-001/)
assert.equal(applyCalls[0].args.apply_actor, "Administrator")
assert.equal(applyResult.source, "runtime_apply")
assert.equal(applyResult.data.contract_type, "korea_leave_allocation_runtime_apply_v1")
assert.equal(applyResult.data.applied, true)

// ---------------------------------------------------------------------------
// applyKoreaLeaveAllocation — no frappe runtime → must throw
// ---------------------------------------------------------------------------
await assert.rejects(
	() =>
		applyKoreaLeaveAllocation({
			draft: draftPayload,
			humanApproved: true,
			win: {},
		}),
	/Frappe runtime is not available/,
)

// ---------------------------------------------------------------------------
// hasKoreaAnnualLeavePreviewData / hasKoreaAnnualLeaveRatioData
// ---------------------------------------------------------------------------
assert.equal(
	hasKoreaAnnualLeavePreviewData({
		contract_type: "korea_leave_allocation_preview_v1",
		runtime_action: "preview_only",
		draft: {},
	}),
	true,
)
assert.equal(hasKoreaAnnualLeavePreviewData(null), false)
assert.equal(
	hasKoreaAnnualLeavePreviewData({
		contract_type: "wrong",
		runtime_action: "preview_only",
		draft: {},
	}),
	false,
)

assert.equal(
	hasKoreaAnnualLeaveRatioData({
		contract_type: "korea_annual_leave_attendance_ratio_preview_v1",
		runtime_action: "preview_only",
		draft: {},
	}),
	true,
)
assert.equal(hasKoreaAnnualLeaveRatioData({}), false)

// ---------------------------------------------------------------------------
// buildKoreaAnnualLeaveDisplayData
// ---------------------------------------------------------------------------
const samplePreview = {
	contract_type: "korea_leave_allocation_preview_v1",
	runtime_action: "preview_only",
	requires_runtime_apply: true,
	draft: {
		contract_type: "korea_leave_allocation_draft_v1",
		employee: "EMP-001",
		employee_name: "홍길동",
		company: "Korea Demo Co",
		leave_type: "Annual Leave",
		from_date: "2026-01-01",
		to_date: "2026-12-31",
		new_leaves_allocated: 15,
		total_reference_entitlement: 15,
		existing_allocated_days: 0,
		requires_runtime_apply: true,
		entitlement_reference: {
			basis: "Hire Date",
			hire_date: "2021-01-01",
			as_of_date: "2026-05-01",
			service_years: 5,
			monthly_accrual_days: 0,
			annual_entitlement_days: 15,
			total_entitlement_days: 15,
		},
	},
}

const display = buildKoreaAnnualLeaveDisplayData({ previewData: samplePreview })
assert.equal(display.employee, "EMP-001")
assert.equal(display.employeeName, "홍길동")
assert.equal(display.serviceYears, 5)
assert.equal(display.annualEntitlement, 15)
assert.equal(display.totalEntitlement, 15)
assert.equal(display.allocatedDays, 15)
assert.equal(display.usedDays, 0)
assert.equal(display.remainingDays, 15)
assert.equal(display.ratioApplied, false)
assert.equal(display.isBelowThreshold, false)

// with usage
const displayWithUsage = buildKoreaAnnualLeaveDisplayData({
	previewData: samplePreview,
	usageData: { used_days: 5 },
})
assert.equal(displayWithUsage.usedDays, 5)
assert.equal(displayWithUsage.remainingDays, 10)

// null input → null
assert.equal(buildKoreaAnnualLeaveDisplayData({}), null)

// ---------------------------------------------------------------------------
// Verify Vue view file references runtime
// ---------------------------------------------------------------------------
const viewSource = await readFile(resolve(frontendRoot, "src/views/KoreaAnnualLeaveDashboard.vue"), "utf8")
assert.match(viewSource, /fetchKoreaAnnualLeavePreview/)
assert.match(viewSource, /koreaAnnualLeaveRuntime/)
assert.match(viewSource, /월차|연차|잔여|사용/)
assert.match(viewSource, /humanApproved/)

console.log("koreaAnnualLeaveRuntime.test.mjs: all assertions passed")
