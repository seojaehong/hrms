<template>
	<BaseLayout :pageTitle="__('임금명세서 분해 (§48②)')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 -->
				<div class="pt-1">
					<div class="k-eyebrow">PAYSLIP BREAKDOWN</div>
					<div class="mt-1 k-t-display text-[var(--k-ink)]">{{ __('임금명세서 분해 (§48②)') }}</div>
					<p class="mt-2 k-t-body text-[var(--k-ink-muted)]">
						근로기준법 시행령 제27조의2·제48조제2항에 따라 임금 구성항목별 계산방법을 표기한 명세서 초안을 만듭니다.
					</p>
				</div>

				<!-- 입력 카드 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div class="k-t-headline text-[var(--k-ink)]">{{ __('명세서 입력') }}</div>

					<!-- 급여형태 토글 -->
					<div class="flex rounded-lg border border-[var(--k-hairline)] p-1 text-sm font-semibold">
						<button
							class="flex-1 py-2 rounded-md transition-colors"
							:class="form.wage_type === 'monthly' ? 'k-segment-active' : 'text-[var(--k-ink-muted)]'"
							@click="form.wage_type = 'monthly'"
						>{{ __('월급제') }}</button>
						<button
							class="flex-1 py-2 rounded-md transition-colors"
							:class="form.wage_type === 'hourly' ? 'k-segment-active' : 'text-[var(--k-ink-muted)]'"
							@click="form.wage_type = 'hourly'"
						>{{ __('시급제') }}</button>
					</div>

					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('근로자 이름') }}</label>
							<input
								type="text"
								v-model="form.employee"
								:placeholder="__('예: 김가상')"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('임금 산정기간') }}</label>
							<input
								type="month"
								v-model="form.period"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
					</div>

					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('임금 지급일') }}</label>
						<input
							type="date"
							v-model="form.payment_date"
							class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
						/>
					</div>

					<!-- 월급제 입력 -->
					<div v-if="form.wage_type === 'monthly'" class="flex flex-col gap-1">
						<label class="k-label">{{ __('월 기본급 (원)') }}</label>
						<input
							type="number"
							v-model.number="form.base_salary"
							:placeholder="__('예: 2156880')"
							class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
						/>
					</div>

					<!-- 시급제 입력 -->
					<template v-else>
						<div class="grid grid-cols-2 gap-2">
							<div class="flex flex-col gap-1">
								<label class="k-label">{{ __('시급 (원)') }}</label>
								<input
									type="number"
									v-model.number="form.hourly_rate"
									:placeholder="__('예: 10320')"
									class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
								/>
							</div>
							<div class="flex flex-col gap-1">
								<label class="k-label">{{ __('소정근로시간 (h)') }}</label>
								<input
									type="number"
									v-model.number="form.regular_hours"
									class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
								/>
							</div>
						</div>
						<div class="grid grid-cols-2 gap-2">
							<div class="flex flex-col gap-1">
								<label class="k-label">{{ __('주 계약시간 (h)') }}</label>
								<input
									type="number"
									v-model.number="form.contracted_weekly_hours"
									:placeholder="__('예: 40')"
									class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
								/>
							</div>
							<div class="flex items-center gap-2 pt-5">
								<input id="perfect-attendance" type="checkbox" v-model="form.perfect_attendance" class="accent-black" />
								<label for="perfect-attendance" class="text-sm text-[var(--k-ink-muted)]">{{ __('개근') }}</label>
							</div>
						</div>
					</template>

					<!-- 가산 시간 -->
					<div class="text-xs font-semibold text-[var(--k-ink-faint)] uppercase tracking-wide mt-1">{{ __('가산 시간 (선택)') }}</div>
					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('연장근로 (h)') }}</label>
							<input type="number" v-model.number="form.overtime_hours" class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full" />
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('야간근로 (h)') }}</label>
							<input type="number" v-model.number="form.night_hours" class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full" />
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('휴일근로 (h)') }}</label>
							<input type="number" v-model.number="form.holiday_work_hours" class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full" />
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('연차수당 (h)') }}</label>
							<input type="number" v-model.number="form.annual_leave_hours" class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full" />
						</div>
					</div>

					<button
						@click="calculate"
						:disabled="buildPayslipBreakdown.loading || !canSubmit"
						class="k-btn-primary w-full"
					>
						<span v-if="buildPayslipBreakdown.loading">{{ __('계산 중...') }}</span>
						<span v-else>{{ __('명세서 생성') }}</span>
					</button>

					<div v-if="buildPayslipBreakdown.error" class="text-center py-2 text-red-600 text-sm">
						{{ __('계산에 실패했습니다. 입력값을 확인해 주세요.') }}
					</div>
				</div>

				<!-- 결과 카드 -->
				<template v-if="breakdown">
					<div v-if="!breakdown.compliance.compliant" class="k-card p-3 text-xs bg-amber-50 border border-amber-300 text-amber-800 leading-relaxed">
						{{ __('⚠ §48② 위반 위험 — 계산방법 미기재 항목: ') }}{{ breakdown.compliance.missing_basis_labels.join(', ') }}
					</div>

					<div class="k-card p-4 flex flex-col gap-3">
						<div class="k-t-headline text-[var(--k-ink)]">{{ __('지급내역') }}</div>
						<table class="w-full text-sm">
							<thead>
								<tr class="text-left text-[var(--k-ink-faint)] text-xs uppercase tracking-wide">
									<th class="pb-2 font-semibold">{{ __('항목') }}</th>
									<th class="pb-2 font-semibold text-right">{{ __('금액') }}</th>
									<th class="pb-2 font-semibold">{{ __('계산방법') }}</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="(line, idx) in breakdown.earnings" :key="'e' + idx" class="border-t border-[var(--k-hairline)]">
									<td class="py-2 font-medium text-[var(--k-ink)]">{{ line.label }}</td>
									<td class="py-2 text-right k-numeric k-amount">{{ formatKRW(line.amount) }}</td>
									<td class="py-2 text-xs text-[var(--k-ink-muted)]">{{ line.basis || __('(계산방법 미기재)') }}</td>
								</tr>
							</tbody>
						</table>
						<div class="k-block k-block--cream -mx-1 mt-1">
							<div class="k-eyebrow">GROSS PAY</div>
							<div class="mt-1 text-sm font-medium text-[var(--k-ink-muted)]">{{ __('지급합계') }}</div>
							<div class="k-display">{{ formatKRW(breakdown.gross_pay) }}</div>
						</div>
					</div>

					<div class="k-card p-4 flex flex-col gap-3">
						<div class="k-t-headline text-[var(--k-ink)]">{{ __('공제내역') }}</div>
						<table class="w-full text-sm">
							<thead>
								<tr class="text-left text-[var(--k-ink-faint)] text-xs uppercase tracking-wide">
									<th class="pb-2 font-semibold">{{ __('항목') }}</th>
									<th class="pb-2 font-semibold text-right">{{ __('금액') }}</th>
									<th class="pb-2 font-semibold">{{ __('산출근거') }}</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="(line, idx) in breakdown.deductions" :key="'d' + idx" class="border-t border-[var(--k-hairline)]">
									<td class="py-2 font-medium text-[var(--k-ink)]">{{ line.label }}</td>
									<td class="py-2 text-right k-numeric k-amount">{{ formatKRW(line.amount) }}</td>
									<td class="py-2 text-xs text-[var(--k-ink-muted)]">{{ line.basis || __('(산출근거 미기재)') }}</td>
								</tr>
							</tbody>
						</table>
						<div class="flex justify-between text-sm pt-2 border-t border-[var(--k-hairline)]">
							<span class="text-[var(--k-ink-muted)]">{{ __('공제합계') }}</span>
							<span class="k-numeric font-semibold k-amount">{{ formatKRW(breakdown.total_deductions) }}</span>
						</div>
					</div>

					<div class="k-block k-block--cream -mx-1">
						<div class="k-eyebrow">NET PAY</div>
						<div class="mt-1 text-sm font-medium text-[var(--k-ink-muted)]">{{ __('실지급액') }}</div>
						<div class="k-display k-settled">{{ formatKRW(breakdown.net_pay) }}</div>
					</div>

					<!-- 마크다운 미리보기 -->
					<div class="k-card p-4 flex flex-col gap-3">
						<div class="k-t-headline text-[var(--k-ink)]">{{ __('교부용 마크다운 미리보기') }}</div>
						<button
							@click="generateMarkdown"
							:disabled="renderPayslipMarkdown.loading"
							class="k-btn-secondary w-full"
						>
							<span v-if="renderPayslipMarkdown.loading">{{ __('생성 중...') }}</span>
							<span v-else>{{ __('마크다운 생성') }}</span>
						</button>
						<template v-if="markdown">
							<div class="bg-[var(--k-surface-soft)] rounded-lg p-3 text-xs text-[var(--k-ink-muted)] leading-relaxed whitespace-pre-wrap font-mono max-h-96 overflow-y-auto">{{ markdown }}</div>
							<button
								@click="copyMarkdown"
								class="k-btn-secondary w-full"
							>{{ copied ? __('복사됨 ✓') : __('마크다운 복사') }}</button>
						</template>
					</div>
				</template>

				<!-- 면책 고지 -->
				<div class="k-card p-3 text-xs text-[var(--k-ink-muted)] leading-relaxed">
					<span class="font-semibold text-[var(--k-ink)]">참고용 초안입니다.</span>
					실제 교부 전 항목별 금액·계산방법과 공제내역을 반드시 검토하시기 바랍니다.
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, reactive, ref, inject } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import { buildPayslipBreakdown, renderPayslipMarkdown } from "@/data/koreaPayslipBreakdownRuntime"

const __ = inject("$translate")

const form = reactive({
	employee: "",
	period: new Date().toISOString().slice(0, 7),
	payment_date: "",
	wage_type: "monthly",
	base_salary: null,
	hourly_rate: null,
	regular_hours: 160,
	contracted_weekly_hours: 40,
	perfect_attendance: true,
	overtime_hours: 0,
	night_hours: 0,
	holiday_work_hours: 0,
	annual_leave_hours: 0,
})

const breakdown = ref(null)
const markdown = ref(null)
const copied = ref(false)

const canSubmit = computed(() => {
	if (!form.employee || !form.period || !form.payment_date) return false
	if (form.wage_type === "monthly") return form.base_salary != null
	return form.hourly_rate != null && form.contracted_weekly_hours != null
})

function formatKRW(amount) {
	if (amount == null) return "-"
	return Number(amount).toLocaleString("ko-KR") + "원"
}

async function calculate() {
	breakdown.value = null
	markdown.value = null
	copied.value = false
	await buildPayslipBreakdown.submit({ ...form })
	if (!buildPayslipBreakdown.error) {
		breakdown.value = buildPayslipBreakdown.data
	}
}

async function generateMarkdown() {
	if (!breakdown.value) return
	markdown.value = null
	await renderPayslipMarkdown.submit({ breakdown: JSON.stringify(breakdown.value) })
	if (!renderPayslipMarkdown.error) {
		markdown.value = renderPayslipMarkdown.data
	}
}

async function copyMarkdown() {
	if (!markdown.value) return
	await navigator.clipboard.writeText(markdown.value)
	copied.value = true
	setTimeout(() => (copied.value = false), 2000)
}
</script>
