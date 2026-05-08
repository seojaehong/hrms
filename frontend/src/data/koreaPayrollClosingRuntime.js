export const KOREA_ADMIN_DASHBOARD_RUNTIME_METHOD =
	"hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime"

export function isFrappeRuntimeAvailable(win = globalThis.window) {
	return Boolean(win?.frappe && typeof win.frappe.call === "function")
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

export function hasKoreaAdminDashboardRuntimeData(data) {
	const metrics = data?.metrics
	if (!metrics || typeof metrics !== "object") return false
	return Object.values(metrics).some((value) => typeof value === "number" && value > 0)
}
