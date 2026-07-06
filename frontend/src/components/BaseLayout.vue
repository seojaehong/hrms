<template>
	<ion-page>
		<ion-header class="ion-no-border">
			<div class="w-full sm:w-96">
				<div class="flex flex-col bg-white shadow-sm p-4">
					<div class="flex flex-row justify-between items-center">
						<div class="flex flex-row items-center gap-2">
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
			<div class="flex flex-col h-screen w-screen sm:w-96">
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

import { inject, onMounted, onBeforeUnmount } from "vue"
import { useRouter } from "vue-router"

const user = inject("$user")
const __ = inject("$translate")
const router = useRouter()

const props = defineProps({
	pageTitle: {
		type: String,
		required: false,
		default: "",
	},
})

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
