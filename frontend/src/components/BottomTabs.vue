<template>
	<ion-tab-bar
		slot="bottom"
		class="bg-[var(--k-card)] border-t border-[var(--k-hairline)] sm:w-96 md:w-[44rem] xl:w-[64rem] 2xl:w-[76rem] mx-auto py-2 pb-2 standalone:pb-safe-bottom"
	>
		<ion-tab-button
			v-for="item in tabItems"
			:key="item.title"
			:tab="item.title"
			:href="item.route"
			:class="[
				'bg-[var(--k-card)] text-xs space-y-1.5 transition active:scale-95',
				route.path.startsWith(item.route)
					? 'k-tab-active text-[var(--k-ink)] font-semibold'
					: 'text-[var(--k-ink-muted)] font-normal',
			]"
		>
			<component :is="item.icon" class="h-5 w-5" />
			<div>{{ item.title }}</div>
		</ion-tab-button>
	</ion-tab-bar>
</template>

<script setup>
import { useRoute } from "vue-router"

import { IonTabBar, IonTabButton } from "@ionic/vue"

import HomeIcon from "@/components/icons/HomeIcon.vue"
import LeaveIcon from "@/components/icons/LeaveIcon.vue"
import RequestIcon from "@/components/icons/RequestIcon.vue"
import SalaryIcon from "@/components/icons/SalaryIcon.vue"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"
import { inject } from "vue"

const __ = inject("$translate")

const route = useRoute()

// 하단탭 canonical — 근태/연차/급여는 Korea 화면으로 통일 (P0-6, P0-3)
const tabItems = [
	{
		icon: HomeIcon,
		title: __("홈"),
		route: "/home",
	},
	{
		icon: AttendanceIcon,
		title: __("근태"),
		route: "/dashboard/korea-attendance",
	},
	{
		icon: LeaveIcon,
		title: __("연차"),
		route: "/dashboard/korea-annual-leave",
	},
	// 비용은 홈 더보기(경비 청구·선급금)로 이동 — 사업주 멘탈모델상 요청(결재)이 1차 탭 (2026-07-13)
	{
		icon: RequestIcon,
		title: __("요청"),
		route: "/dashboard/korea-approval-inbox",
	},
	{
		icon: SalaryIcon,
		title: __("급여"),
		route: "/dashboard/korea-wage-statement",
	},
]
</script>
