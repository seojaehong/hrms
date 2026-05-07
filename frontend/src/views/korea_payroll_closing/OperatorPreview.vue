<template>
	<BaseLayout :pageTitle="__('Payroll Closing')">
		<template #body>
			<div class="flex flex-col gap-5 mt-7 mb-7 p-4">
				<section class="rounded-2xl bg-gray-900 p-5 text-white shadow-sm">
					<div class="flex items-start justify-between gap-3">
						<div>
							<div class="text-xs font-semibold uppercase tracking-[0.18em] text-gray-300">
								{{ __("Korea Closing Center") }}
							</div>
							<h1 class="mt-2 text-2xl font-bold leading-tight">
								{{ demo.company }}
							</h1>
							<p class="mt-2 text-sm leading-6 text-gray-300">
								{{ demo.industry }} · {{ demo.period }} · {{ __("Preview-only operator queue. Runtime save, approval, and sending remain blocked until human review.") }}
							</p>
						</div>
						<div class="rounded-full bg-red-500 px-3 py-1 text-sm font-semibold text-white">
							{{ blockedCount }} {{ __("blocked") }}
						</div>
					</div>

					<div class="mt-5 grid grid-cols-3 gap-2">
						<div v-for="metric in metrics" :key="metric.label" class="rounded-xl bg-white/10 p-3">
							<div class="text-xl font-bold">{{ metric.value }}</div>
							<div class="mt-1 text-xs leading-4 text-gray-300">{{ metric.label }}</div>
						</div>
					</div>
				</section>

				<section class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
					<div class="flex items-center justify-between">
						<h2 class="text-lg font-bold text-gray-900">{{ __("Demo operating roles") }}</h2>
						<span class="text-xs font-medium text-gray-500">{{ demo.roles.length }} {{ __("roles") }}</span>
					</div>
					<div class="mt-3 grid gap-2">
						<div v-for="role in demo.roles" :key="role.label" class="rounded-xl bg-gray-50 p-3">
							<div class="flex items-center justify-between gap-3">
								<div class="text-sm font-semibold text-gray-900">{{ role.label }}</div>
								<div class="text-xs text-gray-500">{{ role.scope }}</div>
							</div>
							<div class="mt-1 text-sm text-gray-600">{{ role.name }}</div>
						</div>
					</div>
				</section>

				<section class="rounded-2xl border border-amber-200 bg-amber-50 p-4">
					<div class="flex gap-3">
						<FeatherIcon name="alert-triangle" class="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
						<div>
							<div class="text-base font-semibold text-amber-900">
								{{ __("Human approval required") }}
							</div>
							<p class="mt-1 text-sm leading-5 text-amber-800">
								{{ __("AI only compares evidence, prepares checklists, and drafts next actions. It does not predict outcomes, approve payroll, submit documents, or send provider messages.") }}
							</p>
						</div>
					</div>
				</section>

				<section class="flex flex-col gap-3">
					<div class="flex items-center justify-between">
						<h2 class="text-lg font-bold text-gray-900">{{ __("Workplace queue") }}</h2>
						<span class="text-xs font-medium text-gray-500">{{ __("Static Vercel preview") }}</span>
					</div>

					<article
						v-for="session in sessions"
						:key="session.name"
						class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm"
					>
						<div class="flex items-start justify-between gap-3">
							<div>
								<div class="text-xs font-medium text-gray-500">{{ session.period }}</div>
								<div class="mt-1 text-lg font-bold text-gray-900">{{ session.workplace }}</div>
								<div class="mt-1 text-sm text-gray-600">
									{{ session.company }} · {{ session.employeeCount }} {{ __("employees") }} · {{ session.manager }}
								</div>
							</div>
							<span
								class="rounded-full px-3 py-1 text-xs font-semibold"
								:class="statusClass(session.status)"
							>
								{{ session.statusLabel }}
							</span>
						</div>

						<div class="mt-4 grid grid-cols-2 gap-2">
							<div v-for="item in session.readiness" :key="item.label" class="rounded-xl bg-gray-50 p-3">
								<div class="flex items-center gap-2">
									<span class="h-2.5 w-2.5 rounded-full" :class="item.ready ? 'bg-green-500' : 'bg-red-500'"></span>
									<div class="text-sm font-semibold text-gray-800">{{ item.label }}</div>
								</div>
								<div class="mt-1 text-xs text-gray-500">{{ item.detail }}</div>
							</div>
						</div>

						<div v-if="session.blockers.length" class="mt-4 rounded-xl bg-red-50 p-3">
							<div class="text-sm font-semibold text-red-900">{{ __("Blockers") }}</div>
							<ul class="mt-2 flex flex-col gap-1 text-sm text-red-800">
								<li v-for="blocker in session.blockers" :key="blocker">• {{ blocker }}</li>
							</ul>
						</div>

						<div class="mt-4 rounded-xl bg-blue-50 p-3 text-sm text-blue-900">
							<span class="font-semibold">{{ __("Next action") }}:</span> {{ session.nextAction }}
						</div>

						<div class="mt-4 flex flex-col gap-2 sm:flex-row">
							<Button class="w-full justify-center" variant="solid">
								{{ __("Review evidence packet") }}
							</Button>
							<Button class="w-full justify-center" variant="subtle" :disabled="!['review_ready', 'draft_ready'].includes(session.status)">
								{{ __("Prepare draft") }}
							</Button>
						</div>
					</article>
				</section>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, inject } from "vue"
import { FeatherIcon } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import { koreaPayrollClosingDemo } from "@/data/koreaPayrollClosingDemo"

const __ = inject("$translate")

const demo = koreaPayrollClosingDemo
const sessions = demo.sessions

const blockedCount = computed(() => sessions.filter((session) => session.status === "blocked").length)

const metrics = computed(() => [
	{ label: __("Workplaces"), value: sessions.length },
	{ label: __("Needs attention"), value: blockedCount.value },
	{ label: __("Review ready"), value: sessions.filter((session) => session.status === "review_ready").length },
])

function statusClass(status) {
	if (status === "review_ready") return "bg-green-100 text-green-700"
	if (status === "draft_ready") return "bg-blue-100 text-blue-700"
	return "bg-red-100 text-red-700"
}
</script>
