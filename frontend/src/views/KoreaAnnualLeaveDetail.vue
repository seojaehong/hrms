<template>
	<BaseLayout :pageTitle="__('연차 상세')">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-[var(--k-card)] p-4 pb-24">
				<router-link to="/dashboard/korea-annual-leave" class="text-sm font-semibold text-[var(--k-ink-muted)]">
					← {{ __("연차 현황 목록으로") }}
				</router-link>

				<!-- 히어로 — 연차(lilac) 색블록 -->
				<section class="k-block k-block--cream">
					<p class="k-eyebrow">ANNUAL LEAVE</p>
					<h1 class="mt-1 k-t-display text-[var(--k-ink)]">{{ __("직원 연차 상세") }}</h1>
					<p class="k-numeric mt-1 text-sm font-medium text-[var(--k-ink-muted)]">{{ employeeId }}</p>
				</section>

				<!-- 대시보드 이동 -->
				<section class="k-card p-4">
					<p class="k-eyebrow">DASHBOARD</p>
					<p class="mt-1 k-t-headline text-[var(--k-ink)]">{{ __("연차 현황 대시보드") }}</p>
					<p class="mt-1 text-sm text-[var(--k-ink-muted)]">
						{{ __("상세 연차 현황은 대시보드 화면에서 확인할 수 있습니다.") }}
					</p>
					<router-link
						:to="`/dashboard/korea-annual-leave?employee=${employeeId}`"
						class="mt-4 inline-flex w-full justify-center rounded-full bg-black px-4 py-3 text-sm font-semibold text-white"
					>
						{{ __("연차 현황 대시보드 열기") }}
					</router-link>
				</section>

				<!-- 조회 전용 안내 -->
				<section class="k-card p-4 text-sm">
					<p class="k-eyebrow">READ-ONLY</p>
					<p class="mt-1 font-semibold text-[var(--k-ink)]">{{ __("조회 전용 화면") }}</p>
					<p class="mt-1 text-[var(--k-ink-muted)]">
						{{ __("연차 상세는 조회 전용이며, 모든 변경은 관리자 승인으로만 이뤄집니다.") }}
					</p>
				</section>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject } from "vue"
import { useRoute } from "vue-router"
import BaseLayout from "@/components/BaseLayout.vue"

const route = useRoute()
const __ = inject("$translate")

const employeeId = computed(() => {
	const id = route.params.employeeId
	return typeof id === "string" && id.trim() ? id.trim() : ""
})
</script>
