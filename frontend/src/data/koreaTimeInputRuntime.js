import { createResource } from "frappe-ui"

/**
 * koreaTimeInputRuntime.js — F1 근무시간 제출 런타임 리소스
 * 서버: hrms.regional.south_korea.payroll_time_input_api
 * (createResource 패턴: koreaWageStatementRuntime.js 참조)
 */

export const timeInputList = createResource({
	url: "hrms.regional.south_korea.payroll_time_input_api.list_time_inputs",
	makeParams(values) {
		return {
			period: values?.period,
			company: values?.company ?? null,
		}
	},
})

export const timeInputSave = createResource({
	url: "hrms.regional.south_korea.payroll_time_input_api.save_time_inputs",
	makeParams(values) {
		return {
			period: values?.period,
			rows: JSON.stringify(values?.rows ?? []),
			company: values?.company ?? null,
		}
	},
})

export const timeInputSubmit = createResource({
	url: "hrms.regional.south_korea.payroll_time_input_api.submit_time_inputs",
	makeParams(values) {
		return {
			period: values?.period,
			company: values?.company ?? null,
		}
	},
})
