<template>
	<BaseLayout pageTitle="Korea Payroll Review Audit Logs">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-[var(--k-surface-soft)] p-4 pb-24">
				<section class="rounded-2xl bg-[var(--k-ink)] p-5 text-white shadow-sm">
					<p class="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--k-ink-faint)]">Human review audit trail</p>
					<h1 class="mt-2 text-2xl font-bold leading-tight">{{ fixture.period_label }}</h1>
					<p class="mt-2 text-sm text-[var(--k-ink-faint)]">
						{{ fixture.company }} · {{ fixture.summary.total_count }} audit rows · updated {{ fixture.updated_at }}
					</p>
					<div class="mt-4 grid grid-cols-3 gap-2 text-center">
						<div class="rounded-xl bg-white/10 p-3">
							<p class="text-2xl font-bold">{{ fixture.summary.approved_count }}</p>
							<p class="text-xs text-[var(--k-ink-faint)]">Approved</p>
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
					<p class="font-semibold">미리보기 전용 감사 조회</p>
					<p class="mt-1">
						이 화면은 급여 마감 검토 감사 로그의 기록 결과를 보여주는 조회 전용 화면입니다. 급여 제출·결재 변경·카카오 발송·외부 호출·감사행 생성은 이 화면에서 일어나지 않으며, 최종 승인 권한은 사람에게 있고 AI는 보조 역할만 합니다.
					</p>
					<p class="mt-2 text-xs">
						조회 전용 감사 기록 · 변경 없음
					</p>
				</section>

				<section class="flex flex-col gap-3">
					<article
						v-for="item in fixture.items"
						:key="item.name"
						class="rounded-2xl border bg-[var(--k-card)] p-4 shadow-sm"
						:class="statusClass(item.status)"
					>
						<router-link :to="item.route" class="block">
							<div class="flex items-start justify-between gap-3">
							<div>
								<p class="text-xs font-semibold uppercase tracking-wide text-[var(--k-ink-muted)]">{{ item.workplace }}</p>
								<h2 class="mt-1 text-lg font-bold text-[var(--k-ink)]">{{ item.name }}</h2>
								<p class="mt-1 text-xs text-[var(--k-ink-muted)]">{{ item.period_start }} → {{ item.period_end }} · {{ item.draft_name }}</p>
							</div>
							<span class="rounded-full px-3 py-1 text-xs font-semibold" :class="badgeClass(item.status)">
								{{ statusLabel(item.status) }}
							</span>
						</div>

						<div class="mt-4 rounded-xl bg-[var(--k-surface-soft)] p-3 text-sm">
							<div class="flex items-center justify-between gap-3">
								<p class="font-semibold text-[var(--k-ink)]">{{ item.action }}</p>
								<p class="text-xs text-[var(--k-ink-muted)]">{{ item.source_payroll_entry }}</p>
							</div>
							<p class="mt-2 text-[var(--k-ink)]">{{ item.previous_status }} → {{ item.status }}</p>
						</div>


							<div class="mt-3 flex items-center justify-between rounded-xl border border-[var(--k-hairline-soft)] bg-[var(--k-card)] px-3 py-2 text-xs font-semibold text-[var(--k-ink)]">
								<span>Open detail</span>
								<span aria-hidden="true">→</span>
							</div>
						</router-link>
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
		draft_human_approved: "Approved",
		draft_human_rejected: "Rejected",
		draft_changes_requested: "Changes requested",
	}[status]
}

function statusClass(status) {
	return {
		draft_human_approved: "border-green-100",
		draft_human_rejected: "border-red-100",
		draft_changes_requested: "border-amber-100",
	}[status]
}

function badgeClass(status) {
	return {
		draft_human_approved: "bg-green-100 text-green-700",
		draft_human_rejected: "bg-red-100 text-red-700",
		draft_changes_requested: "bg-amber-100 text-amber-700",
	}[status]
}
</script>
