import { createResource } from "frappe-ui"

/**
 * 퇴직정산 통합 런타임 데이터
 * hrms.regional.south_korea.severance_settlement_api
 * — 퇴직금 + 미사용연차수당 + 퇴직소득세 + 건보정산 통합 정산
 */

export const severanceSettlement = createResource({
	url: "hrms.regional.south_korea.severance_settlement_api.settle_retirement_api",
	makeParams(values) {
		return {
			hire_date: values?.hire_date,
			severance_date: values?.severance_date,
			average_wage_per_day: values?.average_wage_per_day,
			monthly_base_salary: values?.monthly_base_salary,
			ordinary_wage_per_day: values?.ordinary_wage_per_day ?? null,
			unused_leave_days: values?.unused_leave_days ?? 0,
			monthly_remuneration_for_health: values?.monthly_remuneration_for_health ?? null,
			paid_health_total: values?.paid_health_total ?? 0,
			paid_longterm_care_total: values?.paid_longterm_care_total ?? 0,
			mid_month_hire: values?.mid_month_hire ?? false,
		}
	},
})
