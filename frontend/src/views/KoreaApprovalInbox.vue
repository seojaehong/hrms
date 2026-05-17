<template>
	<BaseLayout :pageTitle="__('결재 인박스')">
		<template #body>
			<div class="flex flex-col h-full">
				<!-- 필터 탭 -->
				<div class="flex overflow-x-auto gap-2 px-4 py-3 bg-white border-b border-gray-100 sticky top-0 z-10">
					<button
						v-for="tab in filterTabs"
						:key="tab.key"
						@click="activeFilter = tab.key"
						:class="[
							'flex-shrink-0 px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
							activeFilter === tab.key
								? 'bg-gray-900 text-white'
								: 'bg-gray-100 text-gray-600 hover:bg-gray-200',
						]"
					>
						{{ tab.label }}
						<span
							v-if="filterCount(tab.key) > 0"
							:class="[
								'ml-1 text-xs rounded-full px-1.5',
								activeFilter === tab.key ? 'bg-white text-gray-900' : 'bg-gray-300 text-gray-700',
							]"
						>
							{{ filterCount(tab.key) }}
						</span>
					</button>
				</div>

				<!-- 로딩 상태 -->
				<div v-if="loading" class="flex flex-col items-center justify-center py-20 gap-3">
					<div class="w-8 h-8 border-2 border-gray-300 border-t-gray-700 rounded-full animate-spin"></div>
					<p class="text-sm text-gray-500">불러오는 중…</p>
				</div>

				<!-- 에러 상태 -->
				<div v-else-if="error" class="flex flex-col items-center justify-center py-20 gap-3 px-4">
					<FeatherIcon name="alert-circle" class="h-10 w-10 text-red-400" />
					<p class="text-sm text-red-600 text-center">{{ error }}</p>
					<Button variant="subtle" size="sm" @click="loadItems">다시 시도</Button>
				</div>

				<!-- 빈 상태 -->
				<div v-else-if="filteredItems.length === 0" class="flex flex-col items-center justify-center py-20 gap-3 px-4">
					<FeatherIcon name="check-circle" class="h-12 w-12 text-green-400" />
					<p class="text-base font-medium text-gray-700">결재 대기 항목 없음</p>
					<p class="text-sm text-gray-500">잘하고 있어요</p>
				</div>

				<!-- 항목 목록 -->
				<div v-else class="flex flex-col gap-3 p-4 pb-8 overflow-y-auto">
					<div
						v-for="item in filteredItems"
						:key="item.name"
						class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden"
					>
						<!-- 카드 헤더 -->
						<div class="flex items-start gap-3 p-4">
							<div
								:class="[
									'flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center text-lg',
									doctypeStyle(item.doctype).bg,
								]"
							>
								<FeatherIcon
									:name="doctypeStyle(item.doctype).icon"
									:class="['h-5 w-5', doctypeStyle(item.doctype).color]"
								/>
							</div>
							<div class="flex-1 min-w-0">
								<p class="text-sm font-semibold text-gray-900 truncate">{{ item.title }}</p>
								<p class="text-xs text-gray-500 mt-0.5">
									{{ item.applicant_name }} · {{ formatDate(item.requested_at) }}
								</p>
								<p class="text-xs text-gray-600 mt-1 line-clamp-2">{{ detailSummary(item) }}</p>
							</div>
						</div>

						<!-- 액션 버튼 -->
						<div class="flex border-t border-gray-100">
							<a
								:href="item.url_app"
								target="_blank"
								rel="noopener"
								class="flex-1 py-2.5 text-center text-sm text-gray-600 hover:bg-gray-50 transition-colors"
							>
								상세 보기
							</a>
							<button
								class="flex-1 py-2.5 text-center text-sm font-medium text-green-700 hover:bg-green-50 transition-colors border-l border-gray-100"
								:disabled="mutatingName === item.name"
								@click="handleApprove(item)"
							>
								<span v-if="mutatingName === item.name && mutatingAction === 'approve'">
									처리 중…
								</span>
								<span v-else>승인</span>
							</button>
							<button
								class="flex-1 py-2.5 text-center text-sm font-medium text-red-600 hover:bg-red-50 transition-colors border-l border-gray-100"
								:disabled="mutatingName === item.name"
								@click="handleReject(item)"
							>
								<span v-if="mutatingName === item.name && mutatingAction === 'reject'">
									처리 중…
								</span>
								<span v-else>반려</span>
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
				<div class="bg-white rounded-t-2xl sm:rounded-2xl w-full sm:w-96 p-6 flex flex-col gap-4 shadow-xl">
					<h3 class="text-base font-semibold text-gray-900">
						{{ pendingAction === 'reject' ? '반려 사유' : '코멘트 (선택)' }}
					</h3>
					<textarea
						v-model="commentText"
						:placeholder="pendingAction === 'reject' ? '반려 사유를 입력하세요.' : '코멘트를 입력하세요. (선택)'"
						class="w-full border border-gray-200 rounded-lg p-3 text-sm text-gray-800 resize-none focus:outline-none focus:ring-2 focus:ring-gray-300"
						rows="4"
					></textarea>
					<div class="flex gap-2">
						<Button class="flex-1" variant="subtle" @click="cancelComment">취소</Button>
						<Button
							class="flex-1"
							:variant="pendingAction === 'reject' ? 'danger' : 'solid'"
							:disabled="pendingAction === 'reject' && !commentText.trim()"
							@click="confirmAction"
						>
							{{ pendingAction === 'reject' ? '반려 확인' : '승인 확인' }}
						</Button>
					</div>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { ref, computed, onMounted, inject } from "vue"
import { FeatherIcon, Button } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import {
	fetchPendingApprovals,
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
	{ key: "all", label: "전체" },
	{ key: "Leave Application", label: "휴가" },
	{ key: "Expense Claim", label: "경비" },
	{ key: "Employment Contract", label: "계약" },
	{ key: "Korea Payroll Closing Draft", label: "페이롤마감" },
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
const DOCTYPE_STYLES = {
	"Leave Application": {
		icon: "calendar",
		bg: "bg-blue-50",
		color: "text-blue-600",
	},
	"Expense Claim": {
		icon: "dollar-sign",
		bg: "bg-amber-50",
		color: "text-amber-600",
	},
	"Employment Contract": {
		icon: "file-text",
		bg: "bg-purple-50",
		color: "text-purple-600",
	},
	"Korea Payroll Closing Draft": {
		icon: "layers",
		bg: "bg-green-50",
		color: "text-green-600",
	},
}

function doctypeStyle(doctype) {
	return DOCTYPE_STYLES[doctype] || { icon: "inbox", bg: "bg-gray-50", color: "text-gray-500" }
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
			return `${d.pay_year_month || ""} · ${d.company || ""}`
		default:
			return ""
	}
}
</script>
