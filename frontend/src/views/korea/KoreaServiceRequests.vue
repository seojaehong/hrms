<template>
	<BaseLayout :pageTitle="__('요청 보드')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 — cream 색블록 -->
				<div class="k-block k-block--cream">
					<div class="k-eyebrow">REQUESTS</div>
					<div class="mt-1 text-xl font-bold tracking-tight text-black">{{ __('요청 보드') }}</div>
					<p class="mt-2 text-sm text-black/60">
						{{ __('급여·4대보험·증명서·연차/근태 요청을 채팅 대신 표준 폼으로 접수하고 처리 현황을 추적합니다.') }}
					</p>
				</div>

				<!-- 새 요청 폼 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div class="k-label px-0.5">{{ __('새 요청') }}</div>

					<!-- 제목 -->
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('제목') }} *</label>
						<input
							type="text"
							v-model="form.title"
							:placeholder="__('예: 5월 급여 명세서 재발급 요청')"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black/60"
						/>
						<span v-if="errors.title" class="text-xs text-red-600">{{ errors.title }}</span>
					</div>

					<!-- 분류 -->
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('분류') }} *</label>
						<select
							v-model="form.category"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-black bg-white focus:outline-none focus:ring-2 focus:ring-black/60"
						>
							<option value="" disabled>{{ __('선택하세요') }}</option>
							<option v-for="cat in CATEGORIES" :key="cat" :value="cat">{{ cat }}</option>
						</select>
						<span v-if="errors.category" class="text-xs text-red-600">{{ errors.category }}</span>
					</div>

					<!-- 내용 -->
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('내용 (선택)') }}</label>
						<textarea
							v-model="form.detail"
							rows="3"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black/60"
						/>
					</div>

					<!-- 제출 CTA — 블랙 pill -->
					<button
						@click="submitRequest"
						:disabled="createRequest.loading"
						class="k-btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
					>
						<span v-if="createRequest.loading">{{ __('제출 중...') }}</span>
						<span v-else>{{ __('요청 접수') }}</span>
					</button>

					<div
						v-if="createRequest.error"
						class="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700"
					>
						{{ __('제출 중 오류가 발생했습니다.') }} {{ createRequest.error.messages?.[0] || "" }}
					</div>
				</div>

				<!-- 요청 목록 -->
				<div class="flex flex-col gap-3">
					<div class="k-label px-1">{{ __('요청 현황') }}</div>

					<div
						v-if="requestRows.length === 0"
						class="k-card p-6 flex flex-col items-center gap-2 text-center"
					>
						<span class="text-2xl">📋</span>
						<div class="text-xs text-black/50">{{ __('아직 접수된 요청이 없습니다.') }}</div>
					</div>

					<div
						v-for="req in requestRows"
						:key="req.name"
						class="k-card p-4 flex flex-col gap-1.5"
					>
						<div class="flex justify-between items-center gap-2">
							<span class="text-sm font-semibold text-black">{{ req.title }}</span>
							<span
								class="text-xs font-medium px-2 py-0.5 rounded-full shrink-0"
								:class="[req.badge.textClass, req.badge.badgeClass]"
							>
								{{ req.badge.text }}
							</span>
						</div>
						<div class="text-xs text-black/50">
							{{ req.category }}<template v-if="req.company"> · {{ req.company }}</template>
						</div>
						<div v-if="req.detail" class="text-xs text-black/60 whitespace-pre-wrap">{{ req.detail }}</div>
						<div v-if="req.resolution_note" class="text-xs text-green-700">
							{{ __('처리 메모') }}: {{ req.resolution_note }}
						</div>

						<!-- HR Manager 상태 변경 -->
						<div v-if="isAdmin && req.transitions.length" class="flex items-center gap-2 pt-1">
							<select
								v-model="statusDraft[req.name]"
								class="flex-1 border border-[var(--k-hairline)] rounded-lg px-2 py-1.5 text-xs text-black bg-white focus:outline-none focus:ring-2 focus:ring-black/60"
							>
								<option value="" disabled>{{ __('상태 변경') }}</option>
								<option v-for="opt in req.transitions" :key="opt" :value="opt">{{ opt }}</option>
							</select>
							<button
								@click="changeStatus(req.name)"
								:disabled="!statusDraft[req.name] || updateStatus.loading"
								class="k-btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
							>
								{{ __('변경') }}
							</button>
						</div>
					</div>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from "vue"
import { createResource } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import { useIsAdmin } from "@/composables/useIsAdmin"
import {
	CATEGORIES,
	CREATE_URL,
	LIST_URL,
	UPDATE_URL,
	makeCreatePayload,
	nextStatusOptions,
	statusBadge,
	validateRequestForm,
} from "@/data/koreaServiceRequestsRuntime"

const __ = inject("$translate")
const isAdmin = useIsAdmin()

// ---------------------------------------------------------------------------
// 상태
// ---------------------------------------------------------------------------
const emptyForm = () => ({ company: "", title: "", category: "", detail: "" })
const form = reactive(emptyForm())
const errors = ref({})
const statusDraft = reactive({})

// ---------------------------------------------------------------------------
// 리소스 (createResource 3종)
// ---------------------------------------------------------------------------
const createRequest = createResource({
	url: CREATE_URL,
	makeParams(values) {
		return { payload: values?.payload }
	},
})

const requestList = createResource({
	url: LIST_URL,
	auto: false,
})

const updateStatus = createResource({
	url: UPDATE_URL,
	makeParams(values) {
		return { name: values?.name, status: values?.status }
	},
})

const requestRows = computed(() => {
	const rows = requestList.data?.requests ?? []
	return rows.map((row) => ({
		...row,
		badge: statusBadge(row.status),
		transitions: nextStatusOptions(row.status),
	}))
})

// ---------------------------------------------------------------------------
// 메서드
// ---------------------------------------------------------------------------
async function submitRequest() {
	const { valid, errors: fieldErrors } = validateRequestForm(form)
	errors.value = fieldErrors
	if (!valid) return

	await createRequest.submit({ payload: makeCreatePayload(form) })

	if (!createRequest.error && createRequest.data) {
		Object.assign(form, emptyForm())
		errors.value = {}
		requestList.fetch()
	}
}

async function changeStatus(name) {
	const status = statusDraft[name]
	if (!status || updateStatus.loading) return
	await updateStatus.submit({ name, status })
	if (!updateStatus.error) {
		statusDraft[name] = ""
		requestList.fetch()
	}
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
onMounted(() => {
	requestList.fetch()
})
</script>
