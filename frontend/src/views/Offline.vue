<template>
	<div class="flex flex-col items-center justify-center min-h-screen p-6 gap-6 text-center bg-[var(--k-surface-soft)]">
		<!-- 오프라인 아이콘 -->
		<div class="w-20 h-20 rounded-full bg-[var(--k-hairline-soft)] flex items-center justify-center">
			<FeatherIcon name="wifi-off" class="w-9 h-9 text-[var(--k-ink)]" />
		</div>

		<!-- 상태 배지 -->
		<span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-50 text-red-600 text-xs font-medium">
			<span class="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
			오프라인
		</span>

		<!-- 제목 + 설명 -->
		<div class="flex flex-col gap-2">
			<h1 class="k-t-display text-[var(--k-ink)]">
				인터넷에 연결되어 있지 않아요
			</h1>
			<p class="text-sm text-[var(--k-ink-muted)] leading-relaxed max-w-xs">
				네트워크 연결을 확인해 주세요.<br />
				Wi-Fi 또는 모바일 데이터를 켜면<br />자동으로 다시 연결됩니다.
			</p>
		</div>

		<!-- 캐시 페이지 바로가기 -->
		<div class="w-full max-w-sm bg-[var(--k-card)] rounded-2xl border border-[var(--k-hairline-soft)] shadow-sm p-4 text-left">
			<p class="text-xs font-semibold text-[var(--k-ink-faint)] uppercase tracking-wide mb-3">
				오프라인에서 이용 가능한 메뉴
			</p>
			<div class="flex flex-col gap-2">
				<router-link
					v-for="link in cachedLinks"
					:key="link.route"
					:to="{ name: link.route }"
					class="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-[var(--k-surface-soft)] hover:bg-[var(--k-hairline-soft)] transition-colors"
				>
					<FeatherIcon :name="link.icon" class="w-4.5 h-4.5 text-[var(--k-ink)] flex-shrink-0" />
					<span class="text-sm font-medium text-[var(--k-ink)]">{{ link.label }}</span>
				</router-link>
			</div>
		</div>

		<!-- 새로고침 버튼 -->
		<Button variant="solid" class="py-5 px-8" @click="reload()">
			<template #prefix>
				<FeatherIcon name="refresh-cw" class="w-4" />
			</template>
			다시 연결하기
		</Button>
	</div>
</template>

<script setup>
/**
 * Offline.vue — 앱 내 오프라인 상태 화면 (in-app, 라우터 기반)
 *
 * ⚠️ 이 컴포넌트는 앱이 이미 로드된 상태에서 /offline 경로로 이동하거나
 *    router.push("Offline")으로 호출할 때만 동작합니다.
 *
 * 완전한 오프라인(콜드 로드) 상황의 fallback은 Service Worker가
 * /assets/hrms/frontend/offline.html (정적 HTML)을 서빙합니다.
 * → public/sw.js OFFLINE_URL 참고
 */
import { FeatherIcon } from "frappe-ui"

const cachedLinks = [
	{ route: "Home", label: "홈", icon: "home" },
	{ route: "AttendanceDashboard", label: "근태 현황", icon: "clock" },
	{ route: "SalarySlipsDashboard", label: "급여명세서", icon: "credit-card" },
	{ route: "LeavesDashboard", label: "휴가 현황", icon: "calendar" },
	{ route: "ExpenseClaimsDashboard", label: "경비 청구", icon: "file-text" },
]

function reload() {
	window.location.reload()
}
</script>
