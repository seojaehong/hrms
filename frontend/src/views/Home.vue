<template>
	<BaseLayout>
		<template #body>
			<div class="flex flex-col items-center my-7 p-4 gap-7">
				<CheckInPanel />
				<router-link
					:to="{ name: 'KoreaPayrollClosingOperatorPreview' }"
					class="w-full rounded-2xl bg-gray-900 p-5 text-white shadow-sm transition hover:bg-gray-800"
				>
					<div class="flex items-start justify-between gap-3">
						<div>
							<div class="text-xs font-semibold uppercase tracking-[0.18em] text-gray-300">
								{{ __("Korea Payroll") }}
							</div>
							<div class="mt-2 text-xl font-bold leading-tight">
								{{ __("Monthly Closing Center") }}
							</div>
							<div class="mt-2 text-sm leading-5 text-gray-300">
								{{ __("Review blocked workplaces, evidence packets, and draft readiness before human approval.") }}
							</div>
						</div>
						<FeatherIcon name="arrow-up-right" class="h-5 w-5 shrink-0 text-gray-300" />
					</div>
				</router-link>
				<QuickLinks :items="quickLinks" :title="__('Quick Links')" />
				<RequestPanel />
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { inject, markRaw } from "vue"
import { FeatherIcon } from "frappe-ui"

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
]
</script>
