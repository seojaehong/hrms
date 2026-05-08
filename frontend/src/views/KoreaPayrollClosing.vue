<template>
	<BaseLayout pageTitle="Korea Payroll Closing">
		<template #body>
			<div class="flex flex-col gap-4 overflow-y-auto bg-gray-50 p-4 pb-24">
				<section v-if="selectedSession" class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
					<router-link to="/dashboard/korea-payroll-closing" class="text-sm font-semibold text-gray-600">← Back to closing queue</router-link>
					<div class="mt-4 flex items-start justify-between gap-3">
						<div>
							<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">Session preview</p>
							<h1 class="mt-1 text-2xl font-bold text-gray-900">{{ selectedSession.workplace }}</h1>
							<p class="mt-1 text-sm text-gray-500">{{ selectedSession.name }} · {{ selectedSession.period_start }} → {{ selectedSession.period_end }}</p>
						</div>
						<span
							class="rounded-full px-3 py-1 text-xs font-semibold"
							:class="selectedSession.status === 'blocked' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'"
						>
							{{ selectedSession.status === 'blocked' ? 'Blocked' : 'Review ready' }}
						</span>
					</div>
					<div class="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
						<p class="font-semibold">Preview-only {{ selectedSession.preview_source === 'runtime_read_only' ? 'runtime read' : 'static fixture' }}</p>
						<p class="mt-1">runtime_action={{ selectedSession.runtime_action }} · requires_runtime_apply={{ selectedSession.requires_runtime_apply }} · human approval required · AI={{ selectedSession.ai_role }}</p>
					</div>
					<div class="mt-4 grid grid-cols-2 gap-2">
						<div
							v-for="card in selectedSession.readiness_cards"
							:key="`${selectedSession.name}-${card.key}`"
							class="rounded-xl border p-3"
							:class="card.state === 'blocked' ? 'border-red-100 bg-red-50' : 'border-gray-100 bg-gray-50'"
						>
							<p class="text-xs font-semibold text-gray-500">{{ card.label }}</p>
							<p class="mt-1 text-sm font-medium text-gray-900">{{ card.summary }}</p>
						</div>
					</div>
					<div class="mt-4 rounded-xl bg-gray-50 p-3">
						<p class="text-xs font-semibold text-gray-500">Primary next action</p>
						<p class="mt-1 text-base font-bold text-gray-900">{{ selectedSession.primary_action.label }}</p>
						<p class="mt-1 text-xs text-gray-500">{{ selectedSession.payroll_entry }} · no save/approve/send mutation in static preview</p>
					</div>
					<div class="mt-4 rounded-xl bg-gray-900 p-3 text-white">
						<p class="text-xs font-semibold uppercase tracking-wide text-gray-300">Audit preview</p>
						<p class="mt-2 text-sm">{{ selectedSession.audit_preview.event_type }}</p>
						<p class="mt-1 text-xs text-gray-300">Blockers: {{ selectedSession.audit_preview.blocker_codes.length ? selectedSession.audit_preview.blocker_codes.join(', ') : 'none' }}</p>
					</div>
					<div class="mt-4 rounded-xl border border-blue-100 bg-blue-50 p-3">
						<div class="flex items-start justify-between gap-3">
							<div>
								<p class="text-xs font-semibold uppercase tracking-wide text-blue-700">Evidence packet</p>
								<p class="mt-1 text-sm font-bold text-blue-950">{{ selectedSession.evidence_packet.contract_type }}</p>
							</div>
							<span class="rounded-full bg-white px-2 py-1 text-xs font-semibold text-blue-700">preview only</span>
						</div>
						<div class="mt-3 grid grid-cols-1 gap-2">
							<div
								v-for="item in selectedSession.evidence_packet.evidence_items"
								:key="`${selectedSession.name}-${item.key}`"
								class="rounded-lg bg-white p-2 text-sm"
							>
								<p class="font-semibold text-gray-900">{{ item.label }}</p>
								<p class="mt-1 text-xs text-gray-500">{{ formatEvidenceSummary(item.summary) }}</p>
							</div>
						</div>
						<div class="mt-3 rounded-lg bg-white p-2 text-xs text-gray-600">
							Human checklist: {{ selectedSession.evidence_packet.review_checklist.length }} item(s) · evidence requires_runtime_apply={{ selectedSession.evidence_packet.requires_runtime_apply }} · AI={{ selectedSession.evidence_packet.ai_role }}
						</div>
					</div>
				</section>
				<section v-else-if="route.params.name" class="rounded-2xl border border-red-100 bg-red-50 p-4 text-red-800">
					<p class="font-semibold">Session fixture not found</p>
					<p class="mt-1 text-sm">{{ route.params.name }} is not included in the active payroll closing worklist.</p>
				</section>
				<section class="rounded-2xl bg-gray-900 p-5 text-white shadow-sm">
					<div class="flex items-start justify-between gap-3">
						<div>
							<p class="text-xs font-semibold uppercase tracking-[0.2em] text-gray-300">{{ dataSourceLabel }}</p>
							<h1 class="mt-2 text-2xl font-bold leading-tight">{{ activePeriodLabel }}</h1>
							<p class="mt-2 text-sm text-gray-300">
								{{ activeCompany }} · {{ summaryCards.total_employees ?? 'runtime' }} employees · updated {{ activeWorklist.updated_at || 'runtime read' }}
							</p>
						</div>
						<span class="rounded-full px-3 py-1 text-xs font-semibold" :class="dataSourceBadgeClass">{{ dataSourceBadge }}</span>
					</div>
					<div v-if="runtimeLoading" class="mt-4 rounded-xl bg-white/10 p-3 text-sm text-gray-200">
						Loading read-only Frappe runtime data…
					</div>
					<div v-else-if="runtimeError" class="mt-4 rounded-xl bg-amber-400/20 p-3 text-sm text-amber-100">
						<p>Runtime read failed; static fixture fallback is active. {{ runtimeError }}</p>
						<p v-if="runtimeWorklistError" class="mt-1">Runtime worklist read failed; fixture worklist fallback is active. {{ runtimeWorklistError }}</p>
					</div>
					<div v-else-if="runtimeWorklistError" class="mt-4 rounded-xl bg-amber-400/20 p-3 text-sm text-amber-100">
						Runtime worklist read failed; fixture worklist fallback is active. {{ runtimeWorklistError }}
					</div>
					<div v-else-if="runtimeDashboard && !runtimeHasData" class="mt-4 rounded-xl bg-white/10 p-3 text-sm text-gray-200">
						No runtime dashboard rows were returned for this company; fixture worklist remains visible as fallback context.
					</div>
					<div v-else-if="runtimeDashboard" class="mt-4 rounded-xl bg-blue-400/20 p-3 text-sm text-blue-100">
						Runtime read-only dashboard loaded · runtime_action={{ runtimeDashboard.runtime_action }} · requires_runtime_apply={{ runtimeDashboard.requires_runtime_apply }}
						<span v-if="!runtimeHasWorklistData"> · fixture worklist remains visible until Gate 2 runtime worklist bridge is populated</span>
					</div>
					<div v-if="runtimeHasWorklistData" class="mt-4 rounded-xl bg-green-400/20 p-3 text-sm text-green-100">
						Runtime worklist loaded · runtime_action={{ runtimeWorklist.runtime_action }} · requires_runtime_apply={{ runtimeWorklist.requires_runtime_apply }} · evidence remains read-only
					</div>
					<div class="mt-4 grid grid-cols-3 gap-2 text-center">
						<div class="rounded-xl bg-white/10 p-3">
							<p class="text-2xl font-bold">{{ summaryCards.total_count }}</p>
							<p class="text-xs text-gray-300">Workplaces</p>
						</div>
						<div class="rounded-xl bg-red-400/20 p-3">
							<p class="text-2xl font-bold text-red-100">{{ summaryCards.blocked_count }}</p>
							<p class="text-xs text-red-100">Blocked</p>
						</div>
						<div class="rounded-xl bg-green-400/20 p-3">
							<p class="text-2xl font-bold text-green-100">{{ summaryCards.review_ready_count }}</p>
							<p class="text-xs text-green-100">Ready</p>
						</div>
					</div>
				</section>

				<section class="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
					<p class="font-semibold">Preview boundary</p>
					<p class="mt-1">
						This screen uses the runtime read-only worklist when validated, then falls back to static demo fixtures shaped like the payroll closing worklist preview API. It does not save, approve, send Kakao messages, or mutate Payroll Entry records. Human approval remains required and AI is assistant-only.
					</p>
				</section>

				<section class="flex flex-col gap-3">
					<article
						v-for="item in activeWorklist.items"
						:key="item.name"
						class="rounded-2xl border bg-white p-4 shadow-sm"
						:class="item.status === 'blocked' ? 'border-red-100' : 'border-green-100'"
					>
						<div class="flex items-start justify-between gap-3">
							<div>
								<p class="text-xs font-semibold uppercase tracking-wide text-gray-500">{{ item.role }}</p>
								<h2 class="mt-1 text-lg font-bold text-gray-900">{{ item.workplace }}</h2>
								<p class="mt-1 text-xs text-gray-500">{{ item.period_start }} → {{ item.period_end }} · {{ item.employee_count ?? 'runtime' }} employees</p>
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
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import BaseLayout from "@/components/BaseLayout.vue"
import {
	findKoreaPayrollClosingSession,
	koreaPayrollClosingOperatorFixture as fixture,
} from "@/data/koreaPayrollClosingFixture"
import {
	hasKoreaAdminDashboardRuntimeData,
	hasKoreaPayrollClosingRuntimeWorklistData,
	loadKoreaAdminDashboardRuntime,
	loadKoreaPayrollClosingRuntimeWorklist,
} from "@/data/koreaPayrollClosingRuntime"

const route = useRoute()
const runtimeDashboard = ref(null)
const runtimeWorklist = ref(null)
const runtimeLoading = ref(false)
const runtimeError = ref("")
const runtimeWorklistError = ref("")
const activeWorklist = computed(() => (hasKoreaPayrollClosingRuntimeWorklistData(runtimeWorklist.value) ? runtimeWorklist.value : fixture))
const selectedSession = computed(() => buildSessionPreview(findActiveSessionItem(route.params.name)))
const runtimeHasData = computed(() => hasKoreaAdminDashboardRuntimeData(runtimeDashboard.value))
const runtimeHasWorklistData = computed(() => hasKoreaPayrollClosingRuntimeWorklistData(runtimeWorklist.value))
const activeCompany = computed(() => runtimeWorklist.value?.company || runtimeDashboard.value?.company || fixture.company)
const dataSourceLabel = computed(() => (runtimeHasWorklistData.value ? "Runtime read-only worklist" : runtimeDashboard.value ? "Runtime read-only dashboard" : "Static fixture preview"))
const dataSourceBadge = computed(() => {
	if (runtimeLoading.value) return "loading"
	if (runtimeHasWorklistData.value) return "runtime worklist"
	if (runtimeDashboard.value) return "runtime_read_only"
	return "static fixture"
})
const dataSourceBadgeClass = computed(() => {
	if (runtimeHasWorklistData.value) return "bg-green-100 text-green-800"
	if (runtimeDashboard.value) return "bg-blue-100 text-blue-800"
	if (runtimeLoading.value) return "bg-white/20 text-white"
	return "bg-amber-100 text-amber-900"
})
const summaryCards = computed(() => {
	if (runtimeHasWorklistData.value) return activeWorklist.value.summary
	const metrics = runtimeDashboard.value?.metrics
	if (!metrics) return fixture.summary
	return {
		total_count: fixture.summary.total_count,
		blocked_count: metrics.blocked_payroll_closings ?? fixture.summary.blocked_count,
		review_ready_count: Math.max(0, fixture.summary.total_count - (metrics.blocked_payroll_closings ?? fixture.summary.blocked_count)),
	}
})
const activePeriodLabel = computed(() => {
	if (!runtimeHasWorklistData.value) return fixture.period_label
	const first = activeWorklist.value.items[0]
	return first?.period_start && first?.period_end ? `${first.period_start} → ${first.period_end}` : fixture.period_label
})

onMounted(loadRuntimeData)

async function loadRuntimeData() {
	runtimeLoading.value = true
	runtimeError.value = ""
	runtimeWorklistError.value = ""
	try {
		const [dashboardResult, worklistResult] = await Promise.allSettled([
			loadKoreaAdminDashboardRuntime({ fallbackCompany: fixture.company }),
			loadKoreaPayrollClosingRuntimeWorklist({ fallbackCompany: fixture.company }),
		])
		if (dashboardResult.status === "fulfilled") runtimeDashboard.value = dashboardResult.value.data
		else runtimeDashboard.value = null
		if (worklistResult.status === "fulfilled") runtimeWorklist.value = worklistResult.value.data
		else {
			runtimeWorklist.value = null
			runtimeWorklistError.value = worklistResult.reason instanceof Error ? worklistResult.reason.message : String(worklistResult.reason)
		}
		if (dashboardResult.status === "rejected" && worklistResult.status === "rejected") {
			const error = worklistResult.reason || dashboardResult.reason
			runtimeError.value = error instanceof Error ? error.message : String(error)
		}
	} finally {
		runtimeLoading.value = false
	}
}

function findActiveSessionItem(name) {
	if (!name) return null
	const runtimeItem = runtimeHasWorklistData.value ? runtimeWorklist.value.items.find((candidate) => candidate.name === name) : null
	return runtimeItem || fixture.items.find((candidate) => candidate.name === name) || null
}

function buildSessionPreview(item) {
	if (!item) return null
	const fixtureSession = findKoreaPayrollClosingSession(item.name)
	if (fixtureSession && !item.runtime_source_doctype) return fixtureSession
	const auditPreview = item.audit_preview || { runtime_action: "preview_only", requires_runtime_apply: false, blocker_codes: item.blocker_codes || [] }
	const session = {
		...item,
		role: item.role || item.draft_status || "Runtime Payroll Operator",
		blocker_codes: Array.isArray(item.blocker_codes) ? [...item.blocker_codes] : [],
		primary_action: { ...(item.primary_action || { action: "review_payroll_artifacts", label: "Review payroll artifacts", requires_runtime_apply: false }) },
		readiness_cards: Array.isArray(item.readiness_cards) ? item.readiness_cards.map((card) => ({ ...card })) : [],
		contract_type: "korea_payroll_closing_session_runtime_preview_v1",
		session_contract_type: item.source_session?.contract_type || "korea_payroll_closing_session_v1",
		preview_source: item.runtime_source_doctype ? "runtime_read_only" : "static_fixture",
		runtime_action: item.runtime_action || "runtime_read_only",
		requires_runtime_apply: false,
		requires_human_approval: true,
		ai_role: "assistant_only",
		audit_preview: {
			...auditPreview,
			blocker_codes: Array.isArray(auditPreview.blocker_codes) ? [...auditPreview.blocker_codes] : [...(item.blocker_codes || [])],
		},
	}
	return {
		...session,
		evidence_packet: buildRuntimeEvidencePacket(session),
	}
}

function buildRuntimeEvidencePacket(session) {
	return {
		contract_type: "korea_payroll_closing_evidence_packet_runtime_read_v1",
		source_session_contract_type: session.session_contract_type,
		runtime_action: "preview_only",
		requires_runtime_apply: false,
		preview_source: "runtime_read_only",
		company: session.company,
		workplace: session.workplace,
		period_start: session.period_start,
		period_end: session.period_end,
		status: session.status,
		actor: session.role,
		purpose: "payroll closing human review runtime read preview",
		blocker_codes: [...session.blocker_codes],
		evidence_items: [
			{ key: "attendance", label: "Attendance readiness", summary: copyCard(session.readiness_cards.find((card) => card.key === "attendance")) },
			{ key: "payroll_artifacts", label: "Payroll and statutory artifacts", summary: { payroll_entry: session.payroll_entry, employee_count: session.employee_count } },
			{ key: "approval", label: "Approval readiness", summary: copyCard(session.readiness_cards.find((card) => card.key === "approval")) },
			{ key: "notification", label: "Payslip/Kakao notification readiness", summary: copyCard(session.readiness_cards.find((card) => card.key === "notification")) },
			{ key: "audit_preview", label: "Audit preview boundary", summary: { ...session.audit_preview, blocker_codes: [...session.audit_preview.blocker_codes] } },
		],
		review_checklist: session.blocker_codes.length
			? session.blocker_codes.map((code) => ({ status: "needs_human_review", blocker_code: code, requires_runtime_apply: false }))
			: [{ status: "needs_human_approval", action: "record_human_review", requires_runtime_apply: false }],
		next_actions: [{ ...session.primary_action }],
		source_session: session.source_session || null,
		requires_human_approval: true,
		ai_role: "assistant_only",
	}
}

function formatEvidenceSummary(summary) {
	if (!summary) return "missing"
	if (typeof summary === "string") return summary
	if (typeof summary !== "object") return String(summary)
	return Object.entries(summary)
		.map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : value}`)
		.join(" · ")
}

function copyCard(card) {
	return card ? { ...card } : { status: "missing" }
}
</script>
