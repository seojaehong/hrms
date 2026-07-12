<template>
	<BaseLayout :pageTitle="__('근무시간 제출')">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-white p-4 pb-40">

				<!-- 히어로 — 근태(mint) 색블록 + 월 선택 -->
				<section class="k-block k-block--cream">
					<div class="flex items-start justify-between gap-3">
						<div>
							<p class="k-eyebrow">TIME INPUT</p>
							<h1 class="mt-1 text-2xl font-bold tracking-tight text-black">{{ __("근무시간 제출") }}</h1>
							<p class="mt-1 text-sm font-medium text-black/60">
								{{ __("초과·야간·휴일·파트 시간을 직접 입력해 채팅 전달 누락을 막습니다.") }}
							</p>
						</div>
						<span v-if="allSubmitted" class="whitespace-nowrap rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-800">
							{{ __("제출 완료") }}
						</span>
					</div>
					<div class="mt-4">
						<label class="text-xs font-medium text-black/50">{{ __("대상 월") }}</label>
						<input
							v-model="period"
							type="month"
							class="k-numeric mt-1 w-full rounded-lg border border-black/10 bg-white/70 px-3 py-2 text-sm font-semibold text-black focus:outline-none focus:ring-2 focus:ring-black/20"
							@change="loadGrid"
						/>
					</div>
					<div class="mt-3 grid grid-cols-4 gap-2">
						<div v-for="field in HOUR_FIELDS" :key="field" class="rounded-xl bg-white/60 p-2 text-center">
							<p class="k-numeric text-lg font-bold text-black">{{ totals[field] }}</p>
							<p class="text-xs font-medium text-black/60">{{ FIELD_LABELS[field] }}(h)</p>
						</div>
					</div>
				</section>

				<!-- 제출 완료 배지 -->
				<div v-if="allSubmitted" class="k-card flex items-center gap-2 p-4">
					<span class="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-semibold text-green-800">{{ __("읽기 전용") }}</span>
					<p class="text-sm font-semibold text-black">
						{{ __("제출 완료") }} · {{ submittedAtLabel }}
					</p>
				</div>

				<!-- 오류 배너 -->
				<div v-if="errorMessage" class="rounded-xl bg-red-100 p-3 text-xs font-semibold text-red-700">
					{{ errorMessage }}
				</div>
				<div v-if="successMessage" class="rounded-xl bg-green-100 p-3 text-xs font-semibold text-green-800">
					{{ successMessage }}
				</div>

				<!-- 직원 그리드 — 모바일: 직원별 카드 스택 -->
				<div v-if="loading" class="k-card p-4 text-sm text-black/40">{{ __("불러오는 중…") }}</div>
				<section v-else class="flex flex-col gap-3">
					<div v-for="row in rows" :key="row.employee" class="k-card p-4">
						<div class="flex items-center justify-between">
							<p class="text-sm font-bold text-black">{{ row.employee_name || row.employee }}</p>
							<span
								class="rounded-full px-2.5 py-0.5 text-xs font-semibold"
								:class="row.status === 'submitted' ? 'bg-green-100 text-green-800' : 'bg-black/10 text-black'"
							>
								{{ row.status === "submitted" ? __("제출됨") : __("작성 중") }}
							</span>
						</div>
						<div class="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
							<div v-for="field in HOUR_FIELDS" :key="field">
								<label class="text-xs text-black/50">{{ FIELD_LABELS[field] }}({{ __("시간") }})</label>
								<input
									v-model="row[field]"
									type="number"
									min="0"
									:max="MAX_HOURS"
									step="0.5"
									inputmode="decimal"
									:disabled="isRowReadonly(row)"
									class="k-numeric mt-1 w-full rounded-lg border px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black/20 disabled:bg-[var(--k-surface-soft)] disabled:text-black/40"
									:class="fieldInvalid(row, field) ? 'border-red-400 bg-red-50' : 'border-[var(--k-hairline)] bg-white'"
								/>
							</div>
						</div>
						<p v-if="rowErrorText(row)" class="mt-2 text-xs font-semibold text-red-700">{{ rowErrorText(row) }}</p>
						<input
							v-model="row.note"
							type="text"
							:placeholder="__('메모 (예: 5월 누락분 소급)')"
							:disabled="isRowReadonly(row)"
							class="mt-2 w-full rounded-lg border border-[var(--k-hairline)] bg-white px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black/20 disabled:bg-[var(--k-surface-soft)] disabled:text-black/40"
						/>
					</div>
					<div v-if="!rows.length" class="k-card p-4 text-sm text-black/40">
						{{ __("재직 중인 직원이 없습니다.") }}
					</div>
				</section>

				<!-- 하단 고정 액션 -->
				<div v-if="!allSubmitted" class="fixed inset-x-0 bottom-16 z-40 border-t border-[var(--k-hairline)] bg-white/95 p-4 backdrop-blur">
					<div class="mx-auto flex max-w-xl gap-3">
						<button
							class="k-btn-secondary flex-1 border-[var(--k-hairline)] disabled:opacity-50"
							:disabled="saving || loading"
							@click="saveDraft"
						>
							{{ saving ? __("저장 중…") : __("임시저장") }}
						</button>
						<button
							class="k-btn-primary flex-1 font-bold disabled:opacity-50"
							:disabled="saving || loading"
							@click="openSubmitDialog"
						>
							{{ __("제출") }}
						</button>
					</div>
				</div>

				<!-- 제출 확인 다이얼로그 -->
				<div
					v-if="showSubmitDialog"
					class="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4"
					@click.self="showSubmitDialog = false"
				>
					<div class="w-full max-w-sm rounded-2xl bg-white p-6">
						<h3 class="text-base font-bold text-black">{{ __("근무시간 제출 확인") }}</h3>
						<p class="mt-2 text-sm text-black/60">
							{{ periodLabel }} {{ __("근무시간을 제출합니다.") }}
						</p>
						<div class="mt-4 rounded-xl bg-red-100 p-3 text-xs font-semibold text-red-700">
							{{ __("제출 후에는 수정할 수 없습니다. 입력한 시간을 다시 확인하세요.") }}
						</div>
						<div class="mt-5 flex gap-3">
							<button
								class="k-btn-secondary flex-1 border-[var(--k-hairline)]"
								@click="showSubmitDialog = false"
							>
								{{ __("취소") }}
							</button>
							<button
								class="k-btn-primary flex-1 font-bold disabled:opacity-50"
								:disabled="submitting"
								@click="doSubmit"
							>
								{{ submitting ? __("제출 중…") : __("제출 확인") }}
							</button>
						</div>
					</div>
				</div>

			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { ref, computed, inject, onMounted } from "vue"
import BaseLayout from "@/components/BaseLayout.vue"
import { timeInputList, timeInputSave, timeInputSubmit } from "@/data/koreaTimeInputRuntime"
import {
	KOREA_TIME_INPUT_HOUR_FIELDS as HOUR_FIELDS,
	KOREA_TIME_INPUT_FIELD_LABELS as FIELD_LABELS,
	KOREA_TIME_INPUT_MAX_HOURS as MAX_HOURS,
	normalizeHoursValue,
	validateTimeInputRows,
	sumTimeInputRows,
	buildSaveRows,
	currentPeriod,
	isValidPeriod,
} from "@/data/koreaTimeInputCore"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

// ── 상태 ────────────────────────────────────────────────────────
const period = ref(currentPeriod())
const rows = ref([])
const listMeta = ref(null)
const loading = ref(false)
const saving = ref(false)
const submitting = ref(false)
const errorMessage = ref("")
const successMessage = ref("")
const showSubmitDialog = ref(false)

const periodLabel = computed(() => {
	const [year, month] = period.value.split("-")
	return `${year}년 ${Number(month)}월`
})

const totals = computed(() => sumTimeInputRows(rows.value))

const allSubmitted = computed(() => Boolean(listMeta.value?.all_submitted))

const submittedAtLabel = computed(() => {
	const submitted = rows.value.find((row) => row.submitted_at)
	if (!submitted?.submitted_at) return ""
	return dayjs ? dayjs(submitted.submitted_at).format("YYYY-MM-DD HH:mm") : submitted.submitted_at
})

function isRowReadonly(row) {
	return row.status === "submitted" || allSubmitted.value
}

function fieldInvalid(row, field) {
	return normalizeHoursValue(row[field]) === null
}

function rowErrorText(row) {
	const invalid = HOUR_FIELDS.filter((field) => fieldInvalid(row, field))
	if (!invalid.length) return ""
	return `${invalid.map((field) => FIELD_LABELS[field]).join("·")} 시간은 0~${MAX_HOURS} 사이 숫자여야 합니다.`
}

// ── 데이터 로딩 ─────────────────────────────────────────────────
async function loadGrid() {
	if (!isValidPeriod(period.value)) return
	loading.value = true
	errorMessage.value = ""
	successMessage.value = ""
	try {
		const result = await timeInputList.submit({ period: period.value })
		listMeta.value = result
		rows.value = (result?.rows || []).map((row) => ({ ...row }))
	} catch (error) {
		errorMessage.value = error?.messages?.[0] || error?.message || __("근무시간 목록을 불러오지 못했습니다.")
	} finally {
		loading.value = false
	}
}

// ── 임시저장 ────────────────────────────────────────────────────
async function saveDraft() {
	const editable = rows.value.filter((row) => !isRowReadonly(row))
	const validation = validateTimeInputRows(editable)
	if (!validation.valid) {
		errorMessage.value = validation.errors[0].message
		return
	}
	saving.value = true
	errorMessage.value = ""
	successMessage.value = ""
	try {
		const result = await timeInputSave.submit({
			period: period.value,
			rows: buildSaveRows(editable),
		})
		await loadGrid()
		successMessage.value =
			__("임시저장이 완료되었습니다.") + ` (신규 ${result?.created ?? 0} · 수정 ${result?.updated ?? 0})`
	} catch (error) {
		errorMessage.value = error?.messages?.[0] || error?.message || __("임시저장에 실패했습니다.")
	} finally {
		saving.value = false
	}
}

// ── 제출 ────────────────────────────────────────────────────────
function openSubmitDialog() {
	const editable = rows.value.filter((row) => !isRowReadonly(row))
	const validation = validateTimeInputRows(editable)
	if (!validation.valid) {
		errorMessage.value = validation.errors[0].message
		return
	}
	showSubmitDialog.value = true
}

async function doSubmit() {
	submitting.value = true
	errorMessage.value = ""
	try {
		// 제출 직전 최신 입력을 draft로 저장한 뒤 확정한다.
		const editable = rows.value.filter((row) => !isRowReadonly(row))
		if (editable.length) {
			await timeInputSave.submit({ period: period.value, rows: buildSaveRows(editable) })
		}
		await timeInputSubmit.submit({ period: period.value })
		showSubmitDialog.value = false
		successMessage.value = __("근무시간이 제출되었습니다. 급여 반영은 담당 노무사가 확인합니다.")
		await loadGrid()
	} catch (error) {
		errorMessage.value = error?.messages?.[0] || error?.message || __("제출에 실패했습니다.")
	} finally {
		submitting.value = false
	}
}

onMounted(loadGrid)
</script>
