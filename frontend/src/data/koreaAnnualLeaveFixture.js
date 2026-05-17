/**
 * Static fixture for Korea Annual Leave Dashboard — preview/no-runtime fallback.
 *
 * Shaped to match the contract_type "korea_annual_leave_preview_v1" returned by
 * the backend preview API. Used when frappe.call is unavailable (PWA offline,
 * unit tests, demo mode).
 */

export const koreaAnnualLeaveFixture = {
	contract_type: "korea_annual_leave_preview_v1",
	runtime_action: "preview_only",
	requires_runtime_apply: true,
	requires_human_approval: true,
	ai_role: "assistant_only",
	preview_source: "static_fixture",

	// employee
	employee: "EMP-DEMO-001",
	employee_name: "홍길동",
	company: "Korea Demo Co",
	department: "영업부",
	designation: "과장",

	// hire info
	date_of_joining: "2021-03-15",
	as_of_date: "2026-05-01",
	basis: "Hire Date",

	// entitlement
	draft: {
		contract_type: "korea_leave_allocation_draft_v1",
		employee: "EMP-DEMO-001",
		employee_name: "홍길동",
		company: "Korea Demo Co",
		leave_type: "Annual Leave",
		from_date: "2026-03-15",
		to_date: "2027-03-14",
		new_leaves_allocated: 15,
		unused_leaves: 15,
		total_reference_entitlement: 15,
		existing_allocated_days: 0,
		carry_forward: false,
		requires_runtime_apply: true,
		entitlement_reference: {
			basis: "Hire Date",
			hire_date: "2021-03-15",
			as_of_date: "2026-05-01",
			employment_end_date: null,
			period_start: "2026-03-15",
			period_end: "2027-03-14",
			service_years: 5,
			monthly_accrual_days: 0,
			annual_entitlement_days: 15,
			total_entitlement_days: 15,
		},
	},

	// ratio adjustment (when attendance ratio is checked)
	ratio_adjustment: null,

	// usage summary (from Leave Allocation + Leave Application records)
	usage: {
		allocated_days: 15,
		used_days: 5,
		remaining_days: 10,
		leave_type: "Annual Leave",
	},
}

export function buildKoreaAnnualLeaveFixtureForEmployee(employeeId) {
	return {
		...koreaAnnualLeaveFixture,
		employee: employeeId || koreaAnnualLeaveFixture.employee,
		preview_source: "static_fixture",
	}
}
