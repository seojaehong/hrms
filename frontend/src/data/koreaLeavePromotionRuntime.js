import { createResource } from "frappe-ui"

/**
 * 연차 사용촉진 런타임 데이터
 * hrms.regional.south_korea.annual_leave_promotion_api
 * — §61 촉진 기한표 + 촉구문 초안 + 미사용 연차수당 정산
 */

export const promotionSchedule = createResource({
	url: "hrms.regional.south_korea.annual_leave_promotion_api.promotion_schedule_api",
	makeParams(values) {
		return {
			hire_date: values?.hire_date,
			as_of: values?.as_of,
			is_first_year: values?.is_first_year ?? false,
		}
	},
})

export const promotionNotice = createResource({
	url: "hrms.regional.south_korea.annual_leave_promotion_api.promotion_notice_api",
	makeParams(values) {
		return {
			worker: values?.worker,
			unused_days: values?.unused_days,
			deadline: values?.deadline,
			stage: values?.stage,
		}
	},
})

export const settleUnusedLeave = createResource({
	url: "hrms.regional.south_korea.annual_leave_promotion_api.settle_unused_leave_api",
	makeParams(values) {
		return {
			monthly_base_salary: values?.monthly_base_salary,
			unused_days: values?.unused_days,
			promotion_completed: values?.promotion_completed ?? false,
		}
	},
})
