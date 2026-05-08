<template>
	<BaseLayout pageTitle="Korea Payroll Review Audit Log">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-gray-50 p-4 pb-24">
				<router-link to="/dashboard/korea-payroll-review-audit-logs" class="text-sm font-semibold text-gray-600">
					← Back to audit logs
				</router-link>

				<section class="rounded-2xl bg-gray-900 p-5 text-white shadow-sm">
					<p class="text-xs font-semibold uppercase tracking-[0.2em] text-gray-300">Audit log detail</p>
					<h1 class="mt-2 break-words text-2xl font-bold leading-tight">{{ detail.name }}</h1>
					<p class="mt-2 text-sm text-gray-300">{{ detail.company }} · {{ detail.workplace }}</p>
					<div class="mt-4 rounded-xl bg-white/10 p-3 text-sm">
						<p class="font-semibold">{{ statusLabel(detail.status) }}</p>
						<p class="mt-1 text-gray-300">{{ detail.previous_status }} → {{ detail.status }}</p>
					</div>
				</section>

				<section class="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
					<p class="font-semibold">No submit · no send · no provider call</p>
					<p class="mt-1">
						This static detail route mirrors the review audit-log detail contract for operator visibility only. It does not approve payroll, submit a Payroll Entry, send Kakao notifications, call providers, or create audit rows.
					</p>
					<p class="mt-2 text-xs">
						runtime_action={{ detail.runtime_action }} · preview_source={{ detail.preview_source }} · requires_runtime_apply={{ detail.requires_runtime_apply }}
					</p>
				</section>

				<section class="grid grid-cols-1 gap-3 md:grid-cols-2">
					<div class="rounded-2xl bg-white p-4 shadow-sm">
						<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">Review action</p>
						<dl class="mt-3 space-y-2 text-sm text-gray-700">
							<div class="flex justify-between gap-3"><dt>Action</dt><dd class="font-semibold text-gray-900">{{ detail.action }}</dd></div>
							<div class="flex justify-between gap-3"><dt>Review actor</dt><dd>{{ detail.review_actor }}</dd></div>
							<div class="flex justify-between gap-3"><dt>Audit actor</dt><dd>{{ detail.audit_actor }}</dd></div>
							<div class="flex justify-between gap-3"><dt>Boundary</dt><dd class="text-right">{{ detail.mutation_boundary }}</dd></div>
						</dl>
					</div>

					<div class="rounded-2xl bg-white p-4 shadow-sm">
						<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">Payroll scope</p>
						<dl class="mt-3 space-y-2 text-sm text-gray-700">
							<div class="flex justify-between gap-3"><dt>Draft</dt><dd>{{ detail.draft_name }}</dd></div>
							<div class="flex justify-between gap-3"><dt>Payroll Entry</dt><dd>{{ detail.source_payroll_entry }}</dd></div>
							<div class="flex justify-between gap-3"><dt>Period</dt><dd>{{ detail.period_start }} → {{ detail.period_end }}</dd></div>
							<div class="flex justify-between gap-3"><dt>AI role</dt><dd>{{ detail.ai_role }}</dd></div>
						</dl>
					</div>
				</section>

				<section class="rounded-2xl bg-white p-4 shadow-sm">
					<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">source_runtime_apply</p>
					<pre class="mt-3 overflow-x-auto rounded-xl bg-gray-900 p-3 text-xs text-gray-100">{{ JSON.stringify(detail.source_runtime_apply, null, 2) }}</pre>
				</section>

				<section class="rounded-2xl bg-white p-4 shadow-sm">
					<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">source_audit_log</p>
					<pre class="mt-3 overflow-x-auto rounded-xl bg-gray-900 p-3 text-xs text-gray-100">{{ JSON.stringify(detail.source_audit_log, null, 2) }}</pre>
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
		draft_human_approved: "Approved by human reviewer",
		draft_human_rejected: "Rejected by human reviewer",
		draft_changes_requested: "Changes requested by human reviewer",
	}[status]
}
</script>
