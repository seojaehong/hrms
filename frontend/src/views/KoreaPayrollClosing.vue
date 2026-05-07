<template>
	<BaseLayout pageTitle="Korea Payroll Closing">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-gray-50 p-4 pb-24">
				<section class="rounded-2xl bg-gray-900 p-5 text-white shadow-sm">
					<p class="text-xs font-semibold uppercase tracking-[0.2em] text-gray-300">Static fixture preview</p>
					<h1 class="mt-2 text-2xl font-bold leading-tight">{{ fixture.period_label }}</h1>
					<p class="mt-2 text-sm text-gray-300">
						{{ fixture.company }} · {{ fixture.summary.total_employees }} employees · updated {{ fixture.updated_at }}
					</p>
					<div class="mt-4 grid grid-cols-3 gap-2 text-center">
						<div class="rounded-xl bg-white/10 p-3">
							<p class="text-2xl font-bold">{{ fixture.summary.total_count }}</p>
							<p class="text-xs text-gray-300">Workplaces</p>
						</div>
						<div class="rounded-xl bg-red-400/20 p-3">
							<p class="text-2xl font-bold text-red-100">{{ fixture.summary.blocked_count }}</p>
							<p class="text-xs text-red-100">Blocked</p>
						</div>
						<div class="rounded-xl bg-green-400/20 p-3">
							<p class="text-2xl font-bold text-green-100">{{ fixture.summary.review_ready_count }}</p>
							<p class="text-xs text-green-100">Ready</p>
						</div>
					</div>
				</section>

				<section class="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
					<p class="font-semibold">Preview boundary</p>
					<p class="mt-1">
						This screen is backed by static demo fixtures shaped like the payroll closing worklist preview API. It does not save, approve, send Kakao messages, or mutate Payroll Entry records. Human approval remains required and AI is assistant-only.
					</p>
				</section>

				<section class="flex flex-col gap-3">
					<article
						v-for="item in fixture.items"
						:key="item.name"
						class="rounded-2xl border bg-white p-4 shadow-sm"
						:class="item.status === 'blocked' ? 'border-red-100' : 'border-green-100'"
					>
						<div class="flex items-start justify-between gap-3">
							<div>
								<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">{{ item.role }}</p>
								<h2 class="mt-1 text-lg font-bold text-gray-900">{{ item.workplace }}</h2>
								<p class="mt-1 text-xs text-gray-500">{{ item.period_start }} → {{ item.period_end }} · {{ item.employee_count }} employees</p>
							</div>
							<span
								class="rounded-full px-3 py-1 text-xs font-semibold"
								:class="item.status === 'blocked' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'"
							>
								{{ item.status === 'blocked' ? 'Blocked' : 'Review ready' }}
							</span>
						</div>

						<div class="mt-4 grid grid-cols-2 gap-2">
							<div
								v-for="card in item.readiness_cards"
								:key="`${item.name}-${card.key}`"
								class="rounded-xl border p-3"
								:class="card.state === 'blocked' ? 'border-red-100 bg-red-50' : 'border-gray-100 bg-gray-50'"
							>
								<p class="text-xs font-semibold text-gray-500">{{ card.label }}</p>
								<p class="mt-1 text-sm font-medium text-gray-900">{{ card.summary }}</p>
							</div>
						</div>

						<div class="mt-4 rounded-xl bg-gray-50 p-3">
							<p class="text-xs font-semibold text-gray-500">Next action</p>
							<div class="mt-1 flex items-center justify-between gap-3">
								<p class="text-sm font-semibold text-gray-900">{{ item.primary_action.label }}</p>
								<p class="text-xs text-gray-500">{{ item.payroll_entry }}</p>
							</div>
							<router-link
								:to="`/${item.route}`"
								class="mt-3 inline-flex w-full justify-center rounded-xl bg-gray-900 px-4 py-2 text-sm font-semibold text-white"
							>
								Open session preview
							</router-link>
						</div>
					</article>
				</section>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import BaseLayout from "@/components/BaseLayout.vue"
import { koreaPayrollClosingOperatorFixture as fixture } from "@/data/koreaPayrollClosingFixture"
</script>
