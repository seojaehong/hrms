import { createResource } from "frappe-ui"

/**
 * 컴플라이언스 진단 런타임 데이터
 * Phase 2-F: hrms.regional.south_korea.compliance_diagnosis_api
 * Phase 5-A-4: 카테고리 상세 / action plan / PDF / audit log 확장
 *
 * 설계 원칙:
 * - 점수/확률 출력 없음. 정성 status(pass/warn/fail)만.
 * - mutation은 admin role + human_approved confirm만.
 * - PII 마스킹 옵션 (직원 이름 부분 마스크).
 * - AI_ROLE: assistant_only.
 */

// ---------------------------------------------------------------------------
// 상수 정의
// ---------------------------------------------------------------------------

export const DIAGNOSIS_API_URL =
	"hrms.regional.south_korea.compliance_diagnosis_api.run_compliance_diagnosis"

export const DIAGNOSIS_RULES_URL =
	"hrms.regional.south_korea.compliance_diagnosis_api.get_diagnosis_rules"

export const PDF_DOWNLOAD_URL =
	"hrms.regional.south_korea.compliance_report_pdf.download_compliance_pdf"

export const ACTION_PLAN_URL =
	"hrms.regional.south_korea.compliance_action_plan_api.generate_action_plan"

export const AUDIT_LOG_URL =
	"hrms.regional.south_korea.compliance_audit_log_api.log_compliance_event"

/** 카테고리 레이블 (백엔드 key → 한국어) */
export const CATEGORY_LABELS = {
	social_insurance: "4대보험 가입",
	wage_delay: "임금 정기 지급",
	overtime_limit: "주 12h 연장근로 한도",
	annual_leave_usage: "연차 사용 촉진",
	anti_bullying_policy: "직장 내 괴롭힘 예방",
}

/** 카테고리별 법 조항 */
export const CATEGORY_LAWS = {
	social_insurance: "국민연금법 / 건강보험법 / 고용보험법 / 산재법",
	wage_delay: "근기법 43조",
	overtime_limit: "근기법 53조",
	annual_leave_usage: "근기법 61조",
	anti_bullying_policy: "근기법 76조의2 ~ 76조의3",
}

/** 카테고리별 관련 Frappe 모듈 */
export const CATEGORY_RELATED_MODULES = {
	social_insurance: [
		{ label: "직원 마스터", route: "/app/employee", doctype: "Employee" },
		{ label: "Korea Employment Profile", route: "/app/korea-employment-profile", doctype: "Korea Employment Profile" },
	],
	wage_delay: [
		{ label: "급여 명세서", route: "/app/salary-slip", doctype: "Salary Slip" },
		{ label: "Korea Workplace Profile", route: "/app/korea-workplace-profile", doctype: "Korea Workplace Profile" },
	],
	overtime_limit: [
		{ label: "근태 기록", route: "/app/attendance", doctype: "Attendance" },
		{ label: "Shift 설정", route: "/app/shift-type", doctype: "Shift Type" },
	],
	annual_leave_usage: [
		{ label: "연차 할당", route: "/app/leave-allocation", doctype: "Leave Allocation" },
		{ label: "연차 신청", route: "/app/leave-application", doctype: "Leave Application" },
	],
	anti_bullying_policy: [
		{ label: "Korea Workplace Profile", route: "/app/korea-workplace-profile", doctype: "Korea Workplace Profile" },
		{ label: "Korea Policy Document", route: "/app/korea-policy-document", doctype: "Korea Policy Document" },
	],
}

/** Status 표시 설정 — 점수/확률 없음 */
export const STATUS_CONFIG = {
	pass: {
		emoji: "🟢",
		text: "양호",
		textClass: "text-green-700",
		badgeStyle: "background:var(--surface-green, #dcfce7)",
	},
	warn: {
		emoji: "🟡",
		text: "주의 필요",
		textClass: "text-yellow-700",
		badgeStyle: "background:var(--surface-yellow, #fef9c3)",
	},
	fail: {
		emoji: "🔴",
		text: "위험",
		textClass: "text-red-700",
		badgeStyle: "background:var(--surface-red, #fee2e2)",
	},
}

/** Overall status 표시 설정 */
export const OVERALL_STATUS_CONFIG = {
	good: { emoji: "🟢", text: "컴플라이언스 양호", textClass: "text-green-700" },
	needs_attention: { emoji: "🟡", text: "일부 항목 검토 필요", textClass: "text-yellow-700" },
	high_risk: { emoji: "🔴", text: "즉시 조치 필요", textClass: "text-red-700" },
}

// ---------------------------------------------------------------------------
// createResource 인스턴스 (Frappe-UI)
// ---------------------------------------------------------------------------

/**
 * 전체 컴플라이언스 진단 실행.
 * Admin only + human_approved confirm 후 호출.
 */
export const complianceDiagnosis = createResource({
	url: DIAGNOSIS_API_URL,
	makeParams(values) {
		return {
			company: values?.company,
			workplace: values?.workplace ?? null,
			as_of_date: values?.as_of_date ?? null,
		}
	},
})

/**
 * 진단 규칙 목록 (참고용, read-only).
 */
export const diagnosisRules = createResource({
	url: DIAGNOSIS_RULES_URL,
	auto: false,
})

/**
 * 개선 액션 플랜 생성.
 * Admin only + human_approved confirm 후 호출.
 */
export const complianceActionPlan = createResource({
	url: ACTION_PLAN_URL,
	makeParams(values) {
		return {
			company: values?.company,
			workplace: values?.workplace ?? null,
			as_of_date: values?.as_of_date ?? null,
			deadline_days: values?.deadline_days ?? 30,
		}
	},
})

// ---------------------------------------------------------------------------
// 유틸리티 함수
// ---------------------------------------------------------------------------

/**
 * 종합 상태 산출 — 진단 결과 dict 기반.
 * 점수/확률 없음. fail > warn > pass 우선순위.
 *
 * @param {Object} diagnoses - { social_insurance: { status: "pass"|"warn"|"fail" }, ... }
 * @returns {"fail"|"warn"|"pass"}
 */
export function deriveOverallStatus(diagnoses) {
	if (!diagnoses || typeof diagnoses !== "object") return "warn"
	const values = Object.values(diagnoses)
	if (values.some((c) => c?.status === "fail")) return "fail"
	if (values.some((c) => c?.status === "warn")) return "warn"
	return "pass"
}

/**
 * 카테고리별 결과 배열 생성 (dashboard card 렌더링용).
 *
 * @param {Object} diagnoses - diagnosis_result.diagnoses
 * @returns {Array}
 */
export function buildCategoryCards(diagnoses) {
	if (!diagnoses) return []
	return Object.entries(diagnoses).map(([key, result]) => {
		const config = STATUS_CONFIG[result?.status] ?? STATUS_CONFIG.warn
		const findings = result?.findings ?? []
		const recommendations = result?.recommendations ?? []

		return {
			key,
			label: CATEGORY_LABELS[key] ?? key,
			law: CATEGORY_LAWS[key] ?? "",
			status: result?.status ?? "warn",
			statusEmoji: config.emoji,
			statusText: config.text,
			statusTextClass: config.textClass,
			badgeStyle: config.badgeStyle,
			findings,
			recommendations,
			findingCount: findings.filter((f) => !f.data_unavailable).length,
			affectedEmployees: _countAffectedEmployees(findings),
			relatedModules: CATEGORY_RELATED_MODULES[key] ?? [],
		}
	})
}

/**
 * PDF 다운로드 트리거.
 * Blob URL 방식으로 파일 다운로드.
 *
 * @param {string} company
 * @param {string} workplace
 * @param {string|null} asOfDate
 * @returns {Promise<void>}
 */
export async function downloadCompliancePdf(company, workplace, asOfDate) {
	const params = new URLSearchParams({
		company,
		workplace: workplace ?? "",
	})
	if (asOfDate) {
		params.set("as_of_date", asOfDate)
	}

	const url = `/api/method/${PDF_DOWNLOAD_URL}?${params.toString()}`

	const response = await fetch(url, { credentials: "include" })
	if (!response.ok) {
		throw new Error(`PDF 다운로드 실패: ${response.status}`)
	}

	const blob = await response.blob()
	const objectUrl = URL.createObjectURL(blob)

	const safeDate = (asOfDate ?? new Date().toISOString().slice(0, 10)).replace(/-/g, "")
	const safeCompany = company.replace(/\s+/g, "_")
	const filename = `compliance_report_${safeCompany}_${safeDate}.pdf`

	const anchor = document.createElement("a")
	anchor.href = objectUrl
	anchor.download = filename
	document.body.appendChild(anchor)
	anchor.click()
	document.body.removeChild(anchor)
	setTimeout(() => URL.revokeObjectURL(objectUrl), 5000)
}

/**
 * PII 마스킹 — 직원 이름 부분 마스크.
 * 이름 두 번째 글자부터 마스크 처리.
 *
 * @param {string} name - 직원 이름
 * @param {boolean} mask - 마스킹 여부
 * @returns {string}
 */
export function maskEmployeeName(name, mask = false) {
	if (!mask || !name || typeof name !== "string") return name
	if (name.length <= 1) return "*"
	return name[0] + "*".repeat(name.length - 1)
}

/**
 * findings 배열에서 영향받는 직원 수 계산.
 *
 * @param {Array} findings
 * @returns {number}
 */
function _countAffectedEmployees(findings) {
	if (!findings || !Array.isArray(findings)) return 0
	const employees = new Set(
		findings
			.filter((f) => f.employee && !f.data_unavailable)
			.map((f) => f.employee)
	)
	return employees.size
}

/**
 * 카테고리 상세 데이터 추출.
 *
 * @param {Object} diagnosisResult - run_full_compliance_diagnosis 반환값
 * @param {string} categoryKey
 * @returns {Object|null}
 */
export function getCategoryDetail(diagnosisResult, categoryKey) {
	if (!diagnosisResult?.diagnoses) return null
	const result = diagnosisResult.diagnoses[categoryKey]
	if (!result) return null

	const config = STATUS_CONFIG[result.status] ?? STATUS_CONFIG.warn
	const overallConfig = OVERALL_STATUS_CONFIG[diagnosisResult.overall_status] ?? OVERALL_STATUS_CONFIG.needs_attention

	return {
		key: categoryKey,
		label: CATEGORY_LABELS[categoryKey] ?? categoryKey,
		law: CATEGORY_LAWS[categoryKey] ?? "",
		status: result.status,
		statusEmoji: config.emoji,
		statusText: config.text,
		statusTextClass: config.textClass,
		badgeStyle: config.badgeStyle,
		findings: result.findings ?? [],
		recommendations: result.recommendations ?? [],
		relatedModules: CATEGORY_RELATED_MODULES[categoryKey] ?? [],
		company: diagnosisResult.company,
		workplace: diagnosisResult.workplace,
		as_of_date: diagnosisResult.as_of_date,
		overall_status: diagnosisResult.overall_status,
		overall_label: overallConfig.text,
	}
}
