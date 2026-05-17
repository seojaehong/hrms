<template>
	<BaseLayout :pageTitle="__('컴플라이언스 진단')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 헤더 정보 -->
				<div class="bg-white rounded shadow-sm p-4 flex flex-col gap-2">
					<div class="text-base font-bold text-gray-800">{{ employee.data?.company || "-" }}</div>
					<div class="text-sm text-gray-500">{{ employee.data?.branch || "-" }}</div>

					<div v-if="lastDiagnosisTime" class="text-xs text-gray-400 mt-1">
						마지막 진단: {{ lastDiagnosisTime }}
					</div>

					<!-- 전체 진단 실행 (admin) -->
					<button
						v-if="isAdmin"
						@click="confirmRunDiagnosis"
						:disabled="complianceDiagnosis.loading"
						class="mt-3 w-full py-3 bg-blue-600 text-white text-sm rounded font-medium hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
					>
						<span v-if="complianceDiagnosis.loading">{{ __('진단 중...') }}</span>
						<span v-else>{{ __('전체 진단 실행') }}</span>
					</button>
				</div>

				<!-- 종합 상태 -->
				<div v-if="diagnosisResult" class="bg-white rounded shadow-sm p-4 flex flex-col gap-3">
					<div class="text-sm font-bold text-gray-700">{{ __('종합 상태') }}</div>
					<div class="flex items-center gap-2">
						<span class="text-2xl">{{ overallStatusEmoji }}</span>
						<span :class="overallStatusClass" class="text-base font-bold">
							{{ overallStatusLabel }}
						</span>
					</div>
				</div>

				<!-- 카테고리별 결과 -->
				<div v-if="diagnosisResult" class="flex flex-col gap-3">
					<div class="text-sm font-bold text-gray-700 px-1">{{ __('카테고리별 결과') }}</div>

					<div
						v-for="cat in categoryResults"
						:key="cat.key"
						class="bg-white rounded shadow-sm p-4 flex flex-col gap-2 cursor-pointer hover:bg-gray-50 transition-colors"
						@click="toggleCategory(cat.key)"
					>
						<div class="flex justify-between items-center">
							<div class="flex items-center gap-2">
								<span class="text-base">{{ cat.statusEmoji }}</span>
								<span class="text-sm font-semibold text-gray-800">{{ cat.label }}</span>
							</div>
							<div class="flex items-center gap-2">
								<span :class="cat.statusTextClass" class="text-xs font-medium px-2 py-0.5 rounded-full" :style="cat.badgeStyle">
									{{ cat.statusText }}
								</span>
								<span class="text-gray-400 text-xs">{{ expandedCategory === cat.key ? "▲" : "▼" }}</span>
							</div>
						</div>

						<!-- 상세 확장 -->
						<div
							v-if="expandedCategory === cat.key"
							class="mt-2 pt-2 border-t border-gray-100 flex flex-col gap-2"
						>
							<div v-if="cat.findings?.length" class="flex flex-col gap-1">
								<div class="text-xs font-semibold text-gray-600 mb-1">발견 사항</div>
								<div
									v-for="(finding, idx) in cat.findings"
									:key="idx"
									class="text-xs text-gray-600 pl-2 border-l-2"
									:class="cat.status === 'fail' ? 'border-red-400' : 'border-yellow-400'"
								>
									{{ finding }}
								</div>
							</div>
							<div v-if="cat.recommendations?.length" class="flex flex-col gap-1 mt-1">
								<div class="text-xs font-semibold text-blue-600 mb-1">권고 사항</div>
								<div
									v-for="(rec, idx) in cat.recommendations"
									:key="idx"
									class="text-xs text-blue-600 pl-2 border-l-2 border-blue-300"
								>
									{{ rec }}
								</div>
							</div>
							<div
								v-if="!cat.findings?.length && !cat.recommendations?.length"
								class="text-xs text-gray-400 text-center py-2"
							>
								{{ __('세부 내용 없음') }}
							</div>
						</div>
					</div>
				</div>

				<!-- 결과 없음 -->
				<div
					v-if="!diagnosisResult && !complianceDiagnosis.loading"
					class="bg-white rounded shadow-sm p-8 flex flex-col items-center gap-3 text-center"
				>
					<span class="text-4xl">📋</span>
					<div class="text-sm text-gray-500">{{ __('아직 진단 결과가 없습니다.') }}</div>
					<div v-if="isAdmin" class="text-xs text-gray-400">
						위의 "전체 진단 실행" 버튼을 눌러 진단을 시작하세요.
					</div>
				</div>

				<!-- 로딩 -->
				<div v-if="complianceDiagnosis.loading" class="flex flex-col items-center py-10 gap-3">
					<div class="text-gray-400 text-sm">{{ __('진단 중입니다. 잠시 기다려 주세요...') }}</div>
				</div>

				<!-- PDF 리포트 다운로드 -->
				<div v-if="diagnosisResult" class="flex">
					<button
						@click="downloadReport"
						class="w-full py-3 border border-gray-300 rounded text-sm text-gray-700 font-medium hover:bg-gray-50 transition-colors"
					>
						{{ __('PDF 리포트 다운로드') }}
					</button>
				</div>

				<!-- Confirm dialog overlay -->
				<div
					v-if="showConfirm"
					class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
					@click.self="showConfirm = false"
				>
					<div class="bg-white rounded-lg shadow-xl p-6 mx-6 flex flex-col gap-4 max-w-sm w-full">
						<div class="text-base font-bold text-gray-800">전체 진단 실행</div>
						<div class="text-sm text-gray-600 leading-relaxed">
							회사 전체 컴플라이언스 진단을 실행합니다.<br />
							이 작업은 모든 직원의 근무 데이터를 분석합니다. 계속하시겠습니까?
						</div>
						<div class="flex flex-row gap-3 mt-2">
							<button
								@click="showConfirm = false"
								class="flex-1 py-2 border border-gray-300 rounded text-sm text-gray-700 font-medium hover:bg-gray-50 transition-colors"
							>
								취소
							</button>
							<button
								@click="runDiagnosis"
								class="flex-1 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 transition-colors"
							>
								실행
							</button>
						</div>
					</div>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { ref, computed, inject, onMounted } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import { complianceDiagnosis } from "@/data/koreaComplianceRuntime"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")

const diagnosisResult = ref(null)
const lastDiagnosisTime = ref(null)
const expandedCategory = ref(null)
const showConfirm = ref(false)
const isAdmin = ref(false) // TODO: 실제 권한 체크 연동

const CATEGORY_LABELS = {
	social_insurance: "4대보험 가입",
	wage_payment: "임금 정기 지급",
	overtime_limit: "주 12h 한도",
	annual_leave: "연차 사용",
	anti_harassment: "직장 내 괴롭힘 신고채널",
}

const STATUS_CONFIG = {
	pass: {
		emoji: "🟢",
		text: "양호",
		textClass: "text-green-700",
		badgeStyle: "background:var(--surface-green, #dcfce7)",
	},
	warn: {
		emoji: "🟡",
		text: "주의 필요",
		textClass: "text-yellow-700",
		badgeStyle: "background:var(--surface-yellow, #fef9c3)",
	},
	fail: {
		emoji: "🔴",
		text: "위험",
		textClass: "text-red-700",
		badgeStyle: "background:var(--surface-red, #fee2e2)",
	},
}

const overallStatus = computed(() => {
	if (!diagnosisResult.value?.categories) return null
	const categories = Object.values(diagnosisResult.value.categories)
	if (categories.some((c) => c.status === "fail")) return "fail"
	if (categories.some((c) => c.status === "warn")) return "warn"
	return "pass"
})

const overallStatusEmoji = computed(() => STATUS_CONFIG[overallStatus.value]?.emoji ?? "⬜")
const overallStatusLabel = computed(() => STATUS_CONFIG[overallStatus.value]?.text ?? "-")
const overallStatusClass = computed(() => {
	const map = { pass: "text-green-700", warn: "text-yellow-700", fail: "text-red-700" }
	return map[overallStatus.value] ?? "text-gray-700"
})

const categoryResults = computed(() => {
	if (!diagnosisResult.value?.categories) return []
	return Object.entries(diagnosisResult.value.categories).map(([key, cat]) => {
		const config = STATUS_CONFIG[cat.status] ?? STATUS_CONFIG.pass
		return {
			key,
			label: CATEGORY_LABELS[key] ?? key,
			status: cat.status,
			statusEmoji: config.emoji,
			statusText: cat.status_text ?? config.text,
			statusTextClass: config.textClass,
			badgeStyle: config.badgeStyle,
			findings: cat.findings ?? [],
			recommendations: cat.recommendations ?? [],
		}
	})
})

function toggleCategory(key) {
	expandedCategory.value = expandedCategory.value === key ? null : key
}

function confirmRunDiagnosis() {
	showConfirm.value = true
}

async function runDiagnosis() {
	showConfirm.value = false
	diagnosisResult.value = null
	await complianceDiagnosis.submit({
		company: employee.data?.company,
		workplace: employee.data?.branch ?? null,
	})
	if (!complianceDiagnosis.error && complianceDiagnosis.data) {
		diagnosisResult.value = complianceDiagnosis.data
		lastDiagnosisTime.value = dayjs().format("YYYY-MM-DD HH:mm")
	}
}

function downloadReport() {
	// TODO: PDF 리포트 생성 API 연동
	alert("PDF 리포트 다운로드 기능은 준비 중입니다.")
}

onMounted(() => {
	// TODO: 최신 저장된 진단 결과 로드
})
</script>
