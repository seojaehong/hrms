<template>
	<BaseLayout :pageTitle="__('근로감독 대비 체크리스트')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 -->
				<div class="pt-1">
					<div class="k-eyebrow">LABOR INSPECTION READINESS</div>
					<div class="mt-1 text-xl font-bold tracking-tight text-[var(--k-ink)]">{{ __('근로감독 대비 체크리스트') }}</div>
					<p class="mt-2 text-sm text-[var(--k-ink-muted)]">
						고용노동부 근로감독관 자율점검표 기반 15항목을 근거 조항·증빙서류·리스크와 함께 점검합니다.
					</p>
				</div>

				<div v-if="listInspectionChecklist.loading && !items.length" class="text-sm text-[var(--k-ink-faint)] py-2">{{ __('불러오는 중...') }}</div>
				<div v-if="listInspectionChecklist.error" class="text-center py-2 text-red-600 text-sm">
					{{ __('체크리스트를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.') }}
				</div>

				<!-- 진행률 -->
				<div v-if="items.length" class="k-block k-block--cream -mx-1">
					<div class="k-eyebrow">PROGRESS</div>
					<div class="mt-1 text-sm font-medium text-[var(--k-ink-muted)]">{{ __('점검 완료율') }}</div>
					<div class="k-display">{{ progressPercent }}%</div>
					<div class="mt-2 h-2 rounded-full bg-[var(--k-hairline)] overflow-hidden">
						<div
							class="h-full rounded-full transition-all"
							:class="progressPercent === 100 ? 'bg-green-600' : 'bg-black'"
							:style="{ width: progressPercent + '%' }"
						></div>
					</div>
					<div class="mt-1 text-xs text-[var(--k-ink-faint)]">{{ completedCount }} / {{ items.length }} {{ __('항목 완료') }}</div>
				</div>

				<!-- 카테고리 그룹 아코디언 -->
				<div v-for="group in groupedItems" :key="group.category" class="k-card p-0 overflow-hidden">
					<button
						@click="toggleCategory(group.category)"
						class="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[var(--k-surface-soft)] transition-colors"
					>
						<div class="flex items-center gap-2">
							<span class="text-base font-bold tracking-tight text-[var(--k-ink)]">{{ group.category }}</span>
							<span class="text-xs text-[var(--k-ink-faint)]">({{ group.items.length }})</span>
						</div>
						<div class="flex items-center gap-2">
							<span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-[var(--k-hairline)] text-[var(--k-ink-muted)]">
								{{ group.completedCount }}/{{ group.items.length }}
							</span>
							<span class="text-[var(--k-ink-faint)] transition-transform" :class="{ 'rotate-180': openCategories[group.category] }">▾</span>
						</div>
					</button>

					<div v-show="openCategories[group.category]" class="flex flex-col gap-2 px-4 pb-4">
						<div
							v-for="item in group.items"
							:key="item.id"
							class="rounded-lg border border-[var(--k-hairline)] p-3 flex flex-col gap-2"
							:class="completed[item.id] ? 'bg-green-50/60 border-green-200' : ''"
						>
							<label class="flex items-start gap-2 cursor-pointer">
								<input type="checkbox" v-model="completed[item.id]" class="mt-0.5" />
								<span class="text-sm font-medium text-[var(--k-ink)]">
									<span class="text-[var(--k-ink-faint)] mr-1">{{ item.id }}</span>{{ item.item }}
								</span>
							</label>

							<div class="pl-6 flex flex-col gap-1.5 text-xs text-[var(--k-ink-muted)]">
								<div><span class="font-semibold text-[var(--k-ink-muted)]">{{ __('근거') }}:</span> {{ item.legal_basis }}</div>
								<div>
									<span class="font-semibold text-[var(--k-ink-muted)]">{{ __('증빙서류') }}:</span>
									{{ item.evidence_needed.join(', ') }}
								</div>
								<div class="flex items-center gap-2 flex-wrap">
									<span class="font-semibold text-[var(--k-ink-muted)]">{{ __('리스크') }}:</span>
									<span class="px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-semibold">
										{{ item.risk.type }}<template v-if="item.risk.amount"> · {{ item.risk.amount }}</template>
									</span>
								</div>
								<div v-if="item.risk.note" class="text-[var(--k-ink-faint)]">{{ item.risk.note }}</div>
								<div class="flex items-center gap-2">
									<span class="font-semibold text-[var(--k-ink-muted)]">{{ __('자동점검') }}:</span>
									<span
										class="px-2 py-0.5 rounded-full font-semibold"
										:class="isAutomated(item) ? 'bg-blue-100 text-blue-700' : 'bg-[var(--k-hairline)] text-[var(--k-ink-faint)]'"
									>
										{{ isAutomated(item) ? item.automated_check : __('미확인 (수동 점검 필요)') }}
									</span>
								</div>
							</div>
						</div>
					</div>
				</div>

				<!-- 면책 고지 -->
				<div class="k-card p-3 text-xs text-[var(--k-ink-muted)] leading-relaxed">
					<span class="font-semibold text-[var(--k-ink)]">자율점검용 체크리스트입니다.</span>
					실제 감독 대응은 사업장별 특수사항을 반영해 노무사 검수를 거쳐야 합니다. 완료 체크는 브라우저 세션에만 저장되며 서버에 저장되지 않습니다.
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, reactive, ref, inject, watch } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import { listInspectionChecklist } from "@/data/koreaLaborInspectionRuntime"

const __ = inject("$translate")

const items = ref([])
const completed = reactive({})
const openCategories = reactive({})

watch(
	() => listInspectionChecklist.data,
	(data) => {
		if (data && Array.isArray(data)) {
			items.value = data
			for (const item of data) {
				if (!(item.id in completed)) completed[item.id] = false
				if (!(item.category in openCategories)) openCategories[item.category] = true
			}
		}
	},
	{ immediate: true }
)

function toggleCategory(category) {
	openCategories[category] = !openCategories[category]
}

function isAutomated(item) {
	return !String(item.automated_check || "").startsWith("미확인")
}

const groupedItems = computed(() => {
	const order = []
	const byCategory = {}
	for (const item of items.value) {
		if (!byCategory[item.category]) {
			byCategory[item.category] = []
			order.push(item.category)
		}
		byCategory[item.category].push(item)
	}
	return order.map((category) => {
		const catItems = byCategory[category]
		return {
			category,
			items: catItems,
			completedCount: catItems.filter((item) => completed[item.id]).length,
		}
	})
})

const completedCount = computed(() => items.value.filter((item) => completed[item.id]).length)

const progressPercent = computed(() => {
	if (!items.value.length) return 0
	return Math.round((completedCount.value / items.value.length) * 100)
})
</script>
