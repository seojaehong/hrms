<template>
	<BaseLayout :pageTitle="`연차 현황${display ? ' — ' + display.employeeName : ''}`">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-white p-4 pb-24">

				<!-- 히어로 — 연차(lilac) 색블록 + 핵심 스탯 -->
				<section class="k-block k-block--lilac">
					<div class="flex items-start justify-between gap-3">
						<div>
							<p class="k-eyebrow">ANNUAL LEAVE</p>
							<h1 class="mt-1 text-2xl font-bold tracking-tight text-black">{{ __("연차 현황") }}</h1>
							<p class="mt-1 text-sm font-medium text-black/60">
								{{ display ? display.employeeName || display.employee : __("직원 미선택") }}
							</p>
						</div>
						<span class="rounded-full px-3 py-1 text-xs font-semibold" :class="dataSourceBadgeClass">{{ dataSourceBadge }}</span>
					</div>
					<div v-if="display" class="mt-4 grid grid-cols-3 gap-2">
						<div class="rounded-xl bg-white/60 p-3 text-center">
							<p class="k-numeric text-2xl font-bold text-black">{{ display.totalEntitlement }}</p>
							<p class="mt-0.5 text-xs font-medium text-black/60">{{ __("총 부여(일)") }}</p>
						</div>
						<div class="rounded-xl bg-white/60 p-3 text-center">
							<p class="k-numeric text-2xl font-bold text-black">{{ display.usedDays }}</p>
							<p class="mt-0.5 text-xs font-medium text-black/60">{{ __("사용(일)") }}</p>
						</div>
						<div class="rounded-xl bg-white/60 p-3 text-center">
							<p class="k-numeric text-2xl font-bold" :class="display.remainingDays <= 0 ? 'text-red-700' : 'text-black'">{{ display.remainingDays }}</p>
							<p class="mt-0.5 text-xs font-medium text-black/60">{{ __("잔여(일)") }}</p>
						</div>
					</div>
				</section>

				<!-- 로딩 -->
				<section v-if="loading" class="k-card p-6 text-center">
					<p class="text-sm font-medium text-black/50">{{ __("연차 현황을 불러오는 중…") }}</p>
				</section>

				<!-- 실데이터 조회 실패 안내 -->
				<section v-if="previewError" class="k-card p-4 text-sm">
					<div class="flex items-center gap-2">
						<span class="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-700">{{ __("예시 데이터") }}</span>
						<p class="font-semibold text-black">{{ __("실데이터 조회 실패 — 정적 예시로 표시 중") }}</p>
					</div>
					<p class="mt-2 text-black/60">{{ previewError }}</p>
				</section>

				<!-- 직원 미지정 (로그인 직원 폴백도 불가한 경우) -->
				<section v-if="!employeeId && !loading" class="k-card p-6 text-center">
					<p class="text-base font-bold text-black">{{ __("연차 정보를 불러올 수 없습니다") }}</p>
					<p class="mt-1 text-sm text-black/60">{{ __("담당자에게 문의하세요.") }}</p>
					<router-link
						:to="{ name: 'Home' }"
						class="mt-4 inline-flex justify-center rounded-full bg-black px-6 py-2.5 text-sm font-semibold text-white"
					>
						{{ __("홈으로 가기") }}
					</router-link>
				</section>

				<!-- 기본 정보 -->
				<section v-if="display" class="k-card p-4">
					<p class="k-eyebrow">PROFILE</p>
					<p class="mt-0.5 text-base font-bold text-black">{{ __("기본 정보") }}</p>
					<div class="mt-3 grid grid-cols-2 gap-2">
						<div class="rounded-xl bg-[#f7f7f5] p-3">
							<p class="text-xs text-black/50">{{ __("입사일") }}</p>
							<p class="k-numeric mt-1 text-sm font-semibold text-black">{{ display.dateOfJoining }}</p>
						</div>
						<div class="rounded-xl bg-[#f7f7f5] p-3">
							<p class="text-xs text-black/50">{{ __("근속") }}</p>
							<p class="mt-1 text-sm font-semibold text-black">{{ tenureLabel }}</p>
						</div>
						<div class="rounded-xl bg-[#f7f7f5] p-3">
							<p class="text-xs text-black/50">{{ __("산정 기준") }}</p>
							<p class="mt-1 text-sm font-semibold text-black">{{ display.basis === 'Hire Date' ? __('입사일 기준') : __('회계연도 기준') }}</p>
						</div>
						<div class="rounded-xl bg-[#f7f7f5] p-3">
							<p class="text-xs text-black/50">{{ __("계산 기준일") }}</p>
							<p class="k-numeric mt-1 text-sm font-semibold text-black">{{ display.asOfDate }}</p>
						</div>
					</div>
				</section>

				<!-- 부여 현황 -->
				<section v-if="display" class="k-card p-4">
					<p class="k-eyebrow">ENTITLEMENT</p>
					<p class="mt-0.5 text-base font-bold text-black">{{ __("부여 현황") }}</p>
					<div class="mt-3 flex flex-col gap-2">
						<div v-if="display.serviceYears < 1 && display.monthlyAccrual > 0" class="flex items-center justify-between rounded-xl bg-[#f7f7f5] p-3">
							<span class="text-sm text-black">{{ __("월차") }} <span class="text-xs text-black/40">{{ __("(1년 미만 월 단위)") }}</span></span>
							<span class="k-numeric font-bold text-black">{{ display.monthlyAccrual }}{{ __("일") }}</span>
						</div>
						<div v-if="display.serviceYears >= 1 || display.annualEntitlement > 0" class="flex items-center justify-between rounded-xl bg-[#f7f7f5] p-3">
							<span class="text-sm text-black">{{ __("연차") }} <span class="text-xs text-black/40">{{ __("(1년 이상)") }}</span></span>
							<span class="k-numeric font-bold text-black">{{ display.annualEntitlement }}{{ __("일") }}</span>
						</div>
						<div v-if="display.serviceYears >= 3" class="flex items-center justify-between rounded-xl bg-[#f7f7f5] p-3">
							<span class="text-sm text-black">{{ __("장기근속 가산 포함") }} <span class="text-xs text-black/40">{{ __("(3년 이상, 2년마다 +1일 · 최대 25일)") }}</span></span>
							<span class="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-semibold text-green-800">{{ __("합산 반영") }}</span>
						</div>
						<div class="flex items-center justify-between rounded-xl bg-black p-3 text-white">
							<span class="text-sm font-semibold">{{ __("총 부여") }}</span>
							<span class="k-numeric text-lg font-bold">{{ display.totalEntitlement }}{{ __("일") }}</span>
						</div>
					</div>
					<div class="k-numeric mt-3 text-xs text-black/40">
						{{ __("적용 기간") }}: {{ display.fromDate }} ~ {{ display.toDate }}
					</div>
				</section>

				<!-- 80% 출근률 룰 (해당 시) -->
				<section v-if="display && display.ratioApplied" class="k-card p-4">
					<div class="flex items-center justify-between gap-2">
						<div>
							<p class="k-eyebrow">ATTENDANCE RULE</p>
							<p class="mt-0.5 text-base font-bold text-black">{{ __("출근률 80% 룰 (근기법 60조 4항)") }}</p>
						</div>
						<span
							class="rounded-full px-2.5 py-0.5 text-xs font-semibold"
							:class="display.isBelowThreshold ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-800'"
						>
							{{ display.isBelowThreshold ? __('미달') : __('충족') }}
						</span>
					</div>
					<div class="mt-3 grid grid-cols-2 gap-2">
						<div class="rounded-xl bg-[#f7f7f5] p-3">
							<p class="text-xs text-black/50">{{ __("출근률") }}</p>
							<p class="k-numeric mt-1 text-lg font-bold" :class="display.isBelowThreshold ? 'text-red-700' : 'text-black'">
								{{ display.attendanceRatio !== null ? (display.attendanceRatio * 100).toFixed(1) + '%' : '—' }}
							</p>
						</div>
						<div class="rounded-xl bg-[#f7f7f5] p-3">
							<p class="text-xs text-black/50">{{ __("기준선") }}</p>
							<p class="k-numeric mt-1 text-lg font-bold text-black">{{ (display.threshold * 100).toFixed(0) }}%</p>
						</div>
					</div>
					<div v-if="display.isBelowThreshold" class="mt-3 rounded-xl bg-red-100 p-3 text-sm text-red-700">
						<p class="font-semibold">{{ __("감액 적용 — 연차 0일, 월차만 부여") }}</p>
						<p class="mt-1 text-xs">{{ __("출근률") }} {{ (display.threshold * 100).toFixed(0) }}% {{ __("미만이면 연차 전환이 불가합니다 (근기법 60조 4항).") }}</p>
					</div>
					<div v-else class="mt-3 rounded-xl bg-green-100 p-3 text-sm font-semibold text-green-800">
						{{ __("출근률 요건 충족 — 연차 정상 부여") }}
					</div>
				</section>

				<!-- 사용 / 잔여 -->
				<section v-if="display" class="k-card p-4">
					<p class="k-eyebrow">USAGE</p>
					<p class="mt-0.5 text-base font-bold text-black">{{ __("사용 / 잔여") }}</p>
					<div class="mt-3 grid grid-cols-2 gap-2">
						<div class="rounded-xl bg-[#f7f7f5] p-3 text-center">
							<p class="text-xs text-black/50">{{ __("사용") }}</p>
							<p class="k-numeric mt-1 text-2xl font-bold text-black">{{ display.usedDays }}</p>
							<p class="text-xs text-black/40">{{ __("일") }}</p>
						</div>
						<div class="rounded-xl bg-[#f7f7f5] p-3 text-center">
							<p class="text-xs" :class="display.remainingDays <= 0 ? 'text-red-700' : 'text-black/50'">{{ __("잔여") }}</p>
							<p class="k-numeric mt-1 text-2xl font-bold" :class="display.remainingDays <= 0 ? 'text-red-700' : 'text-black'">
								{{ display.remainingDays }}
							</p>
							<p class="text-xs" :class="display.remainingDays <= 0 ? 'text-red-700' : 'text-black/40'">{{ __("일") }}</p>
						</div>
					</div>
					<!-- 사용률 바 -->
					<div class="mt-4">
						<div class="mb-1 flex items-center justify-between text-xs text-black/50">
							<span>{{ __("사용률") }}</span>
							<span class="k-numeric">{{ usagePercent }}%</span>
						</div>
						<div class="h-2 overflow-hidden rounded-full bg-[#f1f1f1]">
							<div
								class="h-full rounded-full transition-all duration-300"
								:class="usagePercent >= 100 ? 'bg-red-600' : 'bg-black'"
								:style="{ width: Math.min(usagePercent, 100) + '%' }"
							></div>
						</div>
						<p class="mt-1 text-xs text-black/40">{{ __("총") }} {{ display.allocatedDays }}{{ __("일 중") }} {{ display.usedDays }}{{ __("일 사용") }}</p>
					</div>
				</section>

				<!-- 조회 전용 안내 -->
				<section class="k-card p-4 text-sm">
					<p class="k-eyebrow">READ-ONLY</p>
					<p class="mt-1 font-semibold text-black">{{ __("조회 전용 화면") }}</p>
					<p class="mt-1 text-black/60">
						{{ __("이 화면은 연차 현황을 조회만 합니다. 연차 부여 적용은 관리자가 [신청 적용] 버튼으로 별도 승인하며, AI는 보조 역할만 합니다.") }}
					</p>
				</section>

				<!-- 관리자 액션 -->
				<section v-if="isAdmin && display" class="flex flex-col gap-3">
					<button
						type="button"
						class="w-full rounded-full border border-[#e6e6e6] bg-white py-3 text-sm font-semibold text-black"
						@click="handlePreviewRefresh"
						:disabled="loading"
					>
						{{ __("미리보기 새로고침") }}
					</button>
					<button
						type="button"
						class="w-full rounded-full bg-black py-3 text-sm font-semibold text-white disabled:opacity-50"
						@click="handleApply"
						:disabled="loading || applying || !display.requiresRuntimeApply"
					>
						{{ applying ? __('신청 적용 중…') : __('신청 적용 (관리자 승인 필요)') }}
					</button>
					<div v-if="applyError" class="k-card p-3 text-sm">
						<p class="font-semibold text-red-700">{{ __("신청 적용 실패") }}</p>
						<p class="mt-1 text-black/60">{{ applyError }}</p>
					</div>
					<div v-if="applyResult" class="k-card p-3 text-sm">
						<p class="font-semibold text-green-800">{{ __("신청 완료") }}</p>
						<p class="k-numeric mt-1 text-black/60">Leave Allocation: {{ applyResult.data?.leave_allocation_name }}</p>
					</div>
				</section>

				<!-- 데이터 소스 -->
				<section class="k-card p-4 text-sm">
					<div class="flex items-start justify-between gap-3">
						<div>
							<p class="k-eyebrow">{{ dataSourceLabel }}</p>
							<p class="mt-1 text-base font-bold text-black">
								{{ display ? display.employeeName || display.employee : __('직원 미선택') }}
							</p>
							<p class="mt-1 text-xs text-black/40">
								조회 전용 · 변경 없음 · 적용은 관리자 승인으로만 진행됩니다
							</p>
						</div>
						<span class="rounded-full px-3 py-1 text-xs font-semibold" :class="dataSourceBadgeClass">{{ dataSourceBadge }}</span>
					</div>
					<div v-if="loading" class="mt-3 rounded-xl bg-[#f7f7f5] p-2 text-xs text-black/50">
						{{ __("읽기 전용 실데이터를 불러오는 중…") }}
					</div>
					<div v-else-if="previewError" class="mt-3 rounded-xl bg-[#f7f7f5] p-2 text-xs text-black/60">
						{{ __("실데이터 조회에 실패해 정적 예시 데이터로 표시 중입니다.") }} {{ previewError }}
					</div>
				</section>

			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import BaseLayout from "@/components/BaseLayout.vue"
import { koreaAnnualLeaveFixture, buildKoreaAnnualLeaveFixtureForEmployee } from "@/data/koreaAnnualLeaveFixture"
import {
	fetchKoreaAnnualLeavePreview,
	fetchKoreaAnnualLeaveWithRatio,
	applyKoreaLeaveAllocation,
	buildKoreaAnnualLeaveDisplayData,
	hasKoreaAnnualLeavePreviewData,
} from "@/data/koreaAnnualLeaveRuntime"

const route = useRoute()
const __ = inject("$translate")
// 로그인 사용자의 직원 리소스 (App 전역 provide) — 라우트에 직원 지정이 없을 때 폴백
const employeeResource = inject("$employee", null)

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const previewData = ref(null)
const ratioData = ref(null)
const loading = ref(false)
const applying = ref(false)
const previewError = ref("")
const applyError = ref("")
const applyResult = ref(null)
const humanApproved = ref(false)

// ---------------------------------------------------------------------------
// Derived state
// ---------------------------------------------------------------------------
const employeeId = computed(() => {
	const id = route.params.employeeId || route.query.employee
	if (typeof id === "string" && id.trim()) return id.trim()
	// 폴백: 로그인 사용자의 직원 ID (기존 $employee 리소스 재사용 — 추가 API 호출 없음)
	const ownId = employeeResource?.data?.name
	return typeof ownId === "string" && ownId.trim() ? ownId.trim() : ""
})

const isAdmin = computed(() => {
	// Check frappe session for System Manager / HR Manager role
	const roles = globalThis.window?.frappe?.boot?.user?.roles || []
	return roles.includes("System Manager") || roles.includes("HR Manager")
})

const display = computed(() => {
	if (hasKoreaAnnualLeavePreviewData(previewData.value)) {
		return buildKoreaAnnualLeaveDisplayData({
			previewData: previewData.value,
			ratioData: ratioData.value,
		})
	}
	// fixture fallback
	return buildKoreaAnnualLeaveDisplayData({
		previewData: buildKoreaAnnualLeaveFixtureForEmployee(employeeId.value),
		ratioData: null,
	})
})

const tenureLabel = computed(() => {
	if (!display.value) return "—"
	const y = display.value.serviceYears
	const months = display.value.serviceMonths % 12
	if (y <= 0 && months <= 0) return "1개월 미만"
	const parts = []
	if (y > 0) parts.push(`${y}년`)
	if (months > 0) parts.push(`${months}개월`)
	return parts.join(" ")
})

// Note: longServiceBonus is already folded into annualEntitlement by the backend
// (anniversary_annual_entitlement includes the every-2-years +1 day, capped at 25).
// We do not re-compute it client-side to avoid double-counting.

const usagePercent = computed(() => {
	if (!display.value || display.value.allocatedDays <= 0) return 0
	return Math.round((display.value.usedDays / display.value.allocatedDays) * 100)
})

const dataSourceLabel = computed(() => {
	if (loading.value) return "LOADING"
	if (hasKoreaAnnualLeavePreviewData(previewData.value)) return "RUNTIME READ-ONLY"
	return "STATIC PREVIEW"
})

const dataSourceBadge = computed(() => {
	if (loading.value) return __("불러오는 중")
	if (hasKoreaAnnualLeavePreviewData(previewData.value)) return __("실시간")
	return __("정적 예시")
})

const dataSourceBadgeClass = computed(() => {
	if (loading.value) return "bg-black/10 text-black"
	if (hasKoreaAnnualLeavePreviewData(previewData.value)) return "bg-green-100 text-green-800"
	return "bg-black/10 text-black"
})

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
onMounted(async () => {
	// $employee 리소스 로딩 대기 (경쟁 조건 방지) 후 조회
	try { await employeeResource?.promise } catch { /* 미로그인 등 — 픽스처 폴백 */ }
	await loadPreviewData()
})

async function loadPreviewData() {
	if (!employeeId.value) return
	loading.value = true
	previewError.value = ""
	try {
		const employee = resolveEmployeeFromFrappe(employeeId.value)
		if (!employee) {
			previewError.value = "직원 정보를 frappe session에서 찾을 수 없어 픽스처를 사용합니다."
			return
		}
		const result = await fetchKoreaAnnualLeavePreview({
			employee,
			asOfDate: todayIso(),
		})
		previewData.value = result.data
	} catch (err) {
		previewError.value = err instanceof Error ? err.message : String(err)
		previewData.value = null
	} finally {
		loading.value = false
	}
}

async function handlePreviewRefresh() {
	await loadPreviewData()
}

async function handleApply() {
	if (!display.value) return
	applyError.value = ""
	applyResult.value = null

	// Require explicit human confirmation
	const confirmed = globalThis.window?.confirm?.(
		`[관리자 확인] ${display.value.employeeName || display.value.employee} 의 연차 ${display.value.allocatedDays}일을 부여합니다. 이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?`
	)
	if (!confirmed) return

	humanApproved.value = true
	applying.value = true
	try {
		const draft = previewData.value?.draft
		if (!draft) throw new Error("부여할 draft payload가 없습니다. 미리보기를 먼저 실행하세요.")

		const result = await applyKoreaLeaveAllocation({
			draft,
			humanApproved: true,
			actor: globalThis.window?.frappe?.session?.user || "Administrator",
		})
		applyResult.value = result
	} catch (err) {
		applyError.value = err instanceof Error ? err.message : String(err)
	} finally {
		applying.value = false
		humanApproved.value = false
	}
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function resolveEmployeeFromFrappe(employeeId) {
	// In Frappe PWA context, employee data may be in frappe.boot
	const bootEmployee = globalThis.window?.frappe?.boot?.employee
	if (bootEmployee && bootEmployee.name === employeeId) {
		return {
			name: bootEmployee.name,
			date_of_joining: bootEmployee.date_of_joining,
			employee_name: bootEmployee.employee_name,
			company: bootEmployee.company,
		}
	}
	// 폴백: 전역 $employee 리소스 (로그인 직원 본인)
	const own = employeeResource?.data
	if (own && own.name === employeeId && own.date_of_joining) {
		return {
			name: own.name,
			date_of_joining: own.date_of_joining,
			employee_name: own.employee_name,
			company: own.company,
		}
	}
	return null
}

function todayIso() {
	return new Date().toISOString().slice(0, 10)
}
</script>
