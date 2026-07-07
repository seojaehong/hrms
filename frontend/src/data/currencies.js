import { createResource } from "frappe-ui"

const companyCurrency = createResource({
	url: "hrms.api.get_company_currencies",
	auto: true,
})

const currencySymbols = createResource({
	url: "hrms.api.get_currency_symbols",
	auto: true,
})

export function getCompanyCurrency(company) {
	return companyCurrency?.data?.[company]?.[0]
}

export function getCompanyCurrencySymbol(company) {
	return companyCurrency?.data?.[company]?.[1]
}

export function getCurrencySymbol(currency) {
	return currencySymbols?.data?.[currency]
}

// frappe.client.get_single_value(System Settings)는 일반 직원 권한에서
// 페이지 이동마다 PermissionError를 남김 → 권한 불필요 whitelisted API 사용
export const currencyPrecision = createResource({
	url: "hrms.api.get_system_locale_settings",
	transform: (data) => data?.currency_precision ?? 2,
	auto: true,
	initialData: 2
});