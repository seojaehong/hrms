<template>
	<BaseLayout :pageTitle="__('임금명세서')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 연도/월 필터 -->
				<div class="bg-white rounded shadow-sm p-4 flex flex-row gap-3 items-end">
					<div class="flex flex-col gap-1 flex-1">
						<label class="text-xs text-gray-500 font-medium">{{ __('연도') }}</label>
						<select
							v-model="selectedYear"
							class="border border-gray-300 rounded px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
						>
							<option v-for="y in yearOptions" :key="y" :value="y">{{ y }}년</option>
						</select>
					</div>
					<div class="flex flex-col gap-1 flex-1">
						<label class="text-xs text-gray-500 font-medium">{{ __('월') }}</label>
						<select
							v-model="selectedMonth"
							class="border border-gray-300 rounded px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
						>
							<option v-for="m in 12" :key="m" :value="m">{{ m }}월</option>
						</select>
					</div>
					<button
						@click="loadStatement"
						class="px-4 py-2 bg-blue-600 text-white text-sm rounded font-medium hover:bg-blue-700 active:bg-blue-800 transition-colors"
					>
						{{ __('조회') }}
					</button>
				</div>

				<!-- 선택한 월 명세서 카드 -->
				<div class="bg-white rounded shadow-sm p-4 flex flex-col gap-4">
					<div class="text-base font-bold text-gray-800">
						{{ selectedYear }}년 {{ selectedMonth }}월 임금명세서
					</div>

					<div v-if="wageStatementPreview.loading" class="text-center py-8 text-gray-400 text-sm">
						{{ __('불러오는 중...') }}
					</div>
					<div v-else-if="wageStatementPreview.error" class="text-center py-8 text-red-500 text-sm">
						{{ __('데이터를 불러오지 못했습니다.') }}
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

						<!-- 액션 버튼 (admin 전용) -->
						<div v-if="isAdmin" class="flex flex-row gap-2 pt-2">
							<button
								class="flex-1 py-2 border border-gray-300 rounded text-sm text-gray-700 font-medium hover:bg-gray-50 transition-colors"
								@click="downloadPdf"
							>
								PDF 다운로드
							</button>
							<button
								class="flex-1 py-2 border border-yellow-400 rounded text-sm text-yellow-700 font-medium hover:bg-yellow-50 transition-colors"
								@click="sendKakao"
							>
								카톡 발송
							</button>
						</div>
					</template>
					<div v-else class="text-center py-8 text-gray-400 text-sm">
						{{ __('조회 버튼을 눌러 명세서를 확인하세요.') }}
					</div>
				</div>

				<!-- 지난 12개월 목록 -->
				<div class="bg-white rounded shadow-sm p-4 flex flex-col gap-3">
					<div class="text-base font-bold text-gray-800">{{ __('최근 12개월') }}</div>
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
import { wageStatementPreview, wageStatementHistory } from "@/data/koreaWageStatementRuntime"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")

const now = dayjs()
const selectedYear = ref(now.year())
const selectedMonth = ref(now.month() + 1)
const statement = ref(null)
const isAdmin = ref(false) // TODO: 실제 권한 체크 연동

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

function downloadPdf() {
	// TODO: PDF 생성 API 연동
	alert("PDF 다운로드 기능은 준비 중입니다.")
}

function sendKakao() {
	// TODO: 카카오톡 발송 API 연동
	alert("카카오톡 발송 기능은 준비 중입니다.")
}

onMounted(() => {
	wageStatementHistory.submit({
		employee: employee.data?.name,
		limit: 12,
	})
})
</script>
