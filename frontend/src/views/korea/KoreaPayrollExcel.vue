<template>
	<BaseLayout :pageTitle="__('급여 엑셀 업로드/다운로드')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 — lime 색블록 (급여 계열) -->
				<div class="k-block k-block--cream">
					<div class="k-eyebrow">PAYROLL EXCEL</div>
					<div class="mt-1 k-t-display text-[var(--k-ink)]">{{ __('급여 엑셀 업로드/다운로드') }}</div>
					<p class="mt-2 k-t-body text-[var(--k-ink-muted)]">
						{{ __('급여대장을 시스템에서 내려받고, 수정본을 올려 검증한 뒤 승인 시에만 반영합니다.') }}
					</p>
				</div>

				<!-- ① 다운로드 -->
				<div class="k-card p-4 flex flex-col gap-3">
					<div class="k-label px-0.5">{{ __('급여대장 다운로드') }}</div>
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('대상 월') }}</label>
						<input
							type="month"
							v-model="period"
							class="w-full border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-[var(--k-ink)] focus:outline-none focus:ring-2 focus:ring-black/60"
						/>
						<span v-if="!periodValid" class="text-xs text-red-600">{{ __('YYYY-MM 형식의 월을 선택하세요.') }}</span>
					</div>
					<button
						@click="downloadWorkbook"
						:disabled="!periodValid || downloadResource.loading"
						class="k-btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
					>
						<span v-if="downloadResource.loading">{{ __('생성 중...') }}</span>
						<span v-else>{{ __('급여대장 xlsx 다운로드') }}</span>
					</button>
					<div v-if="downloadResource.error" class="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700">
						{{ __('다운로드 중 오류가 발생했습니다.') }} {{ downloadResource.error.messages?.[0] || "" }}
					</div>
				</div>

				<!-- ② 업로드 + 검증 -->
				<div class="k-card p-4 flex flex-col gap-3">
					<div class="k-label px-0.5">{{ __('수정본 업로드 · 검증') }}</div>
					<p class="text-xs text-[var(--k-ink-faint)]">
						{{ __('선택한 대상 월 기준으로 업로드한 급여대장을 파싱·무결성 검증하고, 현재 데이터와의 차이만 미리보기로 보여줍니다. (이 단계에서는 저장하지 않습니다)') }}
					</p>

					<FileUploader
						:fileTypes="['.xlsx']"
						:uploadArgs="{ private: true }"
						@success="onUploadSuccess"
					>
						<template #default="{ openFileSelector, uploading }">
							<button
								@click="openFileSelector"
								:disabled="uploading || !periodValid || validateResource.loading"
								class="k-btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
							>
								<span v-if="uploading">{{ __('업로드 중...') }}</span>
								<span v-else-if="validateResource.loading">{{ __('검증 중...') }}</span>
								<span v-else>{{ __('급여대장 xlsx 선택') }}</span>
							</button>
						</template>
					</FileUploader>

					<div v-if="uploadedFileName" class="text-xs text-[var(--k-ink-faint)]">
						{{ __('업로드 파일') }}: {{ uploadedFileName }}
					</div>

					<!-- 검증 결과 -->
					<template v-if="validationView.status !== 'none'">
						<!-- 오류 -->
						<div v-if="validationView.hasError" class="bg-red-50 border border-red-200 rounded-lg p-3 flex flex-col gap-1">
							<div class="text-xs font-semibold text-red-700">
								{{ validationView.status === 'parse_error' ? __('파일을 읽을 수 없습니다') : __('무결성 검증 실패') }}
							</div>
							<div v-for="(err, i) in validationView.errors" :key="i" class="text-xs text-red-700">
								{{ err }}
							</div>
						</div>

						<!-- 정상 — diff 요약 -->
						<div v-else class="flex flex-col gap-3">
							<div class="grid grid-cols-4 gap-2">
								<div v-for="stat in diffStats" :key="stat.label" class="k-card p-2 flex flex-col items-center gap-0.5">
									<span class="text-lg font-bold text-[var(--k-ink)]">{{ stat.value }}</span>
									<span class="text-[11px] text-[var(--k-ink-faint)]">{{ stat.label }}</span>
								</div>
							</div>

							<div v-if="validationView.changedRows.length" class="flex flex-col gap-1">
								<div class="k-label px-0.5">{{ __('변경 인원 (실지급 delta)') }}</div>
								<div
									v-for="row in validationView.changedRows"
									:key="row.name"
									class="flex justify-between items-center py-1.5 border-t border-[var(--k-hairline)]"
								>
									<span class="text-sm text-[var(--k-ink)]">{{ row.name }}</span>
									<span
										class="text-xs font-semibold"
										:class="row.netDelta >= 0 ? 'text-green-700' : 'text-red-600'"
									>
										{{ formatSignedWon(row.netDelta) }}
									</span>
								</div>
							</div>

							<div v-if="validationView.newRows.length" class="text-xs text-[var(--k-ink-muted)]">
								{{ __('신규') }}: {{ validationView.newRows.map((r) => r.name).join(', ') }}
							</div>
							<div v-if="validationView.missingRows.length" class="text-xs text-[var(--k-ink-muted)]">
								{{ __('누락') }}: {{ validationView.missingRows.map((r) => r.name).join(', ') }}
							</div>
							<div v-if="!hasChanges" class="text-xs text-[var(--k-ink-faint)]">
								{{ __('현재 데이터와 차이가 없습니다.') }}
							</div>
						</div>
					</template>
				</div>

				<!-- ③ 반영 — isAdmin만 -->
				<div v-if="isAdmin && validationView.ok && hasChanges" class="k-card p-4 flex flex-col gap-3">
					<div class="k-label px-0.5">{{ __('반영') }}</div>
					<label class="flex items-start gap-2 cursor-pointer">
						<input type="checkbox" v-model="approved" class="mt-0.5" />
						<span class="text-sm text-[var(--k-ink-muted)]">{{ __('검토했으며 반영을 승인합니다.') }}</span>
					</label>
					<button
						@click="showConfirm = true"
						:disabled="!approved || applyResource.loading"
						class="k-btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
					>
						<span v-if="applyResource.loading">{{ __('반영 중...') }}</span>
						<span v-else>{{ __('반영하기') }}</span>
					</button>

					<div v-if="applyView.applied" class="bg-green-50 border border-green-200 rounded-lg p-3 text-xs text-green-800">
						{{ __('반영 완료') }} · {{ __('신규') }} {{ applyView.created }} · {{ __('갱신') }} {{ applyView.updated }} · {{ __('유지') }} {{ applyView.skipped }} · {{ __('총지급') }} {{ formatWon(applyView.totalGross) }}
					</div>
					<div v-else-if="applyView.blocked" class="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-800">
						{{ __('승인 게이트가 통과되지 않아 반영되지 않았습니다.') }}
					</div>
					<div v-else-if="applyView.errors.length" class="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700">
						<div v-for="(err, i) in applyView.errors" :key="i">{{ err }}</div>
					</div>
				</div>

				<Dialog
					v-model="showConfirm"
					:options="{
						title: __('급여 반영 확인'),
						message: __('업로드한 급여대장을 Salary Slip으로 반영합니다. 계속하시겠습니까?'),
						actions: [
							{ label: __('반영하기'), variant: 'solid', onClick: applyUpload },
							{ label: __('취소'), onClick: () => (showConfirm = false) },
						],
					}"
				/>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject, reactive, ref } from "vue"
import { createResource, Dialog, FileUploader } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import { useIsAdmin } from "@/composables/useIsAdmin"
import {
	APPLY_URL,
	DOWNLOAD_URL,
	VALIDATE_URL,
	buildApplyView,
	buildValidationView,
	defaultPeriod,
	formatSignedWon,
	formatWon,
	hasPayrollChanges,
	isValidPeriod,
} from "@/data/koreaPayrollExcelRuntime"

const __ = inject("$translate")
const isAdmin = useIsAdmin()

// ---------------------------------------------------------------------------
// 상태
// ---------------------------------------------------------------------------
const period = ref(defaultPeriod())
const uploadedFileName = ref("")
const approved = ref(false)
const showConfirm = ref(false)

const periodValid = computed(() => isValidPeriod(period.value))

// ---------------------------------------------------------------------------
// 리소스 (createResource 3종)
// ---------------------------------------------------------------------------
const downloadResource = createResource({
	url: DOWNLOAD_URL,
	makeParams(values) {
		return { period: values?.period }
	},
})

const validateResource = createResource({
	url: VALIDATE_URL,
	makeParams(values) {
		return { file_url: values?.file_url, period: values?.period }
	},
})

const applyResource = createResource({
	url: APPLY_URL,
	makeParams(values) {
		return { file_url: values?.file_url, period: values?.period, human_approved: values?.human_approved }
	},
})

const uploaded = reactive({ file_url: "" })

const validationView = computed(() => buildValidationView(validateResource.data))
const applyView = computed(() => buildApplyView(applyResource.data))
const hasChanges = computed(() => hasPayrollChanges(validationView.value))

const diffStats = computed(() => {
	const c = validationView.value.counts
	return [
		{ label: __("신규"), value: c.new },
		{ label: __("변경"), value: c.changed },
		{ label: __("동일"), value: c.same },
		{ label: __("누락"), value: c.missing },
	]
})

// ---------------------------------------------------------------------------
// 메서드
// ---------------------------------------------------------------------------
async function downloadWorkbook() {
	if (!periodValid.value) return
	await downloadResource.submit({ period: period.value })
	const fileUrl = downloadResource.data?.file_url
	if (!downloadResource.error && fileUrl) {
		window.open(fileUrl, "_blank")
	}
}

async function onUploadSuccess(file) {
	// 새 파일 업로드 시 이전 검증/반영 결과 초기화
	applyResource.reset?.()
	approved.value = false
	uploaded.file_url = file?.file_url ?? ""
	uploadedFileName.value = file?.file_name ?? file?.name ?? ""
	if (!uploaded.file_url || !periodValid.value) return
	await validateResource.submit({ file_url: uploaded.file_url, period: period.value })
}

async function applyUpload() {
	showConfirm.value = false
	if (!approved.value || !uploaded.file_url || !periodValid.value) return
	await applyResource.submit({
		file_url: uploaded.file_url,
		period: period.value,
		human_approved: true,
	})
	if (!applyResource.error && applyView.value.applied) {
		// 반영 후 재검증하여 diff 갱신
		await validateResource.submit({ file_url: uploaded.file_url, period: period.value })
	}
}
</script>
