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
							class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60"
						>
							<option v-for="y in yearOptions" :key="y" :value="y">{{ y }}년</option>
						</select>
					</div>
					<div class="flex flex-col gap-1 flex-1">
						<label class="k-label">{{ __('월') }}</label>
						<select
							v-model="selectedMonth"
							class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60"
						>
							<option v-for="m in 12" :key="m" :value="m">{{ m }}월</option>
						</select>
					</div>
					<button
						@click="loadStatement"
						class="k-btn-primary"
					>
						{{ __('조회') }}
					</button>
				</div>

				<!-- 선택한 월 명세서 카드 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div>
						<div class="k-eyebrow">WAGE STATEMENT</div>
						<div class="mt-0.5 text-base font-bold tracking-tight text-[var(--k-ink)]">
							{{ selectedYear }}년 {{ selectedMonth }}월 임금명세서
						</div>
					</div>

					<div v-if="wageStatementPreview.loading" class="text-center py-8 text-[var(--k-ink-faint)] text-sm">
						{{ __('불러오는 중...') }}
					</div>
					<div v-else-if="wageStatementPreview.error" class="text-center py-8 text-red-500 text-sm">
						{{ __('해당 월의 명세서가 없습니다. 다른 달을 선택해 조회하세요.') }}
					</div>
					<template v-else-if="statement">
						<!-- 히어로: 실수령액이 주인공 -->
						<div class="k-block k-block--cream -mx-1">
							<div class="k-eyebrow">NET PAY · {{ selectedYear }}.{{ String(selectedMonth).padStart(2, "0") }}</div>
							<div class="mt-1 text-sm font-medium text-[var(--k-ink-muted)]">실수령액</div>
							<div class="k-display k-settled">
								{{ formatKRW(statement.net_pay) }}
							</div>
							<!-- 요약 3스탯: 지급 → 공제 → 실수령 흐름 -->
							<div class="mt-4 grid grid-cols-3 gap-2">
								<div class="rounded-lg bg-white/55 px-3 py-2">
									<p class="text-[11px] text-[var(--k-ink-muted)]">지급 합계</p>
									<p class="text-sm font-bold k-amount">{{ formatKRW(statementGrossTotal) }}</p>
								</div>
								<div class="rounded-lg bg-white/55 px-3 py-2">
									<p class="text-[11px] text-[var(--k-ink-muted)]">공제 합계</p>
									<p class="text-sm font-bold k-amount">−{{ formatKRW(statement.total_deduction) }}</p>
								</div>
								<div class="rounded-lg bg-black px-3 py-2">
									<p class="text-[11px] text-white/60">실수령</p>
									<p class="text-sm font-bold text-white k-numeric k-amount">{{ formatKRW(statement.net_pay) }}</p>
								</div>
							</div>
						</div>

						<!-- 최근 6개월 실수령 추이 — 인라인 SVG 스파크라인 (history 리소스 재사용) -->
						<div v-if="netPayTrend" class="k-card p-4" data-testid="net-pay-sparkline">
							<div class="k-eyebrow mb-2">TREND</div>
							<div class="text-sm font-bold text-[var(--k-ink)]">최근 6개월 실수령 추이</div>
							<svg
								:viewBox="`0 0 ${sparkW + 10} ${sparkH + 10}`"
								class="mt-2 h-14 w-full text-[var(--k-ink)]"
								role="img"
								aria-label="최근 6개월 실수령 추이"
							>
								<g transform="translate(5,5)">
									<polyline
										:points="netPayTrend.points"
										fill="none"
										stroke="currentColor"
										stroke-width="2"
										stroke-linecap="round"
										stroke-linejoin="round"
									/>
									<!-- 마지막 점 강조 원 -->
									<circle
										:cx="netPayTrend.lastPoint.x"
										:cy="netPayTrend.lastPoint.y"
										r="3.5"
										fill="currentColor"
										stroke="white"
										stroke-width="1.5"
									/>
								</g>
							</svg>
							<div class="mt-1 flex justify-between text-[11px] text-[var(--k-ink-faint)] k-numeric">
								<span>{{ trendRows[0].pay_year_month }}</span>
								<span>{{ trendRows[trendRows.length - 1].pay_year_month }} · {{ formatTick(trendRows[trendRows.length - 1].net_pay) }}원</span>
							</div>
						</div>

						<!-- 지급 내역 -->
						<div class="k-card p-4">
							<div class="k-eyebrow mb-2">EARNINGS</div>
							<div class="text-sm font-bold text-[var(--k-ink)] mb-2">지급 내역</div>
							<div class="flex flex-col">
								<div class="flex justify-between items-center py-2 border-t border-[var(--k-hairline-soft)]">
									<span class="text-sm text-[var(--k-ink-muted)]">기본급</span>
									<span class="text-sm font-semibold k-amount">{{ formatKRW(statement.base_salary) }}</span>
								</div>
								<div
									v-for="item in statement.allowances"
									:key="item.code"
									class="flex justify-between items-center py-2 border-t border-[var(--k-hairline-soft)]"
								>
									<span class="text-sm text-[var(--k-ink-muted)]">{{ item.label }}</span>
									<span class="text-sm font-semibold k-amount">{{ formatKRW(item.amount) }}</span>
								</div>
								<div class="flex justify-between items-center py-2 border-t border-[var(--k-hairline-soft)]">
									<span class="text-sm text-[var(--k-ink-muted)]">비과세 합계</span>
									<span class="text-sm font-semibold k-amount">{{ formatKRW(statement.non_taxable_total) }}</span>
								</div>
								<div class="flex justify-between items-center py-2.5 mt-1 rounded-lg bg-[var(--k-surface-soft)] px-3">
									<span class="text-sm font-bold text-[var(--k-ink)]">지급 합계</span>
									<span class="text-sm font-bold k-amount">{{ formatKRW(statementGrossTotal) }}</span>
								</div>
							</div>
						</div>

						<!-- 공제 내역 -->
						<div class="k-card p-4">
							<div class="k-eyebrow mb-2">DEDUCTIONS</div>
							<div class="text-sm font-bold text-[var(--k-ink)] mb-2">공제 내역</div>
							<div class="flex flex-col">
								<div class="flex justify-between items-center py-2 border-t border-[var(--k-hairline-soft)]">
									<button class="text-sm text-[var(--k-ink-muted)] flex items-center gap-1" @click="showInsuranceDetail = !showInsuranceDetail">
										4대보험 <span class="text-[var(--k-ink-faint)] text-xs">{{ showInsuranceDetail ? "▾" : "▸" }}</span>
									</button>
									<span class="text-sm font-semibold k-amount">{{ formatKRW(statementInsuranceTotal) }}</span>
								</div>
								<template v-if="showInsuranceDetail">
									<div class="flex justify-between items-center py-1 pl-4">
										<span class="text-xs text-[var(--k-ink-muted)]">국민연금</span>
										<span class="text-xs k-amount">{{ formatKRW(statement.national_pension) }}</span>
									</div>
									<div class="flex justify-between items-center py-1 pl-4">
										<span class="text-xs text-[var(--k-ink-muted)]">건강보험</span>
										<span class="text-xs k-amount">{{ formatKRW(statement.health_insurance) }}</span>
									</div>
									<div class="flex justify-between items-center py-1 pl-4">
										<span class="text-xs text-[var(--k-ink-muted)]">장기요양보험</span>
										<span class="text-xs k-amount">{{ formatKRW(statement.long_term_care_insurance) }}</span>
									</div>
									<div class="flex justify-between items-center py-1 pl-4">
										<span class="text-xs text-[var(--k-ink-muted)]">고용보험</span>
										<span class="text-xs k-amount">{{ formatKRW(statement.employment_insurance) }}</span>
									</div>
								</template>
								<div class="flex justify-between items-center py-2 border-t border-[var(--k-hairline-soft)]">
									<span class="text-sm text-[var(--k-ink-muted)]">소득세</span>
									<span class="text-sm font-semibold k-amount">{{ formatKRW(statement.income_tax) }}</span>
								</div>
								<div class="flex justify-between items-center py-2 border-t border-[var(--k-hairline-soft)]">
									<span class="text-sm text-[var(--k-ink-muted)]">주민세(지방소득세)</span>
									<span class="text-sm font-semibold k-amount">{{ formatKRW(statement.local_income_tax) }}</span>
								</div>
								<div class="flex justify-between items-center py-2.5 mt-1 rounded-lg bg-[var(--k-surface-soft)] px-3">
									<span class="text-sm font-bold text-[var(--k-ink)]">공제 합계</span>
									<span class="text-sm font-bold k-amount">−{{ formatKRW(statement.total_deduction) }}</span>
								</div>
							</div>
						</div>

						<p class="k-label text-center">근로기준법 제48조제2항에 따른 임금명세서입니다 · 구성항목·계산방법·공제내역 명시</p>

						<!-- 액션 버튼 (admin 전용) — 미구현 기능: disabled + (준비 중) 표기 -->
						<div v-if="isAdmin" class="flex flex-row gap-2 pt-2">
							<button
								disabled
								class="k-btn-secondary flex-1 disabled:opacity-40 disabled:cursor-not-allowed"
							>
								PDF 다운로드 (준비 중)
							</button>
							<button
								disabled
								class="k-btn-secondary flex-1 disabled:opacity-40 disabled:cursor-not-allowed"
							>
								카톡 발송 (준비 중)
							</button>
						</div>
					</template>
					<div v-else class="text-center py-8 text-[var(--k-ink-faint)] text-sm">
						{{ __('조회 버튼을 눌러 명세서를 확인하세요.') }}
					</div>
				</div>

				<!-- 지난 12개월 목록 -->
				<div class="k-card p-4 flex flex-col gap-3">
					<div class="text-base font-bold tracking-tight text-[var(--k-ink)]">{{ __('최근 12개월') }}</div>
					<div v-if="wageStatementHistory.loading" class="text-sm text-[var(--k-ink-faint)] py-4 text-center">
						{{ __('불러오는 중...') }}
					</div>
					<template v-else-if="wageStatementHistory.data?.length">
						<div
							v-for="item in wageStatementHistory.data"
							:key="item.pay_year_month"
							class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2 cursor-pointer hover:bg-[var(--k-surface-soft)] -mx-2 px-2 rounded transition-colors"
							@click="selectHistoryItem(item)"
						>
							<span class="text-sm text-[var(--k-ink)]">{{ item.pay_year_month }}</span>
							<span class="text-sm font-semibold text-[var(--k-ink)] k-amount">{{ formatKRW(item.net_pay) }}</span>
						</div>
					</template>
					<div v-else class="text-sm text-[var(--k-ink-faint)] py-4 text-center">
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
import { buildSparklinePath, formatTick } from "@/utils/koreaCharts"
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
// 지급 합계 (기본급 + 수당 + 비과세) — 히어로 요약용
const statementGrossTotal = computed(() => {
	const s = statement.value
	if (!s) return 0
	return (s.base_salary || 0) + statementAllowanceTotal.value + (s.non_taxable_total || 0)
})

const statementInsuranceTotal = computed(() => {
	const s = statement.value
	if (!s) return 0
	return (s.national_pension || 0) + (s.health_insurance || 0) + (s.long_term_care_insurance || 0) + (s.employment_insurance || 0)
})

// ── 최근 6개월 실수령 추이 스파크라인 ─────────────────────────────
// 데이터 소스: wageStatementHistory (list_korea_wage_statements) 재사용 — 신규 API 없음.
// history는 최신순([0]=최근) → 최근 6건을 시간순(과거→현재)으로 뒤집어 그린다.
const sparkW = 272
const sparkH = 40

const trendRows = computed(() => {
	const rows = wageStatementHistory.data
	if (!Array.isArray(rows)) return []
	return rows
		.filter((r) => r?.pay_year_month && Number.isFinite(Number(r.net_pay)))
		.slice(0, 6)
		.reverse()
})

// 2점 미만이면 추이가 아니므로 차트 숨김 (빈 차트 렌더 금지)
const netPayTrend = computed(() => {
	if (trendRows.value.length < 2) return null
	return buildSparklinePath(
		trendRows.value.map((r) => Number(r.net_pay)),
		sparkW,
		sparkH
	)
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
