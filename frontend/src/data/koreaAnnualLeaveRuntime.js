/**
 * Runtime data binding for the Korea Annual Leave Dashboard.
 *
 * Patterns follow koreaPayrollClosingRuntime.js:
 * - frappe.call() polyfill for browser contexts without the full SDK
 * - fail-closed on mutation (human_approved strictly required)
 * - fixture fallback when Frappe is not available
 * - assertX() validators per contract_type
 *
 * Backend methods (Wave 1-3):
 *   preview:  hrms.regional.south_korea.leave_allocation_api.preview_korea_leave_allocation_draft
 *   ratio:    hrms.regional.south_korea.annual_leave_attendance_ratio_api.preview_korea_annual_leave_with_ratio
 *   apply:    hrms.regional.south_korea.leave_allocation_apply_api.apply_korea_leave_allocation_api
 */

export const KOREA_LEAVE_PREVIEW_METHOD =
	"hrms.regional.south_korea.leave_allocation_api.preview_korea_leave_allocation_draft"

export const KOREA_LEAVE_RATIO_METHOD =
	"hrms.regional.south_korea.annual_leave_attendance_ratio_api.preview_korea_annual_leave_with_ratio"

export const KOREA_LEAVE_APPLY_METHOD =
	"hrms.regional.south_korea.leave_allocation_apply_api.apply_korea_leave_allocation_api"

import { KOREA_ATTENDANCE_READ_ONLY_METHODS } from "./koreaAttendanceRuntime.js"

// 폴리필은 페이지 방문 순서에 따라 이 모듈이 먼저 설치할 수 있으므로,
// 같은 read-only 폴리필을 공유하는 근태 대시보드 메서드도 함께 허용한다.
// (미허용 시 근태 화면에 "fallback only allows ..." 디버그 문구 노출 사고)
const KOREA_ANNUAL_LEAVE_ALLOWED_METHODS = new Set([
	KOREA_LEAVE_PREVIEW_METHOD,
	KOREA_LEAVE_RATIO_METHOD,
	...KOREA_ATTENDANCE_READ_ONLY_METHODS,
])

// ---------------------------------------------------------------------------
// Frappe runtime detection + polyfill
// ---------------------------------------------------------------------------

export function isFrappeRuntimeAvailable(win = globalThis.window) {
	return Boolean(win?.frappe && typeof win.frappe.call === "function")
}

export function ensureKoreaAnnualLeaveFrappeCallRuntime(win = globalThis.window) {
	if (!win?.frappe || typeof win.fetch !== "function") return false
	if (typeof win.frappe.call === "function") return true
	win.frappe.call = async ({ method, args = {} } = {}) => {
		if (typeof method !== "string" || !method.trim()) throw new Error("frappe.call method is required")
		if (!KOREA_ANNUAL_LEAVE_ALLOWED_METHODS.has(method)) {
			throw new Error("frappe.call fallback only allows Korea annual leave read-only runtime methods")
		}
		const body = new URLSearchParams()
		for (const [key, value] of Object.entries(args || {})) {
			if (value !== undefined && value !== null) body.append(key, typeof value === "object" ? JSON.stringify(value) : String(value))
		}
		const response = await win.fetch(`/api/method/${method}`, {
			method: "POST",
			headers: {
				"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
				"X-Frappe-CSRF-Token": win.csrf_token || "",
			},
			body,
			credentials: "same-origin",
		})
		const payload = await response.json()
		if (!response.ok) throw new Error(payload?._server_messages || payload?.exc || `frappe.call failed with HTTP ${response.status}`)
		return payload
	}
	return true
}

export function getKoreaAnnualLeaveRuntimeCompany(win = globalThis.window, fallbackCompany = "Korea Demo Co") {
	const candidateCompanies = [
		win?.frappe?.boot?.user?.company,
		win?.frappe?.boot?.user?.defaults?.company,
		win?.frappe?.session?.company,
		win?.frappe?.boot?.sysdefaults?.company,
	]
	for (const company of candidateCompanies) {
		if (typeof company === "string" && company.trim()) return company.trim()
	}
	const defaultGetter = win?.frappe?.defaults?.get_default
	if (typeof defaultGetter === "function") {
		const defaultCompany = defaultGetter("company")
		if (typeof defaultCompany === "string" && defaultCompany.trim()) return defaultCompany.trim()
	}
	return fallbackCompany
}

// ---------------------------------------------------------------------------
// Preview (read-only)
// ---------------------------------------------------------------------------

/**
 * Fetch the Korea Annual Leave allocation preview draft.
 *
 * @param {Object} opts
 * @param {Object} opts.employee  - { name, date_of_joining, employee_name?, company? }
 * @param {string} opts.asOfDate  - ISO date string "YYYY-MM-DD"
 * @param {string} [opts.basis]   - "Hire Date" | "Fiscal Year"
 * @param {Window} [opts.win]
 * @returns {Promise<{source: string, data: Object}>}
 */
export async function fetchKoreaAnnualLeavePreview({
	employee,
	asOfDate,
	basis = "Hire Date",
	win = globalThis.window,
} = {}) {
	ensureKoreaAnnualLeaveFrappeCallRuntime(win)
	if (!isFrappeRuntimeAvailable(win)) {
		throw new Error("Frappe runtime is not available for Korea annual leave preview reads")
	}
	if (!employee || typeof employee !== "object") throw new Error("employee must be an object with name and date_of_joining")
	if (!employee.name) throw new Error("employee.name is required")
	if (!employee.date_of_joining) throw new Error("employee.date_of_joining is required")
	if (!asOfDate) throw new Error("asOfDate is required")

	const response = await win.frappe.call({
		method: KOREA_LEAVE_PREVIEW_METHOD,
		args: {
			employee: JSON.stringify(employee),
			as_of_date: asOfDate,
			basis,
		},
	})
	const data = response?.message ?? response
	assertKoreaAnnualLeavePreview(data)
	return { source: "runtime_read_only", data }
}

export function assertKoreaAnnualLeavePreview(data) {
	if (!data || typeof data !== "object") {
		throw new Error("Korea annual leave preview response must be an object")
	}
	if (data.contract_type !== "korea_leave_allocation_preview_v1") {
		throw new Error(`Unexpected Korea annual leave preview contract_type: ${data.contract_type}`)
	}
	if (data.runtime_action !== "preview_only") {
		throw new Error("Unexpected Korea annual leave preview runtime_action")
	}
	if (data.requires_runtime_apply !== true) {
		throw new Error("Korea annual leave preview must indicate requires_runtime_apply=true")
	}
	return data
}

// ---------------------------------------------------------------------------
// Preview with attendance ratio (Wave 2-A)
// ---------------------------------------------------------------------------

/**
 * Fetch the Korea Annual Leave preview with the 80% attendance ratio rule applied.
 *
 * @param {Object} opts
 * @param {Object} opts.employee           - { name, date_of_joining, employee_name?, company? }
 * @param {string} opts.asOfDate           - ISO date string
 * @param {number|null} opts.attendanceRatio - 0.0–1.0 or null to skip ratio check
 * @param {Window} [opts.win]
 * @returns {Promise<{source: string, data: Object}>}
 */
export async function fetchKoreaAnnualLeaveWithRatio({
	employee,
	asOfDate,
	attendanceRatio = null,
	win = globalThis.window,
} = {}) {
	ensureKoreaAnnualLeaveFrappeCallRuntime(win)
	if (!isFrappeRuntimeAvailable(win)) {
		throw new Error("Frappe runtime is not available for Korea annual leave ratio reads")
	}
	if (!employee || typeof employee !== "object") throw new Error("employee must be an object with name and date_of_joining")
	if (!employee.name) throw new Error("employee.name is required")
	if (!employee.date_of_joining) throw new Error("employee.date_of_joining is required")
	if (!asOfDate) throw new Error("asOfDate is required")
	if (attendanceRatio !== null && (typeof attendanceRatio !== "number" || attendanceRatio < 0 || attendanceRatio > 1)) {
		throw new Error("attendanceRatio must be a number between 0.0 and 1.0, or null")
	}

	const args = {
		employee: JSON.stringify(employee),
		as_of_date: asOfDate,
	}
	if (attendanceRatio !== null) args.attendance_ratio = String(attendanceRatio)

	const response = await win.frappe.call({
		method: KOREA_LEAVE_RATIO_METHOD,
		args,
	})
	const data = response?.message ?? response
	assertKoreaAnnualLeaveRatioPreview(data)
	return { source: "runtime_read_only", data }
}

export function assertKoreaAnnualLeaveRatioPreview(data) {
	if (!data || typeof data !== "object") {
		throw new Error("Korea annual leave ratio preview response must be an object")
	}
	if (data.contract_type !== "korea_annual_leave_attendance_ratio_preview_v1") {
		throw new Error(`Unexpected Korea annual leave ratio preview contract_type: ${data.contract_type}`)
	}
	if (data.runtime_action !== "preview_only") {
		throw new Error("Unexpected Korea annual leave ratio preview runtime_action")
	}
	return data
}

// ---------------------------------------------------------------------------
// Apply mutation (human_approved strictly required — fail-closed)
// ---------------------------------------------------------------------------

/**
 * Apply the Korea Leave Allocation draft.
 * Requires human_approved === true (strict). Any falsy value is fail-closed.
 * Sends to backend only when humanApproved is strictly true.
 *
 * @param {Object} opts
 * @param {Object} opts.draft          - draft payload from fetchKoreaAnnualLeavePreview
 * @param {boolean} opts.humanApproved - must be true
 * @param {string} [opts.actor]        - human actor identifier
 * @param {Window} [opts.win]
 * @returns {Promise<{source: string, data: Object}>}
 */
export async function applyKoreaLeaveAllocation({
	draft,
	humanApproved,
	actor = null,
	win = globalThis.window,
} = {}) {
	// UI-side fail-closed gate — must be strictly true
	if (humanApproved !== true) {
		throw new Error("applyKoreaLeaveAllocation: humanApproved must be strictly true. This is a fail-closed mutation gate.")
	}
	if (!draft || typeof draft !== "object") {
		throw new Error("applyKoreaLeaveAllocation: draft must be a valid Korea leave allocation draft object")
	}
	if (!isFrappeRuntimeAvailable(win)) {
		throw new Error("Frappe runtime is not available for Korea leave allocation apply")
	}

	const args = {
		draft: JSON.stringify(draft),
		human_approved: "true",
	}
	if (actor) args.apply_actor = String(actor)

	const response = await win.frappe.call({
		method: KOREA_LEAVE_APPLY_METHOD,
		args,
	})
	const data = response?.message ?? response
	assertKoreaLeaveAllocationApplyResult(data)
	return { source: "runtime_apply", data }
}

export function assertKoreaLeaveAllocationApplyResult(data) {
	if (!data || typeof data !== "object") {
		throw new Error("Korea leave allocation apply response must be an object")
	}
	if (data.contract_type !== "korea_leave_allocation_runtime_apply_v1") {
		throw new Error(`Unexpected Korea leave allocation apply contract_type: ${data.contract_type}`)
	}
	return data
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------

export function hasKoreaAnnualLeavePreviewData(data) {
	return (
		data?.contract_type === "korea_leave_allocation_preview_v1" &&
		data?.runtime_action === "preview_only" &&
		data?.draft != null
	)
}

export function hasKoreaAnnualLeaveRatioData(data) {
	return (
		data?.contract_type === "korea_annual_leave_attendance_ratio_preview_v1" &&
		data?.runtime_action === "preview_only" &&
		data?.draft != null
	)
}

/**
 * Compute consolidated display values from preview + optional ratio data.
 * Returns a plain object safe for Vue reactive refs.
 */
export function buildKoreaAnnualLeaveDisplayData({ previewData, ratioData, usageData } = {}) {
	const active = (ratioData && hasKoreaAnnualLeaveRatioData(ratioData)) ? ratioData : previewData
	if (!active) return null

	const draft = active.draft || {}
	const entRef = draft.entitlement_reference || {}
	const ratioDraft = (ratioData && hasKoreaAnnualLeaveRatioData(ratioData)) ? (ratioData.draft || {}) : null

	const serviceYears = entRef.service_years ?? 0
	const serviceMonths = computeMonthsFromDate(entRef.hire_date, entRef.as_of_date)
	const monthlyAccrual = entRef.monthly_accrual_days ?? 0
	const annualEntitlement = entRef.annual_entitlement_days ?? 0
	const totalEntitlement = entRef.total_entitlement_days ?? (draft.total_reference_entitlement ?? 0)

	const ratioApplied = Boolean(ratioDraft)
	const attendanceRatio = ratioData?.meta?.attendance_ratio ?? null
	const threshold = ratioData?.meta?.threshold ?? 0.8
	const isBelowThreshold = ratioApplied && attendanceRatio !== null && attendanceRatio < threshold

	const allocatedDays = draft.new_leaves_allocated ?? totalEntitlement
	const usedDays = usageData?.used_days ?? 0
	const remainingDays = allocatedDays - usedDays

	return {
		employee: draft.employee || "",
		employeeName: draft.employee_name || "",
		company: draft.company || "",
		dateOfJoining: entRef.hire_date || "",
		asOfDate: entRef.as_of_date || "",
		basis: entRef.basis || "Hire Date",
		serviceYears,
		serviceMonths,
		monthlyAccrual,
		annualEntitlement,
		totalEntitlement,
		ratioApplied,
		attendanceRatio,
		threshold,
		isBelowThreshold,
		allocatedDays,
		usedDays,
		remainingDays,
		fromDate: draft.from_date || "",
		toDate: draft.to_date || "",
		leaveType: draft.leave_type || "Annual Leave",
		requiresRuntimeApply: draft.requires_runtime_apply ?? true,
	}
}

function computeMonthsFromDate(hireDateStr, asOfDateStr) {
	if (!hireDateStr || !asOfDateStr) return 0
	try {
		const hire = new Date(hireDateStr)
		const asOf = new Date(asOfDateStr)
		return Math.max(0, (asOf.getFullYear() - hire.getFullYear()) * 12 + (asOf.getMonth() - hire.getMonth()))
	} catch {
		return 0
	}
}
