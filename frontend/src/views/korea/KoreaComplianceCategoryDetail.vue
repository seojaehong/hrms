<template>
	<BaseLayout :pageTitle="categoryDetail?.label ?? __('카테고리 상세')">
		<template #body>
			<div class="flex flex-col my-7 p-4 gap-5">
				<!-- 히어로 — pink 색블록 -->
				<div class="k-block k-block--cream flex flex-col gap-2">
					<div class="k-eyebrow">COMPLIANCE</div>
					<div class="flex items-center gap-3">
						<span class="text-2xl">{{ categoryDetail?.statusEmoji ?? '⬜' }}</span>
						<div class="flex flex-col gap-0.5">
							<div class="k-t-display text-[var(--k-ink)]">
								{{ categoryDetail?.label ?? '-' }}
							</div>
							<div class="text-xs text-[var(--k-ink-faint)]">{{ categoryDetail?.law ?? '' }}</div>
						</div>
						<div class="ml-auto">
							<span
								v-if="categoryDetail"
								class="text-xs font-medium px-2 py-0.5 rounded-full bg-[var(--k-card)]"
								:class="categoryDetail.statusTextClass"
								:style="categoryDetail.badgeStyle"
							>
								{{ categoryDetail.statusText }}
							</span>
						</div>
					</div>

					<div class="text-xs text-[var(--k-ink-muted)] pt-1">
						{{ categoryDetail?.company ?? '-' }} /
						{{ categoryDetail?.workplace || '전사' }} |
						진단 기준일: {{ categoryDetail?.as_of_date ?? '-' }}
					</div>
				</div>

				<!-- 데이터 없음 / 로딩 -->
				<div
					v-if="!categoryDetail && !loading"
					class="k-card p-4 text-sm text-[var(--k-ink-muted)]"
				>
					카테고리 진단 데이터를 찾을 수 없습니다.<br />
					<router-link
						:to="{ name: 'KoreaComplianceDashboard' }"
						class="k-link font-semibold text-xs mt-1"
					>
						← 메인 대시보드로 돌아가기
					</router-link>
				</div>

				<div v-if="loading" class="flex flex-col items-center py-10">
					<div class="text-[var(--k-ink-faint)] text-sm">로딩 중...</div>
				</div>

				<template v-if="categoryDetail">
					<!-- 발견 사항 -->
					<div class="k-card p-4 flex flex-col gap-3">
						<div class="text-sm font-bold tracking-tight text-[var(--k-ink)]">발견 사항</div>

						<div v-if="actualFindings.length === 0 && dataUnavailableFindings.length === 0">
							<div class="text-sm text-[var(--k-success)] py-2 text-center">발견된 문제 없음</div>
						</div>

						<!-- 실제 위반/경고 발견 -->
						<div
							v-for="(finding, idx) in maskedFindings"
							:key="`finding-${idx}`"
							class="border rounded-lg p-3 flex flex-col gap-1"
							:class="categoryDetail.status === 'fail' ? 'border-[var(--k-danger)] bg-[var(--k-surface-3)]' : 'border-[var(--k-warn)] bg-[var(--k-surface-3)]'"
						>
							<div class="flex items-start justify-between gap-2">
								<div class="text-xs font-semibold text-[var(--k-ink)]">
									<span v-if="finding.employee_name">
										{{ finding.employee_name }}
									</span>
									<span v-else class="text-[var(--k-ink-faint)]">직원 미특정</span>
								</div>
								<span class="text-xs text-[var(--k-ink-faint)] shrink-0">
									{{ finding.law ?? '' }}
								</span>
							</div>
							<div class="text-xs text-[var(--k-ink-muted)]">{{ finding.issue }}</div>

							<!-- 상세 데이터 (wage delay: delay_days 등) -->
							<div v-if="finding.detail" class="mt-1 text-xs text-[var(--k-ink-faint)] flex flex-wrap gap-3">
								<span v-for="(val, key) in finding.detail" :key="key">
									{{ key }}: {{ val }}
								</span>
							</div>

							<!-- 해결 표시 (admin, human_approved) -->
							<div v-if="isAdmin && !finding.data_unavailable" class="mt-2 flex justify-end">
								<button
									@click="confirmMarkResolved(idx)"
									class="k-btn-secondary"
								>
									해결 표시
								</button>
							</div>
						</div>

						<!-- 데이터 미등록 경고 -->
						<div
							v-for="(finding, idx) in dataUnavailableFindings"
							:key="`unavailable-${idx}`"
							class="border border-[var(--k-hairline)] rounded-lg p-3 flex flex-col gap-1 bg-[var(--k-surface-soft)]"
						>
							<div class="text-xs text-[var(--k-ink-muted)]">{{ finding.issue }}</div>
							<div class="text-xs text-[var(--k-ink-faint)]">데이터 미등록 — 직접 확인 필요</div>
						</div>

						<!-- PII 마스킹 토글 -->
						<div class="flex items-center gap-2 pt-1">
							<label class="flex items-center gap-1.5 cursor-pointer">
								<input
									type="checkbox"
									v-model="maskPii"
									class="rounded"
								/>
								<span class="text-xs text-[var(--k-ink-muted)]">직원 이름 마스킹</span>
							</label>
						</div>
					</div>

					<!-- 개선 권고 체크리스트 -->
					<div v-if="categoryDetail.recommendations?.length" class="k-card p-4 flex flex-col gap-3">
						<div class="text-sm font-bold tracking-tight text-[var(--k-ink)]">개선 권고 체크리스트</div>

						<div
							v-for="(rec, idx) in categoryDetail.recommendations"
							:key="`rec-${idx}`"
							class="flex items-start gap-2"
						>
							<input
								type="checkbox"
								:id="`rec-check-${idx}`"
								v-model="checkedRecommendations[idx]"
								class="mt-0.5 rounded"
							/>
							<label
								:for="`rec-check-${idx}`"
								class="text-xs text-[var(--k-ink)] cursor-pointer leading-relaxed"
								:class="{ 'line-through !text-[var(--k-ink-faint)]': checkedRecommendations[idx] }"
							>
								{{ rec }}
							</label>
						</div>

						<div class="text-xs text-[var(--k-ink-faint)] pt-1">
							* 체크는 로컬에서만 유효합니다. 실제 조치는 admin 확인 후 진행하세요.
						</div>
					</div>

					<!-- Audit Log (이 카테고리 한정) -->
					<div class="k-card p-4 flex flex-col gap-3">
						<div class="text-sm font-bold tracking-tight text-[var(--k-ink)]">이력</div>

						<div v-if="auditLogs.length === 0" class="text-xs text-[var(--k-ink-faint)] py-2 text-center">
							이 카테고리에 대한 이력이 없습니다.
						</div>

						<div
							v-for="(log, idx) in auditLogs"
							:key="`log-${idx}`"
							class="border-b border-[var(--k-hairline-soft)] pb-2 last:border-0 last:pb-0 flex flex-col gap-0.5"
						>
							<div class="flex items-center justify-between">
								<span class="text-xs font-medium text-[var(--k-ink)]">{{ log.event_label }}</span>
								<span class="text-xs text-[var(--k-ink-faint)]">{{ log.timestamp }}</span>
							</div>
							<div class="text-xs text-[var(--k-ink-faint)]">{{ log.actor }}</div>
						</div>
					</div>

					<!-- 관련 모듈 링크 -->
					<div v-if="categoryDetail.relatedModules?.length" class="k-card p-4 flex flex-col gap-3">
						<div class="text-sm font-bold tracking-tight text-[var(--k-ink)]">관련 모듈</div>
						<div class="flex flex-col gap-2">
							<a
								v-for="mod in categoryDetail.relatedModules"
								:key="mod.doctype"
								:href="mod.route"
								target="_blank"
								rel="noopener noreferrer"
								class="k-link text-xs font-medium flex items-center gap-1"
							>
								{{ mod.label }} →
							</a>
						</div>
					</div>

					<!-- 뒤로가기 -->
					<div class="flex">
						<router-link
							:to="{ name: 'KoreaComplianceDashboard' }"
							class="k-link text-xs"
						>
							← 대시보드로 돌아가기
						</router-link>
					</div>
				</template>
			</div>

			<!-- Confirm: 해결 표시 -->
			<div
				v-if="showResolveConfirm"
				class="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
				@click.self="showResolveConfirm = false"
			>
				<div class="bg-[var(--k-card)] rounded-2xl shadow-xl p-6 mx-6 flex flex-col gap-4 max-w-sm w-full">
					<div class="k-t-headline text-[var(--k-ink)]">발견 사항 해결 표시</div>
					<div class="text-sm text-[var(--k-ink-muted)] leading-relaxed">
						이 발견 사항을 해결됨으로 표시합니다.<br />
						실제 조치가 완료된 경우에만 진행하세요.
					</div>
					<div class="flex flex-row gap-3 mt-2">
						<button
							@click="showResolveConfirm = false"
							class="k-btn-secondary flex-1"
						>
							취소
						</button>
						<button
							@click="markResolved"
							class="k-btn-primary flex-1"
						>
							해결 표시
						</button>
					</div>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { ref, computed, inject, onMounted } from "vue"
import { useRoute } from "vue-router"

import BaseLayout from "@/components/BaseLayout.vue"
import { useIsAdmin } from "@/composables/useIsAdmin"
import {
	getCategoryDetail,
	maskEmployeeName,
	STATUS_CONFIG,
} from "@/data/koreaComplianceRuntime"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const route = useRoute()
const categoryKey = computed(() => route.params.categoryKey)

// ---------------------------------------------------------------------------
// 상태
// ---------------------------------------------------------------------------
const categoryDetail = ref(null)
const loading = ref(false)
const maskPii = ref(false)
const isAdmin = useIsAdmin() // HR Manager/System Manager 롤 기준
const checkedRecommendations = ref({})

const showResolveConfirm = ref(false)
const resolvingFindingIdx = ref(null)
const resolvedFindings = ref(new Set())

// 로컬 audit log (이 카테고리 한정)
const auditLogs = ref([])

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const actualFindings = computed(() =>
	(categoryDetail.value?.findings ?? []).filter((f) => !f.data_unavailable)
)

const dataUnavailableFindings = computed(() =>
	(categoryDetail.value?.findings ?? []).filter((f) => f.data_unavailable)
)

const maskedFindings = computed(() => {
	return actualFindings.value
		.filter((_, idx) => !resolvedFindings.value.has(idx))
		.map((f) => ({
			...f,
			employee_name: maskEmployeeName(f.employee_name, maskPii.value),
		}))
})

// ---------------------------------------------------------------------------
// 메서드
// ---------------------------------------------------------------------------
function loadFromSession() {
	try {
		const cached = sessionStorage.getItem("koreaComplianceDiagnosis")
		if (!cached) return
		const parsed = JSON.parse(cached)
		const detail = getCategoryDetail(parsed.result, categoryKey.value)
		if (detail) {
			categoryDetail.value = detail
		}
	} catch (_) {
		// ignore
	}
}

function confirmMarkResolved(idx) {
	resolvingFindingIdx.value = idx
	showResolveConfirm.value = true
}

function markResolved() {
	showResolveConfirm.value = false
	if (resolvingFindingIdx.value !== null) {
		resolvedFindings.value = new Set([...resolvedFindings.value, resolvingFindingIdx.value])
		// audit log 추가
		auditLogs.value.unshift({
			event_label: `발견 사항 해결 표시 (찾기 #${resolvingFindingIdx.value + 1})`,
			timestamp: dayjs().format("YYYY-MM-DD HH:mm"),
			actor: "현재 사용자",
		})
		resolvingFindingIdx.value = null
	}
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
onMounted(() => {
	loadFromSession()
})
</script>
