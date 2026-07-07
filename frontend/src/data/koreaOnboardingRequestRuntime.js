/**
 * 입사자 등록 요청 런타임 데이터 — F2.
 * backend: hrms.regional.south_korea.onboarding_request_api
 *
 * 설계 원칙:
 * - 주민번호(rrn)는 제출 payload에만 담고, 화면/목록에는 서버가 주는 masked_rrn만 표시.
 * - 이 모듈은 framework-free (frappe-ui import 없음) — node --test에서 직접 import 가능.
 */

export const CREATE_URL =
	"hrms.regional.south_korea.onboarding_request_api.create_onboarding_request"

export const LIST_URL =
	"hrms.regional.south_korea.onboarding_request_api.list_onboarding_requests"

export const PROCESS_URL =
	"hrms.regional.south_korea.onboarding_request_api.mark_onboarding_processed"

export const CONTRACT_TYPES = ["정규직", "계약직", "파트타임", "일용직"]

/** status 배지 표시 설정 */
export const STATUS_BADGES = {
	requested: { text: "대기", textClass: "text-yellow-700", badgeClass: "bg-yellow-50" },
	processing: { text: "처리중", textClass: "text-blue-700", badgeClass: "bg-blue-50" },
	completed: { text: "완료", textClass: "text-green-700", badgeClass: "bg-green-50" },
	rejected: { text: "반려", textClass: "text-red-700", badgeClass: "bg-red-50" },
}

export function statusBadge(status) {
	return STATUS_BADGES[status] ?? { text: status ?? "-", textClass: "text-gray-700", badgeClass: "bg-gray-50" }
}

/** 주민번호 클라이언트 사전 점검 — 하이픈 제거 후 13자리 숫자 + 성별코드 1-8 */
export function normalizeRrnInput(raw) {
	return String(raw ?? "").replace(/-/g, "").replace(/\s+/g, "").trim()
}

export function isRrnShapeValid(raw) {
	const rrn = normalizeRrnInput(raw)
	if (!/^\d{13}$/.test(rrn)) return false
	const month = Number(rrn.slice(2, 4))
	const day = Number(rrn.slice(4, 6))
	if (month < 1 || month > 12) return false
	if (day < 1 || day > 31) return false
	return "12345678".includes(rrn[6])
}

/**
 * 폼 검증 — 필수 5필드 + rrn 형식.
 * @returns {{ valid: boolean, errors: Object }}
 */
export function validateOnboardingForm(form) {
	const errors = {}
	if (!form?.company) errors.company = "사업장(취득사업장)을 선택하세요."
	if (!form?.full_name?.trim()) errors.full_name = "이름을 입력하세요."
	if (!form?.rrn) {
		errors.rrn = "주민등록번호를 입력하세요."
	} else if (!isRrnShapeValid(form.rrn)) {
		errors.rrn = "주민등록번호 형식이 올바르지 않습니다 (13자리, 하이픈 허용)."
	}
	if (!form?.join_date) errors.join_date = "입사일을 선택하세요."
	if (!(Number(form?.reported_monthly_wage) > 0)) {
		errors.reported_monthly_wage = "신고보수(비과세 제외 월 보수)를 입력하세요."
	}
	if (!CONTRACT_TYPES.includes(form?.contract_type)) {
		errors.contract_type = "계약형태를 선택하세요."
	}
	return { valid: Object.keys(errors).length === 0, errors }
}

/** 제출 payload 생성 — rrn은 정규화(하이픈 제거)해서만 담는다. */
export function makeCreatePayload(form) {
	return {
		company: form.company,
		full_name: form.full_name?.trim(),
		rrn: normalizeRrnInput(form.rrn),
		join_date: form.join_date,
		reported_monthly_wage: Number(form.reported_monthly_wage),
		contract_type: form.contract_type,
		phone: form.phone?.trim() || "",
		note: form.note?.trim() || "",
	}
}

/** 원화 표시 */
export function formatWage(value) {
	const n = Number(value)
	if (!Number.isFinite(n)) return "-"
	return `${n.toLocaleString("ko-KR")}원`
}
