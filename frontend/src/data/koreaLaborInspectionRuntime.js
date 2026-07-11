import { createResource } from "frappe-ui"

/**
 * 근로감독 대비 체크리스트 런타임 데이터
 * hrms.regional.south_korea.labor_inspection_api
 * — 고용노동부 자율점검표 기반 15항목 체크리스트
 */

export const listInspectionChecklist = createResource({
	url: "hrms.regional.south_korea.labor_inspection_api.list_inspection_checklist_api",
	auto: true,
})
