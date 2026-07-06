<template>
	<!-- 앱 설치 다이얼로그 (Android / Chrome) -->
	<Dialog v-model="showDialog">
		<template #body-title>
			<h2 class="text-lg font-bold">Korea HRMS 앱 설치</h2>
		</template>
		<template #body-content>
			<p class="text-sm text-gray-700">
				홈 화면에 추가하면 더 빠르고 편리하게 사용할 수 있어요.
			</p>
		</template>
		<template #actions>
			<div class="flex flex-col gap-2 w-full">
				<Button variant="solid" @click="install()" class="py-5 w-full">
					<template #prefix><FeatherIcon name="download" class="w-4" /></template>
					앱으로 설치
				</Button>
				<Button variant="ghost" @click="dismiss()" class="py-5 w-full text-gray-500">
					다음에 하기
				</Button>
			</div>
		</template>
	</Dialog>

	<!-- iOS Safari 전용 — "공유 → 홈 화면 추가" 안내 배너 -->
	<Popover :show="iosInstallMessage" placement="bottom">
		<template #body>
			<div
				class="mt-[calc(100vh-15rem)] flex flex-col gap-3 mx-2 rounded py-5 bg-blue-50 drop-shadow-xl border border-blue-200"
			>
				<div
					class="flex flex-row text-center items-center justify-between mb-1 px-3"
				>
					<span class="text-base text-gray-900 font-bold">
						홈 화면에 추가하기
					</span>
					<span class="inline-flex items-baseline">
						<FeatherIcon
							name="x"
							class="ml-auto h-4 w-4 text-gray-600 cursor-pointer"
							@click="dismissIos()"
						/>
					</span>
				</div>
				<div class="text-xs text-gray-700 px-3">
					<span class="flex flex-col gap-2">
						<span>
							iPhone에서 더 빠르게 접속하려면 홈 화면에 추가하세요.
						</span>
						<span class="inline-flex items-center gap-1 font-medium text-blue-700">
							<FeatherIcon name="share" class="h-4 w-4" />
							<span>공유 버튼</span>
							<span class="text-gray-600 font-normal">탭 후 "홈 화면에 추가"를 선택하세요.</span>
						</span>
					</span>
				</div>
			</div>
		</template>
	</Popover>
</template>

<script setup>
import { ref } from "vue"
import { Dialog, Popover, FeatherIcon } from "frappe-ui"

// localStorage 키 — dismiss 후 30일간 다시 표시하지 않음
const DISMISS_KEY = "nbp-hrms-pwa-install-dismissed"
const DISMISS_DURATION_MS = 30 * 24 * 60 * 60 * 1000

const deferredPrompt = ref(null)
const showDialog = ref(false)
const iosInstallMessage = ref(false)

/** iOS 기기 여부 */
const isIos = () => /iphone|ipad|ipod/.test(window.navigator.userAgent.toLowerCase())

/** 이미 standalone(홈 화면 설치) 모드인지 */
const isInStandaloneMode = () =>
	"standalone" in window.navigator && window.navigator.standalone

/** 사용자가 이미 배너를 dismiss했는지 (30일 이내) */
const isDismissed = () => {
	const ts = localStorage.getItem(DISMISS_KEY)
	if (!ts) return false
	return Date.now() - parseInt(ts, 10) < DISMISS_DURATION_MS
}

// ── 초기화 ──────────────────────────────────────────────────────────────────
if (isIos() && !isInStandaloneMode() && !isDismissed()) {
	iosInstallMessage.value = true
}

window.addEventListener("beforeinstallprompt", (e) => {
	e.preventDefault()
	deferredPrompt.value = e

	if (!isDismissed()) {
		if (isIos() && !isInStandaloneMode()) {
			iosInstallMessage.value = true
		} else {
			showDialog.value = true
		}
	}
})

window.addEventListener("appinstalled", () => {
	showDialog.value = false
	deferredPrompt.value = null
	localStorage.removeItem(DISMISS_KEY)
})

// ── 액션 ────────────────────────────────────────────────────────────────────
async function install() {
	if (!deferredPrompt.value) return
	deferredPrompt.value.prompt()
	showDialog.value = false
}

function dismiss() {
	showDialog.value = false
	localStorage.setItem(DISMISS_KEY, String(Date.now()))
}

function dismissIos() {
	iosInstallMessage.value = false
	localStorage.setItem(DISMISS_KEY, String(Date.now()))
}
</script>
