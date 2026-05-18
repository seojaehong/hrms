<template>
	<BaseLayout :pageTitle="__('퇴직금 미리보기')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 입력 카드 -->
				<div class="bg-white rounded shadow-sm p-4 flex flex-col gap-4">
					<div class="text-base font-bold text-gray-800">{{ __('가정 조건 입력') }}</div>

					<div class="flex flex-col gap-1">
						<label class="text-xs text-gray-500 font-medium">{{ __('가정 퇴직일') }}</label>
						<input
							type="date"
							v-model="assumedRetirementDate"
							class="border border-gray-300 rounded px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 w-full"
						/>
					</div>

					<div class="flex flex-col gap-1">
						<label class="text-xs text-gray-500 font-medium">
							{{ __('통상임금 (원)') }}
							<span class="text-gray-400 font-normal">— 비워두면 자동 계산</span>
						</label>
						<input
							type="number"
							v-model.number="ordinaryWageOverride"
							:placeholder="__('예: 2500000')"
							class="border border-gray-300 rounded px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 w-full"
						/>
					</div>

					<button
						@click="calculate"
						:disabled="severancePreview.loading"
						class="w-full py-3 bg-blue-600 text-white text-sm rounded font-medium hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
					>
						<span v-if="severancePreview.loading">{{ __('계산 중...') }}</span>
						<span v-else>{{ __('퇴직금 계산') }}</span>
					</button>
				</div>

				<!-- 계산 결과 카드 -->
				<div class="bg-white rounded shadow-sm p-4 flex flex-col gap-4">
					<div class="text-base font-bold text-gray-800">{{ __('계산 결과') }}</div>

					<div v-if="severancePreview.loading" class="text-center py-8 text-gray-400 text-sm">
						{{ __('계산 중...') }}
					</div>
					<div v-else-if="severancePreview.error" class="text-center py-6 text-red-500 text-sm">
						{{ __('계산에 실패했습니다. 다시 시도해 주세요.') }}
					</div>
					<template v-else-if="result">
						<div class="flex flex-col gap-2">
							<div class="flex justify-between items-center border-b border-gray-100 pb-2">
								<span class="text-sm text-gray-600">입사일</span>
								<span class="text-sm text-gray-800">{{ result.date_of_joining ?? "-" }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-gray-100 pb-2">
								<span class="text-sm text-gray-600">가정 퇴직일</span>
								<span class="text-sm text-gray-800">{{ result.assumed_retirement_date ?? assumedRetirementDate }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-gray-100 pb-2">
								<span class="text-sm text-gray-600">계속근로일수</span>
								<span class="text-sm font-semibold text-gray-800">{{ result.continuous_service_days != null ? result.continuous_service_days + "일" : "-" }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-gray-100 pb-2">
								<span class="text-sm text-gray-600">평균임금 / 일</span>
								<span class="text-sm font-semibold text-gray-800">{{ formatKRW(result.average_daily_wage) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-gray-100 pb-2">
								<span class="text-sm text-gray-600">통상임금 / 일</span>
								<span class="text-sm text-gray-800">{{ formatKRW(result.ordinary_daily_wage) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-gray-200 pb-3 mt-1">
								<span class="text-base font-bold text-gray-800">퇴직금 (세전)</span>
								<span class="text-base font-bold text-blue-700">{{ formatKRW(result.severance_pay) }}</span>
							</div>
							<div class="flex justify-between items-center border-b border-gray-100 pb-2">
								<span class="text-sm text-gray-600">IRP 의무이체액</span>
								<span class="text-sm font-semibold text-gray-800">{{ formatKRW(result.irp_transfer_amount) }}</span>
							</div>
							<div class="flex justify-between items-center">
								<span class="text-sm text-gray-600">IRP 이체 한도</span>
								<span class="text-sm text-gray-700">{{ formatKRW(result.irp_transfer_limit) }}</span>
							</div>
						</div>

						<!-- 계산식 설명 -->
						<div v-if="result.formula_description" class="bg-gray-50 rounded p-3 text-xs text-gray-500 leading-relaxed">
							<div class="font-medium text-gray-600 mb-1">계산식</div>
							{{ result.formula_description }}
						</div>
					</template>
					<div v-else class="text-center py-8 text-gray-400 text-sm">
						{{ __('조건을 입력하고 계산 버튼을 눌러주세요.') }}
					</div>
				</div>

				<!-- 면책 고지 -->
				<div class="bg-yellow-50 border border-yellow-200 rounded p-3 text-xs text-yellow-800 leading-relaxed">
					<span class="font-semibold">참고용 미리보기입니다.</span>
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

onMounted(() => {
	// 페이지 진입 시 오늘 날짜로 자동 계산
	calculate()
})
</script>
