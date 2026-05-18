export const koreaPayrollClosingOperatorFixture = {
	contract_type: "korea_payroll_closing_worklist_preview_v1",
	worklist_contract_type: "korea_payroll_closing_worklist_v1",
	runtime_action: "preview_only",
	preview_source: "static_fixture",
	requires_runtime_apply: false,
	requires_human_approval: true,
	ai_role: "assistant_only",
	company: "Korea Demo Franchise Co",
	workplaces: ["Busan Branch", "Daegu Store", "Incheon Franchise", "Seoul HQ"],
	period_label: "2026년 5월 급여 마감",
	updated_at: "2026-05-31T18:30:00+09:00",
	summary: {
		total_count: 4,
		blocked_count: 3,
		review_ready_count: 1,
		total_employees: 58,
	},
	items: [
		{
			name: "KPCS-2026-05-SEOUL-HQ",
			company: "Korea Demo Franchise Co",
			workplace: "Seoul HQ",
			role: "HQ Payroll Operator",
			period_start: "2026-05-01",
			period_end: "2026-05-31",
			status: "blocked",
			employee_count: 22,
			blocker_codes: ["attendance_not_ready", "kakao_queue_not_ready"],
			primary_action: {
				action: "resolve_attendance_blockers",
				label: "미확정 출근 3건 검토",
				requires_runtime_apply: false,
			},
			route: "korea-payroll-closing-session/KPCS-2026-05-SEOUL-HQ",
			payroll_entry: "PAY-ENTRY-SEOUL-2026-05",
			readiness_cards: [
				{ key: "attendance", label: "근태", state: "blocked", summary: "미확정 3일" },
				{ key: "payroll", label: "급여/4대보험", state: "ready", summary: "22명 산출 완료" },
				{ key: "approval", label: "승인", state: "ready", summary: "본사 운영자 배정" },
				{ key: "notification", label: "Kakao/급여명세", state: "blocked", summary: "알림 큐 미생성" },
				{ key: "expense", label: "비용정산", state: "ready", summary: "미지급 0건" },
			],
			requires_human_approval: true,
			ai_role: "assistant_only",
		},
		{
			name: "KPCS-2026-05-BUSAN-BRANCH",
			company: "Korea Demo Franchise Co",
			workplace: "Busan Branch",
			role: "Branch Manager",
			period_start: "2026-05-01",
			period_end: "2026-05-31",
			status: "blocked",
			employee_count: 14,
			blocker_codes: ["approver_missing"],
			primary_action: {
				action: "assign_payroll_approver",
				label: "마감 승인자 지정",
				requires_runtime_apply: false,
			},
			route: "korea-payroll-closing-session/KPCS-2026-05-BUSAN-BRANCH",
			payroll_entry: "PAY-ENTRY-BUSAN-2026-05",
			readiness_cards: [
				{ key: "attendance", label: "근태", state: "ready", summary: "14명 확인" },
				{ key: "payroll", label: "급여/4대보험", state: "ready", summary: "검증 요청 준비" },
				{ key: "approval", label: "승인", state: "blocked", summary: "승인자 없음" },
				{ key: "notification", label: "Kakao/급여명세", state: "ready", summary: "14명 대상" },
			],
			requires_human_approval: true,
			ai_role: "assistant_only",
		},
		{
			name: "KPCS-2026-05-INCHEON-FRANCHISE",
			company: "Korea Demo Franchise Co",
			workplace: "Incheon Franchise",
			role: "External Labor Advisor",
			period_start: "2026-05-01",
			period_end: "2026-05-31",
			status: "blocked",
			employee_count: 9,
			blocker_codes: ["employment_contracts_not_ready", "expense_settlement_not_ready"],
			primary_action: {
				action: "review_employment_contracts",
				label: "근로계약/비용 증빙 검토",
				requires_runtime_apply: false,
			},
			route: "korea-payroll-closing-session/KPCS-2026-05-INCHEON-FRANCHISE",
			payroll_entry: "PAY-ENTRY-INCHEON-2026-05",
			readiness_cards: [
				{ key: "attendance", label: "근태", state: "ready", summary: "9명 확인" },
				{ key: "payroll", label: "급여/4대보험", state: "ready", summary: "정책 v2026.05" },
				{ key: "contract", label: "계약서", state: "blocked", summary: "누락 2건" },
				{ key: "expense", label: "비용정산", state: "blocked", summary: "미지급 1건" },
			],
			requires_human_approval: true,
			ai_role: "assistant_only",
		},
		{
			name: "KPCS-2026-05-DAEGU-STORE",
			company: "Korea Demo Franchise Co",
			workplace: "Daegu Store",
			role: "Branch Manager",
			period_start: "2026-05-01",
			period_end: "2026-05-31",
			status: "review_ready",
			employee_count: 13,
			blocker_codes: [],
			primary_action: {
				action: "review_payroll_artifacts",
				label: "최종 검토 시작",
				requires_runtime_apply: false,
			},
			route: "korea-payroll-closing-session/KPCS-2026-05-DAEGU-STORE",
			payroll_entry: "PAY-ENTRY-DAEGU-2026-05",
			readiness_cards: [
				{ key: "attendance", label: "근태", state: "ready", summary: "13명 확인" },
				{ key: "payroll", label: "급여/4대보험", state: "ready", summary: "공제/회사부담 표시" },
				{ key: "approval", label: "승인", state: "ready", summary: "점장 승인 대기" },
				{ key: "notification", label: "Kakao/급여명세", state: "ready", summary: "발송 전 검토" },
			],
			requires_human_approval: true,
			ai_role: "assistant_only",
		},
	],
}

export function findKoreaPayrollClosingSession(name) {
	if (!name) return null
	const item = koreaPayrollClosingOperatorFixture.items.find((candidate) => candidate.name === name)
	if (!item) return null
	const session = {
		...item,
		blocker_codes: [...item.blocker_codes],
		primary_action: { ...item.primary_action },
		readiness_cards: item.readiness_cards.map((card) => ({ ...card })),
		contract_type: "korea_payroll_closing_session_static_preview_v1",
		session_contract_type: "korea_payroll_closing_session_v1",
		runtime_action: koreaPayrollClosingOperatorFixture.runtime_action,
		preview_source: koreaPayrollClosingOperatorFixture.preview_source,
		requires_runtime_apply: false,
		requires_human_approval: true,
		ai_role: "assistant_only",
		audit_preview: {
			event_type: "korea_payroll_closing_session_review_v1",
			runtime_action: "preview_only",
			requires_runtime_apply: false,
			company: item.company,
			workplace: item.workplace,
			period_start: item.period_start,
			period_end: item.period_end,
			status: item.status,
			blocker_codes: [...item.blocker_codes],
		},
	}
	return {
		...session,
		evidence_packet: buildStaticEvidencePacket(session),
	}
}

function buildStaticEvidencePacket(session) {
	const sourceSession = buildSourceSession(session)
	return {
		contract_type: "korea_payroll_closing_evidence_packet_v1",
		source_session_contract_type: "korea_payroll_closing_session_v1",
		runtime_action: "preview_only",
		requires_runtime_apply: false,
		preview_source: koreaPayrollClosingOperatorFixture.preview_source,
		company: session.company,
		workplace: session.workplace,
		period_start: session.period_start,
		period_end: session.period_end,
		status: session.status,
		actor: session.role,
		purpose: "payroll closing human review static preview",
		blocker_codes: [...session.blocker_codes],
		evidence_items: [
			{
				key: "attendance",
				label: "Attendance readiness",
				summary: copyCard(session.readiness_cards.find((card) => card.key === "attendance")),
			},
			{
				key: "payroll_artifacts",
				label: "Payroll and statutory artifacts",
				summary: {
					payroll_entry: session.payroll_entry,
					employee_count: session.employee_count,
					statutory_basis_visible: true,
				},
			},
			{
				key: "approval",
				label: "Approval readiness",
				summary: copyCard(session.readiness_cards.find((card) => card.key === "approval")),
			},
			{
				key: "notification",
				label: "Payslip/Kakao notification readiness",
				summary: copyCard(session.readiness_cards.find((card) => card.key === "notification")),
			},
			{
				key: "expense_settlement",
				label: "Expense settlement readiness",
				summary: copyCard(session.readiness_cards.find((card) => card.key === "expense")),
			},
			{
				key: "employment_contracts",
				label: "Employment contract readiness",
				summary: copyCard(session.readiness_cards.find((card) => card.key === "contract")),
			},
			{
				key: "audit_preview",
				label: "Audit preview boundary",
				summary: {
					...session.audit_preview,
					blocker_codes: [...session.audit_preview.blocker_codes],
				},
			},
		],
		review_checklist: buildStaticReviewChecklist(session),
		next_actions: [{ ...session.primary_action }],
		source_session: sourceSession,
		requires_human_approval: true,
		ai_role: "assistant_only",
	}
}

function buildSourceSession(session) {
	return {
		contract_type: "korea_payroll_closing_session_v1",
		company: session.company,
		workplace: session.workplace,
		period_start: session.period_start,
		period_end: session.period_end,
		status: session.status,
		blockers: session.blocker_codes.map((code) => ({
			code,
			severity: "blocking",
			message: code,
		})),
		next_actions: [{ ...session.primary_action }],
		readiness_cards: session.readiness_cards.map((card) => ({ ...card })),
		payroll_artifacts: {
			payroll_entry: session.payroll_entry,
			salary_slip_count: session.employee_count,
		},
		approval_state: copyCard(session.readiness_cards.find((card) => card.key === "approval")),
		notification_state: copyCard(session.readiness_cards.find((card) => card.key === "notification")),
		audit_preview: {
			...session.audit_preview,
			blocker_codes: [...session.audit_preview.blocker_codes],
		},
		requires_human_approval: true,
		ai_role: "assistant_only",
	}
}

function buildStaticReviewChecklist(session) {
	if (!session.blocker_codes.length) {
		return [{ status: "needs_human_approval", action: "record_human_review", requires_runtime_apply: true }]
	}
	return session.blocker_codes.map((code) => ({
		status: "needs_human_review",
		blocker_code: code,
		requires_runtime_apply: true,
	}))
}

function copyCard(card) {
	return card ? { ...card } : { status: "missing" }
}
