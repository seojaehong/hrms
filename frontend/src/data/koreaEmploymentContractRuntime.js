import { createResource } from "frappe-ui"

/**
 * 근로계약서 작성 런타임 데이터
 * hrms.regional.south_korea.employment_contract_doc_api
 * — §17 필수기재 폼 → 누락 검출 + 서면 교부용 마크다운 미리보기
 */

export const buildEmploymentContract = createResource({
	url: "hrms.regional.south_korea.employment_contract_doc_api.build_employment_contract_api",
	makeParams(values) {
		return {
			data: JSON.stringify(values),
		}
	},
})

export const renderContractMarkdown = createResource({
	url: "hrms.regional.south_korea.employment_contract_doc_api.render_contract_markdown_api",
	makeParams(values) {
		return {
			data: JSON.stringify(values?.contract),
		}
	},
})
