<template>
	<BaseLayout :pageTitle="__('결재 인박스')">
		<template #body>
			<div class="flex flex-col h-full bg-[var(--k-card)]">
				<!-- 히어로 — 결재함(cream) 색블록 -->
				<div class="p-4 pb-0">
					<section class="k-block k-block--cream">
						<div class="flex items-start justify-between gap-3">
							<div>
								<p class="k-eyebrow">APPROVALS</p>
								<h1 class="mt-1 k-t-display text-[var(--k-ink)]">{{ __("결재 인박스") }}</h1>
								<p class="mt-1 text-sm font-medium text-[var(--k-ink-muted)]">{{ __("승인·반려가 필요한 요청을 한곳에서 처리합니다") }}</p>
							</div>
							<div class="rounded-xl bg-white/70 px-4 py-3 text-center">
								<p class="k-numeric text-2xl font-bold text-[var(--k-ink)]">{{ items.length }}</p>
								<p class="mt-0.5 text-xs font-medium text-[var(--k-ink-muted)]">{{ __("대기") }}</p>
							</div>
						</div>
					</section>
				</div>

				<!-- 필터 탭 -->
				<div class="flex overflow-x-auto gap-2 px-4 py-3 bg-[var(--k-card)] sticky top-0 z-10">
					<button
						v-for="tab in filterTabs"
						:key="tab.key"
						@click="activeFilter = tab.key"
						:class="[
							'flex-shrink-0 px-3.5 py-1.5 rounded-md text-sm font-medium transition-colors',
							activeFilter === tab.key
								? 'k-segment-active'
								: 'bg-[var(--k-card)] text-[var(--k-ink)] border border-[var(--k-hairline)] hover:bg-[var(--k-surface-soft)]',
						]"
					>
						{{ tab.label }}
						<span
							v-if="filterCount(tab.key) > 0"
							:class="[
								'ml-1 text-xs rounded-full px-1.5 k-numeric',
								activeFilter === tab.key ? 'bg-[var(--k-card)] text-[var(--k-ink)]' : 'bg-[var(--k-hairline)] text-[var(--k-ink)]',
							]"
						>
							{{ filterCount(tab.key) }}
						</span>
					</button>
				</div>

				<!-- 로딩 상태 -->
				<div v-if="loading" class="flex flex-col items-center justify-center py-20 gap-3">
					<div class="w-8 h-8 border-2 border-[var(--k-hairline)] border-t-black rounded-full animate-spin"></div>
					<p class="text-sm text-[var(--k-ink-faint)]">{{ __("불러오는 중…") }}</p>
				</div>

				<!-- 에러 상태 -->
				<div v-else-if="error" class="flex flex-col items-center justify-center py-20 gap-3 px-4">
					<FeatherIcon name="alert-circle" class="h-10 w-10 text-red-700" />
					<p class="text-sm text-red-700 text-center">{{ error }}</p>
					<button
						class="k-btn-secondary border-[var(--k-hairline)]"
						@click="loadItems"
					>
						{{ __("다시 시도") }}
					</button>
				</div>

				<!-- 빈 상태 — 결재는 지정 결재자에게만 배정되므로 0건이 정상일 수 있음 -->
				<div v-else-if="filteredItems.length === 0" class="flex flex-col items-center justify-center py-20 gap-3 px-4">
					<FeatherIcon name="check-circle" class="h-12 w-12 text-green-700" />
					<p class="k-t-headline text-[var(--k-ink)]">{{ __("내게 배정된 결재가 없습니다") }}</p>
					<p class="text-sm text-[var(--k-ink-faint)]">{{ __("결재는 지정된 결재자에게만 표시됩니다") }}</p>
					<p
						v-if="isAdmin && othersPendingCount > 0"
						class="rounded-full bg-[var(--k-surface-soft)] px-4 py-1.5 text-xs font-semibold text-[var(--k-ink-muted)]"
					>
						{{ __("다른 결재자에게 배정된 대기 {0}건", [othersPendingCount]) }}
					</p>
				</div>

				<!-- 항목 목록 -->
				<div v-else class="flex flex-col gap-3 p-4 pb-8 overflow-y-auto">
					<div
						v-for="item in filteredItems"
						:key="item.name"
						class="k-card overflow-hidden"
					>
						<!-- 카드 헤더 -->
						<div class="flex items-start gap-3 p-4">
							<div class="flex-shrink-0 w-10 h-10 rounded-lg bg-[var(--k-surface-soft)] flex items-center justify-center">
								<FeatherIcon
									:name="doctypeStyle(item.doctype).icon"
									class="h-5 w-5 text-[var(--k-ink)]"
								/>
							</div>
							<div class="flex-1 min-w-0">
								<p class="text-sm font-semibold text-[var(--k-ink)] truncate">{{ item.title }}</p>
								<p class="text-xs text-[var(--k-ink-faint)] mt-0.5">
									{{ item.applicant_name }} · {{ formatDate(item.requested_at) }}
								</p>
								<p class="k-numeric text-xs text-[var(--k-ink-muted)] mt-1 line-clamp-2">{{ detailSummary(item) }}</p>
							</div>
						</div>

						<!-- 액션 버튼 -->
						<div class="flex border-t border-[var(--k-hairline-soft)]">
							<a
								:href="item.url_app"
								target="_blank"
								rel="noopener"
								class="flex-1 py-2.5 text-center text-sm text-[var(--k-ink-muted)] hover:bg-[var(--k-surface-soft)] transition-colors"
							>
								{{ __("상세 보기") }}
							</a>
							<button
								class="flex-1 py-2.5 text-center text-sm font-semibold text-green-800 hover:bg-green-100 transition-colors border-l border-[var(--k-hairline-soft)]"
								:disabled="mutatingName === item.name"
								@click="handleApprove(item)"
							>
								<span v-if="mutatingName === item.name && mutatingAction === 'approve'">
									{{ __("처리 중…") }}
								</span>
								<span v-else>{{ __("승인") }}</span>
							</button>
							<button
								class="flex-1 py-2.5 text-center text-sm font-semibold text-red-700 hover:bg-red-100 transition-colors border-l border-[var(--k-hairline-soft)]"
								:disabled="mutatingName === item.name"
								@click="handleReject(item)"
							>
								<span v-if="mutatingName === item.name && mutatingAction === 'reject'">
									{{ __("처리 중…") }}
								</span>
								<span v-else>{{ __("반려") }}</span>
							</button>
						</div>
					</div>
				</div>
			</div>

			<!-- 반려 사유 다이얼로그 -->
			<div
				v-if="showCommentDialog"
				class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40"
				@click.self="cancelComment"
			>
				<div class="bg-[var(--k-card)] rounded-t-2xl sm:rounded-2xl w-full sm:w-96 md:w-[44rem] xl:w-[64rem] 2xl:w-[76rem] mx-auto p-6 flex flex-col gap-4">
					<h3 class="k-t-headline text-[var(--k-ink)]">
						{{ pendingAction === 'reject' ? __('반려 사유') : __('코멘트 (선택)') }}
					</h3>
					<textarea
						v-model="commentText"
						:placeholder="pendingAction === 'reject' ? __('반려 사유를 입력하세요.') : __('코멘트를 입력하세요. (선택)')"
						class="w-full border border-[var(--k-hairline)] rounded-lg p-3 text-sm text-[var(--k-ink)] resize-none focus:outline-none focus:ring-2 focus:ring-black/20"
						rows="4"
					></textarea>
					<div class="flex gap-2">
						<button
							class="k-btn-secondary flex-1 border-[var(--k-hairline)]"
							@click="cancelComment"
						>
							{{ __("취소") }}
						</button>
						<button
							class="k-btn-primary flex-1 disabled:opacity-50"
							:disabled="pendingAction === 'reject' && !commentText.trim()"
							@click="confirmAction"
						>
							{{ pendingAction === 'reject' ? __('반려 확인') : __('승인 확인') }}
						</button>
					</div>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { ref, computed, onMounted, inject } from "vue"
import { FeatherIcon } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import { useIsAdmin } from "@/composables/useIsAdmin"
import {
	fetchPendingApprovals,
	fetchPendingCountForOthers,
	approveItem,
	rejectItem,
} from "@/data/koreaApprovalInboxRuntime.js"

const __ = inject("$translate")

// ---------------------------------------------------------------------------
// 상태
// ---------------------------------------------------------------------------
const items = ref([])
const loading = ref(false)
const error = ref("")
const activeFilter = ref("all")

// HR Manager 한정: 빈 결재함일 때 "다른 결재자에게 배정된 대기 N건" 보조 문구
const isAdmin = useIsAdmin()
const othersPendingCount = ref(0)

const mutatingName = ref(null)
const mutatingAction = ref(null)

const showCommentDialog = ref(false)
const pendingItem = ref(null)
const pendingAction = ref(null)
const commentText = ref("")

// ---------------------------------------------------------------------------
// 필터 탭 정의
// ---------------------------------------------------------------------------
const filterTabs = [
	{ key: "all", label: __("전체") },
	{ key: "Leave Application", label: __("휴가") },
	{ key: "Expense Claim", label: __("경비") },
	{ key: "Employment Contract", label: __("계약") },
	{ key: "Korea Payroll Closing Draft", label: __("급여 마감") },
]

const filteredItems = computed(() => {
	if (activeFilter.value === "all") return items.value
	return items.value.filter((i) => i.doctype === activeFilter.value)
})

function filterCount(key) {
	if (key === "all") return items.value.length
	return items.value.filter((i) => i.doctype === key).length
}

// ---------------------------------------------------------------------------
// 데이터 로드
// ---------------------------------------------------------------------------
async function loadItems() {
	loading.value = true
	error.value = ""
	try {
		items.value = await fetchPendingApprovals()
	} catch (e) {
		error.value = e?.message || "결재 목록을 불러오지 못했습니다."
	} finally {
		loading.value = false
	}
	// 빈 결재함이면 (HR Manager 한정) 타 결재자 대기 건수 조회 — 실패 시 조용히 생략
	if (!error.value && items.value.length === 0 && isAdmin.value) {
		const counts = await fetchPendingCountForOthers()
		othersPendingCount.value = counts?.total ?? 0
	} else {
		othersPendingCount.value = 0
	}
}

onMounted(loadItems)

// ---------------------------------------------------------------------------
// 승인 / 반려 핸들러
// ---------------------------------------------------------------------------
function handleApprove(item) {
	pendingItem.value = item
	pendingAction.value = "approve"
	commentText.value = ""
	showCommentDialog.value = true
}

function handleReject(item) {
	pendingItem.value = item
	pendingAction.value = "reject"
	commentText.value = ""
	showCommentDialog.value = true
}

function cancelComment() {
	showCommentDialog.value = false
	pendingItem.value = null
	pendingAction.value = null
	commentText.value = ""
}

async function confirmAction() {
	const item = pendingItem.value
	const action = pendingAction.value
	if (!item || !action) return

	showCommentDialog.value = false
	mutatingName.value = item.name
	mutatingAction.value = action

	try {
		if (action === "approve") {
			await approveItem({
				doctype: item.doctype,
				name: item.name,
				comment: commentText.value || "",
			})
		} else {
			await rejectItem({
				doctype: item.doctype,
				name: item.name,
				comment: commentText.value || "",
			})
		}
		// 처리 완료된 항목 제거
		items.value = items.value.filter((i) => i.name !== item.name)
	} catch (e) {
		error.value = e?.message || "처리 중 오류가 발생했습니다."
	} finally {
		mutatingName.value = null
		mutatingAction.value = null
		pendingItem.value = null
		pendingAction.value = null
		commentText.value = ""
	}
}

// ---------------------------------------------------------------------------
// 표시 헬퍼
// ---------------------------------------------------------------------------
// 모노크롬 아이콘 매핑 — 색은 상태 배지에만 사용 (DESIGN-figma)
const DOCTYPE_STYLES = {
	"Leave Application": { icon: "calendar" },
	"Expense Claim": { icon: "dollar-sign" },
	"Employment Contract": { icon: "file-text" },
	"Korea Payroll Closing Draft": { icon: "layers" },
}

function doctypeStyle(doctype) {
	return DOCTYPE_STYLES[doctype] || { icon: "inbox" }
}

function formatDate(isoStr) {
	if (!isoStr) return ""
	try {
		const d = new Date(isoStr)
		return d.toLocaleDateString("ko-KR", {
			month: "short",
			day: "numeric",
			hour: "2-digit",
			minute: "2-digit",
		})
	} catch {
		return isoStr
	}
}

function detailSummary(item) {
	const d = item.details || {}
	switch (item.doctype) {
		case "Leave Application":
			return `${d.leave_type || ""} · ${d.from_date || ""} ~ ${d.to_date || ""} (${d.total_leave_days || 0}일)`
		case "Expense Claim":
			return `${Number(d.total_claimed_amount || 0).toLocaleString("ko-KR")} ${d.currency || "KRW"} · ${d.posting_date || ""}`
		case "Employment Contract":
			return `${d.contract_type || ""} · ${d.start_date || ""} ~ ${d.end_date || ""}`
		case "Korea Payroll Closing Draft":
			// 승인=draft 승인 기록(문서 제출 아님) — 확정·전송은 담당자 플로우
			return `${d.workplace || d.company || ""} · ${d.period_start || ""} ~ ${d.period_end || ""}`
		default:
			return ""
	}
}
</script>
