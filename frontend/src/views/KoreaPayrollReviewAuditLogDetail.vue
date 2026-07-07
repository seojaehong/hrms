<template>
	<BaseLayout pageTitle="급여 검토 감사 로그 상세">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-gray-50 p-4 pb-24">
				<router-link to="/dashboard/korea-payroll-review-audit-logs" class="text-sm font-semibold text-gray-600">
					← 감사 로그 목록으로
				</router-link>

				<section class="rounded-2xl bg-gray-900 p-5 text-white shadow-sm">
					<p class="text-xs font-semibold uppercase tracking-[0.2em] text-gray-300">감사 로그 상세</p>
					<h1 class="mt-2 break-words text-2xl font-bold leading-tight">{{ detail.name }}</h1>
					<p class="mt-2 text-sm text-gray-300">{{ detail.company }} · {{ detail.workplace }}</p>
					<div class="mt-4 rounded-xl bg-white/10 p-3 text-sm">
						<p class="font-semibold">{{ statusLabel(detail.status) }}</p>
						<p class="mt-1 text-gray-300">{{ detail.previous_status }} → {{ detail.status }}</p>
					</div>
				</section>

				<section class="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
					<p class="font-semibold">제출 없음 · 발송 없음 · 외부 연동 호출 없음</p>
					<p class="mt-1">
						이 화면은 검토 감사 로그를 담당자 확인용으로 보여주는 조회 전용 화면입니다. 급여 승인, Payroll Entry 제출, 카카오 알림 발송, 외부 연동 호출, 감사 행 생성을 수행하지 않습니다.
					</p>
					<p class="mt-2 text-xs">
						runtime_action={{ detail.runtime_action }} · preview_source={{ detail.preview_source }} · requires_runtime_apply={{ detail.requires_runtime_apply }}
					</p>
				</section>

				<section class="grid grid-cols-1 gap-3 md:grid-cols-2">
					<div class="rounded-2xl bg-white p-4 shadow-sm">
						<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">검토 액션</p>
						<dl class="mt-3 space-y-2 text-sm text-gray-700">
							<div class="flex justify-between gap-3"><dt>액션</dt><dd class="font-semibold text-gray-900">{{ detail.action }}</dd></div>
							<div class="flex justify-between gap-3"><dt>검토 담당자</dt><dd>{{ detail.review_actor }}</dd></div>
							<div class="flex justify-between gap-3"><dt>감사 기록자</dt><dd>{{ detail.audit_actor }}</dd></div>
							<div class="flex justify-between gap-3"><dt>변경 경계</dt><dd class="text-right">{{ detail.mutation_boundary }}</dd></div>
						</dl>
					</div>

					<div class="rounded-2xl bg-white p-4 shadow-sm">
						<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">급여 범위</p>
						<dl class="mt-3 space-y-2 text-sm text-gray-700">
							<div class="flex justify-between gap-3"><dt>초안</dt><dd>{{ detail.draft_name }}</dd></div>
							<div class="flex justify-between gap-3"><dt>급여 대장(Payroll Entry)</dt><dd>{{ detail.source_payroll_entry }}</dd></div>
							<div class="flex justify-between gap-3"><dt>기간</dt><dd>{{ detail.period_start }} → {{ detail.period_end }}</dd></div>
							<div class="flex justify-between gap-3"><dt>AI 역할</dt><dd>{{ detail.ai_role }}</dd></div>
						</dl>
					</div>
				</section>

				<section class="rounded-2xl bg-white p-4 shadow-sm">
					<details>
						<summary class="cursor-pointer text-xs font-semibold uppercase tracking-wide text-gray-500">기술 상세(JSON) — source_runtime_apply</summary>
						<pre class="mt-3 overflow-x-auto rounded-xl bg-gray-900 p-3 text-xs text-gray-100">{{ JSON.stringify(detail.source_runtime_apply, null, 2) }}</pre>
					</details>
				</section>

				<section class="rounded-2xl bg-white p-4 shadow-sm">
					<details>
						<summary class="cursor-pointer text-xs font-semibold uppercase tracking-wide text-gray-500">기술 상세(JSON) — source_audit_log</summary>
						<pre class="mt-3 overflow-x-auto rounded-xl bg-gray-900 p-3 text-xs text-gray-100">{{ JSON.stringify(detail.source_audit_log, null, 2) }}</pre>
					</details>
				</section>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed } from "vue"
import { useRoute } from "vue-router"
import BaseLayout from "@/components/BaseLayout.vue"
import { getKoreaPayrollReviewAuditDetail } from "@/data/koreaPayrollReviewAuditFixture"

const route = useRoute()
const detail = computed(() => getKoreaPayrollReviewAuditDetail(String(route.params.name || "")))

function statusLabel(status) {
	return {
		draft_human_approved: "담당자 승인 완료",
		draft_human_rejected: "담당자 반려",
		draft_changes_requested: "담당자 수정 요청",
	}[status]
}
</script>
