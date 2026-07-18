<template>
	<BaseLayout :pageTitle="__('퇴직정산 (통합)')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 -->
				<div class="pt-1">
					<div class="k-eyebrow">SEVERANCE SETTLEMENT</div>
					<div class="mt-1 k-t-display text-[var(--k-ink)]">{{ __('퇴직정산 (통합)') }}</div>
					<p class="mt-2 k-t-body text-[var(--k-ink-muted)]">
						퇴직금·미사용연차수당·퇴직소득세·건보정산을 한 번에 계산해 실지급액을 확인합니다.
					</p>
				</div>

				<!-- 입력 카드 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div class="k-t-headline text-[var(--k-ink)]">{{ __('정산 조건 입력') }}</div>

					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('입사일') }}</label>
							<input
								type="date"
								v-model="form.hire_date"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('퇴직일 (마지막 근무일+1)') }}</label>
							<input
								type="date"
								v-model="form.severance_date"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
					</div>

					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('1일 평균임금 (원)') }}</label>
							<input
								type="number"
								v-model.number="form.average_wage_per_day"
								:placeholder="__('예: 100000')"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('1일 통상임금 (원, 선택)') }}</label>
							<input
								type="number"
								v-model.number="form.ordinary_wage_per_day"
								:placeholder="__('평균임금보다 높으면 대체')"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('월 기본급 (원)') }}</label>
							<input
								type="number"
								v-model.number="form.monthly_base_salary"
								:placeholder="__('예: 2090000')"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('미사용 연차 (일)') }}</label>
							<input
								type="number"
								v-model.number="form.unused_leave_days"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
					</div>

					<!-- 건보정산 옵션 -->
					<div class="flex items-center gap-2">
						<input id="health-toggle" type="checkbox" v-model="useHealth" class="accent-black" />
						<label for="health-toggle" class="text-sm font-medium text-[var(--k-ink)]">{{ __('건강보험 퇴직 정산 포함') }}</label>
					</div>
					<template v-if="useHealth">
						<div class="flex flex-col gap-1">
							<label class="k-label">
								{{ __('당해연도 월별 보수 (원, 쉼표 구분)') }}
								<span class="normal-case tracking-normal opacity-70">— 예: 2000000, 2000000, 2100000</span>
							</label>
							<textarea
								v-model="remunerationText"
								rows="2"
								:placeholder="__('예: 2000000, 2000000, 2000000')"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							></textarea>
						</div>
						<div class="grid grid-cols-2 gap-2">
							<div class="flex flex-col gap-1">
								<label class="k-label">{{ __('기납부 건강보험료 (원)') }}</label>
								<input
									type="number"
									v-model.number="form.paid_health_total"
									class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
								/>
							</div>
							<div class="flex flex-col gap-1">
								<label class="k-label">{{ __('기납부 장기요양보험료 (원)') }}</label>
								<input
									type="number"
									v-model.number="form.paid_longterm_care_total"
									class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
								/>
							</div>
						</div>
						<div class="flex items-center gap-2">
							<input id="midmonth-toggle" type="checkbox" v-model="form.mid_month_hire" class="accent-black" />
							<label for="midmonth-toggle" class="text-sm text-[var(--k-ink-muted)]">{{ __('중도입사 (1일 입사 아님 — 입사월 보험료 미납)') }}</label>
						</div>
					</template>

					<button
						@click="calculate"
						:disabled="severanceSettlement.loading || !canSubmit"
						class="k-btn-primary w-full"
					>
						<span v-if="severanceSettlement.loading">{{ __('정산 중...') }}</span>
						<span v-else>{{ __('퇴직정산 계산') }}</span>
					</button>
				</div>

				<!-- 결과 카드 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div class="k-t-headline text-[var(--k-ink)]">{{ __('정산 결과') }}</div>

					<div v-if="severanceSettlement.loading" class="text-center py-8 text-[var(--k-ink-faint)] text-sm">
						{{ __('정산 중...') }}
					</div>
					<div v-else-if="severanceSettlement.error" class="text-center py-6 text-red-600 text-sm">
						{{ __('정산에 실패했습니다. 입력값을 확인해 주세요.') }}
					</div>
					<template v-else-if="result">
						<!-- 주인공: 실지급 총액 (cream 블록) -->
						<div class="k-block k-block--cream -mx-1">
							<div class="k-eyebrow">NET TOTAL PAYOUT</div>
							<div class="mt-1 text-sm font-medium text-[var(--k-ink-muted)]">실지급 총액</div>
							<div class="k-display k-settled">{{ formatKRW(summary.net_total_payout) }}</div>
							<div class="mt-4 grid grid-cols-3 gap-2">
								<div class="rounded-lg bg-white/55 px-3 py-2 text-center">
									<p class="k-numeric text-sm font-bold k-amount">{{ formatKRW(summary.severance_pay_amount) }}</p>
									<p class="text-[11px] text-[var(--k-ink-muted)]">퇴직금 (세전)</p>
								</div>
								<div class="rounded-lg bg-white/55 px-3 py-2 text-center">
									<p class="k-numeric text-sm font-bold k-amount">{{ formatKRW(summary.unused_leave_allowance) }}</p>
									<p class="text-[11px] text-[var(--k-ink-muted)]">미사용연차수당</p>
								</div>
								<div class="rounded-lg bg-black px-3 py-2 text-center">
									<p class="k-numeric text-sm font-bold text-white k-amount">{{ formatKRW(summary.net_severance_payout) }}</p>
									<p class="text-[11px] text-white/60">퇴직금 실지급</p>
								</div>
							</div>
						</div>

						<!-- 미발생 안내 -->
						<div
							v-if="!result.severance_pay?.qualified_for_severance"
							class="rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs text-amber-800 leading-relaxed"
						>
							{{ __('재직 1년 미만으로 퇴직금이 발생하지 않습니다 (근퇴법 제8조).') }}
						</div>

						<!-- 항목별 정산 내역 -->
						<div class="flex flex-col gap-2">
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">계속근로일수</span>
								<span class="text-sm text-[var(--k-ink)] k-numeric">{{ result.severance_pay?.continuous_service_days != null ? result.severance_pay.continuous_service_days + "일" : "-" }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">퇴직금 (세전)</span>
								<span class="text-sm font-semibold k-numeric k-amount">{{ formatKRW(summary.severance_pay_amount) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">퇴직소득세</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(summary.severance_income_tax) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">지방소득세</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(summary.severance_local_income_tax) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">미사용연차수당 (세전 근로소득)</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(summary.unused_leave_allowance) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">건강보험 정산 {{ settlementDirection(summary.health_insurance_settlement) }}</span>
								<span class="text-sm k-numeric k-amount" :class="summary.health_insurance_settlement > 0 ? 'font-semibold text-red-600' : 'text-[var(--k-ink)]'">{{ formatKRW(summary.health_insurance_settlement) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">장기요양 정산 {{ settlementDirection(summary.longterm_care_settlement) }}</span>
								<span class="text-sm k-numeric k-amount" :class="summary.longterm_care_settlement > 0 ? 'font-semibold text-red-600' : 'text-[var(--k-ink)]'">{{ formatKRW(summary.longterm_care_settlement) }}</span>
							</div>
							<div class="flex justify-between items-center">
								<span class="text-sm font-semibold text-[var(--k-ink)]">실지급 총액</span>
								<span class="text-sm font-bold k-numeric k-amount">{{ formatKRW(summary.net_total_payout) }}</span>
							</div>
						</div>

						<!-- 퇴직소득세 산출 근거 -->
						<div v-if="result.severance_income_tax" class="bg-[var(--k-surface-soft)] rounded-lg p-3 text-xs text-[var(--k-ink-muted)] leading-relaxed flex flex-col gap-1">
							<div class="k-label mb-1">퇴직소득세 산출 (소득세법 §48·§55②)</div>
							<div class="flex justify-between"><span>근속연수 (1년 미만 올림)</span><span class="k-numeric">{{ result.severance_income_tax.service_years_rounded }}년</span></div>
							<div class="flex justify-between k-amount"><span>근속연수공제</span><span class="k-numeric">{{ formatKRW(result.severance_income_tax.service_year_deduction) }}</span></div>
							<div class="flex justify-between k-amount"><span>환산급여</span><span class="k-numeric">{{ formatKRW(result.severance_income_tax.converted_wage) }}</span></div>
							<div class="flex justify-between k-amount"><span>환산급여공제</span><span class="k-numeric">{{ formatKRW(result.severance_income_tax.converted_wage_deduction) }}</span></div>
							<div class="flex justify-between k-amount"><span>과세표준</span><span class="k-numeric">{{ formatKRW(result.severance_income_tax.tax_base) }}</span></div>
							<div class="flex justify-between font-semibold k-amount"><span>소득세 (10원 절사)</span><span class="k-numeric">{{ formatKRW(result.severance_income_tax.income_tax) }}</span></div>
						</div>

						<!-- 퇴직금 계산식 -->
						<div v-if="result.severance_pay?.calculation_formula" class="bg-[var(--k-surface-soft)] rounded-lg p-3 text-xs text-[var(--k-ink-muted)] leading-relaxed">
							<div class="k-label mb-1">퇴직금 계산식 (근퇴법 제8조)</div>
							{{ result.severance_pay.calculation_formula }}
						</div>

						<!-- 건보정산 근거 -->
						<div v-if="result.health_insurance_reconciliation" class="bg-[var(--k-surface-soft)] rounded-lg p-3 text-xs text-[var(--k-ink-muted)] leading-relaxed flex flex-col gap-1">
							<div class="k-label mb-1">건보정산 (보수총액 확정)</div>
							<div class="flex justify-between"><span>산정월수 / 납부월수</span><span class="k-numeric">{{ result.health_insurance_reconciliation.calc_months }}개월 / {{ result.health_insurance_reconciliation.paid_months }}개월</span></div>
							<div class="flex justify-between k-amount"><span>확정 건강보험료</span><span class="k-numeric">{{ formatKRW(result.health_insurance_reconciliation.determined_health_insurance) }}</span></div>
							<div class="flex justify-between k-amount"><span>확정 장기요양보험료</span><span class="k-numeric">{{ formatKRW(result.health_insurance_reconciliation.determined_longterm_care) }}</span></div>
						</div>
					</template>
					<div v-else class="text-center py-8 text-[var(--k-ink-faint)] text-sm">
						{{ __('조건을 입력하고 계산 버튼을 눌러주세요.') }}
					</div>
				</div>

				<!-- 면책 고지 -->
				<div class="k-card p-3 text-xs text-[var(--k-ink-muted)] leading-relaxed">
					<span class="font-semibold text-[var(--k-ink)]">참고용 정산입니다.</span>
					미사용연차수당은 근로소득으로 중도퇴사 연말정산 대상이며, 이 화면의 실지급액은
					연차수당 원천징수 전 금액입니다. 확정 정산은 노무사 검토를 거쳐 확정하시기 바랍니다.
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, reactive, ref, inject } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import { severanceSettlement } from "@/data/koreaSeveranceSettlementRuntime"

const __ = inject("$translate")

const form = reactive({
	hire_date: "",
	severance_date: "",
	average_wage_per_day: null,
	ordinary_wage_per_day: null,
	monthly_base_salary: null,
	unused_leave_days: 0,
	paid_health_total: 0,
	paid_longterm_care_total: 0,
	mid_month_hire: false,
})
const useHealth = ref(false)
const remunerationText = ref("")
const result = ref(null)

const canSubmit = computed(
	() =>
		form.hire_date &&
		form.severance_date &&
		form.average_wage_per_day != null &&
		form.monthly_base_salary != null
)

const summary = computed(() => result.value?.payout_summary ?? {})

function formatKRW(amount) {
	if (amount == null) return "-"
	return Number(amount).toLocaleString("ko-KR") + "원"
}

function settlementDirection(amount) {
	if (!amount) return ""
	return amount > 0 ? "(추가납부)" : "(환급)"
}

function parseRemuneration() {
	const values = remunerationText.value
		.split(/[,\s]+/)
		.filter((v) => v !== "")
		.map(Number)
	return values.length && values.every((v) => Number.isFinite(v) && v >= 0) ? values : null
}

async function calculate() {
	result.value = null
	await severanceSettlement.submit({
		...form,
		ordinary_wage_per_day: form.ordinary_wage_per_day || null,
		monthly_remuneration_for_health: useHealth.value ? parseRemuneration() : null,
		paid_health_total: useHealth.value ? form.paid_health_total || 0 : 0,
		paid_longterm_care_total: useHealth.value ? form.paid_longterm_care_total || 0 : 0,
		mid_month_hire: useHealth.value ? form.mid_month_hire : false,
	})
	if (!severanceSettlement.error) {
		result.value = severanceSettlement.data
	}
}
</script>
