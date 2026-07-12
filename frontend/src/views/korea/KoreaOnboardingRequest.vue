<template>
	<BaseLayout :pageTitle="__('입사자 등록 요청')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 — cream 색블록 (직원/사업장 계열) -->
				<div class="k-block k-block--cream">
					<div class="k-eyebrow">ONBOARDING</div>
					<div class="mt-1 text-xl font-bold tracking-tight text-[var(--k-ink)]">{{ __('입사자 등록 요청') }}</div>
					<p class="mt-2 text-sm text-[var(--k-ink-muted)]">
						{{ __('신규 입사자 정보를 표준 폼으로 제출하면 4대보험 취득신고까지 연결됩니다.') }}
					</p>
				</div>

				<!-- 성공 화면 -->
				<div v-if="submitted" class="k-card p-4 flex flex-col gap-3">
					<div class="flex items-center gap-2">
						<span class="text-2xl">✅</span>
						<div class="text-base font-bold tracking-tight text-[var(--k-ink)]">{{ __('등록 요청이 접수되었습니다') }}</div>
					</div>
					<div class="flex flex-col divide-y divide-[var(--k-hairline-soft)]">
						<div v-for="row in successSummaryRows" :key="row.label" class="flex justify-between py-2">
							<span class="text-xs text-[var(--k-ink-faint)]">{{ row.label }}</span>
							<span class="text-xs font-medium text-[var(--k-ink)]">{{ row.value }}</span>
						</div>
					</div>
					<button
						@click="resetForm"
						class="k-btn-primary w-full"
					>
						{{ __('추가 등록') }}
					</button>
				</div>

				<!-- 입력 폼 -->
				<div v-else class="k-card p-4 flex flex-col gap-4">
					<!-- 사업장 -->
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('취득사업장') }} *</label>
						<input
							type="text"
							v-model="form.company"
							:placeholder="__('예: 노호')"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60"
						/>
						<span v-if="errors.company" class="text-xs text-red-600">{{ errors.company }}</span>
					</div>

					<!-- 이름 -->
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('이름') }} *</label>
						<input
							type="text"
							v-model="form.full_name"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60"
						/>
						<span v-if="errors.full_name" class="text-xs text-red-600">{{ errors.full_name }}</span>
					</div>

					<!-- 주민등록번호 — type=password, 노출토글 없음 -->
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('주민등록번호') }} *</label>
						<input
							type="password"
							v-model="form.rrn"
							autocomplete="off"
							inputmode="numeric"
							:placeholder="__('13자리 (하이픈 허용)')"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60"
						/>
						<span class="k-label">{{ __('암호화 저장 · 4대보험 취득신고에만 사용') }}</span>
						<span v-if="errors.rrn" class="text-xs text-red-600">{{ errors.rrn }}</span>
					</div>

					<!-- 입사일 -->
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('입사일') }} *</label>
						<input
							type="date"
							v-model="form.join_date"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60"
						/>
						<span v-if="errors.join_date" class="text-xs text-red-600">{{ errors.join_date }}</span>
					</div>

					<!-- 신고보수 -->
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('신고보수 (비과세 제외, 월)') }} *</label>
						<input
							type="number"
							v-model="form.reported_monthly_wage"
							min="0"
							step="1"
							:placeholder="__('예: 2800000')"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60"
						/>
						<span v-if="errors.reported_monthly_wage" class="text-xs text-red-600">{{ errors.reported_monthly_wage }}</span>
					</div>

					<!-- 계약형태 -->
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('계약형태') }} *</label>
						<select
							v-model="form.contract_type"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] bg-[var(--k-card)] focus:outline-none focus:ring-2 focus:ring-black/60"
						>
							<option value="" disabled>{{ __('선택하세요') }}</option>
							<option v-for="type in CONTRACT_TYPES" :key="type" :value="type">{{ type }}</option>
						</select>
						<span v-if="errors.contract_type" class="text-xs text-red-600">{{ errors.contract_type }}</span>
					</div>

					<!-- 연락처 (선택) -->
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('연락처 (선택)') }}</label>
						<input
							type="tel"
							v-model="form.phone"
							:placeholder="__('010-0000-0000')"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60"
						/>
					</div>

					<!-- 비고 (선택) -->
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('비고 (선택)') }}</label>
						<textarea
							v-model="form.note"
							rows="2"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60"
						/>
					</div>

					<!-- 제출 CTA — 블랙 pill -->
					<button
						@click="submitRequest"
						:disabled="createRequest.loading"
						class="k-btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
					>
						<span v-if="createRequest.loading">{{ __('제출 중...') }}</span>
						<span v-else>{{ __('등록 요청 제출') }}</span>
					</button>

					<div
						v-if="createRequest.error"
						class="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700"
					>
						{{ __('제출 중 오류가 발생했습니다.') }} {{ createRequest.error.messages?.[0] || "" }}
					</div>
				</div>

				<!-- 내 요청 현황 -->
				<div class="flex flex-col gap-3">
					<div class="k-label px-1">{{ __('내 요청 현황') }}</div>

					<div
						v-if="requestRows.length === 0"
						class="k-card p-6 flex flex-col items-center gap-2 text-center"
					>
						<span class="text-2xl">📋</span>
						<div class="text-xs text-[var(--k-ink-faint)]">{{ __('아직 등록 요청이 없습니다.') }}</div>
					</div>

					<div
						v-for="req in requestRows"
						:key="req.name"
						class="k-card p-4 flex flex-col gap-1.5"
					>
						<div class="flex justify-between items-center">
							<span class="text-sm font-semibold text-[var(--k-ink)]">{{ req.full_name }}</span>
							<span
								class="text-xs font-medium px-2 py-0.5 rounded-full"
								:class="[req.badge.textClass, req.badge.badgeClass]"
							>
								{{ req.badge.text }}
							</span>
						</div>
						<div class="text-xs text-[var(--k-ink-faint)]">
							{{ req.company }} · {{ __('입사일') }} {{ req.join_date }} · {{ req.contract_type }}
						</div>
						<div class="text-xs text-[var(--k-ink-faint)]">
							{{ req.masked_rrn }} · {{ formatWage(req.reported_monthly_wage) }}
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
import {
	CONTRACT_TYPES,
	CREATE_URL,
	LIST_URL,
	formatWage,
	makeCreatePayload,
	statusBadge,
	validateOnboardingForm,
} from "@/data/koreaOnboardingRequestRuntime"

const __ = inject("$translate")
const employee = inject("$employee")

// ---------------------------------------------------------------------------
// 상태
// ---------------------------------------------------------------------------
const emptyForm = () => ({
	company: employee?.data?.company ?? "",
	full_name: "",
	rrn: "",
	join_date: "",
	reported_monthly_wage: "",
	contract_type: "",
	phone: "",
	note: "",
})

const form = reactive(emptyForm())
const errors = ref({})
const submitted = ref(false)
const successSummary = ref(null)

// ---------------------------------------------------------------------------
// 리소스
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

const requestRows = computed(() => {
	const rows = requestList.data?.requests ?? []
	return rows.map((row) => ({ ...row, badge: statusBadge(row.status) }))
})

const successSummaryRows = computed(() => {
	const s = successSummary.value
	if (!s) return []
	return [
		{ label: __("이름"), value: s.full_name },
		{ label: __("취득사업장"), value: s.company },
		{ label: __("주민등록번호"), value: s.masked_rrn },
		{ label: __("입사일"), value: s.join_date },
		{ label: __("신고보수"), value: formatWage(s.reported_monthly_wage) },
		{ label: __("계약형태"), value: s.contract_type },
	]
})

// ---------------------------------------------------------------------------
// 메서드
// ---------------------------------------------------------------------------
async function submitRequest() {
	const { valid, errors: fieldErrors } = validateOnboardingForm(form)
	errors.value = fieldErrors
	if (!valid) return

	await createRequest.submit({ payload: makeCreatePayload(form) })

	if (!createRequest.error && createRequest.data) {
		// 응답에는 rrn 평문이 없다(서버 불변식) — masked_rrn만 표시
		successSummary.value = createRequest.data
		submitted.value = true
		form.rrn = "" // 제출 후 메모리상 rrn 즉시 폐기
		requestList.fetch()
	}
}

function resetForm() {
	Object.assign(form, emptyForm())
	errors.value = {}
	successSummary.value = null
	submitted.value = false
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
onMounted(() => {
	requestList.fetch()
})
</script>
