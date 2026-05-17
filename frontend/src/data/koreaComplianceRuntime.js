import { createResource } from "frappe-ui"
import { employeeResource } from "./employee"

/**
 * 컴플라이언스 진단 런타임 데이터
 * Phase 2-F: hrms.regional.south_korea.compliance_diagnosis_api
 */

export const complianceDiagnosis = createResource({
	url: "hrms.regional.south_korea.compliance_diagnosis_api.run_compliance_diagnosis",
	makeParams(values) {
		return {
			company: values?.company ?? employeeResource.data?.company,
			workplace: values?.workplace ?? null,
		}
	},
})
