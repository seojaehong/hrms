<template>
	<BaseLayout :pageTitle="__('임금명세서')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 연도/월 필터 -->
				<div class="k-card p-4 flex flex-row gap-3 items-end">
					<div class="flex flex-col gap-1 flex-1">
						<label class="k-label">{{ __('연도') }}</label>
						<select
							v-model="selectedYear"
							class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black/60"
						>
							<option v-for="y in yearOptions" :key="y" :value="y">{{ y }}년</option>
						</select>
					</div>
					<div class="flex flex-col gap-1 flex-1">
						<label class="k-label">{{ __('월') }}</label>
						<select
							v-model="selectedMonth"
							class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black/60"
						>
							<option v-for="m in 12" :key="m" :value="m">{{ m }}월</option>
						</select>
					</div>
					<button
						@click="loadStatement"
						class="px-5 py-2 bg-black text-white text-sm rounded-full font-semibold hover:bg-black/80 active:bg-black transition-colors"
					>
						{{ __('조회') }}
					</button>
				</div>

				<!-- 선택한 월 명세서 카드 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div>
						<div class="k-eyebrow">WAGE STATEMENT</div>
						<div class="mt-0.5 text-base font-bold tracking-tight text-black">
							{{ selectedYear }}년 {{ selectedMonth }}월 임금명세서
						</div>
					</div>

					<div v-if="wageStatementPreview.loading" class="text-center py-8 text-gray-400 text-sm">
						{{ __('불러오는 중...') }}
					</div>
					<div v-else-if="wageStatementPreview.error" class="text-center py-8 text-red-500 text-sm">
						{{ __('해당 월의 명세서가 없습니다. 다른 달을 선택해 조회하세요.') }}
					</div>
					<template v-else-if="statement">
						<!-- 법정 항목 그리드 -->
						<div class="flex flex-col gap-2">
							<!-- 기본급 -->
							<div class="flex justify-between items-center border-b border-gray-100 pb-2">
								<span class="text-sm text-gray-600">① 기본급</span>
								<span class="text-sm font-semibold text-gray-800">{{ formatKRW(statement.base_salary) }}</span>
							</div>
							<!-- 각종 수당 -->
							<div class="flex justify-between items-center border-b border-gray-100 pb-2">
								<span class="text-sm text-gray-600">② 각종 수당 합계</span>
								<span class="text-sm font-semibold text-gray-800">{{ formatKRW(statementAllowanceTotal) }}</span>
							</div>
							<!-- 수당 명세 -->
							<div
								v-for="item in statement.allowances"
								:key="item.code"
								class="flex justify-between items-center pl-3 pb-1"
							>
								<span class="text-xs text-gray-500">· {{ item.label }}</span>
								<span class="text-xs text-gray-700">{{ formatKRW(item.amount) }}</span>
							</div>

							<!-- 비과세 -->
							<div class="flex justify-between items-center border-b border-gray-100 pb-2">
								<span class="text-sm text-gray-600">③ 비과세 합계</span>
								<span class="text-sm font-semibold text-gray-800">{{ formatKRW(statement.non_taxable_total) }}</span>
							</div>
							<!-- 공제 -->
							<div class="flex justify-between items-center border-b border-gray-100 pb-2">
								<span class="text-sm text-gray-600">④ 공제 합계</span>
								<span class="text-sm font-semibold text-red-600">-{{ formatKRW(statement.total_deduction) }}</span>
							</div>
							<!-- 공제 요약: 4대보험 합계 · 소득세 · 주민세 (상세는 토글) -->
							<div class="flex justify-between items-center pl-3 pb-1">
								<button class="text-xs text-gray-500 flex items-center gap-1" @click="showInsuranceDetail = !showInsuranceDetail">
									· 4대보험 <span class="text-gray-400">{{ showInsuranceDetail ? "▾" : "▸" }}</span>
								</button>
								<span class="text-xs text-gray-700 k-numeric">{{ formatKRW(statementInsuranceTotal) }}</span>
							</div>
							<template v-if="showInsuranceDetail">
								<div class="flex justify-between items-center pl-6 pb-0.5">
									<span class="text-[11px] text-gray-400">국민연금</span>
									<span class="text-[11px] text-gray-500 k-numeric">{{ formatKRW(statement.national_pension) }}</span>
								</div>
								<div class="flex justify-between items-center pl-6 pb-0.5">
									<span class="text-[11px] text-gray-400">건강보험</span>
									<span class="text-[11px] text-gray-500 k-numeric">{{ formatKRW(statement.health_insurance) }}</span>
								</div>
								<div class="flex justify-between items-center pl-6 pb-0.5">
									<span class="text-[11px] text-gray-400">장기요양보험</span>
									<span class="text-[11px] text-gray-500 k-numeric">{{ formatKRW(statement.long_term_care_insurance) }}</span>
								</div>
								<div class="flex justify-between items-center pl-6 pb-0.5">
									<span class="text-[11px] text-gray-400">고용보험</span>
									<span class="text-[11px] text-gray-500 k-numeric">{{ formatKRW(statement.employment_insurance) }}</span>
								</div>
							</template>
							<div class="flex justify-between items-center pl-3 pb-1">
								<span class="text-xs text-gray-500">· 소득세</span>
								<span class="text-xs text-gray-700 k-numeric">{{ formatKRW(statement.income_tax) }}</span>
							</div>
							<div class="flex justify-between items-center pl-3 pb-2 border-b border-gray-100">
								<span class="text-xs text-gray-500">· 주민세(지방소득세)</span>
								<span class="text-xs text-gray-700 k-numeric">{{ formatKRW(statement.local_income_tax) }}</span>
							</div>

							<!-- 실수령액 -->
							<div class="flex justify-between items-center pt-1">
								<span class="text-base font-bold text-gray-800">⑦ 실수령액</span>
								<span class="text-base font-bold text-black k-numeric">{{ formatKRW(statement.net_pay) }}</span>
							</div>
						</div>

						<!-- 액션 버튼 (admin 전용) — 미구현 기능: disabled + (준비 중) 표기 -->
						<div v-if="isAdmin" class="flex flex-row gap-2 pt-2">
							<button
								disabled
								class="flex-1 py-2 border border-black/15 rounded-full text-sm text-black font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
							>
								PDF 다운로드 (준비 중)
							</button>
							<button
								disabled
								class="flex-1 py-2 border border-black/15 rounded-full text-sm text-black font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
							>
								카톡 발송 (준비 중)
							</button>
						</div>
					</template>
					<div v-else class="text-center py-8 text-gray-400 text-sm">
						{{ __('조회 버튼을 눌러 명세서를 확인하세요.') }}
					</div>
				</div>

				<!-- 지난 12개월 목록 -->
				<div class="k-card p-4 flex flex-col gap-3">
					<div class="text-base font-bold tracking-tight text-black">{{ __('최근 12개월') }}</div>
					<div v-if="wageStatementHistory.loading" class="text-sm text-gray-400 py-4 text-center">
						{{ __('불러오는 중...') }}
					</div>
					<template v-else-if="wageStatementHistory.data?.length">
						<div
							v-for="item in wageStatementHistory.data"
							:key="item.pay_year_month"
							class="flex justify-between items-center border-b border-gray-100 pb-2 cursor-pointer hover:bg-gray-50 -mx-2 px-2 rounded transition-colors"
							@click="selectHistoryItem(item)"
						>
							<span class="text-sm text-gray-700">{{ item.pay_year_month }}</span>
							<span class="text-sm font-semibold text-gray-800">{{ formatKRW(item.net_pay) }}</span>
						</div>
					</template>
					<div v-else class="text-sm text-gray-400 py-4 text-center">
						{{ __('명세서 내역이 없습니다.') }}
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
import { wageStatementPreview, wageStatementHistory } from "@/data/koreaWageStatementRuntime"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")

const now = dayjs()
const selectedYear = ref(now.year())
const selectedMonth = ref(now.month() + 1)
const statement = ref(null)
const isAdmin = useIsAdmin() // HR Manager/System Manager 롤 기준

const yearOptions = computed(() => {
	const current = now.year()
	return [current - 2, current - 1, current]
})

const statementAllowanceTotal = computed(() => {
	if (!statement.value?.allowances) return 0
	return statement.value.allowances.reduce((sum, item) => sum + (item.amount || 0), 0)
})

// 4대보험 합계 (국민연금+건강+장기요양+고용) — 공제 요약 표시용
const showInsuranceDetail = ref(false)
const statementInsuranceTotal = computed(() => {
	const s = statement.value
	if (!s) return 0
	return (s.national_pension || 0) + (s.health_insurance || 0) + (s.long_term_care_insurance || 0) + (s.employment_insurance || 0)
})

function formatKRW(amount) {
	if (amount == null) return "-"
	return Number(amount).toLocaleString("ko-KR") + "원"
}

async function loadStatement() {
	statement.value = null
	await wageStatementPreview.submit({
		employee: employee.data?.name,
		year: selectedYear.value,
		month: selectedMonth.value,
	})
	if (!wageStatementPreview.error) {
		statement.value = wageStatementPreview.data
	}
}

function selectHistoryItem(item) {
	if (!item?.pay_year_month) return
	const [y, m] = item.pay_year_month.split("-")
	selectedYear.value = parseInt(y)
	selectedMonth.value = parseInt(m)
	loadStatement()
}

// PDF 다운로드·카톡 발송: API 미구현 — 버튼 disabled + "(준비 중)" 표기 (핸들러 제거)

onMounted(async () => {
	// $employee 리소스 로딩 대기 (경쟁 조건 방지)
	try { await employee?.promise } catch { /* 폴백 */ }
	await wageStatementHistory.submit({
		employee: employee.data?.name,
		limit: 12,
	})
	// 첫 진입: 명세서가 있는 가장 최근 달로 자동 조회 (없으면 당월)
	const latest = wageStatementHistory.data?.[0]?.pay_year_month
	if (typeof latest === "string" && /^\d{4}-\d{2}$/.test(latest)) {
		selectedYear.value = Number(latest.slice(0, 4))
		selectedMonth.value = Number(latest.slice(5, 7))
	}
	loadStatement()
})
</script>
