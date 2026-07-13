<template>
	<div
		class="bg-[var(--k-card)] w-full flex flex-col items-center justify-center pb-5 max-h-[calc(100vh-5rem)]"
	>
		<!-- Header -->
		<div
			class="w-full flex flex-row gap-2 pt-8 pb-5 border-b justify-center items-center sticky top-0 z-[100]"
		>
			<span class="k-t-title text-gray-900 text-center">
				{{ title }}
			</span>
		</div>

		<!-- 빈 상태 — 값 있는 행이 하나도 없으면 한 줄 안내 -->
		<div v-if="!data.length" class="w-full p-6 text-center text-sm text-gray-500">
			{{ emptyMessage }}
		</div>

		<div v-else class="w-full flex flex-col items-center justify-center gap-4 p-4">
			<div
				v-for="item in data"
				:key="item.fieldname"
				class="flex flex-row items-center justify-between w-full"
			>
				<div class="text-gray-600 text-base">{{ item.label }}</div>
				<FormattedField
					:value="item.value"
					:fieldtype="item.fieldtype"
					:fieldname="item.fieldname"
				/>
			</div>
		</div>
	</div>
</template>

<script setup>
import { FeatherIcon } from "frappe-ui"
import FormattedField from "@/components/FormattedField.vue"

const props = defineProps({
	title: {
		type: String,
		required: true,
	},
	data: {
		type: Array,
		required: true,
	},
	emptyMessage: {
		type: String,
		default: "아직 등록된 정보가 없습니다",
	},
})
</script>
