<template>
	<ion-page>
		<ion-header class="ion-no-border">
			<div class="w-full bg-white shadow-sm">
				<div class="flex flex-col p-4 w-full sm:w-96 md:w-[44rem] xl:w-[60rem] mx-auto">
					<div class="flex flex-row justify-between items-center">
						<div class="flex flex-row items-center gap-2">
							<!-- 홈이 아닌 화면 공통 뒤로가기 — 히스토리 없으면 홈으로 -->
							<button
								v-if="showBack"
								class="flex items-center justify-center h-8 w-8 rounded-full text-gray-600 hover:bg-gray-100 transition"
								:aria-label="__('뒤로가기')"
								@click="goBack"
							>
								<FeatherIcon name="chevron-left" class="h-6 w-6" />
							</button>
							<h2 class="text-xl font-bold text-gray-900">
								{{ props.pageTitle || __("Korea HRMS") }}
							</h2>
						</div>
						<div class="flex flex-row items-center gap-3 ml-auto">
							<!-- 통합 검색 버튼 (Cmd/Ctrl+K) -->
							<router-link
								:to="{ name: 'KoreaGlobalSearch' }"
								class="flex flex-col items-center text-gray-600 hover:text-gray-900 transition"
								:aria-label="__('통합 검색')"
							>
								<SearchIcon class="h-6 w-6" />
							</router-link>
							<router-link
								:to="{ name: 'Notifications' }"
								v-slot="{ navigate }"
								class="flex flex-col items-center"
							>
								<span class="relative inline-block" @click="navigate">
									<FeatherIcon name="bell" class="h-6 w-6" />
									<span
										v-if="unreadNotificationsCount.data"
										class="absolute top-0 right-0.5 inline-block w-2 h-2 bg-red-600 rounded-full border border-white"
									>
									</span>
								</span>
							</router-link>
							<router-link
								:to="{ name: 'Profile' }"
								class="flex flex-col items-center"
							>
								<Avatar
									:image="user.data.user_image"
									:label="user.data.first_name"
									size="xl"
								/>
							</router-link>
						</div>
					</div>
				</div>
			</div>
		</ion-header>

		<ion-content class="ion-no-padding">
			<div class="flex flex-col h-screen w-full sm:w-96 md:w-[44rem] xl:w-[60rem] mx-auto">
				<slot name="body"></slot>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonHeader, IonContent, IonPage } from "@ionic/vue"
import { FeatherIcon, Avatar } from "frappe-ui"

import { unreadNotificationsCount } from "@/data/notifications"
import SearchIcon from "@/components/icons/SearchIcon.vue"

import { computed, inject, onMounted, onBeforeUnmount } from "vue"
import { useRoute, useRouter } from "vue-router"

const user = inject("$user")
const __ = inject("$translate")
const router = useRouter()
const route = useRoute()

const props = defineProps({
	pageTitle: {
		type: String,
		required: false,
		default: "",
	},
})

// 홈이 아닌 모든 화면에 뒤로가기 노출
const showBack = computed(() => route.name !== "Home" && route.path !== "/home")

function goBack() {
	// 브라우저 히스토리가 있으면 뒤로, 없으면(딥링크 진입) 홈으로
	if (window.history.state && window.history.state.back) {
		router.back()
	} else {
		router.push({ name: "Home" })
	}
}

// Cmd/Ctrl+K → /search 라우트로 이동
function handleGlobalKeydown(e) {
	if ((e.metaKey || e.ctrlKey) && e.key === "k") {
		e.preventDefault()
		router.push({ name: "KoreaGlobalSearch" })
	}
}

onMounted(() => {
	window.addEventListener("keydown", handleGlobalKeydown)
})

onBeforeUnmount(() => {
	window.removeEventListener("keydown", handleGlobalKeydown)
})
</script>
