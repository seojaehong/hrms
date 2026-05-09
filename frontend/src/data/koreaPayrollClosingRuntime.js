export const KOREA_ADMIN_DASHBOARD_RUNTIME_METHOD =
	"hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime"

export const KOREA_PAYROLL_CLOSING_WORKLIST_RUNTIME_METHOD =
	"hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime"

const KOREA_PAYROLL_CLOSING_READ_ONLY_RUNTIME_METHODS = new Set([
	KOREA_ADMIN_DASHBOARD_RUNTIME_METHOD,
	KOREA_PAYROLL_CLOSING_WORKLIST_RUNTIME_METHOD,
])

export function isFrappeRuntimeAvailable(win = globalThis.window) {
	return Boolean(win?.frappe && typeof win.frappe.call === "function")
}

export function ensureKoreaPayrollClosingFrappeCallRuntime(win = globalThis.window) {
	if (!win?.frappe || typeof win.fetch !== "function") return false
	if (typeof win.frappe.call === "function") return true
	win.frappe.call = async ({ method, args = {} } = {}) => {
		if (typeof method !== "string" || !method.trim()) throw new Error("frappe.call method is required")
		if (!KOREA_PAYROLL_CLOSING_READ_ONLY_RUNTIME_METHODS.has(method)) {
			throw new Error("frappe.call fallback only allows Korea payroll closing read-only runtime methods")
		}
		const body = new URLSearchParams()
		for (const [key, value] of Object.entries(args || {})) {
			if (value !== undefined && value !== null) body.append(key, value)
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

export function getKoreaPayrollClosingRuntimeCompany(win = globalThis.window, fallbackCompany = "Korea Demo Franchise Co") {
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

export async function loadKoreaAdminDashboardRuntime({
	win = globalThis.window,
	fallbackCompany = "Korea Demo Franchise Co",
	workplaces,
} = {}) {
	ensureKoreaPayrollClosingFrappeCallRuntime(win)
	if (!isFrappeRuntimeAvailable(win)) {
		throw new Error("Frappe runtime is not available for Korea payroll closing runtime reads")
	}

	const company = getKoreaPayrollClosingRuntimeCompany(win, fallbackCompany)
	const args = { company }
	if (Array.isArray(workplaces) && workplaces.length) args.workplaces = JSON.stringify(workplaces)

	const response = await win.frappe.call({
		method: KOREA_ADMIN_DASHBOARD_RUNTIME_METHOD,
		args,
	})
	const data = response?.message ?? response
	assertKoreaAdminDashboardRuntime(data)
	return {
		source: "runtime_read_only",
		data,
	}
}

export function assertKoreaAdminDashboardRuntime(data) {
	if (!data || typeof data !== "object") {
		throw new Error("Korea admin dashboard runtime response must be an object")
	}
	if (data.contract_type !== "korea_admin_dashboard_runtime_api_v1") {
		throw new Error("Unexpected Korea admin dashboard runtime contract")
	}
	if (data.runtime_action !== "runtime_read_only") {
		throw new Error("Unexpected Korea admin dashboard runtime action")
	}
	if (data.requires_runtime_apply !== false) {
		throw new Error("Korea admin dashboard runtime read must not require runtime apply")
	}
	return data
}

export async function loadKoreaPayrollClosingRuntimeWorklist({
	win = globalThis.window,
	fallbackCompany = "Korea Demo Franchise Co",
	workplaces,
	limit,
} = {}) {
	ensureKoreaPayrollClosingFrappeCallRuntime(win)
	if (!isFrappeRuntimeAvailable(win)) {
		throw new Error("Frappe runtime is not available for Korea payroll closing worklist runtime reads")
	}

	const company = getKoreaPayrollClosingRuntimeCompany(win, fallbackCompany)
	const args = { company }
	if (Array.isArray(workplaces) && workplaces.length) args.workplaces = JSON.stringify(workplaces)
	if (limit !== undefined) args.limit = limit

	const response = await win.frappe.call({
		method: KOREA_PAYROLL_CLOSING_WORKLIST_RUNTIME_METHOD,
		args,
	})
	const data = response?.message ?? response
	assertKoreaPayrollClosingRuntimeWorklist(data)
	return {
		source: "runtime_read_only",
		data,
	}
}

export function assertKoreaPayrollClosingRuntimeWorklist(data) {
	if (!data || typeof data !== "object") {
		throw new Error("Korea payroll closing worklist runtime response must be an object")
	}
	if (data.contract_type !== "korea_payroll_closing_worklist_runtime_api_v1") {
		throw new Error("Unexpected Korea payroll closing worklist runtime contract")
	}
	if (data.runtime_action !== "runtime_read_only") {
		throw new Error("Unexpected Korea payroll closing worklist runtime action")
	}
	if (data.requires_runtime_apply !== false) {
		throw new Error("Korea payroll closing worklist runtime read must not require runtime apply")
	}
	if (data.requires_human_approval !== true || data.ai_role !== "assistant_only") {
		throw new Error("Korea payroll closing worklist runtime must preserve human approval and assistant-only AI")
	}
	if (!Array.isArray(data.items)) {
		throw new Error("Korea payroll closing worklist runtime items must be a list")
	}
	assertNoForbiddenScoreKeys(data)
	for (const item of data.items) {
		if (!item || typeof item !== "object") throw new Error("Korea payroll closing worklist item must be an object")
		if (item.runtime_action !== "runtime_read_only") throw new Error("Korea payroll closing worklist item must be runtime read-only")
		if (item.requires_runtime_apply !== false) throw new Error("Korea payroll closing worklist item must not require runtime apply")
		if (item.requires_human_approval !== true || item.ai_role !== "assistant_only") {
			throw new Error("Korea payroll closing worklist item must preserve human approval and assistant-only AI")
		}
	}
	return data
}

export function hasKoreaAdminDashboardRuntimeData(data) {
	const metrics = data?.metrics
	if (!metrics || typeof metrics !== "object") return false
	return Object.values(metrics).some((value) => typeof value === "number" && value > 0)
}

export function hasKoreaPayrollClosingRuntimeWorklistData(data) {
	return data?.contract_type === "korea_payroll_closing_worklist_runtime_api_v1" &&
		data?.runtime_action === "runtime_read_only" &&
		data?.requires_runtime_apply === false &&
		Array.isArray(data?.items) &&
		data.items.length > 0
}

export function getKoreaPayrollClosingRuntimeUiState({ runtimeDashboard = null, runtimeWorklist = null, runtimeLoading = false } = {}) {
	const runtimeHasWorklistData = hasKoreaPayrollClosingRuntimeWorklistData(runtimeWorklist)
	const runtimeHasDashboard = Boolean(runtimeDashboard)
	const runtimeAction = runtimeWorklist?.runtime_action || "runtime_read_only"
	const requiresRuntimeApply = runtimeWorklist?.requires_runtime_apply ?? false
	return {
		dataSourceLabel: runtimeHasWorklistData
			? "Runtime read-only worklist"
			: runtimeHasDashboard
				? "Runtime read-only dashboard"
				: "Static fixture preview",
		dataSourceBadge: runtimeLoading
			? "loading"
			: runtimeHasWorklistData
				? "runtime worklist"
				: runtimeHasDashboard
					? "runtime_read_only"
					: "static fixture",
		showFixtureFallbackCopy: !runtimeHasWorklistData,
		showRuntimePositiveCopy: runtimeHasWorklistData,
		worklistBanner: runtimeHasWorklistData
			? `Runtime worklist loaded · runtime_action=${runtimeAction} · requires_runtime_apply=${requiresRuntimeApply} · evidence remains read-only`
			: "No positive runtime worklist rows were returned; static fixture fallback remains active for static/no-runtime preview contexts.",
	}
}

const FORBIDDEN_SCORE_KEY_FRAGMENTS = ["score", "risk", "probability", "successrate"]

function assertNoForbiddenScoreKeys(value) {
	for (const key of iterObjectKeys(value)) {
		const normalized = key.toLowerCase().replace(/[^a-z0-9]+/g, "")
		if (normalized === "score" || normalized === "risk" || normalized === "probability" || FORBIDDEN_SCORE_KEY_FRAGMENTS.some((fragment) => normalized.includes(fragment))) {
			throw new Error("score keys are not allowed in Korea payroll closing worklist runtime responses")
		}
	}
}

function* iterObjectKeys(value) {
	if (Array.isArray(value)) {
		for (const item of value) yield* iterObjectKeys(item)
		return
	}
	if (!value || typeof value !== "object") return
	for (const [key, nested] of Object.entries(value)) {
		yield key
		yield* iterObjectKeys(nested)
	}
}
