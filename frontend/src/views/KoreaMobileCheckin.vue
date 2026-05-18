<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div class="flex flex-col min-h-full p-4 gap-5 bg-gray-50">

				<!-- Header -->
				<div class="flex items-center gap-3 pt-2">
					<router-link :to="{ name: 'Home' }">
						<button class="p-1 rounded-full hover:bg-gray-200" aria-label="뒤로 가기">
							<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
							</svg>
						</button>
					</router-link>
					<h1 class="text-lg font-bold text-gray-900">{{ __("Korea Mobile Check-In") }}</h1>
				</div>

				<!-- Status Card -->
				<div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
					<div class="flex items-center justify-between">
						<div>
							<p class="text-sm text-gray-500">{{ __("Current Time") }}</p>
							<p class="text-2xl font-bold text-gray-900 tabular-nums">{{ currentTime }}</p>
							<p class="text-sm text-gray-500 mt-0.5">{{ currentDate }}</p>
						</div>
						<div class="flex flex-col items-end gap-1">
							<span
								class="text-xs px-2 py-1 rounded-full font-medium"
								:class="nextAction === 'IN' ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'"
							>
								{{ nextAction === "IN" ? __("Check In") : __("Check Out") }}
							</span>
							<p v-if="lastCheckinTime" class="text-xs text-gray-400">
								{{ __("Last: {0}", [lastCheckinTime]) }}
							</p>
						</div>
					</div>
				</div>

				<!-- GPS Status Card -->
				<div
					class="bg-white rounded-xl p-4 shadow-sm border"
					:class="{
						'border-green-200': gpsStatus === 'ok',
						'border-yellow-200': gpsStatus === 'warn',
						'border-red-200': gpsStatus === 'error',
						'border-gray-100': gpsStatus === 'idle' || gpsStatus === 'loading',
					}"
				>
					<div class="flex items-start gap-3">
						<div
							class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
							:class="{
								'bg-green-100': gpsStatus === 'ok',
								'bg-yellow-100': gpsStatus === 'warn',
								'bg-red-100': gpsStatus === 'error',
								'bg-gray-100': gpsStatus === 'idle' || gpsStatus === 'loading',
							}"
						>
							<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4"
								:class="{
									'text-green-600': gpsStatus === 'ok',
									'text-yellow-600': gpsStatus === 'warn',
									'text-red-600': gpsStatus === 'error',
									'text-gray-400': gpsStatus === 'idle' || gpsStatus === 'loading',
								}"
								fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
									d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
							</svg>
						</div>
						<div class="flex-1 min-w-0">
							<p class="text-sm font-medium text-gray-800">{{ __("GPS Location") }}</p>
							<p class="text-xs text-gray-500 mt-0.5">{{ gpsStatusLabel }}</p>
							<p v-if="gpsCoords" class="text-xs text-gray-400 mt-1 font-mono">
								{{ gpsCoords }}
							</p>
						</div>
						<button
							v-if="gpsStatus !== 'loading'"
							@click="fetchGps"
							class="text-xs text-blue-600 underline flex-shrink-0"
						>
							{{ gpsStatus === 'idle' ? __("Get GPS") : __("Retry") }}
						</button>
						<div v-else class="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin flex-shrink-0 mt-1"></div>
					</div>
				</div>

				<!-- Selfie Section -->
				<div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
					<div class="flex items-center justify-between mb-3">
						<p class="text-sm font-medium text-gray-800">{{ __("Selfie (Optional)") }}</p>
						<span class="text-xs text-gray-400">{{ __("Privacy protected") }}</span>
					</div>

					<!-- Preview -->
					<div v-if="selfiePreviewUrl" class="relative mb-3">
						<img
							:src="selfiePreviewUrl"
							alt="Selfie preview"
							class="w-full max-h-48 object-cover rounded-lg"
						/>
						<button
							@click="removeSelfie"
							aria-label="셀카 삭제"
							class="absolute top-2 right-2 bg-black bg-opacity-50 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs"
						>
							&times;
						</button>
					</div>

					<button
						v-if="!selfiePreviewUrl"
						@click="takeSelfie"
						class="w-full py-3 border-2 border-dashed border-gray-200 rounded-lg text-sm text-gray-500 hover:border-blue-300 hover:text-blue-500 transition-colors flex items-center justify-center gap-2"
					>
						<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
								d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
						</svg>
						{{ __("Take Selfie") }}
					</button>
				</div>

				<!-- Warnings -->
				<div v-if="warnings.length" class="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
					<p class="text-sm font-medium text-yellow-800 mb-2">{{ __("Notices") }}</p>
					<ul class="space-y-1">
						<li v-for="(warn, i) in warnings" :key="i" class="text-xs text-yellow-700 flex gap-1.5">
							<span class="flex-shrink-0">&#9888;</span>
							<span>{{ warn }}</span>
						</li>
					</ul>
				</div>

				<!-- Result Card -->
				<div v-if="result" class="rounded-xl p-4 border"
					:class="result.applied ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'"
				>
					<div class="flex items-start gap-3">
						<span class="text-xl">{{ result.applied ? '✓' : '✗' }}</span>
						<div>
							<p class="text-sm font-bold"
								:class="result.applied ? 'text-green-800' : 'text-red-800'"
							>
								{{ result.applied
									? (result.data?.check_type === 'IN' ? __("Check-In Recorded") : __("Check-Out Recorded"))
									: __("Check-In Failed")
								}}
							</p>
							<p v-if="result.attendance_name" class="text-xs text-gray-500 mt-0.5 font-mono">
								{{ result.attendance_name }}
							</p>
							<p v-if="errorMessage" class="text-xs text-red-600 mt-0.5">{{ errorMessage }}</p>
						</div>
					</div>
				</div>

				<!-- Action Buttons -->
				<div class="flex flex-col gap-3 mt-auto pb-8">
					<button
						@click="submit"
						:disabled="isSubmitting || gpsStatus !== 'ok'"
						class="w-full py-4 rounded-xl text-white font-bold text-base transition-all disabled:opacity-40"
						:class="nextAction === 'IN' ? 'bg-green-500 hover:bg-green-600 active:bg-green-700' : 'bg-orange-500 hover:bg-orange-600 active:bg-orange-700'"
					>
						<span v-if="isSubmitting" class="flex items-center justify-center gap-2">
							<span class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
							{{ __("Recording...") }}
						</span>
						<span v-else>
							{{ nextAction === "IN" ? __("Check In") : __("Check Out") }}
						</span>
					</button>
					<p v-if="gpsStatus !== 'ok'" class="text-xs text-center text-gray-400">
						{{ __("GPS location required to proceed") }}
					</p>
				</div>

			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { ref, computed, inject, onMounted, onBeforeUnmount } from "vue"
import { IonPage, IonContent } from "@ionic/vue"
import { toast } from "frappe-ui"

import { recordMobileCheckin, getCurrentGps, captureSelfiePicker } from "@/data/koreaMobileAttendanceRuntime"

// ---------------------------------------------------------------------------
// Injected services
// ---------------------------------------------------------------------------
const __ = inject("$translate")
const employee = inject("$employee")
const dayjs = inject("$dayjs")

// ---------------------------------------------------------------------------
// Clock
// ---------------------------------------------------------------------------
const now = ref(dayjs())
let clockTimer = null

onMounted(() => {
	// Refresh clock every second.
	clockTimer = setInterval(() => {
		now.value = dayjs()
	}, 1_000)
})

onBeforeUnmount(() => {
	clearInterval(clockTimer)
})

const currentTime = computed(() => now.value.format("HH:mm:ss"))
const currentDate = computed(() => now.value.format("ddd, D MMMM YYYY"))

// ---------------------------------------------------------------------------
// Last check-in / next action (tracked via session storage for simplicity)
// ---------------------------------------------------------------------------
const lastCheckinType = ref(sessionStorage.getItem("korea_last_checkin_type") || null)
const lastCheckinTime = ref(sessionStorage.getItem("korea_last_checkin_time") || null)

const nextAction = computed(() => (lastCheckinType.value === "IN" ? "OUT" : "IN"))

// ---------------------------------------------------------------------------
// GPS state
// ---------------------------------------------------------------------------
const gpsStatus = ref("idle") // idle | loading | ok | warn | error
const gpsPosition = ref(null)

const gpsStatusLabel = computed(() => {
	switch (gpsStatus.value) {
		case "idle":
			return __("Tap 'Get GPS' to locate you")
		case "loading":
			return __("Locating...")
		case "ok":
			return __("Location acquired (accuracy: {0}m)", [Math.round(gpsPosition.value?.coords?.accuracy ?? 0)])
		case "warn":
			return __("Low accuracy — consider retrying")
		case "error":
			return __("Could not get location — check permissions")
		default:
			return ""
	}
})

const gpsCoords = computed(() => {
	if (!gpsPosition.value) return null
	const { latitude, longitude } = gpsPosition.value.coords
	return `${latitude.toFixed(5)}°, ${longitude.toFixed(5)}°`
})

async function fetchGps() {
	gpsStatus.value = "loading"
	try {
		const pos = await getCurrentGps()
		gpsPosition.value = pos
		gpsStatus.value = pos.coords.accuracy > 100 ? "warn" : "ok"
	} catch (err) {
		gpsStatus.value = "error"
		gpsPosition.value = null
	}
}

// ---------------------------------------------------------------------------
// Selfie state
// ---------------------------------------------------------------------------
const selfieFile = ref(null)
const selfiePreviewUrl = ref(null)

async function takeSelfie() {
	try {
		const file = await captureSelfiePicker()
		selfieFile.value = file
		selfiePreviewUrl.value = URL.createObjectURL(file)
	} catch {
		// User cancelled — not an error.
	}
}

function removeSelfie() {
	if (selfiePreviewUrl.value) {
		URL.revokeObjectURL(selfiePreviewUrl.value)
	}
	selfieFile.value = null
	selfiePreviewUrl.value = null
}

// ---------------------------------------------------------------------------
// Submission state
// ---------------------------------------------------------------------------
const isSubmitting = ref(false)
const result = ref(null)
const errorMessage = ref(null)
const warnings = ref([])

async function submit() {
	if (!gpsPosition.value) return
	if (isSubmitting.value) return

	isSubmitting.value = true
	result.value = null
	errorMessage.value = null
	warnings.value = []

	const ts = dayjs().format("YYYY-MM-DD HH:mm:ss")

	try {
		const response = await recordMobileCheckin({
			employee: employee.data?.name,
			checkType: nextAction.value,
			timestamp: ts,
			gpsLatitude: gpsPosition.value.coords.latitude,
			gpsLongitude: gpsPosition.value.coords.longitude,
			accuracyMeters: gpsPosition.value.coords.accuracy,
			selfieFile: selfieFile.value,
		})

		result.value = response
		warnings.value = response.warnings || []

		// Persist last check-in state for next-action tracking.
		const ctype = response.data?.check_type || nextAction.value
		sessionStorage.setItem("korea_last_checkin_type", ctype)
		sessionStorage.setItem("korea_last_checkin_time", ts)
		lastCheckinType.value = ctype
		lastCheckinTime.value = ts

		toast({
			title: ctype === "IN" ? __("Checked In") : __("Checked Out"),
			text: __("Recorded: {0}", [response.attendance_name || ts]),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
	} catch (err) {
		result.value = { status: "error" }
		const msg = err?.messages?.[0] || err?.message || __("An unexpected error occurred")
		errorMessage.value = msg
		toast({
			title: __("Error"),
			text: msg,
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	} finally {
		isSubmitting.value = false
	}
}
</script>
