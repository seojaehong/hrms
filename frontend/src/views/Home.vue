<template>
	<BaseLayout>
		<template #body>
			<div class="flex flex-col items-center my-7 p-4 gap-6">
				<CheckInPanel />

				<!-- 핵심 4축: 급여 / 퇴직금 / 연차 / 근태 — DESIGN-figma 색블록 섹션 -->
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
					<div
						v-for="section in sections"
						:key="section.key"
						class="k-block"
						:class="`k-block--${section.block}`"
					>
						<div class="k-eyebrow mb-0.5">{{ section.eyebrow }}</div>
						<div class="text-lg font-bold text-black mb-2 tracking-tight">{{ section.title }}</div>
						<div class="flex flex-col">
							<router-link
								v-for="link in section.links"
								:key="link.route"
								:to="{ name: link.route }"
								class="flex flex-row items-center justify-between py-2.5 border-t border-black/10"
							>
								<span class="text-sm font-medium text-black">{{ link.title }}</span>
								<FeatherIcon name="chevron-right" class="h-4 w-4 text-black/40" />
							</router-link>
						</div>
					</div>
				</div>

				<!-- 그 외 기능 — 모노크롬 리스트 -->
				<QuickLinks :items="moreLinks" :title="__('더 보기')" />

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
import { FeatherIcon } from "frappe-ui"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"
import ShiftIcon from "@/components/icons/ShiftIcon.vue"
import ExpenseIcon from "@/components/icons/ExpenseIcon.vue"
import EmployeeAdvanceIcon from "@/components/icons/EmployeeAdvanceIcon.vue"

const __ = inject("$translate")

// 핵심 4축 — 사업주/담당자 멘탈모델(급여·퇴직금·연차·근태) 그대로.
const sections = [
	{
		key: "payroll",
		block: "lime",
		eyebrow: "PAYROLL",
		title: __("급여"),
		links: [
			{ title: __("임금명세서"), route: "KoreaWageStatementDashboard" },
			{ title: __("급여 마감 센터"), route: "KoreaPayrollClosingDashboard" },
			{ title: __("급여 검토 감사 로그"), route: "KoreaPayrollReviewAuditLogs" },
		],
	},
	{
		key: "severance",
		block: "cream",
		eyebrow: "SEVERANCE",
		title: __("퇴직금"),
		links: [
			{ title: __("퇴직금 미리보기"), route: "KoreaSeverancePreview" },
		],
	},
	{
		key: "leave",
		block: "lilac",
		eyebrow: "ANNUAL LEAVE",
		title: __("연차"),
		links: [
			{ title: __("연차 대시보드"), route: "KoreaAnnualLeaveDashboard" },
			{ title: __("휴가 신청"), route: "LeaveApplicationFormView" },
		],
	},
	{
		key: "attendance",
		block: "mint",
		eyebrow: "ATTENDANCE",
		title: __("근태"),
		links: [
			{ title: __("모바일 출퇴근"), route: "KoreaMobileCheckin" },
			{ title: __("근태 대시보드"), route: "KoreaAttendanceDashboard" },
			{ title: __("출근기록 신청"), route: "AttendanceRequestFormView" },
		],
	},
]

const moreLinks = [
	{
		icon: markRaw(EmployeeAdvanceIcon),
		title: __("입사자 등록 요청"),
		route: "KoreaOnboardingRequest",
	},
	{
		icon: markRaw(AttendanceIcon),
		title: __("결재 인박스"),
		route: "KoreaApprovalInbox",
	},
	{
		icon: markRaw(ShiftIcon),
		title: __("교대근무 신청"),
		route: "ShiftRequestFormView",
	},
	{
		icon: markRaw(ExpenseIcon),
		title: __("경비 청구"),
		route: "ExpenseClaimFormView",
	},
	{
		icon: markRaw(EmployeeAdvanceIcon),
		title: __("선급금 신청"),
		route: "EmployeeAdvanceFormView",
	},
	{
		icon: markRaw(ShiftIcon),
		title: __("컴플라이언스 진단"),
		route: "KoreaComplianceDashboard",
	},
	{
		icon: markRaw(AttendanceIcon),
		title: __("AI HR 담당자"),
		route: "KoreaAIChat",
	},
]
</script>
