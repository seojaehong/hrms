<template>
	<BaseLayout :pageTitle="__('연차 사용촉진 (§61)')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 -->
				<div class="pt-1">
					<div class="k-eyebrow">ANNUAL LEAVE PROMOTION</div>
					<div class="mt-1 text-xl font-bold tracking-tight text-black">{{ __('연차 사용촉진 (§61)') }}</div>
					<p class="mt-2 text-sm text-black/60">
						근로기준법 제61조 사용촉진 기한을 계산하고, 서면 촉구·통보 초안과 미사용 연차수당을 확인합니다.
					</p>
				</div>

				<!-- 입력 카드 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div class="text-base font-bold tracking-tight text-black">{{ __('촉진 기한 계산') }}</div>

					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('입사일') }}</label>
							<input
								type="date"
								v-model="form.hire_date"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('판정 기준일 (오늘)') }}</label>
							<input
								type="date"
								v-model="form.as_of"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
					</div>

					<div class="flex items-center gap-2">
						<input id="first-year-toggle" type="checkbox" v-model="form.is_first_year" class="accent-black" />
						<label for="first-year-toggle" class="text-sm text-black/70">
							{{ __('근속 1년 미만 (§60② 특칙 — 3개월 전/1개월 전 스케줄)') }}
						</label>
					</div>

					<button
						@click="calculateSchedule"
						:disabled="promotionSchedule.loading || !canSubmitSchedule"
						class="w-full py-3 bg-black text-white text-sm rounded-full font-semibold hover:bg-black/80 active:bg-black disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
					>
						<span v-if="promotionSchedule.loading">{{ __('계산 중...') }}</span>
						<span v-else>{{ __('촉진 기한 계산') }}</span>
					</button>
				</div>

				<!-- 타임라인 카드 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div class="text-base font-bold tracking-tight text-black">{{ __('촉진 시한 타임라인') }}</div>

					<div v-if="promotionSchedule.loading" class="text-center py-8 text-black/40 text-sm">
						{{ __('계산 중...') }}
					</div>
					<div v-else-if="promotionSchedule.error" class="text-center py-6 text-red-600 text-sm">
						{{ __('계산에 실패했습니다. 입력값을 확인해 주세요. (근속 1년 미만이면 특칙을 체크하세요.)') }}
					</div>
					<template v-else-if="schedule">
						<!-- 현재 단계 (cream 블록) -->
						<div class="k-block k-block--cream -mx-1">
							<div class="k-eyebrow">CURRENT STAGE</div>
							<div class="mt-1 text-sm font-medium text-black/60">현재 단계 ({{ schedule.as_of }} 기준)</div>
							<div class="k-display">{{ stageLabel(schedule.stage) }}</div>
							<p class="mt-2 text-xs text-black/55">{{ stageHint(schedule.stage) }}</p>
						</div>

						<!-- 타임라인 -->
						<div class="flex flex-col">
							<div
								v-for="(step, idx) in timelineSteps"
								:key="step.key"
								class="flex gap-3"
							>
								<!-- 마커 열 -->
								<div class="flex flex-col items-center">
									<div
										class="w-3 h-3 rounded-full mt-1.5 shrink-0"
										:class="step.current ? 'bg-black ring-4 ring-black/15' : 'bg-black/20'"
									></div>
									<div v-if="idx < timelineSteps.length - 1" class="w-px flex-1 bg-[var(--k-hairline)]"></div>
								</div>
								<!-- 내용 -->
								<div class="pb-4 flex-1" :class="step.current ? '' : 'opacity-60'">
									<div class="text-sm font-semibold text-black flex items-center gap-2">
										{{ step.label }}
										<span
											v-if="step.current"
											class="text-[10px] font-bold uppercase tracking-wide bg-black text-white rounded-full px-2 py-0.5"
										>{{ __('현재') }}</span>
									</div>
									<div class="text-xs text-black/60 k-numeric mt-0.5">{{ step.period }}</div>
									<div class="text-xs text-black/45 mt-0.5">{{ step.note }}</div>
								</div>
							</div>
						</div>

						<!-- 1년 미만 특칙 단서분 -->
						<div v-if="schedule.proviso_stage" class="bg-[var(--k-surface-soft)] rounded-lg p-3 text-xs text-black/60 leading-relaxed flex flex-col gap-1">
							<div class="k-label mb-1">단서분 — 촉구 후 발생 휴가 (§61② 단서)</div>
							<div class="flex justify-between"><span>1차 촉구 기간</span><span class="k-numeric">{{ schedule.proviso_notice_window_start }} ~ {{ schedule.proviso_notice_deadline }}</span></div>
							<div class="flex justify-between"><span>2차 통보 기한</span><span class="k-numeric">{{ schedule.proviso_second_deadline }}까지</span></div>
							<div class="flex justify-between font-semibold text-black"><span>단서분 현재 단계</span><span>{{ stageLabel(schedule.proviso_stage) }}</span></div>
						</div>

						<div class="text-xs text-black/45">근거: {{ (schedule.legal_basis || []).join(', ') }}</div>
					</template>
					<div v-else class="text-center py-8 text-black/40 text-sm">
						{{ __('입사일과 기준일을 입력하고 계산 버튼을 눌러주세요.') }}
					</div>
				</div>

				<!-- 촉구문 미리보기 카드 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div class="text-base font-bold tracking-tight text-black">{{ __('서면 촉구·통보 초안') }}</div>

					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('근로자 이름') }}</label>
							<input
								type="text"
								v-model="noticeForm.worker_name"
								:placeholder="__('예: 김가상')"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('미사용 연차 (일)') }}</label>
							<input
								type="number"
								v-model.number="noticeForm.unused_days"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-black k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
					</div>

					<!-- 단계 토글 -->
					<div class="flex rounded-full border border-[var(--k-hairline)] p-1 text-sm font-semibold">
						<button
							class="flex-1 py-2 rounded-full transition-colors"
							:class="noticeForm.stage === 1 ? 'bg-black text-white' : 'text-black/60'"
							@click="noticeForm.stage = 1"
						>{{ __('1차 촉구서') }}</button>
						<button
							class="flex-1 py-2 rounded-full transition-colors"
							:class="noticeForm.stage === 2 ? 'bg-black text-white' : 'text-black/60'"
							@click="noticeForm.stage = 2"
						>{{ __('2차 지정 통보서') }}</button>
					</div>

					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('기한 날짜') }}<span class="normal-case tracking-normal opacity-70"> — 타임라인 계산 시 자동 입력</span></label>
						<input
							type="date"
							v-model="noticeForm.deadline"
							class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
						/>
					</div>

					<button
						@click="generateNotice"
						:disabled="promotionNotice.loading || !canSubmitNotice"
						class="w-full py-3 bg-black text-white text-sm rounded-full font-semibold hover:bg-black/80 active:bg-black disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
					>
						<span v-if="promotionNotice.loading">{{ __('생성 중...') }}</span>
						<span v-else>{{ __('초안 생성') }}</span>
					</button>

					<div v-if="promotionNotice.error" class="text-center py-4 text-red-600 text-sm">
						{{ __('초안 생성에 실패했습니다. 입력값을 확인해 주세요.') }}
					</div>
					<template v-else-if="noticeMarkdown">
						<div class="bg-[var(--k-surface-soft)] rounded-lg p-3 text-xs text-black/70 leading-relaxed whitespace-pre-wrap font-mono">{{ noticeMarkdown }}</div>
						<button
							@click="copyNotice"
							class="w-full py-2.5 border border-black text-black text-sm rounded-full font-semibold hover:bg-black/5 transition-colors"
						>{{ copied ? __('복사됨 ✓') : __('마크다운 복사') }}</button>
					</template>
				</div>

				<!-- 미사용 수당 카드 -->
				<div class="k-card p-4 flex flex-col gap-4">
					<div class="text-base font-bold tracking-tight text-black">{{ __('미사용 연차수당 정산') }}</div>

					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('월 기본급 (원)') }}</label>
							<input
								type="number"
								v-model.number="allowanceForm.monthly_base_salary"
								:placeholder="__('예: 2090000')"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-black k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('미사용 연차 (일)') }}</label>
							<input
								type="number"
								v-model.number="noticeForm.unused_days"
								class="border border-[var(--k-hairline)] rounded-lg px-3 py-2 text-sm text-black k-numeric focus:outline-none focus:ring-2 focus:ring-black/60 w-full"
							/>
						</div>
					</div>

					<div class="flex items-center gap-2">
						<input id="promo-done-toggle" type="checkbox" v-model="allowanceForm.promotion_completed" class="accent-black" />
						<label for="promo-done-toggle" class="text-sm text-black/70">
							{{ __('§61 촉진 조치(1·2차) 모두 적법하게 이행함') }}
						</label>
					</div>

					<button
						@click="calculateAllowance"
						:disabled="settleUnusedLeave.loading || !canSubmitAllowance"
						class="w-full py-3 bg-black text-white text-sm rounded-full font-semibold hover:bg-black/80 active:bg-black disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
					>
						<span v-if="settleUnusedLeave.loading">{{ __('계산 중...') }}</span>
						<span v-else>{{ __('수당 계산') }}</span>
					</button>

					<div v-if="settleUnusedLeave.error" class="text-center py-4 text-red-600 text-sm">
						{{ __('계산에 실패했습니다. 입력값을 확인해 주세요.') }}
					</div>
					<template v-else-if="allowance">
						<div class="k-block k-block--cream -mx-1">
							<div class="k-eyebrow">UNUSED LEAVE ALLOWANCE</div>
							<div class="mt-1 text-sm font-medium text-black/60">미사용 연차수당</div>
							<div class="k-display">{{ formatKRW(allowance.allowance_won) }}</div>
							<p class="mt-2 text-xs" :class="allowance.compensation_exempt ? 'text-black/55' : 'text-black/70'">
								{{ allowance.reason }}
							</p>
						</div>
					</template>
				</div>

				<!-- 면책 고지 -->
				<div class="k-card p-3 text-xs text-black/60 leading-relaxed">
					<span class="font-semibold text-black">참고용 계산입니다.</span>
					§61 면책은 서면 촉구·통보의 형식과 시기를 모두 충족해야 인정됩니다.
					확정 판단은 노무사 검토를 거쳐 확정하시기 바랍니다.
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, reactive, ref, inject } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import {
	promotionSchedule,
	promotionNotice,
	settleUnusedLeave,
} from "@/data/koreaLeavePromotionRuntime"

const __ = inject("$translate")

const form = reactive({
	hire_date: "",
	as_of: new Date().toISOString().slice(0, 10),
	is_first_year: false,
})
const noticeForm = reactive({
	worker_name: "",
	unused_days: 0,
	deadline: "",
	stage: 1,
})
const allowanceForm = reactive({
	monthly_base_salary: null,
	promotion_completed: false,
})

const schedule = ref(null)
const noticeMarkdown = ref(null)
const allowance = ref(null)
const copied = ref(false)

const canSubmitSchedule = computed(() => form.hire_date && form.as_of)
const canSubmitNotice = computed(
	() => noticeForm.worker_name && noticeForm.unused_days > 0 && noticeForm.deadline
)
const canSubmitAllowance = computed(
	() => allowanceForm.monthly_base_salary != null && noticeForm.unused_days >= 0
)

const STAGE_LABELS = {
	촉구_전: "촉구 기간 전",
	"1차_촉구_기간": "1차 촉구 기간",
	"2차_통보_기간": "2차 통보 기간",
	통보_기한_도과: "통보 기한 도과",
	소멸: "연차 소멸",
}
const STAGE_HINTS = {
	촉구_전: "아직 촉구 기간이 아닙니다. 1차 촉구 창이 열리면 서면으로 촉구하세요.",
	"1차_촉구_기간": "지금 근로자에게 미사용 일수를 알리고 사용시기 지정을 서면으로 촉구해야 합니다.",
	"2차_통보_기간": "근로자가 시기를 통보하지 않았다면, 회사가 사용시기를 지정해 서면 통보해야 합니다.",
	통보_기한_도과: "법정 통보 기한이 지났습니다 — 이번 기간은 §61 면책 요건을 충족하지 못했을 수 있습니다.",
	소멸: "해당 연차는 이미 소멸했습니다.",
}

function stageLabel(stage) {
	return STAGE_LABELS[stage] ?? stage
}
function stageHint(stage) {
	return STAGE_HINTS[stage] ?? ""
}

const timelineSteps = computed(() => {
	const s = schedule.value
	if (!s) return []
	return [
		{
			key: "first",
			label: "1차 서면 촉구",
			period: `${s.first_notice_window_start} ~ ${s.first_notice_deadline}`,
			note: "미사용 일수를 알리고 근로자의 사용시기 지정·통보를 촉구 (10일 이내)",
			current: s.stage === "1차_촉구_기간",
		},
		{
			key: "second",
			label: "2차 사용시기 지정 통보",
			period: `${s.second_notice_deadline}까지`,
			note: "근로자 미통보 시 회사가 사용시기를 지정해 서면 통보",
			current: s.stage === "2차_통보_기간",
		},
		{
			key: "expiry",
			label: "연차 소멸",
			period: s.expiry_date,
			note: "촉진 완료 시 보상 의무 없이 소멸 (§60⑦ 본문)",
			current: s.stage === "소멸" || s.stage === "통보_기한_도과",
		},
	]
})

function formatKRW(amount) {
	if (amount == null) return "-"
	return Number(amount).toLocaleString("ko-KR") + "원"
}

async function calculateSchedule() {
	schedule.value = null
	await promotionSchedule.submit({ ...form })
	if (!promotionSchedule.error) {
		schedule.value = promotionSchedule.data
		// 촉구문 기한을 현재 단계에 맞춰 자동 채움
		const s = promotionSchedule.data
		if (s.stage === "2차_통보_기간") {
			noticeForm.stage = 2
			noticeForm.deadline = s.second_notice_deadline
		} else {
			noticeForm.stage = 1
			noticeForm.deadline = s.first_notice_deadline
		}
	}
}

async function generateNotice() {
	noticeMarkdown.value = null
	copied.value = false
	await promotionNotice.submit({
		worker: JSON.stringify({ name: noticeForm.worker_name }),
		unused_days: noticeForm.unused_days,
		deadline: noticeForm.deadline,
		stage: noticeForm.stage,
	})
	if (!promotionNotice.error) {
		noticeMarkdown.value = promotionNotice.data
	}
}

async function copyNotice() {
	if (!noticeMarkdown.value) return
	await navigator.clipboard.writeText(noticeMarkdown.value)
	copied.value = true
	setTimeout(() => (copied.value = false), 2000)
}

async function calculateAllowance() {
	allowance.value = null
	await settleUnusedLeave.submit({
		monthly_base_salary: allowanceForm.monthly_base_salary,
		unused_days: noticeForm.unused_days,
		promotion_completed: allowanceForm.promotion_completed,
	})
	if (!settleUnusedLeave.error) {
		allowance.value = settleUnusedLeave.data
	}
}
</script>
