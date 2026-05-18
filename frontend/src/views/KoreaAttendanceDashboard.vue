<template>
	<BaseLayout pageTitle="한국 근태/가산수당">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-gray-50 p-4 pb-24">

				<!-- 픽스처/오류 배너 -->
				<div
					v-if="attendanceError || premiumError"
					class="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
				>
					<p class="font-semibold">미리보기 모드 (픽스처)</p>
					<p v-if="attendanceError" class="mt-1">{{ attendanceError }}</p>
					<p v-if="premiumError" class="mt-1">{{ premiumError }}</p>
				</div>

				<!-- Card 1: 이번 달 출근 요약 -->
				<section class="rounded-2xl bg-white p-5 shadow-sm border border-gray-100">
					<div class="flex items-center justify-between mb-3">
						<h2 class="text-base font-bold text-gray-900">이번 달 출근 요약</h2>
						<span
							class="rounded-full px-2 py-0.5 text-xs font-semibold"
							:class="dataSourceBadgeClass"
						>
							{{ dataSourceBadge }}
						</span>
					</div>

					<div v-if="attendanceLoading" class="text-sm text-gray-400">불러오는 중...</div>

					<template v-else>
						<div class="grid grid-cols-2 gap-3">
							<div class="rounded-xl bg-gray-50 p-3">
								<p class="text-xs text-gray-500">출근일</p>
								<p class="mt-1 text-xl font-bold text-gray-900">{{ empSummary?.present_days ?? "—" }}일</p>
							</div>
							<div class="rounded-xl bg-gray-50 p-3">
								<p class="text-xs text-gray-500">마감기준일</p>
								<p class="mt-1 text-xl font-bold text-gray-900">{{ closingDays }}</p>
							</div>
							<div class="rounded-xl bg-gray-50 p-3">
								<p class="text-xs text-gray-500">결근</p>
								<p class="mt-1 text-lg font-bold text-gray-900">{{ empSummary?.absent_days ?? "—" }}일</p>
							</div>
							<div class="rounded-xl bg-gray-50 p-3">
								<p class="text-xs text-gray-500">휴가</p>
								<p class="mt-1 text-lg font-bold text-gray-900">{{ empSummary?.leave_days ?? "—" }}일</p>
							</div>
							<div class="rounded-xl bg-gray-50 p-3">
								<p class="text-xs text-gray-500">반차</p>
								<p class="mt-1 text-lg font-bold text-gray-900">{{ empSummary?.half_day_count ?? "—" }}회</p>
							</div>
							<div
								class="rounded-xl p-3"
								:class="attendanceRatioLow ? 'bg-red-50' : 'bg-green-50'"
							>
								<p class="text-xs" :class="attendanceRatioLow ? 'text-red-600' : 'text-gray-500'">
									출근률
									<span v-if="attendanceRatioLow" class="ml-1">⚠️</span>
								</p>
								<p
									class="mt-1 text-lg font-bold"
									:class="attendanceRatioLow ? 'text-red-700' : 'text-gray-900'"
								>
									{{ attendanceRatioFormatted }}
								</p>
								<p v-if="attendanceRatioLow" class="mt-0.5 text-xs text-red-600">
									80% 미달 — 연차 감액 위험 (근기법 60조 4항)
								</p>
							</div>
						</div>
					</template>
				</section>

				<!-- Card 2: 연장/야간/휴일 시간 -->
				<section class="rounded-2xl bg-white p-5 shadow-sm border border-gray-100">
					<h2 class="text-base font-bold text-gray-900 mb-3">연장·야간·휴일 시간</h2>

					<div v-if="attendanceLoading" class="text-sm text-gray-400">불러오는 중...</div>

					<template v-else>
						<div class="flex flex-col gap-2">
							<div class="flex items-center justify-between rounded-xl bg-gray-50 p-3">
								<p class="text-sm text-gray-600">정시근로</p>
								<p class="text-sm font-bold text-gray-900">{{ regularHours }}시간</p>
							</div>
							<div
								class="flex items-center justify-between rounded-xl p-3"
								:class="weeklyOvertimeExceeded ? 'bg-red-50' : 'bg-gray-50'"
							>
								<div>
									<p class="text-sm" :class="weeklyOvertimeExceeded ? 'text-red-700' : 'text-gray-600'">
										연장근로
										<span v-if="weeklyOvertimeExceeded" class="ml-1">⚠️</span>
									</p>
									<p v-if="weeklyOvertimeExceeded" class="text-xs text-red-600 mt-0.5">
										주 12h 초과 — 근기법 53조 위반 위험
									</p>
								</div>
								<div class="text-right">
									<p class="text-sm font-bold" :class="weeklyOvertimeExceeded ? 'text-red-700' : 'text-gray-900'">
										{{ overtimeHours }}시간
									</p>
									<p class="text-xs text-gray-400">/ 주 한도 12h</p>
								</div>
							</div>
							<div class="flex items-center justify-between rounded-xl bg-gray-50 p-3">
								<p class="text-sm text-gray-600">야간근로</p>
								<p class="text-sm font-bold text-gray-900">{{ nightHours }}시간</p>
							</div>
							<div class="flex items-center justify-between rounded-xl bg-gray-50 p-3">
								<p class="text-sm text-gray-600">휴일근로</p>
								<p class="text-sm font-bold text-gray-900">{{ holidayHours }}시간</p>
							</div>
						</div>
					</template>
				</section>

				<!-- Card 3: 가산수당 미리보기 -->
				<section class="rounded-2xl bg-white p-5 shadow-sm border border-gray-100">
					<h2 class="text-base font-bold text-gray-900 mb-3">가산수당 미리보기 (근기법 56조)</h2>

					<div class="flex flex-col gap-2 mb-4">
						<label class="text-xs text-gray-500 font-medium">통상시급 (원)</label>
						<div class="flex gap-2">
							<input
								v-model.number="hourlyRateInput"
								type="number"
								min="0"
								placeholder="예: 10030"
								class="flex-1 rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
								style="color: var(--color-text-primary, #111827); background: var(--color-surface, #fff);"
								@input="onHourlyRateInput"
							/>
							<button
								class="rounded-xl px-4 py-2 text-sm font-semibold text-white"
								style="background: var(--color-primary, #2563eb);"
								@click="loadPremiumPreview"
							>
								계산
							</button>
						</div>
					</div>

					<div v-if="premiumLoading" class="text-sm text-gray-400">계산 중...</div>

					<template v-else>
						<div class="flex flex-col gap-2">
							<div class="flex justify-between rounded-xl bg-gray-50 p-3">
								<p class="text-sm text-gray-600">정시급 (정시 × 시급)</p>
								<p class="text-sm font-bold text-gray-900">{{ formatWon(premiumBasePay) }}</p>
							</div>
							<div class="flex justify-between rounded-xl bg-gray-50 p-3">
								<p class="text-sm text-gray-600">연장수당 (50% 가산)</p>
								<p class="text-sm font-bold text-gray-900">{{ formatWon(premiumOvertime) }}</p>
							</div>
							<div class="flex justify-between rounded-xl bg-gray-50 p-3">
								<p class="text-sm text-gray-600">야간수당 (50% 추가)</p>
								<p class="text-sm font-bold text-gray-900">{{ formatWon(premiumNight) }}</p>
							</div>
							<div class="flex justify-between rounded-xl bg-gray-50 p-3">
								<p class="text-sm text-gray-600">휴일수당 (50%/100%)</p>
								<p class="text-sm font-bold text-gray-900">{{ formatWon(premiumHoliday) }}</p>
							</div>
							<div class="flex justify-between rounded-xl p-3" style="background: var(--color-primary, #2563eb); opacity: 0.9;">
								<p class="text-sm font-bold text-white">합계</p>
								<p class="text-base font-bold text-white">{{ formatWon(premiumTotal) }}</p>
							</div>
						</div>
						<p class="mt-2 text-xs text-gray-400">
							* 통상시급 미입력 시 가산금액은 0원입니다. 정확한 계산을 위해 시급을 입력하세요.
						</p>
					</template>
				</section>

				<!-- Card 4: 마감 상태 (관리자용) -->
				<section v-if="isAdminUser" class="rounded-2xl bg-gray-900 p-5 text-white shadow-sm">
					<h2 class="text-base font-bold text-white mb-1">마감 상태 (관리자)</h2>
					<p class="text-xs text-gray-400 mb-3">사업장 단위 마감 진행 현황</p>

					<div class="grid grid-cols-2 gap-2 mb-4">
						<div class="rounded-xl bg-white/10 p-3 text-center">
							<p class="text-xl font-bold text-white">{{ closingProgress.total }}</p>
							<p class="text-xs text-gray-300">전체</p>
						</div>
						<div class="rounded-xl bg-green-400/20 p-3 text-center">
							<p class="text-xl font-bold text-green-100">{{ closingProgress.completed }}</p>
							<p class="text-xs text-green-300">마감 완료</p>
						</div>
					</div>

					<div class="rounded-xl border border-amber-200/30 bg-amber-400/10 p-3 mb-4 text-sm text-amber-100">
						<p class="font-semibold">뮤테이션 경계</p>
						<p class="mt-1 text-xs text-amber-200">
							마감 적용은 draft 저장 전용입니다. submit/cancel/approve/send는 별도 워크플로우에서 처리합니다.
						</p>
						<!-- mutation_boundary: draft_only_no_submit_no_approve_no_send -->
						<p class="mt-1 text-xs text-amber-300/50">boundary: draft_only_no_submit_no_approve_no_send</p>
					</div>

					<div class="flex gap-2">
						<button
							class="flex-1 rounded-xl border border-white/30 py-2.5 text-sm font-semibold text-white"
							@click="loadAttendanceSummary"
						>
							마감 미리보기
						</button>
						<button
							class="flex-1 rounded-xl py-2.5 text-sm font-semibold text-gray-900"
							style="background: #fbbf24;"
							@click="showApplyDialog = true"
						>
							마감 적용
						</button>
					</div>
				</section>

				<!-- 마감 적용 확인 다이얼로그 -->
				<div
					v-if="showApplyDialog"
					class="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4"
					@click.self="showApplyDialog = false"
				>
					<div class="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
						<h3 class="text-base font-bold text-gray-900">마감 적용 확인</h3>
						<p class="mt-2 text-sm text-gray-600">
							{{ closingPeriodLabel }} 근태 마감을 적용합니다.<br />
							이 작업은 Draft 저장이며 승인·발송은 포함하지 않습니다.
						</p>
						<div class="mt-4 rounded-xl bg-red-50 p-3 text-xs text-red-700">
							⚠️ 관리자가 직접 검토·승인한 경우에만 진행하세요.
						</div>
						<div class="mt-5 flex gap-3">
							<button
								class="flex-1 rounded-xl border border-gray-200 py-2.5 text-sm font-semibold text-gray-700"
								@click="showApplyDialog = false"
							>
								취소
							</button>
							<button
								class="flex-1 rounded-xl py-2.5 text-sm font-bold text-white"
								style="background: var(--color-primary, #2563eb);"
								:disabled="applyLoading"
								@click="doApplyClosing"
							>
								{{ applyLoading ? "처리 중..." : "적용 확인" }}
							</button>
						</div>
						<p v-if="applyError" class="mt-3 text-xs text-red-600">{{ applyError }}</p>
						<p v-if="applySuccess" class="mt-3 text-xs text-green-700">{{ applySuccess }}</p>
					</div>
				</div>

			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { ref, computed, inject, onMounted } from "vue"
import BaseLayout from "@/components/BaseLayout.vue"
import {
	fetchKoreaAttendanceSummary,
	fetchKoreaPremiumPreview,
	applyKoreaAttendanceClosing,
	extractEmployeeSummary,
	formatAttendanceRatio,
	isWeeklyOvertimeExceeded,
} from "@/data/koreaAttendanceRuntime"

// ── Frappe 주입 ──────────────────────────────────────────────────
const employee = inject("$employee")
const dayjs = inject("$dayjs")

// ── 기간 설정 (이번 달) ──────────────────────────────────────────
const periodStart = computed(() => dayjs().startOf("month").format("YYYY-MM-DD"))
const periodEnd = computed(() => dayjs().endOf("month").format("YYYY-MM-DD"))
const closingPeriodLabel = computed(() => `${periodStart.value} ~ ${periodEnd.value}`)

// ── 출근 요약 상태 ───────────────────────────────────────────────
const attendanceLoading = ref(false)
const attendanceError = ref("")
const attendanceData = ref(null)
const attendanceSource = ref("fixture")

const empSummary = computed(() =>
	extractEmployeeSummary(attendanceData.value, employee?.data?.name)
)

const closingDays = computed(() =>
	empSummary.value?.closing_days != null ? `${empSummary.value.closing_days}일` : "—"
)

const attendanceRatioFormatted = computed(() =>
	formatAttendanceRatio(empSummary.value?.attendance_ratio)
)

const attendanceRatioLow = computed(() => {
	const ratio = empSummary.value?.attendance_ratio
	return ratio != null && Number(ratio) < 0.8
})

const regularHours = computed(() =>
	empSummary.value?.total_regular_hours?.toFixed(1) ?? "—"
)
const overtimeHours = computed(() =>
	empSummary.value?.total_overtime_hours?.toFixed(1) ?? "—"
)
const nightHours = computed(() =>
	empSummary.value?.total_night_hours?.toFixed(1) ?? "—"
)
const holidayHours = computed(() =>
	empSummary.value?.total_holiday_hours?.toFixed(1) ?? "—"
)

const weeklyOvertimeExceeded = computed(() =>
	isWeeklyOvertimeExceeded(empSummary.value?.total_overtime_hours ?? 0)
)

const dataSourceBadge = computed(() =>
	attendanceSource.value === "runtime" ? "실시간" : "픽스처"
)
const dataSourceBadgeClass = computed(() =>
	attendanceSource.value === "runtime"
		? "bg-green-100 text-green-800"
		: "bg-amber-100 text-amber-800"
)

// ── 가산수당 상태 ────────────────────────────────────────────────
const hourlyRateInput = ref(null)
const premiumLoading = ref(false)
const premiumError = ref("")
const premiumData = ref(null)

const premiumBasePay = computed(() =>
	premiumData.value?.total_premium?.base_pay ?? 0
)
const premiumOvertime = computed(() =>
	premiumData.value?.total_premium?.overtime_premium ?? 0
)
const premiumNight = computed(() =>
	premiumData.value?.total_premium?.night_premium ?? 0
)
const premiumHoliday = computed(() =>
	(premiumData.value?.total_premium?.holiday_premium ?? 0) +
	(premiumData.value?.total_premium?.holiday_overtime_premium ?? 0)
)
const premiumTotal = computed(() =>
	premiumData.value?.total_premium?.total_pay ?? 0
)

// ── 관리자 상태 ──────────────────────────────────────────────────
// 실제 구현: frappe.user_roles 또는 employee.data.is_hr_manager 등으로 판별
const isAdminUser = computed(() =>
	Boolean(
		globalThis.window?.frappe?.boot?.user?.roles?.includes("HR Manager") ||
		globalThis.window?.frappe?.boot?.user?.roles?.includes("System Manager")
	)
)

const closingProgress = ref({ total: 0, completed: 0 })

// ── 마감 적용 상태 ───────────────────────────────────────────────
const showApplyDialog = ref(false)
const applyLoading = ref(false)
const applyError = ref("")
const applySuccess = ref("")

// ── 포맷 헬퍼 ───────────────────────────────────────────────────
function formatWon(amount) {
	if (amount == null || amount === 0) return "0원"
	return `${Math.round(Number(amount)).toLocaleString("ko-KR")}원`
}

// ── 데이터 로딩 ─────────────────────────────────────────────────
async function loadAttendanceSummary() {
	attendanceLoading.value = true
	attendanceError.value = ""
	try {
		const result = await fetchKoreaAttendanceSummary({
			employee: employee?.data?.name,
			periodStart: periodStart.value,
			periodEnd: periodEnd.value,
			workplace: employee?.data?.company || "",
		})
		attendanceData.value = result.data
		attendanceSource.value = result.source
		if (result.error) attendanceError.value = result.error
	} finally {
		attendanceLoading.value = false
	}
}

async function loadPremiumPreview() {
	if (!hourlyRateInput.value || Number(hourlyRateInput.value) <= 0) {
		premiumError.value = "통상시급을 입력하세요."
		return
	}
	premiumLoading.value = true
	premiumError.value = ""
	try {
		const result = await fetchKoreaPremiumPreview({
			employee: employee?.data?.name,
			periodStart: periodStart.value,
			periodEnd: periodEnd.value,
			hourlyRate: hourlyRateInput.value,
		})
		premiumData.value = result.data
		if (result.error) premiumError.value = result.error
	} finally {
		premiumLoading.value = false
	}
}

function onHourlyRateInput() {
	// 시급 입력 시 자동 재계산 (픽스처 환경)
	if (hourlyRateInput.value && Number(hourlyRateInput.value) > 0) {
		loadPremiumPreview()
	}
}

async function doApplyClosing() {
	applyLoading.value = true
	applyError.value = ""
	applySuccess.value = ""
	try {
		const snapshot = attendanceData.value?.snapshot
		const result = await applyKoreaAttendanceClosing({
			snapshot,
			humanApproved: true,
			actor: globalThis.window?.frappe?.session?.user || "hr_manager",
		})
		if (result.data?.applied === false) {
			applyError.value = result.error || result.data?.reason || "마감 적용 실패"
		} else {
			applySuccess.value = "근태 마감이 Draft에 저장되었습니다. 최종 승인은 별도 워크플로우에서 처리합니다."
			showApplyDialog.value = false
		}
	} finally {
		applyLoading.value = false
	}
}

// ── 초기 로드 ────────────────────────────────────────────────────
onMounted(() => {
	loadAttendanceSummary()
})
</script>
