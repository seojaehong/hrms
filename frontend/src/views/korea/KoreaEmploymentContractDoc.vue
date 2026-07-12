<template>
	<BaseLayout :pageTitle="__('근로계약서 작성 (§17)')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 -->
				<div class="pt-1">
					<div class="k-eyebrow">EMPLOYMENT CONTRACT</div>
					<div class="mt-1 text-xl font-bold tracking-tight text-black">{{ __('근로계약서 작성 (§17)') }}</div>
					<p class="mt-2 text-sm text-black/60">
						근로기준법 제17조 필수기재사항을 빠짐없이 입력하고, 누락 항목을 확인한 뒤 서면 교부용 초안을 생성합니다.
					</p>
				</div>

				<!-- 회사 정보 -->
				<div class="k-card p-4 flex flex-col gap-3">
					<div class="text-base font-bold tracking-tight text-black">{{ __('사업주(회사) 정보') }}</div>
					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('사업체명') }}</label>
							<input type="text" v-model="form.company.company_name" :placeholder="__('예: 가상상사')" class="k-input" />
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('대표자') }}</label>
							<input type="text" v-model="form.company.representative_name" :placeholder="__('예: 홍길동')" class="k-input" />
						</div>
					</div>
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('사업장 주소') }}</label>
						<input type="text" v-model="form.company.address" class="k-input" />
					</div>
					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('사업자등록번호') }}</label>
							<input type="text" v-model="form.company.business_registration_number" :placeholder="__('예: 123-45-67890')" class="k-input" />
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('연락처 (선택)') }}</label>
							<input type="text" v-model="form.company.contact" class="k-input" />
						</div>
					</div>
				</div>

				<!-- 근로자 정보 -->
				<div class="k-card p-4 flex flex-col gap-3">
					<div class="text-base font-bold tracking-tight text-black">{{ __('근로자 정보') }}</div>
					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('근로자 이름') }}</label>
							<input type="text" v-model="form.employee.employee_name" :placeholder="__('예: 김가상')" class="k-input" />
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('연락처 (선택)') }}</label>
							<input type="text" v-model="form.employee.contact" class="k-input" />
						</div>
					</div>
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('주소') }}</label>
						<input type="text" v-model="form.employee.address" class="k-input" />
					</div>
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('주민등록번호 (선택, 마스킹 처리됨)') }}</label>
						<input type="text" v-model="form.employee.resident_registration_number" :placeholder="__('예: 900101-1234567')" class="k-input" />
					</div>
				</div>

				<!-- 근무 조건 -->
				<div class="k-card p-4 flex flex-col gap-3">
					<div class="text-base font-bold tracking-tight text-black">{{ __('근무 조건') }}</div>
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('근무장소') }}</label>
						<input type="text" v-model="form.workplace" class="k-input" />
					</div>
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('업무 내용') }}</label>
						<input type="text" v-model="form.job_description" class="k-input" />
					</div>
					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('계약 시작일') }}</label>
							<input type="date" v-model="form.contract_period.start_date" class="k-input" />
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('계약 종료일 (기간의 정함 없으면 비움)') }}</label>
							<input type="date" v-model="form.contract_period.end_date" class="k-input" />
						</div>
					</div>
					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('소정근로 시작시각') }}</label>
							<input type="time" v-model="form.scheduled_work.start_time" class="k-input" />
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('소정근로 종료시각') }}</label>
							<input type="time" v-model="form.scheduled_work.end_time" class="k-input" />
						</div>
					</div>
					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('근무일') }}</label>
							<input type="text" v-model="form.scheduled_work.work_days" :placeholder="__('예: 월~금')" class="k-input" />
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('휴게시간 (선택)') }}</label>
							<input type="text" v-model="form.scheduled_work.break_time" :placeholder="__('예: 12:00~13:00')" class="k-input" />
						</div>
					</div>
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('휴일 (§55)') }}</label>
						<input type="text" v-model="form.holidays" :placeholder="__('예: 주휴일 매주 일요일')" class="k-input" />
					</div>
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('연차유급휴가 (§60)') }}</label>
						<input type="text" v-model="form.annual_leave" :placeholder="__('예: 근로기준법 제60조에 따름')" class="k-input" />
					</div>
				</div>

				<!-- 임금 구성항목 -->
				<div class="k-card p-4 flex flex-col gap-3">
					<div class="text-base font-bold tracking-tight text-black">{{ __('임금 구성항목') }}</div>
					<div v-for="(item, idx) in form.wage_components" :key="idx" class="flex gap-2 items-center">
						<input type="text" v-model="item.component" :placeholder="__('예: 기본급')" class="k-input flex-1" />
						<input type="number" v-model.number="item.amount" :placeholder="__('금액')" class="k-input k-numeric w-32" />
						<button @click="removeWageComponent(idx)" class="text-black/40 hover:text-black text-sm px-2">✕</button>
					</div>
					<button
						@click="addWageComponent"
						class="w-full py-2 border border-dashed border-[var(--k-hairline)] text-black/60 text-sm rounded-lg hover:border-black/40 transition-colors"
					>{{ __('+ 항목 추가') }}</button>
					<div class="flex justify-between text-sm pt-2 border-t border-[var(--k-hairline)]">
						<span class="text-black/60">{{ __('임금 합계') }}</span>
						<span class="k-numeric font-semibold k-amount">{{ formatKRW(wageTotal) }}</span>
					</div>
					<div class="grid grid-cols-2 gap-2">
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('임금 지급일') }}</label>
							<input type="text" v-model="form.wage_payment_date" :placeholder="__('예: 매월 10일')" class="k-input" />
						</div>
						<div class="flex flex-col gap-1">
							<label class="k-label">{{ __('지급 방법') }}</label>
							<input type="text" v-model="form.wage_payment_method" :placeholder="__('예: 근로자 명의 계좌 입금')" class="k-input" />
						</div>
					</div>
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('사회보험 적용 (선택)') }}</label>
						<input type="text" v-model="form.social_insurance" :placeholder="__('예: 고용·산재·국민연금·건강보험 가입')" class="k-input" />
					</div>
					<div class="flex flex-col gap-1">
						<label class="k-label">{{ __('기타 사항 (선택)') }}</label>
						<textarea v-model="form.other_terms" rows="2" class="k-input"></textarea>
					</div>
				</div>

				<button
					@click="calculate"
					:disabled="buildEmploymentContract.loading"
					class="k-btn-primary w-full"
				>
					<span v-if="buildEmploymentContract.loading">{{ __('검토 중...') }}</span>
					<span v-else>{{ __('계약서 검토') }}</span>
				</button>

				<div v-if="buildEmploymentContract.error" class="text-center py-2 text-red-600 text-sm">
					{{ __('검토에 실패했습니다. 입력값을 확인해 주세요.') }}
				</div>

				<!-- 결과 -->
				<template v-if="contract">
					<div v-if="contract.missing.length" class="k-card p-3 text-xs bg-amber-50 border border-amber-300 text-amber-800 leading-relaxed">
						<div class="font-semibold mb-1">{{ __('⚠ §17 필수기재 누락 경고') }}</div>
						<ul class="list-disc list-inside">
							<li v-for="field in contract.missing" :key="field">{{ field }}</li>
						</ul>
					</div>
					<div v-else class="k-card p-3 text-xs bg-green-50 border border-green-300 text-green-800 leading-relaxed">
						{{ __('✓ §17 필수기재 항목이 모두 입력되었습니다.') }}
					</div>

					<div class="k-block k-block--cream -mx-1">
						<div class="k-eyebrow">WAGE TOTAL</div>
						<div class="mt-1 text-sm font-medium text-black/60">{{ __('계약서 임금 합계') }}</div>
						<div class="k-display">{{ formatKRW(contract.wage_total) }}</div>
					</div>

					<!-- 마크다운 미리보기 -->
					<div class="k-card p-4 flex flex-col gap-3">
						<div class="text-base font-bold tracking-tight text-black">{{ __('계약서 초안 미리보기') }}</div>
						<button
							@click="generateMarkdown"
							:disabled="renderContractMarkdown.loading"
							class="k-btn-secondary w-full"
						>
							<span v-if="renderContractMarkdown.loading">{{ __('생성 중...') }}</span>
							<span v-else>{{ __('마크다운 생성') }}</span>
						</button>
						<template v-if="markdown">
							<div class="bg-[var(--k-surface-soft)] rounded-lg p-3 text-xs text-black/70 leading-relaxed whitespace-pre-wrap font-mono max-h-96 overflow-y-auto">{{ markdown }}</div>
							<button
								@click="copyMarkdown"
								class="k-btn-secondary w-full"
							>{{ copied ? __('복사됨 ✓') : __('마크다운 복사') }}</button>
						</template>
					</div>
				</template>

				<!-- 면책 고지 -->
				<div class="k-card p-3 text-xs text-black/60 leading-relaxed">
					<span class="font-semibold text-black">참고용 초안입니다.</span>
					실제 서면 교부 전 반드시 시행령 세부 항목과 사업장별 사정을 검토하시기 바랍니다.
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, reactive, ref, inject } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import { buildEmploymentContract, renderContractMarkdown } from "@/data/koreaEmploymentContractRuntime"

const __ = inject("$translate")

const form = reactive({
	company: {
		company_name: "",
		representative_name: "",
		address: "",
		business_registration_number: "",
		contact: "",
	},
	employee: {
		employee_name: "",
		address: "",
		contact: "",
		resident_registration_number: "",
	},
	workplace: "",
	job_description: "",
	contract_period: { start_date: "", end_date: "" },
	scheduled_work: { start_time: "", end_time: "", work_days: "", break_time: "" },
	holidays: "",
	annual_leave: "",
	wage_components: [{ component: "기본급", amount: null }],
	wage_payment_date: "",
	wage_payment_method: "",
	social_insurance: "",
	other_terms: "",
})

const contract = ref(null)
const markdown = ref(null)
const copied = ref(false)

const wageTotal = computed(() =>
	form.wage_components.reduce((sum, item) => sum + (Number(item.amount) || 0), 0)
)

function addWageComponent() {
	form.wage_components.push({ component: "", amount: null })
}

function removeWageComponent(idx) {
	form.wage_components.splice(idx, 1)
}

function formatKRW(amount) {
	if (amount == null) return "-"
	return Number(amount).toLocaleString("ko-KR") + "원"
}

async function calculate() {
	contract.value = null
	markdown.value = null
	copied.value = false
	await buildEmploymentContract.submit(JSON.parse(JSON.stringify(form)))
	if (!buildEmploymentContract.error) {
		contract.value = buildEmploymentContract.data
	}
}

async function generateMarkdown() {
	if (!contract.value) return
	markdown.value = null
	await renderContractMarkdown.submit({ contract: contract.value })
	if (!renderContractMarkdown.error) {
		markdown.value = renderContractMarkdown.data
	}
}

async function copyMarkdown() {
	if (!markdown.value) return
	await navigator.clipboard.writeText(markdown.value)
	copied.value = true
	setTimeout(() => (copied.value = false), 2000)
}
</script>

<style scoped>
.k-input {
	border: 1px solid var(--k-hairline);
	border-radius: 0.5rem;
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	color: black;
	width: 100%;
}
.k-input:focus {
	outline: none;
	box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.6);
}
</style>
