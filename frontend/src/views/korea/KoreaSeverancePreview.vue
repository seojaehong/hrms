<template>
	<BaseLayout :pageTitle="__('퇴직금 미리보기')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 — cream 색블록 -->
				<div class="pt-1">
					<div class="k-eyebrow">SEVERANCE</div>
					<div class="mt-1 text-xl font-bold tracking-tight text-[var(--k-ink)]">{{ __('퇴직금 미리보기') }}</div>
					<p class="mt-2 text-sm text-[var(--k-ink-muted)]">
						가정 퇴직일 기준으로 예상 퇴직금을 미리 확인합니다.
					</p>
				</div>

				<!-- 입력 카드 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div class="text-base font-bold tracking-tight text-[var(--k-ink)]">{{ __('가정 조건 입력') }}</div>

					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('가정 퇴직일') }}</label>
						<input
							type="date"
							v-model="assumedRetirementDate"
							class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
						/>
					</div>

					<div class="flex flex-col gap-1">
						<label class="k-eyebrow">
							{{ __('1일 통상임금 (원)') }}
							<span class="normal-case tracking-normal opacity-70">— 비워두면 자동 계산</span>
						</label>
						<input
							type="number"
							v-model.number="ordinaryWageOverride"
							:placeholder="__('예: 120000')"
							class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
						/>
					</div>

					<button
						@click="calculate"
						:disabled="severancePreview.loading"
						class="k-btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
					>
						<span v-if="severancePreview.loading">{{ __('계산 중...') }}</span>
						<span v-else>{{ __('퇴직금 계산') }}</span>
					</button>
				</div>

				<!-- 계산 결과 카드 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div class="text-base font-bold tracking-tight text-[var(--k-ink)]">{{ __('계산 결과') }}</div>

					<div v-if="severancePreview.loading" class="text-center py-8 text-[var(--k-ink-faint)] text-sm">
						{{ __('계산 중...') }}
					</div>
					<div v-else-if="severancePreview.error" class="text-center py-6 text-red-600 text-sm">
						{{ __('계산에 실패했습니다. 다시 시도해 주세요.') }}
					</div>
					<template v-else-if="result">
						<!-- 주인공: 예상 퇴직금 (cream 블록) -->
						<div class="k-block k-block--cream -mx-1">
							<div class="k-eyebrow">ESTIMATED SEVERANCE</div>
							<div class="mt-1 text-sm font-medium text-[var(--k-ink-muted)]">퇴직금 (세전)</div>
							<div class="k-display">
								{{ formatKRW(result.severance_pay) }}
							</div>
							<div class="mt-4 grid grid-cols-3 gap-2">
								<div class="rounded-lg bg-white/55 px-3 py-2 text-center">
									<p class="k-numeric text-sm font-bold text-[var(--k-ink)]">{{ result.continuous_service_days != null ? result.continuous_service_days + "일" : "-" }}</p>
									<p class="text-[11px] text-[var(--k-ink-muted)]">계속근로</p>
								</div>
								<div class="rounded-lg bg-white/55 px-3 py-2 text-center">
									<p class="k-numeric text-sm font-bold k-amount">{{ formatKRW(result.average_daily_wage) }}</p>
									<p class="text-[11px] text-[var(--k-ink-muted)]">1일 평균임금</p>
								</div>
								<div class="rounded-lg bg-black px-3 py-2 text-center">
									<p class="k-numeric text-sm font-bold text-white k-amount">{{ formatKRW(result.severance_pay) }}</p>
									<p class="text-[11px] text-white/60">퇴직금</p>
								</div>
							</div>
						</div>

						<div class="flex flex-col gap-2">
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">입사일</span>
								<span class="text-sm text-[var(--k-ink)] k-numeric">{{ result.date_of_joining ?? "-" }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">가정 퇴직일</span>
								<span class="text-sm text-[var(--k-ink)] k-numeric">{{ result.assumed_retirement_date ?? assumedRetirementDate }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">계속근로일수</span>
								<span class="text-sm font-semibold text-[var(--k-ink)] k-numeric">{{ result.continuous_service_days != null ? result.continuous_service_days + "일" : "-" }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">평균임금 / 일</span>
								<span class="text-sm font-semibold k-numeric k-amount">{{ formatKRW(result.average_daily_wage) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">통상임금 / 일</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(result.ordinary_daily_wage) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-[var(--k-hairline-soft)] pb-2">
								<span class="text-sm text-[var(--k-ink-muted)]">IRP 의무이체액</span>
								<span class="text-sm font-semibold k-numeric k-amount">{{ formatKRW(result.irp_transfer_amount) }}</span>
							</div>
							<div class="flex justify-between items-center">
								<span class="text-sm text-[var(--k-ink-muted)]">IRP 이체 한도</span>
								<span class="text-sm k-numeric k-amount">{{ formatKRW(result.irp_transfer_limit) }}</span>
							</div>
						</div>

						<!-- 계산식 설명 -->
						<div v-if="result.formula_description" class="bg-[var(--k-surface-soft)] rounded-lg p-3 text-xs text-[var(--k-ink-muted)] leading-relaxed">
							<div class="k-label mb-1">계산식</div>
							{{ result.formula_description }}
						</div>
					</template>
					<div v-else class="text-center py-8 text-[var(--k-ink-faint)] text-sm">
						{{ __('조건을 입력하고 계산 버튼을 눌러주세요.') }}
					</div>
				</div>

				<!-- 퇴직정산(통합) 바로가기 -->
				<router-link
					:to="{ name: 'KoreaSeveranceSettlement' }"
					class="w-full py-3 border border-[var(--k-ink)] text-[var(--k-ink)] text-sm rounded-full font-semibold text-center hover:bg-[var(--k-surface-soft)] active:bg-[var(--k-hairline)] transition-colors"
				>
					{{ __('퇴직정산 (통합) — 세금·건보정산까지 계산') }}
				</router-link>

				<!-- 면책 고지 -->
				<div class="k-card p-3 text-xs text-[var(--k-ink-muted)] leading-relaxed">
					<span class="font-semibold text-[var(--k-ink)]">참고용 미리보기입니다.</span>
					정확한 금액은 실제 퇴직 시 산정 기준(평균임금, 근로일수 등)에 따라 달라질 수 있습니다.
					법적 효력이 있는 퇴직금 산정은 실제 퇴직일을 기준으로 확인하시기 바랍니다.
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { ref, inject, onMounted } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import { severancePreview } from "@/data/koreaSeverancePreviewRuntime"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")

const today = dayjs().format("YYYY-MM-DD")
const assumedRetirementDate = ref(today)
const ordinaryWageOverride = ref(null)
const result = ref(null)

function formatKRW(amount) {
	if (amount == null) return "-"
	return Number(amount).toLocaleString("ko-KR") + "원"
}

async function calculate() {
	result.value = null
	await severancePreview.submit({
		employee: employee.data?.name,
		assumed_retirement_date: assumedRetirementDate.value,
		ordinary_wage_override: ordinaryWageOverride.value || null,
	})
	if (!severancePreview.error) {
		result.value = severancePreview.data
	}
}

onMounted(async () => {
	// $employee 리소스 로딩 대기(경쟁 조건 방지) 후 오늘 날짜로 자동 계산
	try { await employee?.promise } catch { /* 미로그인 폴백 */ }
	calculate()
})
</script>
