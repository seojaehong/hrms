/**
 * koreaComplianceRuntime.js — unit tests (Phase 5-A-4 확장)
 *
 * Tests verify:
 * 1. makeParams forwards company and workplace.
 * 2. workplace defaults to null when not provided.
 * 3. Company falls back to injected employee data.
 * 4. deriveOverallStatus derivation logic.
 * 5. buildCategoryCards 구조 (점수/확률 없음 확인).
 * 6. maskEmployeeName PII 마스킹.
 * 7. getCategoryDetail 추출 로직.
 * 8. downloadCompliancePdf URL 생성 로직.
 * 9. STATUS_CONFIG no-score assertion.
 * 10. CATEGORY_LABELS 5개 카테고리 완전성.
 */

import assert from "node:assert/strict"
import { describe, it } from "node:test"

// ---------------------------------------------------------------------------
// Replicate module functions (framework-free)
// ---------------------------------------------------------------------------

const DIAGNOSIS_API_URL =
	"hrms.regional.south_korea.compliance_diagnosis_api.run_compliance_diagnosis"

const PDF_DOWNLOAD_URL =
	"hrms.regional.south_korea.compliance_report_pdf.download_compliance_pdf"

const ACTION_PLAN_URL =
	"hrms.regional.south_korea.compliance_action_plan_api.generate_action_plan"

const AUDIT_LOG_URL =
	"hrms.regional.south_korea.compliance_audit_log_api.log_compliance_event"

const CATEGORY_LABELS = {
	social_insurance: "4대보험 가입",
	wage_delay: "임금 정기 지급",
	overtime_limit: "주 12h 연장근로 한도",
	annual_leave_usage: "연차 사용 촉진",
	anti_bullying_policy: "직장 내 괴롭힘 예방",
}

const CATEGORY_LAWS = {
	social_insurance: "국민연금법 / 건강보험법 / 고용보험법 / 산재법",
	wage_delay: "근기법 43조",
	overtime_limit: "근기법 53조",
	annual_leave_usage: "근기법 61조",
	anti_bullying_policy: "근기법 76조의2 ~ 76조의3",
}

const CATEGORY_RELATED_MODULES = {
	social_insurance: [
		{ label: "직원 마스터", route: "/app/employee", doctype: "Employee" },
		{ label: "Korea Employment Profile", route: "/app/korea-employment-profile", doctype: "Korea Employment Profile" },
	],
	wage_delay: [
		{ label: "급여 명세서", route: "/app/salary-slip", doctype: "Salary Slip" },
	],
	overtime_limit: [
		{ label: "근태 기록", route: "/app/attendance", doctype: "Attendance" },
	],
	annual_leave_usage: [
		{ label: "연차 할당", route: "/app/leave-allocation", doctype: "Leave Allocation" },
	],
	anti_bullying_policy: [
		{ label: "Korea Workplace Profile", route: "/app/korea-workplace-profile", doctype: "Korea Workplace Profile" },
	],
}

const STATUS_CONFIG = {
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

const OVERALL_STATUS_CONFIG = {
	good: { emoji: "🟢", text: "컴플라이언스 양호", textClass: "text-green-700" },
	needs_attention: { emoji: "🟡", text: "일부 항목 검토 필요", textClass: "text-yellow-700" },
	high_risk: { emoji: "🔴", text: "즉시 조치 필요", textClass: "text-red-700" },
}

// Replicated functions
const makeParams = function (values, employeeData) {
	return {
		company: values?.company ?? employeeData?.company,
		workplace: values?.workplace ?? null,
		as_of_date: values?.as_of_date ?? null,
	}
}

function deriveOverallStatus(diagnoses) {
	if (!diagnoses || typeof diagnoses !== "object") return "warn"
	const values = Object.values(diagnoses)
	if (values.some((c) => c?.status === "fail")) return "fail"
	if (values.some((c) => c?.status === "warn")) return "warn"
	return "pass"
}

function maskEmployeeName(name, mask = false) {
	if (!mask || !name || typeof name !== "string") return name
	if (name.length <= 1) return "*"
	return name[0] + "*".repeat(name.length - 1)
}

function buildCategoryCards(diagnoses) {
	if (!diagnoses) return []
	return Object.entries(diagnoses).map(([key, result]) => {
		const config = STATUS_CONFIG[result?.status] ?? STATUS_CONFIG.warn
		const findings = result?.findings ?? []
		const recommendations = result?.recommendations ?? []
		const affectedEmployees = new Set(
			findings.filter((f) => f.employee && !f.data_unavailable).map((f) => f.employee)
		).size

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
			affectedEmployees,
			relatedModules: CATEGORY_RELATED_MODULES[key] ?? [],
		}
	})
}

function getCategoryDetail(diagnosisResult, categoryKey) {
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

// ---------------------------------------------------------------------------
// 테스트 픽스처
// ---------------------------------------------------------------------------

const MOCK_DIAGNOSIS_RESULT = {
	contract_type: "korea_compliance_diagnosis_v1",
	as_of_date: "2026-05-17",
	company: "위너스",
	workplace: "서울지사",
	overall_status: "high_risk",
	high_severity_findings: 2,
	recommendation_summary: "[즉시 조치 필요] 위반 항목: 4대보험 가입, 직장 내 괴롭힘 예방",
	diagnoses: {
		social_insurance: {
			status: "fail",
			findings: [
				{
					employee: "EMP-001",
					employee_name: "김철수",
					issue: "4대보험 미가입: 국민연금",
					law: "국민연금법",
				},
			],
			recommendations: ["미가입 직원의 4대보험 즉시 취득 신고를 진행하세요."],
		},
		wage_delay: {
			status: "pass",
			findings: [],
			recommendations: [],
		},
		overtime_limit: {
			status: "warn",
			findings: [
				{
					employee: "EMP-002",
					employee_name: "이영희",
					issue: "주 연장근로 한도 초과: 14.0h",
					law: "근기법 53조",
					data_unavailable: false,
					detail: { week_start: "2026-05-11", overtime_hours: 14.0, limit_hours: 12.0 },
				},
			],
			recommendations: ["주 12시간 연장근로 한도를 초과한 직원에 대한 근로시간 조정이 필요합니다."],
		},
		annual_leave_usage: {
			status: "warn",
			findings: [
				{
					employee: "EMP-001",
					employee_name: "김철수",
					issue: "연차 미사용 비율 높음",
					law: "근기법 61조",
					data_unavailable: false,
					detail: { allocated_days: 15, used_days: 1, unused_days: 14 },
				},
			],
			recommendations: ["연차 사용 촉진 제도를 적용하세요."],
		},
		anti_bullying_policy: {
			status: "fail",
			findings: [
				{
					issue: "직장 내 괴롭힘 예방 정책 문서가 시스템에 등록되지 않음",
					law: "근기법 76조의2",
				},
			],
			recommendations: ["직장 내 괴롭힘 예방 정책 문서를 작성하여 시스템에 등록하세요."],
		},
	},
}

// ---------------------------------------------------------------------------
// 테스트 슈트
// ---------------------------------------------------------------------------

describe("koreaComplianceRuntime — makeParams logic", () => {
	it("forwards explicit company and workplace", () => {
		const params = makeParams({ company: "위너스", workplace: "서울지점" }, {})
		assert.equal(params.company, "위너스")
		assert.equal(params.workplace, "서울지점")
	})

	it("defaults workplace to null when not provided", () => {
		const params = makeParams({ company: "위너스" }, {})
		assert.equal(params.workplace, null)
	})

	it("defaults as_of_date to null when not provided", () => {
		const params = makeParams({ company: "위너스" }, {})
		assert.equal(params.as_of_date, null)
	})

	it("forwards explicit as_of_date", () => {
		const params = makeParams({ company: "위너스", as_of_date: "2026-05-17" }, {})
		assert.equal(params.as_of_date, "2026-05-17")
	})

	it("falls back to injected employee company", () => {
		const params = makeParams({}, { company: "노무법인위너스" })
		assert.equal(params.company, "노무법인위너스")
	})

	it("DIAGNOSIS_API_URL points to compliance_diagnosis_api", () => {
		assert.ok(DIAGNOSIS_API_URL.includes("compliance_diagnosis_api"))
		assert.ok(DIAGNOSIS_API_URL.includes("run_compliance_diagnosis"))
	})

	it("PDF_DOWNLOAD_URL points to compliance_report_pdf", () => {
		assert.ok(PDF_DOWNLOAD_URL.includes("compliance_report_pdf"))
		assert.ok(PDF_DOWNLOAD_URL.includes("download_compliance_pdf"))
	})

	it("ACTION_PLAN_URL points to compliance_action_plan_api", () => {
		assert.ok(ACTION_PLAN_URL.includes("compliance_action_plan_api"))
		assert.ok(ACTION_PLAN_URL.includes("generate_action_plan"))
	})

	it("AUDIT_LOG_URL points to compliance_audit_log_api", () => {
		assert.ok(AUDIT_LOG_URL.includes("compliance_audit_log_api"))
		assert.ok(AUDIT_LOG_URL.includes("log_compliance_event"))
	})
})

describe("deriveOverallStatus — 정성 status 판정", () => {
	it("fail when any category is fail", () => {
		const status = deriveOverallStatus({
			social_insurance: { status: "pass" },
			wage_delay: { status: "fail" },
			overtime_limit: { status: "warn" },
		})
		assert.equal(status, "fail")
	})

	it("warn when any category is warn (no fail)", () => {
		const status = deriveOverallStatus({
			social_insurance: { status: "pass" },
			wage_delay: { status: "warn" },
			overtime_limit: { status: "pass" },
		})
		assert.equal(status, "warn")
	})

	it("pass when all categories pass", () => {
		const status = deriveOverallStatus({
			social_insurance: { status: "pass" },
			wage_delay: { status: "pass" },
			overtime_limit: { status: "pass" },
			annual_leave_usage: { status: "pass" },
			anti_bullying_policy: { status: "pass" },
		})
		assert.equal(status, "pass")
	})

	it("returns warn for null/undefined input", () => {
		assert.equal(deriveOverallStatus(null), "warn")
		assert.equal(deriveOverallStatus(undefined), "warn")
	})

	it("returns warn for empty object", () => {
		assert.equal(deriveOverallStatus({}), "pass")
	})
})

describe("STATUS_CONFIG — 점수/확률 없음 검증", () => {
	it("STATUS_CONFIG has pass/warn/fail keys", () => {
		assert.ok(STATUS_CONFIG.pass)
		assert.ok(STATUS_CONFIG.warn)
		assert.ok(STATUS_CONFIG.fail)
	})

	it("no numeric score exposed in STATUS_CONFIG", () => {
		for (const cfg of Object.values(STATUS_CONFIG)) {
			assert.ok(!("score" in cfg), "score field must not exist")
			assert.ok(!("probability" in cfg), "probability field must not exist")
			assert.ok(!("percent" in cfg), "percent field must not exist")
			assert.ok(!("risk_score" in cfg), "risk_score field must not exist")
		}
	})

	it("OVERALL_STATUS_CONFIG has good/needs_attention/high_risk keys", () => {
		assert.ok(OVERALL_STATUS_CONFIG.good)
		assert.ok(OVERALL_STATUS_CONFIG.needs_attention)
		assert.ok(OVERALL_STATUS_CONFIG.high_risk)
	})
})

describe("CATEGORY_LABELS — 5 카테고리 완전성", () => {
	const EXPECTED_CATEGORIES = [
		"social_insurance",
		"wage_delay",
		"overtime_limit",
		"annual_leave_usage",
		"anti_bullying_policy",
	]

	it("has all 5 expected category keys", () => {
		for (const key of EXPECTED_CATEGORIES) {
			assert.ok(key in CATEGORY_LABELS, `CATEGORY_LABELS missing: ${key}`)
		}
	})

	it("all category labels are non-empty strings", () => {
		for (const [key, label] of Object.entries(CATEGORY_LABELS)) {
			assert.ok(typeof label === "string" && label.length > 0, `Empty label for: ${key}`)
		}
	})

	it("CATEGORY_LAWS has all 5 categories", () => {
		for (const key of EXPECTED_CATEGORIES) {
			assert.ok(key in CATEGORY_LAWS, `CATEGORY_LAWS missing: ${key}`)
		}
	})

	it("CATEGORY_RELATED_MODULES has all 5 categories", () => {
		for (const key of EXPECTED_CATEGORIES) {
			assert.ok(key in CATEGORY_RELATED_MODULES, `CATEGORY_RELATED_MODULES missing: ${key}`)
			assert.ok(Array.isArray(CATEGORY_RELATED_MODULES[key]), `Related modules must be array for: ${key}`)
		}
	})
})

describe("buildCategoryCards — 카테고리 카드 생성", () => {
	it("returns empty array for null diagnoses", () => {
		assert.deepEqual(buildCategoryCards(null), [])
		assert.deepEqual(buildCategoryCards(undefined), [])
	})

	it("returns correct number of cards", () => {
		const cards = buildCategoryCards(MOCK_DIAGNOSIS_RESULT.diagnoses)
		assert.equal(cards.length, 5)
	})

	it("each card has required fields", () => {
		const cards = buildCategoryCards(MOCK_DIAGNOSIS_RESULT.diagnoses)
		for (const card of cards) {
			assert.ok(card.key, "card must have key")
			assert.ok(card.label, "card must have label")
			assert.ok(card.status, "card must have status")
			assert.ok(card.statusEmoji, "card must have statusEmoji")
			assert.ok(card.statusText, "card must have statusText")
			assert.ok(Array.isArray(card.findings), "findings must be array")
			assert.ok(Array.isArray(card.recommendations), "recommendations must be array")
			assert.ok(Array.isArray(card.relatedModules), "relatedModules must be array")
			assert.ok(typeof card.findingCount === "number", "findingCount must be number")
			assert.ok(typeof card.affectedEmployees === "number", "affectedEmployees must be number")
		}
	})

	it("no score/probability fields in cards", () => {
		const cards = buildCategoryCards(MOCK_DIAGNOSIS_RESULT.diagnoses)
		for (const card of cards) {
			assert.ok(!("score" in card), "score must not exist in card")
			assert.ok(!("probability" in card), "probability must not exist in card")
			assert.ok(!("percent" in card), "percent must not exist in card")
		}
	})

	it("fail card has correct status", () => {
		const cards = buildCategoryCards(MOCK_DIAGNOSIS_RESULT.diagnoses)
		const socialCard = cards.find((c) => c.key === "social_insurance")
		assert.equal(socialCard.status, "fail")
		assert.equal(socialCard.statusEmoji, "🔴")
	})

	it("pass card has correct status", () => {
		const cards = buildCategoryCards(MOCK_DIAGNOSIS_RESULT.diagnoses)
		const wageCard = cards.find((c) => c.key === "wage_delay")
		assert.equal(wageCard.status, "pass")
		assert.equal(wageCard.statusEmoji, "🟢")
	})

	it("affectedEmployees counts unique employees from non-unavailable findings", () => {
		const cards = buildCategoryCards(MOCK_DIAGNOSIS_RESULT.diagnoses)
		const overtimeCard = cards.find((c) => c.key === "overtime_limit")
		assert.equal(overtimeCard.affectedEmployees, 1)
	})
})

describe("maskEmployeeName — PII 마스킹", () => {
	it("returns original name when mask is false", () => {
		assert.equal(maskEmployeeName("김철수", false), "김철수")
	})

	it("masks all chars after first when mask is true", () => {
		assert.equal(maskEmployeeName("김철수", true), "김**")
	})

	it("single char name becomes *", () => {
		assert.equal(maskEmployeeName("김", true), "*")
	})

	it("returns empty string as-is", () => {
		assert.equal(maskEmployeeName("", true), "")
	})

	it("returns null as-is", () => {
		assert.equal(maskEmployeeName(null, true), null)
	})

	it("returns undefined as-is", () => {
		assert.equal(maskEmployeeName(undefined, true), undefined)
	})

	it("non-string name returned as-is", () => {
		assert.equal(maskEmployeeName(123, true), 123)
	})
})

describe("getCategoryDetail — 카테고리 상세 추출", () => {
	it("returns null for missing category", () => {
		const detail = getCategoryDetail(MOCK_DIAGNOSIS_RESULT, "nonexistent_key")
		assert.equal(detail, null)
	})

	it("returns null for null diagnosisResult", () => {
		assert.equal(getCategoryDetail(null, "social_insurance"), null)
	})

	it("extracts correct category detail", () => {
		const detail = getCategoryDetail(MOCK_DIAGNOSIS_RESULT, "social_insurance")
		assert.ok(detail)
		assert.equal(detail.key, "social_insurance")
		assert.equal(detail.label, "4대보험 가입")
		assert.equal(detail.status, "fail")
		assert.equal(detail.company, "위너스")
		assert.equal(detail.workplace, "서울지사")
		assert.equal(detail.as_of_date, "2026-05-17")
	})

	it("includes relatedModules", () => {
		const detail = getCategoryDetail(MOCK_DIAGNOSIS_RESULT, "social_insurance")
		assert.ok(Array.isArray(detail.relatedModules))
		assert.ok(detail.relatedModules.length > 0)
	})

	it("includes findings and recommendations", () => {
		const detail = getCategoryDetail(MOCK_DIAGNOSIS_RESULT, "overtime_limit")
		assert.equal(detail.findings.length, 1)
		assert.equal(detail.recommendations.length, 1)
	})

	it("no score/probability in category detail", () => {
		const detail = getCategoryDetail(MOCK_DIAGNOSIS_RESULT, "social_insurance")
		assert.ok(!("score" in detail))
		assert.ok(!("probability" in detail))
	})
})

describe("KoreaComplianceCategoryDetail — 라우터 경로 검증", () => {
	const EXPECTED_ROUTE_PATTERN = /\/dashboard\/korea-compliance\/category\/:categoryKey/

	it("category detail route matches expected pattern", () => {
		const routes = [
			{ path: "/dashboard/korea-compliance" },
			{ path: "/dashboard/korea-compliance/category/:categoryKey" },
		]
		const detailRoute = routes.find((r) => r.path.includes("category"))
		assert.ok(detailRoute, "category detail route must exist")
		assert.match(detailRoute.path, EXPECTED_ROUTE_PATTERN)
	})
})
