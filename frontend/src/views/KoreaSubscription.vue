<template>
	<ion-page>
		<ion-content class="ion-padding">
			<div class="flex flex-col h-full w-full sm:max-w-2xl mx-auto">
				<!-- Header -->
				<header
					class="flex flex-row bg-white shadow-sm py-4 px-3 items-center justify-between border-b sticky top-0 z-10"
				>
					<div class="flex flex-row items-center gap-2">
						<Button
							variant="ghost"
							class="!pl-0 hover:bg-white"
							@click="router.back()"
						>
							<FeatherIcon name="chevron-left" class="h-5 w-5" />
						</Button>
						<h2 class="text-xl font-semibold text-gray-900">
							{{ __("구독 플랜") }}
						</h2>
					</div>
				</header>

				<div class="flex flex-col gap-6 p-4">
					<!-- DRY-RUN 안내 배너 -->
					<div
						class="flex items-start gap-3 rounded-lg border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-800"
					>
						<FeatherIcon name="info" class="mt-0.5 h-4 w-4 shrink-0" />
						<span>
							현재 <strong>테스트 모드(Dry Run)</strong>입니다.
							플랜 변경 버튼을 눌러도 실제 결제는 이루어지지 않습니다.
							실제 결제 연동은 v2에서 제공됩니다.
						</span>
					</div>

					<!-- 현재 플랜 요약 -->
					<section
						v-if="currentPlan"
						class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
					>
						<p class="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">
							{{ __("현재 플랜") }}
						</p>
						<div class="flex items-center justify-between">
							<span class="text-lg font-semibold text-gray-900">
								{{ currentPlan.name }}
							</span>
							<span
								class="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700"
							>
								{{ __("활성") }}
							</span>
						</div>
						<p class="mt-1 text-sm text-gray-500">
							{{ __("직원") }}
							<strong>{{ employeeCount }}</strong> /
							<strong>
								{{ currentPlan.max_employees ?? "무제한" }}
							</strong>
							{{ __("명") }}
						</p>
					</section>

					<!-- 플랜 그리드 -->
					<section>
						<h3 class="mb-3 text-base font-semibold text-gray-800">
							{{ __("플랜 비교") }}
						</h3>
						<div class="flex flex-col gap-3">
							<div
								v-for="(plan, tier) in plans"
								:key="tier"
								class="rounded-xl border p-4 transition-shadow hover:shadow-md"
								:class="
									activeTier === tier
										? 'border-blue-500 bg-blue-50'
										: 'border-gray-200 bg-white'
								"
							>
								<div class="flex items-start justify-between">
									<div>
										<p class="font-semibold text-gray-900">{{ plan.name }}</p>
										<p class="mt-0.5 text-sm text-gray-500">
											{{
												typeof plan.monthly_price_krw === "number"
													? plan.monthly_price_krw.toLocaleString("ko-KR") + "원/월"
													: plan.monthly_price_krw
											}}
										</p>
										<p class="mt-0.5 text-xs text-gray-400">
											최대
											{{ plan.max_employees ?? "무제한" }}명
										</p>
									</div>
									<span
										v-if="activeTier === tier"
										class="shrink-0 rounded-full bg-blue-600 px-2.5 py-0.5 text-xs font-medium text-white"
									>
										{{ __("현재") }}
									</span>
								</div>

								<!-- 기능 목록 -->
								<ul class="mt-3 flex flex-col gap-1">
									<li
										v-for="feature in plan.features"
										:key="feature"
										class="flex items-center gap-2 text-sm text-gray-700"
									>
										<FeatherIcon name="check" class="h-3.5 w-3.5 text-green-500 shrink-0" />
										{{ feature }}
									</li>
								</ul>

								<!-- 업그레이드 버튼 (admin only, 현재 플랜 아닐 때만) -->
								<Button
									v-if="isAdmin && activeTier !== tier"
									class="mt-3 w-full"
									variant="outline"
									:loading="changingTier === tier"
									@click="handlePlanChange(tier)"
								>
									{{
										tier === "enterprise"
											? __("문의하기")
											: activeTier
												? __("이 플랜으로 변경")
												: __("시작하기")
									}}
								</Button>
							</div>
						</div>
					</section>

					<!-- 청구 내역 -->
					<section>
						<h3 class="mb-3 text-base font-semibold text-gray-800">
							{{ __("청구 내역") }}
						</h3>

						<div
							v-if="invoices.length === 0"
							class="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-white py-10 text-sm text-gray-400"
						>
							<FeatherIcon name="file-text" class="mb-2 h-8 w-8" />
							{{ __("청구 내역이 없습니다.") }}
						</div>

						<div
							v-else
							class="overflow-hidden rounded-xl border border-gray-200 bg-white"
						>
							<table class="w-full text-sm">
								<thead class="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
									<tr>
										<th class="py-2 pl-4 pr-2 text-left">{{ __("기간") }}</th>
										<th class="py-2 pr-4 text-right">{{ __("금액") }}</th>
									</tr>
								</thead>
								<tbody>
									<tr
										v-for="inv in invoices"
										:key="inv.subscription_id + inv.period_start"
										class="border-t border-gray-100"
									>
										<td class="py-2 pl-4 pr-2 text-gray-700">
											{{ inv.period_start }} ~ {{ inv.period_end }}
										</td>
										<td class="py-2 pr-4 text-right font-medium text-gray-900">
											{{
												inv.total_amount_krw != null
													? inv.total_amount_krw.toLocaleString("ko-KR") + "원"
													: "협의"
											}}
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</section>

					<!-- 결제 수단 안내 -->
					<section
						class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
					>
						<h3 class="mb-2 text-sm font-semibold text-gray-800">
							{{ __("결제 수단") }}
						</h3>
						<p class="text-sm text-gray-500">
							Stripe (USD/KRW) · 토스페이먼츠 (KRW) 지원 예정
						</p>
						<p class="mt-1 text-xs text-gray-400">
							현재 테스트 모드 — 실제 결제 연동은 v2에서 제공됩니다.
						</p>
					</section>
				</div>
			</div>
		</ion-content>

		<!-- 플랜 변경 확인 다이얼로그 -->
		<CustomIonModal
			v-if="pendingTier"
			:is-open="!!pendingTier"
			@did-dismiss="pendingTier = null"
		>
			<template #actionSheet>
				<div class="flex flex-col gap-4 p-6">
					<h3 class="text-lg font-semibold text-gray-900">
						{{ __("플랜 변경 확인") }}
					</h3>
					<p class="text-sm text-gray-600">
						<strong>{{ plans[pendingTier]?.name }}</strong> 플랜으로 변경하시겠습니까?
					</p>
					<div
						class="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-xs text-yellow-700"
					>
						[DRY RUN] 실제 결제가 발생하지 않습니다.
					</div>
					<div class="flex gap-2">
						<Button variant="outline" class="flex-1" @click="pendingTier = null">
							{{ __("취소") }}
						</Button>
						<Button
							class="flex-1"
							:loading="!!changingTier"
							@click="confirmPlanChange"
						>
							{{ __("변경하기") }}
						</Button>
					</div>
				</div>
			</template>
		</CustomIonModal>
	</ion-page>
</template>

<script setup>
import { ref, computed, onMounted, inject } from "vue"
import { IonPage, IonContent } from "@ionic/vue"
import { useRouter } from "vue-router"
import { Button, FeatherIcon, toast } from "frappe-ui"

import CustomIonModal from "@/components/CustomIonModal.vue"

const __ = inject("$translate")
const router = useRouter()

// ---------------------------------------------------------------------------
// 상태
// ---------------------------------------------------------------------------
const plans = ref({})
const activeTier = ref("starter") // v2: 실제 구독 상태 조회
const employeeCount = ref(0)       // v2: frappe.db에서 활성 직원 수 조회
const invoices = ref([])

const pendingTier = ref(null)
const changingTier = ref(null)

// admin 여부: window.frappe.boot에서 System Manager 역할 확인
const isAdmin = computed(
	() => window.frappe?.boot?.user?.roles?.includes("System Manager") ?? false
)

const currentPlan = computed(
	() => plans.value[activeTier.value] ?? null
)

// ---------------------------------------------------------------------------
// 데이터 로드
// ---------------------------------------------------------------------------
async function loadPlans() {
	try {
		const res = await window.frappe.call({
			method:
				"hrms.regional.south_korea._api.get_all_plans",
		})
		if (res.message?.plans) {
			plans.value = res.message.plans
		}
	} catch (err) {
		toast({
			title: __("오류"),
			text: __("플랜 정보를 불러오지 못했습니다."),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	}
}

async function loadInvoices() {
	try {
		const company = window.frappe?.boot?.sysdefaults?.company ?? ""
		const res = await window.frappe.call({
			method: "hrms.regional.south_korea._api.list_invoices",
			args: { company, limit: 12 },
		})
		invoices.value = res.message ?? []
	} catch {
		invoices.value = []
	}
}

onMounted(async () => {
	await Promise.all([loadPlans(), loadInvoices()])
})

// ---------------------------------------------------------------------------
// 플랜 변경
// ---------------------------------------------------------------------------
function handlePlanChange(tier) {
	if (tier === "enterprise") {
		// Enterprise는 문의 링크로 이동
		window.open("mailto:support@winhr.co.kr?subject=Enterprise%20플랜%20문의", "_blank")
		return
	}
	pendingTier.value = tier
}

async function confirmPlanChange() {
	if (!pendingTier.value) return
	const tier = pendingTier.value
	changingTier.value = tier
	pendingTier.value = null

	try {
		const subscriptionId = `KR-SUB-DEMO` // v2: 실제 구독 ID 조회
		const res = await window.frappe.call({
			method: "hrms.regional.south_korea._api.upgrade_downgrade",
			args: { subscription_id: subscriptionId, new_tier: tier },
		})
		activeTier.value = tier
		toast({
			title: __("플랜 변경 완료"),
			text: res.message?.message ?? __("플랜이 변경되었습니다."),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		await loadInvoices()
	} catch (err) {
		toast({
			title: __("오류"),
			text: err.message ?? __("플랜 변경에 실패했습니다."),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	} finally {
		changingTier.value = null
	}
}
</script>
