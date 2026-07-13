<template>
	<BaseLayout :pageTitle="__('취업규칙 점검 (§93·§94)')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 -->
				<div class="pt-1">
					<div class="k-eyebrow">WORK RULES REVIEW</div>
					<div class="mt-1 k-t-display text-[var(--k-ink)]">{{ __('취업규칙 점검 (§93·§94)') }}</div>
					<p class="mt-2 k-t-body text-[var(--k-ink-muted)]">
						근로기준법 제93조 필수기재 14개 항목의 커버리지를 점검하고, 제94조 변경 절차(의견청취/동의)를 확인합니다.
					</p>
				</div>

				<!-- 필수항목 체크리스트 -->
				<div class="k-card p-4 flex flex-col gap-3">
					<div class="k-t-headline text-[var(--k-ink)]">{{ __('§93 필수기재 14개 항목') }}</div>
					<p class="text-xs text-[var(--k-ink-faint)]">{{ __('현재 취업규칙에 규정되어 있는 항목을 체크하세요.') }}</p>
					<div v-if="listRequiredItems.loading && !items.length" class="text-sm text-[var(--k-ink-faint)] py-2">{{ __('불러오는 중...') }}</div>
					<div class="flex flex-col gap-2">
						<label
							v-for="item in items"
							:key="item.ho"
							class="flex items-start gap-2 py-1.5 px-2 rounded-lg hover:bg-[var(--k-surface-soft)] cursor-pointer"
						>
							<input type="checkbox" v-model="checked[item.ho]" class="mt-0.5" />
							<span class="text-sm text-[var(--k-ink)]">
								<span class="text-[var(--k-ink-faint)] mr-1">{{ item.ho }}호</span>{{ item.label }}
							</span>
						</label>
					</div>
					<button
						@click="checkCoverage"
						:disabled="checkRequiredItems.loading || !items.length"
						class="k-btn-primary w-full"
					>
						<span v-if="checkRequiredItems.loading">{{ __('확인 중...') }}</span>
						<span v-else>{{ __('커버리지 확인') }}</span>
					</button>
					<div v-if="checkRequiredItems.error" class="text-center py-2 text-red-600 text-sm">
						{{ __('확인에 실패했습니다. 잠시 후 다시 시도해 주세요.') }}
					</div>
				</div>

				<!-- 커버리지 결과 -->
				<template v-if="coverage">
					<div class="k-block k-block--cream -mx-1">
						<div class="k-eyebrow">COVERAGE</div>
						<div class="mt-1 text-sm font-medium text-[var(--k-ink-muted)]">{{ __('필수기재 커버리지') }}</div>
						<div class="k-display">{{ coveragePercent }}%</div>
						<div class="mt-2 h-2 rounded-full bg-[var(--k-hairline)] overflow-hidden">
							<div
								class="h-full rounded-full transition-all"
								:class="coveragePercent === 100 ? 'bg-green-600' : 'bg-black'"
								:style="{ width: coveragePercent + '%' }"
							></div>
						</div>
						<div class="mt-1 text-xs text-[var(--k-ink-faint)]">{{ coverage.covered.length }} / {{ items.length }} {{ __('항목 커버') }}</div>
					</div>

					<div v-if="coverage.missing.length" class="k-card p-4 flex flex-col gap-2">
						<div class="k-t-headline text-[var(--k-ink)]">{{ __('누락 항목') }}</div>
						<ul class="flex flex-col gap-1">
							<li v-for="m in coverage.missing" :key="m.ho" class="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-1.5">
								<span class="text-red-400 mr-1">{{ m.ho }}호</span>{{ m.label }}
							</li>
						</ul>
					</div>
					<div v-else class="k-card p-3 text-xs bg-green-50 border border-green-300 text-green-800 leading-relaxed">
						{{ __('✓ §93 필수기재 항목이 모두 커버되었습니다.') }}
					</div>

					<div class="k-card p-3 text-xs text-[var(--k-ink-faint)] leading-relaxed">{{ coverage.note }}</div>
				</template>

				<!-- 변경 절차 -->
				<div class="k-card p-4 flex flex-col gap-3">
					<div class="k-t-headline text-[var(--k-ink)]">{{ __('§94 변경 절차 안내') }}</div>
					<label class="flex items-center gap-2 cursor-pointer">
						<input type="checkbox" v-model="form.is_disadvantageous" />
						<span class="text-sm text-[var(--k-ink)]">{{ __('불이익 변경입니다 (근로조건을 근로자에게 불리하게 변경)') }}</span>
					</label>
					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('상시 근로자 수') }}</label>
							<input type="number" v-model.number="form.headcount" min="0" class="k-input k-numeric" />
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('과반수 노동조합 존재 여부') }}</label>
							<select v-model="form.has_majority_union" class="k-input">
								<option :value="null">{{ __('모름 / 미확인') }}</option>
								<option :value="true">{{ __('있음') }}</option>
								<option :value="false">{{ __('없음') }}</option>
							</select>
						</div>
					</div>
					<button
						@click="checkProcedure"
						:disabled="amendmentProcedure.loading"
						class="k-btn-primary w-full"
					>
						<span v-if="amendmentProcedure.loading">{{ __('확인 중...') }}</span>
						<span v-else>{{ __('절차 확인') }}</span>
					</button>
					<div v-if="amendmentProcedure.error" class="text-center py-2 text-red-600 text-sm">
						{{ __('확인에 실패했습니다. 상시 근로자 수를 확인해 주세요.') }}
					</div>
				</div>

				<!-- 절차 결과 -->
				<template v-if="procedure">
					<div class="k-card p-4 flex flex-col gap-3">
						<div class="flex items-center justify-between">
							<div class="k-t-headline text-[var(--k-ink)]">{{ __('진행 단계') }}</div>
							<span
								class="text-xs font-semibold px-2.5 py-1 rounded-full"
								:class="procedure.requirement === 'consent' ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'"
							>
								{{ procedure.requirement === 'consent' ? __('동의 필요') : __('의견청취') }}
							</span>
						</div>
						<div class="text-sm text-[var(--k-ink-muted)]">{{ __('대상') }}: {{ procedure.subject }}</div>
						<ol class="flex flex-col gap-2">
							<li
								v-for="(step, idx) in procedure.steps"
								:key="idx"
								class="flex gap-2 text-sm text-[var(--k-ink)] items-start"
							>
								<span class="k-numeric shrink-0 w-5 h-5 rounded-full bg-black text-white text-[11px] font-semibold flex items-center justify-center">{{ idx + 1 }}</span>
								<span>{{ step }}</span>
							</li>
						</ol>
					</div>

					<div class="k-card p-4 flex flex-col gap-2">
						<div class="flex items-center justify-between">
							<div class="k-t-headline text-[var(--k-ink)]">{{ __('§93 신고의무') }}</div>
							<span
								class="text-xs font-semibold px-2.5 py-1 rounded-full"
								:class="procedure.filing_obligation.required ? 'bg-red-100 text-red-700' : 'bg-[var(--k-hairline)] text-[var(--k-ink-muted)]'"
							>
								{{ procedure.filing_obligation.required ? __('신고 대상') : __('신고 의무 없음') }}
							</span>
						</div>
						<p class="text-sm text-[var(--k-ink-muted)]">{{ procedure.filing_obligation.note }}</p>
					</div>
				</template>

				<!-- 면책 고지 -->
				<div class="k-card p-3 text-xs text-[var(--k-ink-muted)] leading-relaxed">
					<span class="font-semibold text-[var(--k-ink)]">키워드 candidate 판정입니다.</span>
					있음/불충분의 최종 확정과 불이익변경 해당 여부 판단은 반드시 노무사가 원문을 검수하시기 바랍니다.
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, reactive, ref, inject, watch } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import { listRequiredItems, checkRequiredItems, amendmentProcedure } from "@/data/koreaWorkRulesRuntime"

const __ = inject("$translate")

const items = ref([])
const checked = reactive({})

watch(
	() => listRequiredItems.data,
	(data) => {
		if (data && Array.isArray(data)) {
			items.value = data
			for (const item of data) {
				if (!(item.ho in checked)) checked[item.ho] = false
			}
		}
	},
	{ immediate: true }
)

const coverage = ref(null)

const coveragePercent = computed(() => {
	if (!coverage.value) return 0
	return Math.round((coverage.value.coverage_ratio || 0) * 100)
})

async function checkCoverage() {
	coverage.value = null
	const markers = items.value.filter((item) => checked[item.ho]).map((item) => item.marker)
	await checkRequiredItems.submit({ rules_outline: markers })
	if (!checkRequiredItems.error) {
		coverage.value = checkRequiredItems.data
	}
}

const form = reactive({
	is_disadvantageous: false,
	headcount: null,
	has_majority_union: null,
})

const procedure = ref(null)

async function checkProcedure() {
	procedure.value = null
	await amendmentProcedure.submit({
		is_disadvantageous: form.is_disadvantageous,
		headcount: form.headcount ?? 0,
		has_majority_union: form.has_majority_union,
	})
	if (!amendmentProcedure.error) {
		procedure.value = amendmentProcedure.data
	}
}
</script>

<style scoped>
.k-input {
	border: 1px solid var(--k-hairline);
	border-radius: 0.5rem;
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	color: black;
	width: 100%;
}
.k-input:focus {
	outline: none;
	box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.6);
}
</style>
