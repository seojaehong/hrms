import { createResource } from "frappe-ui"

/**
 * 임금명세서 분해 런타임 데이터
 * hrms.regional.south_korea.payslip_breakdown_api
 * — §48② 산정내역 분해(항목+계산방법) + 공제내역 + 마크다운 미리보기
 */

export const buildPayslipBreakdown = createResource({
	url: "hrms.regional.south_korea.payslip_breakdown_api.build_payslip_breakdown_api",
	makeParams(values) {
		return {
			employee: values?.employee,
			period: values?.period,
			payment_date: values?.payment_date,
			wage_type: values?.wage_type,
			base_salary: values?.base_salary,
			hourly_rate: values?.hourly_rate,
			regular_hours: values?.regular_hours ?? 0,
			contracted_weekly_hours: values?.contracted_weekly_hours,
			perfect_attendance: values?.perfect_attendance ?? true,
			overtime_hours: values?.overtime_hours ?? 0,
			night_hours: values?.night_hours ?? 0,
			holiday_work_hours: values?.holiday_work_hours ?? 0,
			annual_leave_hours: values?.annual_leave_hours ?? 0,
			extra_earnings: values?.extra_earnings ?? [],
			dependents: values?.dependents ?? 1,
			children_under_8: values?.children_under_8 ?? 0,
		}
	},
})

export const renderPayslipMarkdown = createResource({
	url: "hrms.regional.south_korea.payslip_breakdown_api.render_payslip_markdown_api",
	makeParams(values) {
		return {
			breakdown: values?.breakdown,
		}
	},
})
