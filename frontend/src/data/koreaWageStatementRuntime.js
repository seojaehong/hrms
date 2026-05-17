import { createResource } from "frappe-ui"
import { employeeResource } from "./employee"

/**
 * 임금명세서 런타임 데이터
 * Phase 2-A: hrms.regional.south_korea.wage_statement
 */

export const wageStatementPreview = createResource({
	url: "hrms.regional.south_korea.wage_statement.build_korea_wage_statement_preview",
	makeParams(values) {
		return {
			employee: values?.employee ?? employeeResource.data?.name,
			year: values?.year,
			month: values?.month,
		}
	},
})

export const wageStatementHistory = createResource({
	url: "hrms.regional.south_korea.wage_statement.list_korea_wage_statements",
	makeParams(values) {
		return {
			employee: values?.employee ?? employeeResource.data?.name,
			limit: values?.limit ?? 12,
		}
	},
})
