<template>
	<BaseLayout pageTitle="연차 상세">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-gray-50 p-4 pb-24">
				<router-link to="/dashboard/korea-annual-leave" class="text-sm font-semibold text-gray-600">
					← 연차 현황 목록으로
				</router-link>

				<!-- Redirect to dashboard with employee param -->
				<section class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
					<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">직원 연차 상세</p>
					<h1 class="mt-2 text-xl font-bold text-gray-900">{{ employeeId }}</h1>
					<p class="mt-1 text-sm text-gray-500">
						상세 연차 현황은 대시보드 화면에서 확인할 수 있습니다.
					</p>
					<router-link
						:to="`/dashboard/korea-annual-leave?employee=${employeeId}`"
						class="mt-4 inline-flex w-full justify-center rounded-xl bg-gray-900 px-4 py-3 text-sm font-semibold text-white"
					>
						연차 현황 대시보드 열기
					</router-link>
				</section>

				<section class="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
					<p class="font-semibold">Preview boundary</p>
					<p class="mt-1">
						연차 상세 조회는 preview_only · human approval required · AI=assistant_only.
					</p>
				</section>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed } from "vue"
import { useRoute } from "vue-router"
import BaseLayout from "@/components/BaseLayout.vue"

const route = useRoute()

const employeeId = computed(() => {
	const id = route.params.employeeId
	return typeof id === "string" && id.trim() ? id.trim() : ""
})
</script>
