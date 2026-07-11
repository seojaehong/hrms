import { createResource } from "frappe-ui"

/**
 * 포괄임금 설계·역산 런타임 데이터
 * hrms.regional.south_korea.inclusive_wage_api
 * 최저시급은 서버가 온톨로지에서 주입 — 프런트는 결과의 minimum_hourly_wage만 표시.
 */

export const inclusiveWageDesign = createResource({
	url: "hrms.regional.south_korea.inclusive_wage_api.design_inclusive_wage_api",
	makeParams(values) {
		return {
			total_monthly: values?.total_monthly,
			fixed_ot_hours: values?.fixed_ot_hours ?? 0,
			fixed_night_hours: values?.fixed_night_hours ?? 0,
			fixed_holiday_hours: values?.fixed_holiday_hours ?? 0,
		}
	},
})

export const inclusiveWageAudit = createResource({
	url: "hrms.regional.south_korea.inclusive_wage_api.audit_inclusive_wage_api",
	makeParams(values) {
		return {
			base_pay: values?.base_pay,
			fixed_ot_pay: values?.fixed_ot_pay ?? 0,
			fixed_ot_hours: values?.fixed_ot_hours ?? 0,
			fixed_night_pay: values?.fixed_night_pay ?? 0,
			fixed_night_hours: values?.fixed_night_hours ?? 0,
			fixed_holiday_pay: values?.fixed_holiday_pay ?? 0,
			fixed_holiday_hours: values?.fixed_holiday_hours ?? 0,
		}
	},
})
