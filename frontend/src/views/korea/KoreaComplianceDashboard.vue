<template>
	<BaseLayout :pageTitle="__('컴플라이언스 진단')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 — pink 색블록 -->
				<div class="k-block k-block--cream">
					<div class="k-eyebrow">COMPLIANCE</div>
					<div class="mt-1 k-t-display text-[var(--k-ink)]">{{ __('컴플라이언스 진단') }}</div>
					<p class="mt-2 k-t-body text-[var(--k-ink-muted)]">
						{{ employee.data?.company || "-" }} · {{ employee.data?.branch || "전사" }}
					</p>
				</div>

				<!-- 진단 조건 카드 -->
				<div class="k-card p-4 flex flex-col gap-3">
					<!-- 진단 기준일 선택 -->
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('진단 기준일') }}</label>
						<input
							type="date"
							v-model="asOfDate"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60"
						/>
					</div>

					<!-- 진단 버튼 (admin only) -->
					<div class="flex gap-2">
						<button
							v-if="isAdmin"
							@click="confirmRunDiagnosis"
							:disabled="complianceDiagnosis.loading"
							class="k-btn-primary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
						>
							<span v-if="complianceDiagnosis.loading">{{ __('진단 중...') }}</span>
							<span v-else>{{ __('전체 진단 실행') }}</span>
						</button>
						<button
							v-if="diagnosisResult"
							@click="refreshFromCache"
							class="k-btn-secondary"
						>
							{{ __('새로고침') }}
						</button>
					</div>

					<!-- 비관리자 안내 — 기준일만 보이는 죽은 화면 방지 -->
					<p v-if="!isAdmin" class="text-xs text-[var(--k-ink-faint)]">
						{{ __('진단 실행은 관리자(HR Manager) 권한이 필요합니다. 결과 공유는 관리자에게 요청하세요.') }}
					</p>

					<!-- 마지막 진단 정보 -->
					<div v-if="lastDiagnosisTime" class="flex flex-col gap-0.5">
						<div class="text-xs text-[var(--k-ink-faint)]">
							마지막 진단: {{ lastDiagnosisTime }}
						</div>
						<div v-if="diagnosisResult?.as_of_date" class="text-xs text-[var(--k-ink-faint)]">
							진단 기준일: {{ diagnosisResult.as_of_date }}
						</div>
					</div>
				</div>

				<!-- 종합 상태 배너 -->
				<div
					v-if="diagnosisResult"
					:class="overallBannerClass"
					class="rounded-lg border border-[var(--k-hairline)] p-4 flex items-center gap-3"
				>
					<span class="text-2xl">{{ overallStatusEmoji }}</span>
					<div class="flex flex-col gap-0.5">
						<div class="text-base font-bold tracking-tight" :class="overallStatusTextClass">
							{{ overallStatusLabel }}
						</div>
						<div class="text-xs text-[var(--k-ink-muted)]">
							<template v-if="diagnosisResult.high_severity_findings > 0">
								즉시 조치 필요 항목 {{ diagnosisResult.high_severity_findings }}건
							</template>
							<template v-else>
								모든 high severity 항목 이상 없음
							</template>
						</div>
					</div>
				</div>

				<!-- 5 카테고리 카드 -->
				<div v-if="diagnosisResult" class="flex flex-col gap-3">
					<div class="k-label px-1">{{ __('카테고리별 결과') }}</div>

					<div
						v-for="cat in categoryCards"
						:key="cat.key"
						class="k-card p-4 flex flex-col gap-2"
					>
						<div class="flex justify-between items-start">
							<div class="flex items-center gap-2">
								<span class="text-base">{{ cat.statusEmoji }}</span>
								<div class="flex flex-col">
									<span class="text-sm font-semibold text-[var(--k-ink)]">{{ cat.label }}</span>
									<span class="text-xs text-[var(--k-ink-faint)]">{{ cat.law }}</span>
								</div>
							</div>
							<span
								class="text-xs font-medium px-2 py-0.5 rounded-full"
								:class="cat.statusTextClass"
								:style="cat.badgeStyle"
							>
								{{ cat.statusText }}
							</span>
						</div>

						<!-- 발견 수 요약 -->
						<div class="text-xs text-[var(--k-ink-faint)] pl-7">
							<template v-if="cat.affectedEmployees > 0">
								{{ cat.affectedEmployees }}명 영향 / {{ cat.findingCount }}건 발견
							</template>
							<template v-else-if="cat.findingCount > 0">
								{{ cat.findingCount }}건 발견
							</template>
							<template v-else-if="cat.status === 'pass'">
								이상 없음
							</template>
							<template v-else>
								데이터 확인 필요
							</template>
						</div>

						<!-- 상세 보기 링크 -->
						<div class="pl-7 pt-1">
							<router-link
								:to="{ name: 'KoreaComplianceCategoryDetail', params: { categoryKey: cat.key }, query: { diagnosisId: currentDiagnosisId } }"
								class="text-xs text-[var(--k-ink)] font-semibold hover:underline"
							>
								상세 보기 →
							</router-link>
						</div>
					</div>
				</div>

				<!-- 결과 없음 -->
				<div
					v-if="!diagnosisResult && !complianceDiagnosis.loading"
					class="k-card p-8 flex flex-col items-center gap-3 text-center"
				>
					<span class="text-4xl">📋</span>
					<div class="text-sm text-[var(--k-ink-faint)]">{{ __('아직 진단 결과가 없습니다.') }}</div>
					<div v-if="isAdmin" class="text-xs text-[var(--k-ink-faint)]">
						위의 "전체 진단 실행" 버튼을 눌러 진단을 시작하세요.
					</div>
				</div>

				<!-- 로딩 -->
				<div v-if="complianceDiagnosis.loading" class="flex flex-col items-center py-10 gap-3">
					<div class="text-[var(--k-ink-faint)] text-sm">{{ __('진단 중입니다. 잠시 기다려 주세요...') }}</div>
				</div>

				<!-- Actions bar (admin only) -->
				<div v-if="diagnosisResult && isAdmin" class="flex flex-col gap-2">
					<!-- PDF 다운로드 -->
					<button
						@click="handlePdfDownload"
						:disabled="pdfDownloading"
						class="k-btn-secondary w-full disabled:opacity-50 disabled:cursor-not-allowed"
					>
						<span v-if="pdfDownloading">PDF 생성 중...</span>
						<span v-else>{{ __('전체 PDF 리포트 다운로드') }}</span>
					</button>

					<!-- 개선 액션 플랜 생성 -->
					<button
						@click="confirmGenerateActionPlan"
						:disabled="complianceActionPlan.loading"
						class="k-btn-secondary w-full disabled:opacity-50 disabled:cursor-not-allowed"
					>
						<span v-if="complianceActionPlan.loading">액션 플랜 생성 중...</span>
						<span v-else>{{ __('개선 액션 플랜 생성') }}</span>
					</button>
				</div>

				<!-- 액션 플랜 결과 -->
				<div v-if="actionPlanResult" class="k-card p-4 flex flex-col gap-3">
					<div class="text-sm font-bold tracking-tight text-[var(--k-ink)]">개선 액션 플랜</div>
					<div class="text-xs text-[var(--k-ink-faint)]">완료 기한: {{ actionPlanResult.deadline_date }}</div>
					<div
						v-for="(action, idx) in actionPlanResult.actions"
						:key="idx"
						class="border border-[var(--k-hairline)] rounded-lg p-3 flex flex-col gap-1"
					>
						<div class="flex items-center justify-between">
							<span class="text-xs font-semibold text-[var(--k-ink)]">{{ action.category_label }}</span>
							<span
								class="text-xs px-2 py-0.5 rounded-full font-medium"
								:class="severityClass(action.severity)"
							>
								{{ severityLabel(action.severity) }}
							</span>
						</div>
						<div class="text-xs text-[var(--k-ink-muted)]">{{ action.issue }}</div>
						<div class="text-xs text-[var(--k-ink)] font-medium mt-1">{{ action.recommended_action }}</div>
						<div class="text-xs text-[var(--k-ink-faint)] mt-1">
							담당: {{ action.assignee_role }} | 예상 {{ action.estimated_effort_hours }}h | 기한 {{ action.deadline }}
						</div>
					</div>
					<div class="text-xs text-[var(--k-ink-faint)] border-t border-[var(--k-hairline-soft)] pt-2 mt-1">
						{{ actionPlanResult.summary }}
					</div>
					<div class="text-xs text-red-600">
						* 이 플랜은 human-review 대상입니다. 실제 조치는 담당자 확인 후 진행하세요.
					</div>
				</div>

				<!-- 에러 -->
				<div
					v-if="complianceDiagnosis.error"
					class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700"
				>
					진단 중 오류가 발생했습니다: {{ complianceDiagnosis.error }}
				</div>
			</div>

			<!-- Confirm: 진단 실행 -->
			<div
				v-if="showDiagnosisConfirm"
				class="fixed inset-0 bg-[var(--k-surface-soft)]0 flex items-center justify-center z-50"
				@click.self="showDiagnosisConfirm = false"
			>
				<div class="bg-[var(--k-card)] rounded-2xl shadow-xl p-6 mx-6 flex flex-col gap-4 max-w-sm w-full">
					<div class="k-t-headline text-[var(--k-ink)]">전체 진단 실행</div>
					<div class="text-sm text-[var(--k-ink-muted)] leading-relaxed">
						회사 전체 컴플라이언스 진단을 실행합니다.<br />
						모든 직원의 근무·급여·연차 데이터를 분석합니다. 계속하시겠습니까?
					</div>
					<div class="k-eyebrow">
						read-only 진단 — 데이터 수정 없음
					</div>
					<div class="flex flex-row gap-3 mt-2">
						<button
							@click="showDiagnosisConfirm = false"
							class="k-btn-secondary flex-1"
						>
							취소
						</button>
						<button
							@click="runDiagnosis"
							class="k-btn-primary flex-1"
						>
							실행
						</button>
					</div>
				</div>
			</div>

			<!-- Confirm: 액션 플랜 생성 -->
			<div
				v-if="showActionPlanConfirm"
				class="fixed inset-0 bg-[var(--k-surface-soft)]0 flex items-center justify-center z-50"
				@click.self="showActionPlanConfirm = false"
			>
				<div class="bg-[var(--k-card)] rounded-2xl shadow-xl p-6 mx-6 flex flex-col gap-4 max-w-sm w-full">
					<div class="k-t-headline text-[var(--k-ink)]">개선 액션 플랜 생성</div>
					<div class="text-sm text-[var(--k-ink-muted)] leading-relaxed">
						현재 진단 결과를 기반으로 개선 액션 플랜을 생성합니다.<br />
						생성된 플랜은 human-review 대상이며 즉시 실행되지 않습니다.
					</div>
					<div class="flex flex-row gap-3 mt-2">
						<button
							@click="showActionPlanConfirm = false"
							class="k-btn-secondary flex-1"
						>
							취소
						</button>
						<button
							@click="generateActionPlan"
							class="k-btn-primary flex-1"
						>
							생성
						</button>
					</div>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { ref, computed, inject, onMounted } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import { useIsAdmin } from "@/composables/useIsAdmin"
import {
	complianceDiagnosis,
	complianceActionPlan,
	buildCategoryCards,
	downloadCompliancePdf,
	OVERALL_STATUS_CONFIG,
} from "@/data/koreaComplianceRuntime"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")

// ---------------------------------------------------------------------------
// 상태
// ---------------------------------------------------------------------------
const diagnosisResult = ref(null)
const actionPlanResult = ref(null)
const lastDiagnosisTime = ref(null)
const currentDiagnosisId = ref(null)

const asOfDate = ref(new Date().toISOString().slice(0, 10))
const isAdmin = useIsAdmin() // HR Manager/System Manager 롤 기준

const showDiagnosisConfirm = ref(false)
const showActionPlanConfirm = ref(false)
const pdfDownloading = ref(false)

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const overallStatus = computed(
	() => diagnosisResult.value?.overall_status ?? null
)

const overallConfig = computed(
	() => OVERALL_STATUS_CONFIG[overallStatus.value] ?? OVERALL_STATUS_CONFIG.needs_attention
)

const overallStatusEmoji = computed(() => overallConfig.value?.emoji ?? "⬜")
const overallStatusLabel = computed(() => overallConfig.value?.text ?? "-")
const overallStatusTextClass = computed(() => overallConfig.value?.textClass ?? "text-[var(--k-ink)]")

const overallBannerClass = computed(() => {
	const map = {
		good: "bg-green-50",
		needs_attention: "bg-yellow-50",
		high_risk: "bg-red-50",
	}
	return map[overallStatus.value] ?? "bg-[var(--k-surface-soft)]"
})

const categoryCards = computed(() => buildCategoryCards(diagnosisResult.value?.diagnoses))

// ---------------------------------------------------------------------------
// 메서드
// ---------------------------------------------------------------------------
function confirmRunDiagnosis() {
	showDiagnosisConfirm.value = true
}

async function runDiagnosis() {
	showDiagnosisConfirm.value = false
	diagnosisResult.value = null
	actionPlanResult.value = null

	await complianceDiagnosis.submit({
		company: employee.data?.company,
		workplace: employee.data?.branch ?? null,
		as_of_date: asOfDate.value,
	})

	if (!complianceDiagnosis.error && complianceDiagnosis.data) {
		diagnosisResult.value = complianceDiagnosis.data
		lastDiagnosisTime.value = dayjs().format("YYYY-MM-DD HH:mm")
		currentDiagnosisId.value = `diag-${Date.now()}`
		// 세션 스토리지에 저장 (페이지 이동 후 복원용)
		try {
			sessionStorage.setItem(
				"koreaComplianceDiagnosis",
				JSON.stringify({
					result: complianceDiagnosis.data,
					timestamp: lastDiagnosisTime.value,
					id: currentDiagnosisId.value,
				})
			)
		} catch (_) {
			// ignore storage errors
		}
	}
}

function refreshFromCache() {
	try {
		const cached = sessionStorage.getItem("koreaComplianceDiagnosis")
		if (cached) {
			const parsed = JSON.parse(cached)
			diagnosisResult.value = parsed.result
			lastDiagnosisTime.value = parsed.timestamp
			currentDiagnosisId.value = parsed.id
		}
	} catch (_) {
		// ignore
	}
}

async function handlePdfDownload() {
	if (!diagnosisResult.value) return
	pdfDownloading.value = true
	try {
		await downloadCompliancePdf(
			employee.data?.company,
			employee.data?.branch ?? "",
			asOfDate.value
		)
	} catch (err) {
		alert("PDF 다운로드 오류: " + err.message)
	} finally {
		pdfDownloading.value = false
	}
}

function confirmGenerateActionPlan() {
	showActionPlanConfirm.value = true
}

async function generateActionPlan() {
	showActionPlanConfirm.value = false
	if (!diagnosisResult.value) return

	await complianceActionPlan.submit({
		company: employee.data?.company,
		workplace: employee.data?.branch ?? null,
		as_of_date: asOfDate.value,
		deadline_days: 30,
	})

	if (!complianceActionPlan.error && complianceActionPlan.data) {
		actionPlanResult.value = complianceActionPlan.data
	}
}

function severityClass(severity) {
	return {
		high: "text-red-700 bg-red-50",
		medium: "text-yellow-700 bg-yellow-50",
		low: "text-green-700 bg-green-50",
	}[severity] ?? "text-[var(--k-ink)] bg-[var(--k-surface-soft)]"
}

function severityLabel(severity) {
	return { high: "즉시 조치", medium: "14일 내", low: "30일 내" }[severity] ?? severity
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
onMounted(() => {
	// 세션 캐시에서 복원
	refreshFromCache()
})
</script>
