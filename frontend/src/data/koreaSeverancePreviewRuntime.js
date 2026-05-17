import { createResource } from "frappe-ui"
import { employeeResource } from "./employee"

/**
 * 퇴직금 미리보기 런타임 데이터
 * Phase 2-B: hrms.regional.south_korea.severance_pay_api
 */

export const severancePreview = createResource({
	url: "hrms.regional.south_korea.severance_pay_api.calculate_severance_preview",
	makeParams(values) {
		return {
			employee: values?.employee ?? employeeResource.data?.name,
			assumed_retirement_date: values?.assumed_retirement_date,
			ordinary_wage_override: values?.ordinary_wage_override ?? null,
		}
	},
})
