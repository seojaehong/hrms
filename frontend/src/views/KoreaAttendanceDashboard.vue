<template>
	<BaseLayout :pageTitle="__('근태 현황')">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-white p-4 pb-24">

				<!-- 히어로 — 근태(mint) 색블록 + 핵심 스탯 -->
				<section class="k-block k-block--mint">
					<div class="flex items-start justify-between gap-3">
						<div>
							<p class="k-eyebrow">ATTENDANCE</p>
							<h1 class="mt-1 text-2xl font-bold tracking-tight text-black">{{ __("근태 현황") }}</h1>
							<p class="k-numeric mt-1 text-sm font-medium text-black/60">{{ closingPeriodLabel }}</p>
						</div>
						<span class="rounded-full px-3 py-1 text-xs font-semibold" :class="dataSourceBadgeClass">{{ dataSourceBadge }}</span>
					</div>
					<!-- 주인공: 출근일수 -->
					<div class="mt-3">
						<p class="text-sm font-medium text-black/60">{{ __("이번 마감 출근") }}</p>
						<p class="k-numeric text-4xl font-bold tracking-tight leading-tight text-black">
							{{ empSummary?.present_days ?? "—" }}<span class="text-xl font-bold">일</span>
						</p>
					</div>
					<div class="mt-4 grid grid-cols-3 gap-2">
						<div class="rounded-xl bg-white/60 p-3 text-center">
							<p class="k-numeric text-xl font-bold text-black">{{ closingDays }}</p>
							<p class="mt-0.5 text-xs font-medium text-black/60">{{ __("마감기준일") }}</p>
						</div>
						<div class="rounded-xl bg-white/60 p-3 text-center">
							<p class="k-numeric text-xl font-bold" :class="attendanceRatioLow ? 'text-red-700' : 'text-black'">{{ attendanceRatioFormatted }}</p>
							<p class="mt-0.5 text-xs font-medium text-black/60">{{ __("출근률") }}</p>
						</div>
						<div class="rounded-xl bg-black p-3 text-center">
							<p class="k-numeric text-xl font-bold text-white">{{ empSummary?.present_days ?? "—" }}</p>
							<p class="mt-0.5 text-xs font-medium text-white/60">{{ __("출근(일)") }}</p>
						</div>
					</div>
				</section>

				<!-- 픽스처/오류 배너 -->
				<div v-if="attendanceError || premiumError" class="k-card p-4 text-sm">
					<div class="flex items-center gap-2">
						<span class="rounded-full bg-black/10 px-2.5 py-0.5 text-xs font-semibold text-black">{{ __("정적 예시") }}</span>
						<p class="font-semibold text-black">{{ __("미리보기 모드 (픽스처)") }}</p>
					</div>
					<p v-if="attendanceError" class="mt-2 text-black/60">{{ attendanceError }}</p>
					<p v-if="premiumError" class="mt-1 text-black/60">{{ premiumError }}</p>
				</div>

				<!-- Card 1: 이번 달 출근 요약 -->
				<section class="k-card p-4">
					<p class="k-eyebrow">MONTHLY SUMMARY</p>
					<h2 class="mt-0.5 text-base font-bold text-black">{{ __("이번 달 출근 요약") }}</h2>

					<div v-if="attendanceLoading" class="mt-3 text-sm text-black/40">{{ __("불러오는 중…") }}</div>

					<template v-else>
						<!-- 출근/결근/휴가 구성 바 — 인라인 SVG (뷰에 이미 로드된 empSummary만 사용, 데이터 없으면 숨김) -->
						<div v-if="compositionBar" class="mt-3" data-testid="attendance-composition-bar">
							<svg
								viewBox="0 0 280 12"
								class="h-3 w-full overflow-hidden rounded-full text-black"
								role="img"
								aria-label="출근·결근·휴가 구성"
								preserveAspectRatio="none"
							>
								<rect
									v-for="(seg, i) in compositionBar"
									:key="i"
									:x="seg.x"
									y="0"
									:width="seg.width"
									height="12"
									fill="currentColor"
									:fill-opacity="compositionOpacities[i]"
								/>
							</svg>
							<div class="mt-1.5 flex gap-4 text-[11px] text-black/50">
								<span class="flex items-center gap-1">
									<span class="h-2 w-2 rounded-full bg-black"></span>{{ __("출근") }} <span class="k-numeric font-semibold text-black/70">{{ compositionValues[0] }}</span>
								</span>
								<span class="flex items-center gap-1">
									<span class="h-2 w-2 rounded-full bg-black/35"></span>{{ __("결근") }} <span class="k-numeric font-semibold text-black/70">{{ compositionValues[1] }}</span>
								</span>
								<span class="flex items-center gap-1">
									<span class="h-2 w-2 rounded-full bg-black/15"></span>{{ __("휴가") }} <span class="k-numeric font-semibold text-black/70">{{ compositionValues[2] }}</span>
								</span>
							</div>
						</div>

						<div class="mt-3 grid grid-cols-2 gap-2">
							<div class="rounded-xl bg-[#f7f7f5] p-3">
								<p class="text-xs text-black/50">{{ __("출근일") }}</p>
								<p class="k-numeric mt-1 text-xl font-bold text-black">{{ empSummary?.present_days ?? "—" }}{{ __("일") }}</p>
							</div>
							<div class="rounded-xl bg-[#f7f7f5] p-3">
								<p class="text-xs text-black/50">{{ __("마감기준일") }}</p>
								<p class="k-numeric mt-1 text-xl font-bold text-black">{{ closingDays }}</p>
							</div>
							<div class="rounded-xl bg-[#f7f7f5] p-3">
								<p class="text-xs text-black/50">{{ __("결근") }}</p>
								<p class="k-numeric mt-1 text-lg font-bold text-black">{{ empSummary?.absent_days ?? "—" }}{{ __("일") }}</p>
							</div>
							<div class="rounded-xl bg-[#f7f7f5] p-3">
								<p class="text-xs text-black/50">{{ __("휴가") }}</p>
								<p class="k-numeric mt-1 text-lg font-bold text-black">{{ empSummary?.leave_days ?? "—" }}{{ __("일") }}</p>
							</div>
							<div class="rounded-xl bg-[#f7f7f5] p-3">
								<p class="text-xs text-black/50">{{ __("반차") }}</p>
								<p class="k-numeric mt-1 text-lg font-bold text-black">{{ empSummary?.half_day_count ?? "—" }}{{ __("회") }}</p>
							</div>
							<div class="rounded-xl p-3" :class="attendanceRatioLow ? 'bg-red-100' : 'bg-[#f7f7f5]'">
								<p class="text-xs" :class="attendanceRatioLow ? 'text-red-700' : 'text-black/50'">
									{{ __("출근률") }}
								</p>
								<p class="k-numeric mt-1 text-lg font-bold" :class="attendanceRatioLow ? 'text-red-700' : 'text-black'">
									{{ attendanceRatioFormatted }}
								</p>
								<p v-if="attendanceRatioLow" class="mt-0.5 text-xs font-semibold text-red-700">
									80% 미달 — 연차 감액 위험 (근기법 60조 4항)
								</p>
							</div>
						</div>
					</template>
				</section>

				<!-- Card 2: 연장/야간/휴일 시간 -->
				<section class="k-card p-4">
					<p class="k-eyebrow">OVERTIME</p>
					<h2 class="mt-0.5 text-base font-bold text-black">{{ __("연장·야간·휴일 시간") }}</h2>

					<div v-if="attendanceLoading" class="mt-3 text-sm text-black/40">{{ __("불러오는 중…") }}</div>

					<template v-else>
						<div class="mt-3 flex flex-col gap-2">
							<div class="flex items-center justify-between rounded-xl bg-[#f7f7f5] p-3">
								<p class="text-sm text-black">{{ __("정시근로") }}</p>
								<p class="k-numeric text-sm font-bold text-black">{{ regularHours }}{{ __("시간") }}</p>
							</div>
							<div
								class="flex items-center justify-between rounded-xl p-3"
								:class="weeklyOvertimeExceeded ? 'bg-red-100' : 'bg-[#f7f7f5]'"
							>
								<div>
									<p class="text-sm" :class="weeklyOvertimeExceeded ? 'font-semibold text-red-700' : 'text-black'">
										{{ __("연장근로") }}
									</p>
									<p v-if="weeklyOvertimeExceeded" class="mt-0.5 text-xs font-semibold text-red-700">
										주 12h 초과 — 근기법 53조 위반 위험
									</p>
								</div>
								<div class="text-right">
									<p class="k-numeric text-sm font-bold" :class="weeklyOvertimeExceeded ? 'text-red-700' : 'text-black'">
										{{ overtimeHours }}{{ __("시간") }}
									</p>
									<p class="k-numeric text-xs text-black/40">/ {{ __("주 한도") }} 12h</p>
								</div>
							</div>
							<div class="flex items-center justify-between rounded-xl bg-[#f7f7f5] p-3">
								<p class="text-sm text-black">{{ __("야간근로") }}</p>
								<p class="k-numeric text-sm font-bold text-black">{{ nightHours }}{{ __("시간") }}</p>
							</div>
							<div class="flex items-center justify-between rounded-xl bg-[#f7f7f5] p-3">
								<p class="text-sm text-black">{{ __("휴일근로") }}</p>
								<p class="k-numeric text-sm font-bold text-black">{{ holidayHours }}{{ __("시간") }}</p>
							</div>
						</div>
					</template>
				</section>

				<!-- Card 3: 가산수당 미리보기 -->
				<section class="k-card p-4">
					<p class="k-eyebrow">PREMIUM PAY</p>
					<h2 class="mt-0.5 text-base font-bold text-black">{{ __("가산수당 미리보기 (근기법 56조)") }}</h2>

					<div class="mt-3 mb-4 flex flex-col gap-2">
						<label class="text-xs font-medium text-black/50">{{ __("통상시급 (원)") }}</label>
						<div class="flex gap-2">
							<input
								v-model.number="hourlyRateInput"
								type="number"
								min="0"
								placeholder="예: 10030"
								class="k-numeric flex-1 rounded-lg border border-[#e6e6e6] bg-white px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black/20"
								@input="onHourlyRateInput"
							/>
							<button
								class="rounded-full bg-black px-5 py-2 text-sm font-semibold text-white"
								@click="loadPremiumPreview"
							>
								{{ __("계산") }}
							</button>
						</div>
					</div>

					<div v-if="premiumLoading" class="text-sm text-black/40">{{ __("계산 중…") }}</div>

					<template v-else>
						<div class="flex flex-col gap-2">
							<div class="flex justify-between rounded-xl bg-[#f7f7f5] p-3">
								<p class="text-sm text-black">{{ __("정시급 (정시 × 시급)") }}</p>
								<p class="k-numeric text-sm font-bold text-black">{{ formatWon(premiumBasePay) }}</p>
							</div>
							<div class="flex justify-between rounded-xl bg-[#f7f7f5] p-3">
								<p class="text-sm text-black">{{ __("연장수당 (50% 가산)") }}</p>
								<p class="k-numeric text-sm font-bold text-black">{{ formatWon(premiumOvertime) }}</p>
							</div>
							<div class="flex justify-between rounded-xl bg-[#f7f7f5] p-3">
								<p class="text-sm text-black">{{ __("야간수당 (50% 추가)") }}</p>
								<p class="k-numeric text-sm font-bold text-black">{{ formatWon(premiumNight) }}</p>
							</div>
							<div class="flex justify-between rounded-xl bg-[#f7f7f5] p-3">
								<p class="text-sm text-black">{{ __("휴일수당 (50%/100%)") }}</p>
								<p class="k-numeric text-sm font-bold text-black">{{ formatWon(premiumHoliday) }}</p>
							</div>
							<div class="flex justify-between rounded-xl bg-black p-3 text-white">
								<p class="text-sm font-bold">{{ __("합계") }}</p>
								<p class="k-numeric text-base font-bold">{{ formatWon(premiumTotal) }}</p>
							</div>
						</div>
						<p class="mt-2 text-xs text-black/40">
							{{ __("* 통상시급 미입력 시 가산금액은 0원입니다. 정확한 계산을 위해 시급을 입력하세요.") }}
						</p>
					</template>
				</section>

				<!-- Card 4: 마감 상태 (관리자용) -->
				<section v-if="isAdminUser" class="k-card p-4">
					<p class="k-eyebrow">CLOSING · ADMIN</p>
					<h2 class="mt-0.5 text-base font-bold text-black">{{ __("마감 상태 (관리자)") }}</h2>
					<p class="mt-1 text-xs text-black/50">{{ __("사업장 단위 마감 진행 현황") }}</p>

					<div class="mt-3 mb-4 grid grid-cols-2 gap-2">
						<div class="rounded-xl bg-[#f7f7f5] p-3 text-center">
							<p class="k-numeric text-xl font-bold text-black">{{ closingProgress.total }}</p>
							<p class="text-xs text-black/50">{{ __("전체") }}</p>
						</div>
						<div class="rounded-xl bg-[#f7f7f5] p-3 text-center">
							<p class="k-numeric text-xl font-bold text-green-800">{{ closingProgress.completed }}</p>
							<p class="text-xs text-black/50">{{ __("마감 완료") }}</p>
						</div>
					</div>

					<div class="mb-4 rounded-xl bg-[#f7f7f5] p-3 text-sm">
						<p class="font-semibold text-black">{{ __("뮤테이션 경계") }}</p>
						<p class="mt-1 text-xs text-black/60">
							{{ __("마감 적용은 draft 저장 전용입니다. submit/cancel/approve/send는 별도 워크플로우에서 처리합니다.") }}
						</p>
						<!-- mutation_boundary: draft_only_no_submit_no_approve_no_send -->
						<p class="k-numeric mt-1 text-xs text-black/30">boundary: draft_only_no_submit_no_approve_no_send</p>
					</div>

					<div class="flex gap-2">
						<button
							class="flex-1 rounded-full border border-[#e6e6e6] bg-white py-2.5 text-sm font-semibold text-black"
							@click="loadAttendanceSummary"
						>
							{{ __("마감 미리보기") }}
						</button>
						<button
							class="flex-1 rounded-full bg-black py-2.5 text-sm font-semibold text-white"
							@click="showApplyDialog = true"
						>
							{{ __("마감 임시저장(Draft)") }}
						</button>
					</div>
				</section>

				<!-- 마감 적용 확인 다이얼로그 -->
				<div
					v-if="showApplyDialog"
					class="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4"
					@click.self="showApplyDialog = false"
				>
					<div class="w-full max-w-sm rounded-2xl bg-white p-6">
						<h3 class="text-base font-bold text-black">{{ __("마감 임시저장 확인") }}</h3>
						<p class="mt-2 text-sm text-black/60">
							{{ closingPeriodLabel }} {{ __("근태 마감을 임시저장(Draft)합니다.") }}<br />
							{{ __("이 작업은 Draft 저장이며 승인·발송은 포함하지 않습니다.") }}
						</p>
						<div class="mt-4 rounded-xl bg-red-100 p-3 text-xs font-semibold text-red-700">
							{{ __("관리자가 직접 검토·승인한 경우에만 진행하세요.") }}
						</div>
						<div class="mt-5 flex gap-3">
							<button
								class="flex-1 rounded-full border border-[#e6e6e6] bg-white py-2.5 text-sm font-semibold text-black"
								@click="showApplyDialog = false"
							>
								{{ __("취소") }}
							</button>
							<button
								class="flex-1 rounded-full bg-black py-2.5 text-sm font-bold text-white disabled:opacity-50"
								:disabled="applyLoading"
								@click="doApplyClosing"
							>
								{{ applyLoading ? __("처리 중…") : __("임시저장 확인") }}
							</button>
						</div>
						<p v-if="applyError" class="mt-3 text-xs font-semibold text-red-700">{{ applyError }}</p>
						<p v-if="applySuccess" class="mt-3 text-xs font-semibold text-green-800">{{ applySuccess }}</p>
					</div>
				</div>

			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { ref, computed, inject, onMounted } from "vue"
import BaseLayout from "@/components/BaseLayout.vue"
import { buildStackedBar } from "@/utils/koreaCharts"
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
const __ = inject("$translate")

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

// ── 출근/결근/휴가 구성 바 (이미 로드된 empSummary만 사용 — 신규 API 없음) ──
const compositionValues = computed(() => {
	const s = empSummary.value
	if (!s) return null
	const vals = [s.present_days, s.absent_days, s.leave_days].map((v) => Number(v))
	// 하나라도 숫자가 아니면 데이터 불충분 → 차트 숨김
	if (vals.some((v) => !Number.isFinite(v))) return null
	return vals
})

// buildStackedBar는 합계 0이면 null → 빈 차트 렌더 금지
const compositionBar = computed(() =>
	compositionValues.value ? buildStackedBar(compositionValues.value, 280) : null
)
// 모노크롬 구성: 출근=black, 결근=black/35, 휴가=black/15 (붉은색은 경고 전용)
const compositionOpacities = [1, 0.35, 0.15]

const weeklyOvertimeExceeded = computed(() =>
	isWeeklyOvertimeExceeded(empSummary.value?.total_overtime_hours ?? 0)
)

const dataSourceBadge = computed(() =>
	attendanceSource.value === "runtime" ? "실시간" : "정적 예시"
)
const dataSourceBadgeClass = computed(() =>
	attendanceSource.value === "runtime"
		? "bg-green-100 text-green-800"
		: "bg-black/10 text-black"
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
