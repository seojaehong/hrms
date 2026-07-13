<template>
	<BaseLayout>
		<template #body>
			<div class="flex flex-col items-center my-7 p-4 gap-6 md:gap-10">
				<!-- 데스크톱 인사 헤드라인 — 가이드 display 타이포 -->
				<div class="hidden md:block w-full pt-2">
					<p class="k-eyebrow">SAFECLAW HR</p>
					<h1 class="mt-2 text-5xl xl:text-6xl font-extrabold tracking-[-0.03em] leading-[1.04] text-[var(--k-ink)]">
						{{ __("급여부터 근태까지,") }}<br />{{ __("오늘 할 일이 정리되어 있습니다") }}
					</h1>
				</div>

				<CheckInPanel />

				<!-- 핵심 4축: 급여 / 퇴직금 / 연차 / 근태 — DESIGN-figma 색블록 섹션 -->
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6 w-full">
					<div
						v-for="(section, idx) in sections"
						:key="section.key"
						class="k-block transition-transform duration-200 md:hover:-translate-y-0.5"
						:class="`k-block--${section.block}`"
					>
						<div class="flex items-baseline justify-between">
							<div class="k-eyebrow mb-0.5">{{ section.eyebrow }}</div>
							<span class="k-eyebrow opacity-40">{{ String(idx + 1).padStart(2, "0") }}</span>
						</div>
						<div class="k-block-title text-[var(--k-ink)] mb-2">{{ section.title }}</div>
						<div class="flex flex-col">
							<router-link
								v-for="link in section.links"
								:key="link.route"
								:to="{ name: link.route }"
								class="group flex flex-row items-center justify-between py-2.5 md:py-3 border-t border-[var(--k-hairline)]"
							>
								<span class="text-sm md:text-base font-medium text-[var(--k-ink)]">{{ link.title }}</span>
								<FeatherIcon name="chevron-right" class="h-4 w-4 text-[var(--k-ink-faint)] transition-transform group-hover:translate-x-0.5" />
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
			{ title: __("임금명세서 분해 (§48②)"), route: "KoreaPayslipBreakdown" },
			{ title: __("포괄임금 설계·역산"), route: "KoreaInclusiveWage" },
			{ title: __("급여 엑셀 관리"), route: "KoreaPayrollExcel" },
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
			{ title: __("퇴직정산 (통합)"), route: "KoreaSeveranceSettlement" },
		],
	},
	{
		key: "leave",
		block: "lilac",
		eyebrow: "ANNUAL LEAVE",
		title: __("연차"),
		links: [
			{ title: __("연차 대시보드"), route: "KoreaAnnualLeaveDashboard" },
			{ title: __("연차 사용촉진 (§61)"), route: "KoreaLeavePromotion" },
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
			{ title: __("근무시간 제출"), route: "KoreaTimeInput" },
			{ title: __("출근기록 신청"), route: "AttendanceRequestFormView" },
		],
	},
	{
		key: "labor",
		block: "pink",
		eyebrow: "LABOR COMPLIANCE",
		title: __("노무"),
		links: [
			{ title: __("근로계약서 작성 (§17)"), route: "KoreaEmploymentContractDoc" },
			{ title: __("취업규칙 점검 (§93·§94)"), route: "KoreaWorkRules" },
			{ title: __("근로감독 대비 체크리스트"), route: "KoreaLaborInspection" },
			{ title: __("컴플라이언스 진단"), route: "KoreaComplianceDashboard" },
		],
	},
]

const moreLinks = [
	{
		icon: markRaw(AttendanceIcon),
		title: __("요청 보드"),
		route: "KoreaServiceRequests",
	},
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
		icon: markRaw(AttendanceIcon),
		title: __("AI HR 담당자"),
		route: "KoreaAIChat",
	},
]
</script>
