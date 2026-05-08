<template>
	<BaseLayout pageTitle="Korea Payroll Review Audit Logs">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-gray-50 p-4 pb-24">
				<section class="rounded-2xl bg-gray-900 p-5 text-white shadow-sm">
					<p class="text-xs font-semibold uppercase tracking-[0.2em] text-gray-300">Human review audit trail</p>
					<h1 class="mt-2 text-2xl font-bold leading-tight">{{ fixture.period_label }}</h1>
					<p class="mt-2 text-sm text-gray-300">
						{{ fixture.company }} · {{ fixture.summary.total_count }} audit rows · updated {{ fixture.updated_at }}
					</p>
					<div class="mt-4 grid grid-cols-3 gap-2 text-center">
						<div class="rounded-xl bg-white/10 p-3">
							<p class="text-2xl font-bold">{{ fixture.summary.approved_count }}</p>
							<p class="text-xs text-gray-300">Approved</p>
						</div>
						<div class="rounded-xl bg-amber-400/20 p-3">
							<p class="text-2xl font-bold text-amber-100">{{ fixture.summary.changes_requested_count }}</p>
							<p class="text-xs text-amber-100">Changes</p>
						</div>
						<div class="rounded-xl bg-red-400/20 p-3">
							<p class="text-2xl font-bold text-red-100">{{ fixture.summary.rejected_count }}</p>
							<p class="text-xs text-red-100">Rejected</p>
						</div>
					</div>
				</section>

				<section class="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
					<p class="font-semibold">Preview-only audit visibility</p>
					<p class="mt-1">
						This static fixture mirrors the payroll closing review audit-log runtime insert result. It is for operator visibility only: no payroll submission, approval workflow mutation, Kakao send, provider call, or audit-row creation happens from this screen. Human approval remains the authority and AI is assistant-only.
					</p>
					<p class="mt-2 text-xs">
						runtime_action={{ fixture.runtime_action }} · preview_source={{ fixture.preview_source }} · requires_runtime_apply={{ fixture.requires_runtime_apply }}
					</p>
				</section>

				<section class="flex flex-col gap-3">
					<article
						v-for="item in fixture.items"
						:key="item.name"
						class="rounded-2xl border bg-white p-4 shadow-sm"
						:class="statusClass(item.review_status)"
					>
						<div class="flex items-start justify-between gap-3">
							<div>
								<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">{{ item.workplace }}</p>
								<h2 class="mt-1 text-lg font-bold text-gray-900">{{ item.name }}</h2>
								<p class="mt-1 text-xs text-gray-500">{{ item.period_start }} → {{ item.period_end }} · {{ item.source_draft }}</p>
							</div>
							<span class="rounded-full px-3 py-1 text-xs font-semibold" :class="badgeClass(item.review_status)">
								{{ statusLabel(item.review_status) }}
							</span>
						</div>

						<div class="mt-4 rounded-xl bg-gray-50 p-3 text-sm">
							<div class="flex items-center justify-between gap-3">
								<p class="font-semibold text-gray-900">{{ item.review_action }}</p>
								<p class="text-xs text-gray-500">{{ item.reviewed_at }}</p>
							</div>
							<p class="mt-2 text-gray-700">{{ item.note }}</p>
						</div>

						<div class="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-600">
							<p class="rounded-lg bg-gray-50 p-2">Actor: {{ item.audit_actor }}</p>
							<p class="rounded-lg bg-gray-50 p-2">Boundary: {{ item.mutation_boundary }}</p>
							<p class="rounded-lg bg-gray-50 p-2">AI={{ item.ai_role }} · human approval required={{ item.requires_human_approval }}</p>
						</div>
					</article>
				</section>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import BaseLayout from "@/components/BaseLayout.vue"
import { koreaPayrollReviewAuditFixture as fixture } from "@/data/koreaPayrollReviewAuditFixture"

function statusLabel(status) {
	return {
		approved: "Approved",
		rejected: "Rejected",
		changes_requested: "Changes requested",
	}[status]
}

function statusClass(status) {
	return {
		approved: "border-green-100",
		rejected: "border-red-100",
		changes_requested: "border-amber-100",
	}[status]
}

function badgeClass(status) {
	return {
		approved: "bg-green-100 text-green-700",
		rejected: "bg-red-100 text-red-700",
		changes_requested: "bg-amber-100 text-amber-700",
	}[status]
}
</script>
