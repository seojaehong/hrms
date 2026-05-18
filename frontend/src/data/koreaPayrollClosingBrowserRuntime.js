import {
	KOREA_ADMIN_DASHBOARD_RUNTIME_METHOD,
	KOREA_PAYROLL_CLOSING_WORKLIST_RUNTIME_METHOD,
	assertKoreaAdminDashboardRuntime,
	assertKoreaPayrollClosingRuntimeWorklist,
	hasKoreaPayrollClosingRuntimeWorklistData,
} from "./koreaPayrollClosingRuntime.js"

export const KOREA_PAYROLL_CLOSING_BROWSER_ROUTE = "/hrms/dashboard/korea-payroll-closing"
export const KOREA_PAYROLL_CLOSING_BROWSER_RUNTIME_CONTRACT = "korea_payroll_closing_browser_runtime_walkthrough_v1"

export function buildKoreaPayrollClosingBrowserProbe({ company, workplaces } = {}) {
	const companyJson = JSON.stringify(requireNonEmptyText(company, "company"))
	const workplacesJson = JSON.stringify(Array.isArray(workplaces) ? workplaces : null)
	const allowedMethodsJson = JSON.stringify([
		KOREA_ADMIN_DASHBOARD_RUNTIME_METHOD,
		KOREA_PAYROLL_CLOSING_WORKLIST_RUNTIME_METHOD,
	])
	return `
(async () => {
  const calledMethods = [];
  if (!window.frappe) {
    throw new Error("Frappe runtime is not available in the browser session");
  }
  if (typeof window.frappe.call !== "function" && typeof window.fetch === "function") {
    window.frappe.call = async ({ method, args = {} } = {}) => {
      if (!method) throw new Error("frappe.call method is required");
      const allowedMethods = new Set(${allowedMethodsJson});
      if (!allowedMethods.has(method)) throw new Error("browser runtime probe only allows Korea payroll closing read-only methods");
      const response = await window.fetch("/api/method/" + method, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
          "X-Frappe-CSRF-Token": window.csrf_token || "",
        },
        body: new URLSearchParams(args),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload._server_messages || payload.exception || "Frappe API call failed");
      return payload;
    };
  }
  if (typeof window.frappe.call !== "function") {
    throw new Error("Frappe runtime is not available in the browser session");
  }
  async function getAuthenticatedUser() {
    const sessionUser = window.frappe.session && window.frappe.session.user;
    if (sessionUser && sessionUser !== "Guest") return sessionUser;
    const response = await window.fetch("/api/method/frappe.auth.get_logged_user", {
      method: "GET",
      credentials: "same-origin",
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload._server_messages || payload.exception || "Frappe logged-user check failed");
    return payload.message;
  }
  async function callRuntime(method, args) {
    calledMethods.push(method);
    const response = await window.frappe.call({ method, args });
    return response && Object.prototype.hasOwnProperty.call(response, "message") ? response.message : response;
  }
  const args = { company: ${companyJson} };
  const workplaces = ${workplacesJson};
  if (Array.isArray(workplaces) && workplaces.length) args.workplaces = JSON.stringify(workplaces);
  const authenticatedUser = await getAuthenticatedUser();
  const [dashboard, worklist] = await Promise.all([
    callRuntime(${JSON.stringify(KOREA_ADMIN_DASHBOARD_RUNTIME_METHOD)}, args),
    callRuntime(${JSON.stringify(KOREA_PAYROLL_CLOSING_WORKLIST_RUNTIME_METHOD)}, args),
  ]);
  return {
    url: window.location.href,
    authenticated: Boolean(authenticatedUser && authenticatedUser !== "Guest"),
    dashboard,
    worklist,
    domText: document.body ? document.body.innerText : "",
    calledMethods,
  };
})()`
}

export function assertKoreaPayrollClosingBrowserWalkthrough(result) {
	if (!result || typeof result !== "object") {
		throw new Error("Korea payroll closing browser walkthrough result must be an object")
	}
	if (result.authenticated !== true) {
		throw new Error("authenticated browser session is required for Korea payroll closing runtime walkthrough")
	}
	if (typeof result.url !== "string" || !result.url.includes(KOREA_PAYROLL_CLOSING_BROWSER_ROUTE)) {
		throw new Error("Korea payroll closing browser walkthrough must run on the operator route")
	}
	if (!Array.isArray(result.calledMethods)) {
		throw new Error("Korea payroll closing browser walkthrough must report called Frappe methods")
	}
	for (const method of [KOREA_ADMIN_DASHBOARD_RUNTIME_METHOD, KOREA_PAYROLL_CLOSING_WORKLIST_RUNTIME_METHOD]) {
		if (!result.calledMethods.includes(method)) {
			throw new Error(`Korea payroll closing browser walkthrough did not execute ${method}`)
		}
	}
	assertKoreaAdminDashboardRuntime(result.dashboard)
	assertKoreaPayrollClosingRuntimeWorklist(result.worklist)
	if (!hasKoreaPayrollClosingRuntimeWorklistData(result.worklist)) {
		throw new Error("Korea payroll closing browser walkthrough requires positive runtime worklist rows")
	}
	if (!String(result.domText || "").match(/Runtime worklist loaded/i) || !String(result.domText || "").match(/evidence remains read-only/i)) {
		throw new Error("browser DOM did not show the runtime-positive read-only state")
	}
	if (!String(result.domText || "").match(/assistant_only/i) && !String(result.domText || "").match(/AI=assistant_only/i) && !String(result.domText || "").match(/AI is assistant-only/i)) {
		throw new Error("browser DOM did not preserve assistant-only AI copy")
	}
	assertNoMutationMarkers(result)
	return {
		contract_type: KOREA_PAYROLL_CLOSING_BROWSER_RUNTIME_CONTRACT,
		runtime_action: "browser_runtime_read_only",
		requires_runtime_apply: false,
		requires_human_approval: true,
		ai_role: "assistant_only",
		mutation_boundary: "read_only_no_save_submit_approve_send_provider",
		runtime_verified: true,
		fixture_fallback_required: false,
		url: result.url,
		dashboard: summarizeDashboard(result.dashboard),
		worklist: summarizeWorklist(result.worklist),
		calledMethods: [...result.calledMethods],
	}
}

function summarizeDashboard(dashboard) {
	return {
		contract_type: dashboard.contract_type,
		runtime_action: dashboard.runtime_action,
		requires_runtime_apply: dashboard.requires_runtime_apply,
		metric_keys: dashboard.metrics && typeof dashboard.metrics === "object" ? Object.keys(dashboard.metrics).sort() : [],
	}
}

function summarizeWorklist(worklist) {
	return {
		contract_type: worklist.contract_type,
		runtime_action: worklist.runtime_action,
		requires_runtime_apply: worklist.requires_runtime_apply,
		requires_human_approval: worklist.requires_human_approval,
		ai_role: worklist.ai_role,
		item_count: Array.isArray(worklist.items) ? worklist.items.length : 0,
	}
}

function requireNonEmptyText(value, fieldname) {
	if (typeof value !== "string" || !value.trim()) throw new Error(`${fieldname} must be a non-empty string`)
	return value.trim()
}

function assertNoMutationMarkers(value) {
	for (const key of iterObjectKeys(value)) {
		const normalized = key.toLowerCase().replace(/[^a-z0-9]+/g, "")
		if (normalized === "score" || normalized === "risk" || normalized === "probability" || normalized.includes("score") || normalized.includes("risk") || normalized.includes("probability") || normalized.includes("successrate")) {
			throw new Error("score keys are not allowed in Korea payroll closing browser walkthrough responses")
		}
		if (["save", "submit", "approve", "send", "providercall"].includes(normalized)) {
			throw new Error("mutation markers are not allowed in Korea payroll closing browser walkthrough responses")
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
