<template>
	<BaseLayout :pageTitle="__('포괄임금 설계·역산')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 -->
				<div class="pt-1">
					<div class="k-eyebrow">INCLUSIVE WAGE</div>
					<div class="mt-1 text-xl font-bold tracking-tight text-[var(--k-ink)]">{{ __('포괄임금 설계·역산') }}</div>
					<p class="mt-2 text-sm text-[var(--k-ink-muted)]">
						총액을 통상시급 기준으로 분해하거나, 기존 계약의 적법 최소 지급액을 검증합니다.
					</p>
				</div>

				<!-- 설계 섹션 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div>
						<div class="k-eyebrow">DESIGN</div>
						<div class="text-base font-bold tracking-tight text-[var(--k-ink)]">{{ __('설계 — 총액 분해') }}</div>
					</div>

					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('월 총액 (원)') }}</label>
						<input
							type="number"
							v-model.number="design.total_monthly"
							:placeholder="__('예: 3000000')"
							class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
						/>
					</div>
					<div class="grid grid-cols-3 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('고정연장 (h)') }}</label>
							<input
								type="number"
								v-model.number="design.fixed_ot_hours"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('고정야간 (h)') }}</label>
							<input
								type="number"
								v-model.number="design.fixed_night_hours"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('고정휴일 (h)') }}</label>
							<input
								type="number"
								v-model.number="design.fixed_holiday_hours"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
					</div>

					<button
						@click="runDesign"
						:disabled="inclusiveWageDesign.loading"
						class="k-btn-primary w-full"
					>
						<span v-if="inclusiveWageDesign.loading">{{ __('계산 중...') }}</span>
						<span v-else>{{ __('총액 분해') }}</span>
					</button>

					<div v-if="inclusiveWageDesign.error" class="text-center py-3 text-red-600 text-sm">
						{{ __('계산에 실패했습니다. 입력값을 확인해 주세요.') }}
					</div>
					<template v-else-if="designResult">
						<!-- 경고 배너 -->
						<div
							v-if="designResult.warnings?.length"
							class="rounded-lg bg-red-50 border border-red-200 p-3 flex flex-col gap-1"
						>
							<p v-for="(w, i) in designResult.warnings" :key="i" class="text-xs text-red-700 leading-relaxed">
								{{ w }}
							</p>
						</div>

						<!-- 통상시급 (cream 블록) -->
						<div class="k-block k-block--cream -mx-1">
							<div class="k-eyebrow">ORDINARY HOURLY WAGE</div>
							<div class="mt-1 text-sm font-medium text-[var(--k-ink-muted)]">통상시급</div>
							<div class="k-display">{{ formatKRW(Math.round(designResult.ordinary_hourly_wage)) }}</div>
							<p class="mt-1 text-[11px] text-[var(--k-ink-muted)] k-numeric">
								최저임금 {{ formatKRW(designResult.minimum_hourly_wage) }} —
								{{ designResult.legal_floor_ok ? "충족" : "미달" }}
							</p>
						</div>

						<!-- 항목 분해 -->
						<div class="flex flex-col gap-2">
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">기본급</span>
								<span class="text-sm font-semibold k-numeric k-amount">{{ formatKRW(designResult.base_pay) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">고정연장수당</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(designResult.fixed_ot_pay) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">야간수당 (가산분)</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(designResult.night_pay) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">휴일수당</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(designResult.holiday_pay) }}</span>
							</div>
							<div class="flex justify-between items-center">
								<span class="text-sm font-semibold text-[var(--k-ink)]">합계 검산</span>
								<span class="text-sm font-bold k-numeric k-amount">{{ formatKRW(designResult.total) }}</span>
							</div>
						</div>
					</template>
				</div>

				<!-- 역산 감사 섹션 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div>
						<div class="k-eyebrow">AUDIT</div>
						<div class="text-base font-bold tracking-tight text-[var(--k-ink)]">{{ __('역산 감사 — 기존 계약 검증') }}</div>
					</div>

					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('기본급 (원)') }}</label>
						<input
							type="number"
							v-model.number="audit.base_pay"
							:placeholder="__('예: 2623431')"
							class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
						/>
					</div>
					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('연장수당 기재액 (원)') }}</label>
							<input
								type="number"
								v-model.number="audit.fixed_ot_pay"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('고정연장 (h)') }}</label>
							<input
								type="number"
								v-model.number="audit.fixed_ot_hours"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('야간수당 기재액 (원)') }}</label>
							<input
								type="number"
								v-model.number="audit.fixed_night_pay"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('고정야간 (h)') }}</label>
							<input
								type="number"
								v-model.number="audit.fixed_night_hours"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('휴일수당 기재액 (원)') }}</label>
							<input
								type="number"
								v-model.number="audit.fixed_holiday_pay"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('고정휴일 (h)') }}</label>
							<input
								type="number"
								v-model.number="audit.fixed_holiday_hours"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
					</div>

					<button
						@click="runAudit"
						:disabled="inclusiveWageAudit.loading"
						class="k-btn-primary w-full"
					>
						<span v-if="inclusiveWageAudit.loading">{{ __('감사 중...') }}</span>
						<span v-else>{{ __('역산 감사') }}</span>
					</button>

					<div v-if="inclusiveWageAudit.error" class="text-center py-3 text-red-600 text-sm">
						{{ __('감사에 실패했습니다. 입력값을 확인해 주세요.') }}
					</div>
					<template v-else-if="auditResult">
						<!-- 경고 배너 -->
						<div
							v-if="auditResult.warnings?.length"
							class="rounded-lg bg-red-50 border border-red-200 p-3 flex flex-col gap-1"
						>
							<p v-for="(w, i) in auditResult.warnings" :key="i" class="text-xs text-red-700 leading-relaxed">
								{{ w }}
							</p>
						</div>
						<div
							v-else
							class="rounded-lg bg-green-50 border border-green-200 p-3 text-xs text-green-700 leading-relaxed"
						>
							{{ __('부족분 없음 — 계약 기재액이 적법 최소 지급액을 충족합니다.') }}
						</div>

						<div class="flex flex-col gap-2">
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">통상시급 (기본급 ÷ 209h)</span>
								<span class="text-sm font-semibold k-numeric k-amount">{{ formatKRW(Math.round(auditResult.ordinary_hourly_wage)) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">적정 연장수당</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(auditResult.expected_ot_pay) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">연장 부족분</span>
								<span class="text-sm k-numeric k-amount" :class="auditResult.ot_shortfall > 0 ? 'font-semibold text-red-600' : 'text-[var(--k-ink)]'">{{ formatKRW(auditResult.ot_shortfall) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">적정 야간수당</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(auditResult.expected_night_pay) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">야간 부족분</span>
								<span class="text-sm k-numeric k-amount" :class="auditResult.night_shortfall > 0 ? 'font-semibold text-red-600' : 'text-[var(--k-ink)]'">{{ formatKRW(auditResult.night_shortfall) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">적정 휴일수당</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(auditResult.expected_holiday_pay) }}</span>
							</div>
							<div class="flex justify-between items-center">
								<span class="text-sm text-[var(--k-ink-muted)]">휴일 부족분</span>
								<span class="text-sm k-numeric k-amount" :class="auditResult.holiday_shortfall > 0 ? 'font-semibold text-red-600' : 'text-[var(--k-ink)]'">{{ formatKRW(auditResult.holiday_shortfall) }}</span>
							</div>
						</div>
					</template>
				</div>

				<!-- NET 역산 섹션 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div>
						<div class="k-eyebrow">NET REVERSE</div>
						<div class="text-base font-bold tracking-tight text-[var(--k-ink)]">{{ __('NET 역산 — 세후 → 세전') }}</div>
						<p class="mt-1 text-xs text-[var(--k-ink-muted)]">
							목표 실수령액을 만족하는 최소 세전 총액을 4대보험·간이세액표 기준으로 찾습니다.
						</p>
					</div>

					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('목표 실수령액 (원)') }}</label>
							<input
								type="number"
								v-model.number="reverse.target_net"
								:placeholder="__('예: 3000000')"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('월 비과세 (식대 등)') }}</label>
							<input
								type="number"
								v-model.number="reverse.non_taxable"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('부양가족 수 (본인 포함)') }}</label>
							<input
								type="number"
								v-model.number="reverse.dependents"
								min="1"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('국민연금 수동액 (선택)') }}</label>
							<input
								type="number"
								v-model.number="reverse.pension_override"
								:placeholder="__('기준소득월액 결정분')"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
					</div>

					<div class="flex flex-wrap gap-x-4 gap-y-2">
						<label class="flex items-center gap-1.5 text-sm text-[var(--k-ink-muted)]">
							<input type="checkbox" v-model="reverse.include_pension" class="accent-black" />
							{{ __('국민연금') }}
						</label>
						<label class="flex items-center gap-1.5 text-sm text-[var(--k-ink-muted)]">
							<input type="checkbox" v-model="reverse.include_health" class="accent-black" />
							{{ __('건강보험') }}
						</label>
						<label class="flex items-center gap-1.5 text-sm text-[var(--k-ink-muted)]">
							<input type="checkbox" v-model="reverse.include_longterm_care" class="accent-black" />
							{{ __('장기요양') }}
						</label>
						<label class="flex items-center gap-1.5 text-sm text-[var(--k-ink-muted)]">
							<input type="checkbox" v-model="reverse.include_employment" class="accent-black" />
							{{ __('고용보험') }}
						</label>
					</div>

					<button
						@click="runReverse"
						:disabled="inclusiveWageReverseNet.loading || !reverse.target_net"
						class="k-btn-primary w-full"
					>
						<span v-if="inclusiveWageReverseNet.loading">{{ __('역산 중...') }}</span>
						<span v-else>{{ __('세전 총액 역산') }}</span>
					</button>

					<div v-if="inclusiveWageReverseNet.error" class="text-center py-3 text-red-600 text-sm">
						{{ __('역산에 실패했습니다. 입력값을 확인해 주세요.') }}
					</div>
					<template v-else-if="reverseResult">
						<!-- 세전 총액 (cream 블록) -->
						<div class="k-block k-block--cream -mx-1">
							<div class="k-eyebrow">REQUIRED GROSS</div>
							<div class="mt-1 text-sm font-medium text-[var(--k-ink-muted)]">필요 세전 총액</div>
							<div class="k-display">{{ formatKRW(reverseResult.gross) }}</div>
							<p class="mt-1 text-[11px] text-[var(--k-ink-muted)] k-numeric">
								실수령 {{ formatKRW(reverseResult.achieved_net) }}
								<template v-if="!reverseResult.exact">
									(목표 대비 +{{ reverseResult.diff.toLocaleString("ko-KR") }}원 — 절사 경계로 정확 일치 불가)
								</template>
							</p>
						</div>

						<div class="flex flex-col gap-2">
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">국민연금</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(reverseResult.deductions.pension) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">건강보험</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(reverseResult.deductions.health) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">장기요양</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(reverseResult.deductions.longterm_care) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">고용보험</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(reverseResult.deductions.employment) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">소득세</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(reverseResult.deductions.income_tax) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">지방소득세</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(reverseResult.deductions.local_income_tax) }}</span>
							</div>
							<div class="flex justify-between items-center">
								<span class="text-sm font-semibold text-[var(--k-ink)]">공제 합계</span>
								<span class="text-sm font-bold k-numeric k-amount">{{ formatKRW(reverseResult.deductions.total) }}</span>
							</div>
						</div>
					</template>
				</div>

				<!-- 면책 고지 -->
				<div class="k-card p-3 text-xs text-[var(--k-ink-muted)] leading-relaxed">
					<span class="font-semibold text-[var(--k-ink)]">참고용 계산입니다.</span>
					최저시급은 서버의 승인된 법정수치를 사용하며, 계약 유지·재설계 판단은
					노무사 검토를 거쳐 확정하시기 바랍니다.
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { reactive, ref, inject } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import {
	inclusiveWageDesign,
	inclusiveWageAudit,
	inclusiveWageReverseNet,
} from "@/data/koreaInclusiveWageRuntime"

const __ = inject("$translate")

const design = reactive({
	total_monthly: null,
	fixed_ot_hours: 0,
	fixed_night_hours: 0,
	fixed_holiday_hours: 0,
})
const audit = reactive({
	base_pay: null,
	fixed_ot_pay: 0,
	fixed_ot_hours: 0,
	fixed_night_pay: 0,
	fixed_night_hours: 0,
	fixed_holiday_pay: 0,
	fixed_holiday_hours: 0,
})
const reverse = reactive({
	target_net: null,
	non_taxable: 200000,
	dependents: 1,
	pension_override: null,
	include_pension: true,
	include_health: true,
	include_longterm_care: true,
	include_employment: true,
})
const designResult = ref(null)
const auditResult = ref(null)
const reverseResult = ref(null)

function formatKRW(amount) {
	if (amount == null) return "-"
	return Number(amount).toLocaleString("ko-KR") + "원"
}

async function runDesign() {
	designResult.value = null
	await inclusiveWageDesign.submit({ ...design })
	if (!inclusiveWageDesign.error) {
		designResult.value = inclusiveWageDesign.data
	}
}

async function runReverse() {
	reverseResult.value = null
	await inclusiveWageReverseNet.submit({ ...reverse })
	if (!inclusiveWageReverseNet.error) {
		reverseResult.value = inclusiveWageReverseNet.data
	}
}

async function runAudit() {
	auditResult.value = null
	await inclusiveWageAudit.submit({ ...audit })
	if (!inclusiveWageAudit.error) {
		auditResult.value = inclusiveWageAudit.data
	}
}
</script>
