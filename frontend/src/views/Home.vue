<template>
	<BaseLayout>
		<template #body>
			<div class="flex flex-col items-center my-7 p-4 gap-7">
				<CheckInPanel />
				<QuickLinks :items="quickLinks" :title="__('Quick Links')" />
				<RequestPanel />
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { inject, markRaw } from "vue"

import CheckInPanel from "@/components/CheckInPanel.vue"
import QuickLinks from "@/components/QuickLinks.vue"
import BaseLayout from "@/components/BaseLayout.vue"
import RequestPanel from "@/components/RequestPanel.vue"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"
import ShiftIcon from "@/components/icons/ShiftIcon.vue"
import LeaveIcon from "@/components/icons/LeaveIcon.vue"
import ExpenseIcon from "@/components/icons/ExpenseIcon.vue"
import EmployeeAdvanceIcon from "@/components/icons/EmployeeAdvanceIcon.vue"
import SalaryIcon from "@/components/icons/SalaryIcon.vue"

const __ = inject("$translate")

const quickLinks = [
	{
		icon: markRaw(AttendanceIcon),
		title: __("Request Attendance"),
		route: "AttendanceRequestFormView",
	},
	{
		icon: markRaw(ShiftIcon),
		title: __("Request a Shift"),
		route: "ShiftRequestFormView",
	},
	{
		icon: markRaw(LeaveIcon),
		title: __("Request Leave"),
		route: "LeaveApplicationFormView",
	},
	{
		icon: markRaw(ExpenseIcon),
		title: __("Claim an Expense"),
		route: "ExpenseClaimFormView",
	},
	{
		icon: markRaw(EmployeeAdvanceIcon),
		title: __("Request an Advance"),
		route: "EmployeeAdvanceFormView",
	},
	{
		icon: markRaw(SalaryIcon),
		title: __("View Salary Slips"),
		route: "SalarySlipsDashboard",
	},
	{
		icon: markRaw(SalaryIcon),
		title: __("급여 마감 센터"),
		route: "KoreaPayrollClosingDashboard",
	},
	{
		icon: markRaw(SalaryIcon),
		title: __("급여 검토 감사 로그"),
		route: "KoreaPayrollReviewAuditLogs",
	},
	{
		icon: markRaw(AttendanceIcon),
		title: __("근태 대시보드"),
		route: "KoreaAttendanceDashboard",
	},
	{
		icon: markRaw(AttendanceIcon),
		title: __("모바일 출퇴근"),
		route: "KoreaMobileCheckin",
	},
	{
		icon: markRaw(LeaveIcon),
		title: __("연차 대시보드"),
		route: "KoreaAnnualLeaveDashboard",
	},
	{
		icon: markRaw(ShiftIcon),
		title: __("결재 인박스"),
		route: "KoreaApprovalInbox",
	},
	{
		icon: markRaw(SalaryIcon),
		title: __("임금명세서"),
		route: "KoreaWageStatementDashboard",
	},
	{
		icon: markRaw(SalaryIcon),
		title: __("퇴직금 미리보기"),
		route: "KoreaSeverancePreview",
	},
	{
		icon: markRaw(ExpenseIcon),
		title: __("컴플라이언스 진단"),
		route: "KoreaComplianceDashboard",
	},
	{
		icon: markRaw(EmployeeAdvanceIcon),
		title: __("AI HR 담당자"),
		route: "KoreaAIChat",
	},
]
</script>
