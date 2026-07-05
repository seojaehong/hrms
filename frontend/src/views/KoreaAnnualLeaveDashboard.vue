<template>
	<BaseLayout :pageTitle="`한국 연차 현황${display ? ' — ' + display.employeeName : ''}`">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-gray-50 p-4 pb-24">

				<!-- Loading -->
				<section v-if="loading" class="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm text-center">
					<p class="text-sm text-gray-500">연차 현황 불러오는 중…</p>
				</section>

				<!-- Error + fixture fallback notice -->
				<section v-if="previewError" class="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
					<p class="font-semibold">런타임 읽기 실패 — 정적 픽스처 사용 중</p>
					<p class="mt-1">{{ previewError }}</p>
				</section>

				<!-- Employee not specified -->
				<section v-if="!employeeId && !loading" class="rounded-2xl border border-red-100 bg-red-50 p-4 text-red-800">
					<p class="font-semibold">직원 ID가 필요합니다</p>
					<p class="mt-1 text-sm">URL 파라미터 또는 쿼리 파라미터로 직원 ID를 제공하세요.</p>
				</section>

				<!-- Card 1: 기본 정보 -->
				<section v-if="display" class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
					<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">기본 정보</p>
					<div class="mt-3 grid grid-cols-2 gap-3">
						<div class="rounded-xl bg-gray-50 p-3">
							<p class="text-xs text-gray-500">입사일</p>
							<p class="mt-1 text-sm font-semibold text-gray-900">{{ display.dateOfJoining }}</p>
						</div>
						<div class="rounded-xl bg-gray-50 p-3">
							<p class="text-xs text-gray-500">근속</p>
							<p class="mt-1 text-sm font-semibold text-gray-900">{{ tenureLabel }}</p>
						</div>
						<div class="rounded-xl bg-gray-50 p-3">
							<p class="text-xs text-gray-500">기준</p>
							<p class="mt-1 text-sm font-semibold text-gray-900">{{ display.basis === 'Hire Date' ? '입사일 기준' : '회계연도 기준' }}</p>
						</div>
						<div class="rounded-xl bg-gray-50 p-3">
							<p class="text-xs text-gray-500">계산 기준일</p>
							<p class="mt-1 text-sm font-semibold text-gray-900">{{ display.asOfDate }}</p>
						</div>
					</div>
				</section>

				<!-- Card 2: 부여 현황 -->
				<section v-if="display" class="rounded-2xl border border-blue-100 bg-white p-4 shadow-sm">
					<p class="text-xs font-semibold uppercase tracking-wide text-blue-700">부여 현황</p>
					<div class="mt-3 flex flex-col gap-2">
						<div v-if="display.serviceYears < 1 && display.monthlyAccrual > 0" class="flex items-center justify-between rounded-xl bg-gray-50 p-3">
							<span class="text-sm text-gray-700">월차 <span class="text-xs text-gray-400">(1년 미만 월 단위)</span></span>
							<span class="font-bold text-gray-900">{{ display.monthlyAccrual }}일</span>
						</div>
						<div v-if="display.serviceYears >= 1 || display.annualEntitlement > 0" class="flex items-center justify-between rounded-xl bg-gray-50 p-3">
							<span class="text-sm text-gray-700">연차 <span class="text-xs text-gray-400">(1년 이상)</span></span>
							<span class="font-bold text-gray-900">{{ display.annualEntitlement }}일</span>
						</div>
						<div v-if="display.serviceYears >= 3" class="flex items-center justify-between rounded-xl bg-green-50 p-3">
							<span class="text-sm text-green-800">장기근속 가산 포함 <span class="text-xs text-green-600">(3년 이상, 2년마다 +1일 최대 25일)</span></span>
							<span class="font-bold text-green-900">합산 반영</span>
						</div>
						<div class="flex items-center justify-between rounded-xl bg-blue-50 p-3">
							<span class="text-sm font-semibold text-blue-800">총 부여</span>
							<span class="text-lg font-bold text-blue-900">{{ display.totalEntitlement }}일</span>
						</div>
					</div>
					<div class="mt-3 text-xs text-gray-400">
						적용 기간: {{ display.fromDate }} ~ {{ display.toDate }}
					</div>
				</section>

				<!-- Card 3: 80% 출근률 룰 (해당 시) -->
				<section v-if="display && display.ratioApplied" class="rounded-2xl border p-4 shadow-sm"
					:class="display.isBelowThreshold ? 'border-red-200 bg-red-50' : 'border-green-200 bg-green-50'">
					<p class="text-xs font-semibold uppercase tracking-wide" :class="display.isBelowThreshold ? 'text-red-700' : 'text-green-700'">
						출근률 80% 룰 (근기법 60조 4항)
					</p>
					<div class="mt-3 grid grid-cols-2 gap-2">
						<div class="rounded-xl bg-white p-3">
							<p class="text-xs text-gray-500">출근률</p>
							<p class="mt-1 font-bold" :class="display.isBelowThreshold ? 'text-red-700' : 'text-green-700'">
								{{ display.attendanceRatio !== null ? (display.attendanceRatio * 100).toFixed(1) + '%' : '—' }}
							</p>
						</div>
						<div class="rounded-xl bg-white p-3">
							<p class="text-xs text-gray-500">임계값</p>
							<p class="mt-1 font-bold text-gray-700">{{ (display.threshold * 100).toFixed(0) }}%</p>
						</div>
					</div>
					<div v-if="display.isBelowThreshold" class="mt-3 rounded-xl bg-red-100 p-3 text-sm text-red-900">
						<p class="font-semibold">⚠ 감액 적용 — 연차 0일, 월차만 부여</p>
						<p class="mt-1 text-xs text-red-700">출근률 {{ (display.threshold * 100).toFixed(0) }}% 미만 시 연차 전환 불가 (근기법 60조 4항)</p>
					</div>
					<div v-else class="mt-3 rounded-xl bg-green-100 p-3 text-sm text-green-900">
						<p class="font-semibold">출근률 요건 충족 — 연차 정상 부여</p>
					</div>
				</section>

				<!-- Card 4: 사용 / 잔여 -->
				<section v-if="display" class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
					<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">사용 / 잔여</p>
					<div class="mt-3 grid grid-cols-2 gap-3">
						<div class="rounded-xl bg-gray-50 p-3 text-center">
							<p class="text-xs text-gray-500">사용</p>
							<p class="mt-1 text-2xl font-bold text-gray-800">{{ display.usedDays }}</p>
							<p class="text-xs text-gray-400">일</p>
						</div>
						<div class="rounded-xl p-3 text-center" :class="display.remainingDays <= 0 ? 'bg-red-50' : 'bg-green-50'">
							<p class="text-xs" :class="display.remainingDays <= 0 ? 'text-red-500' : 'text-green-600'">잔여</p>
							<p class="mt-1 text-2xl font-bold" :class="display.remainingDays <= 0 ? 'text-red-700' : 'text-green-700'">
								{{ display.remainingDays }}
							</p>
							<p class="text-xs" :class="display.remainingDays <= 0 ? 'text-red-400' : 'text-green-400'">일</p>
						</div>
					</div>
					<!-- Progress bar -->
					<div class="mt-4">
						<div class="flex items-center justify-between text-xs text-gray-500 mb-1">
							<span>사용률</span>
							<span>{{ usagePercent }}%</span>
						</div>
						<div class="h-2 rounded-full bg-gray-200 overflow-hidden">
							<div
								class="h-full rounded-full transition-all duration-300"
								:class="usagePercent >= 100 ? 'bg-red-500' : usagePercent >= 80 ? 'bg-amber-400' : 'bg-green-500'"
								:style="{ width: Math.min(usagePercent, 100) + '%' }"
							></div>
						</div>
						<p class="mt-1 text-xs text-gray-400">총 {{ display.allocatedDays }}일 중 {{ display.usedDays }}일 사용</p>
					</div>
				</section>

				<!-- Preview boundary notice -->
				<section class="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
					<p class="font-semibold">Preview boundary</p>
					<p class="mt-1">
						이 화면은 연차 현황을 조회만 합니다 (runtime_action=preview_only). 연차 신청·부여 적용은 관리자가 [신청 적용] 버튼을 통해 별도 승인해야 합니다.
						AI는 assistant_only · human approval required.
					</p>
				</section>

				<!-- Action buttons (admin role only) -->
				<section v-if="isAdmin && display" class="flex flex-col gap-3">
					<button
						type="button"
						class="w-full rounded-2xl border border-blue-200 bg-blue-50 py-3 text-sm font-semibold text-blue-800"
						@click="handlePreviewRefresh"
						:disabled="loading"
					>
						미리보기 새로고침
					</button>
					<button
						type="button"
						class="w-full rounded-2xl bg-gray-900 py-3 text-sm font-semibold text-white disabled:opacity-50"
						@click="handleApply"
						:disabled="loading || applying || !display.requiresRuntimeApply"
					>
						{{ applying ? '신청 적용 중…' : '신청 적용 (관리자 승인 필요)' }}
					</button>
					<div v-if="applyError" class="rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
						<p class="font-semibold">신청 적용 실패</p>
						<p class="mt-1">{{ applyError }}</p>
					</div>
					<div v-if="applyResult" class="rounded-2xl border border-green-200 bg-green-50 p-3 text-sm text-green-900">
						<p class="font-semibold">신청 완료</p>
						<p class="mt-1">Leave Allocation: {{ applyResult.data?.leave_allocation_name }}</p>
					</div>
				</section>

				<!-- Data source badge -->
				<section class="rounded-2xl bg-gray-900 p-4 text-white text-sm shadow-sm">
					<div class="flex items-start justify-between gap-3">
						<div>
							<p class="text-xs font-semibold uppercase tracking-[0.2em] text-gray-300">{{ dataSourceLabel }}</p>
							<p class="mt-1 text-base font-bold">
								{{ display ? display.employeeName || display.employee : '직원 미선택' }}
							</p>
							<p class="mt-1 text-xs text-gray-400">
								runtime_action=preview_only · requires_runtime_apply={{ display ? display.requiresRuntimeApply : '—' }} · human approval required · AI=assistant_only
							</p>
						</div>
						<span class="rounded-full px-3 py-1 text-xs font-semibold" :class="dataSourceBadgeClass">{{ dataSourceBadge }}</span>
					</div>
					<div v-if="loading" class="mt-3 rounded-xl bg-white/10 p-2 text-xs text-gray-300">
						Loading read-only Frappe runtime data…
					</div>
					<div v-else-if="previewError" class="mt-3 rounded-xl bg-amber-400/20 p-2 text-xs text-amber-200">
						실데이터 조회에 실패해 정적 예시 데이터로 표시 중입니다. {{ previewError }}
					</div>
				</section>

			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
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
	return typeof id === "string" && id.trim() ? id.trim() : ""
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
	if (loading.value) return "Loading…"
	if (hasKoreaAnnualLeavePreviewData(previewData.value)) return "Runtime read-only preview"
	return "정적 예시 데이터 미리보기"
})

const dataSourceBadge = computed(() => {
	if (loading.value) return "loading"
	if (hasKoreaAnnualLeavePreviewData(previewData.value)) return "runtime_read_only"
	return "정적 예시"
})

const dataSourceBadgeClass = computed(() => {
	if (loading.value) return "bg-white/20 text-white"
	if (hasKoreaAnnualLeavePreviewData(previewData.value)) return "bg-green-100 text-green-800"
	return "bg-amber-100 text-amber-900"
})

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
onMounted(loadPreviewData)

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
	// Fallback: return minimal shape if date_of_joining is not available
	// The caller should prefetch employee data via frappe.db.get_value in production
	return null
}

function todayIso() {
	return new Date().toISOString().slice(0, 10)
}
</script>
