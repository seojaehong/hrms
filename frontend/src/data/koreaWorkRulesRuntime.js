import { createResource } from "frappe-ui"

/**
 * 취업규칙 점검 런타임 데이터
 * hrms.regional.south_korea.work_rules_api
 * — §93 필수기재 커버리지 + §94 변경 절차 안내
 */

export const listRequiredItems = createResource({
	url: "hrms.regional.south_korea.work_rules_api.list_required_items_api",
	auto: true,
})

export const checkRequiredItems = createResource({
	url: "hrms.regional.south_korea.work_rules_api.check_required_items_api",
	makeParams(values) {
		return {
			rules_outline: JSON.stringify(values?.rules_outline ?? []),
		}
	},
})

export const amendmentProcedure = createResource({
	url: "hrms.regional.south_korea.work_rules_api.amendment_procedure_api",
	makeParams(values) {
		return {
			is_disadvantageous: values?.is_disadvantageous ? "true" : "false",
			headcount: values?.headcount,
			has_majority_union:
				values?.has_majority_union == null ? "" : values.has_majority_union ? "true" : "false",
		}
	},
})
