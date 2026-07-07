/**
 * F3 요청 보드 런타임 데이터 — Korea Service Request.
 * backend: hrms.regional.south_korea.service_request_api
 *
 * 설계 원칙:
 * - framework-free (frappe-ui import 없음) — node --test에서 직접 import 가능.
 *   createResource 3종은 화면(KoreaServiceRequests.vue)에서 이 URL 상수로 생성한다.
 */

export const CREATE_URL =
	"hrms.regional.south_korea.service_request_api.create_service_request"

export const LIST_URL =
	"hrms.regional.south_korea.service_request_api.list_service_requests"

export const UPDATE_URL =
	"hrms.regional.south_korea.service_request_api.update_service_request_status"

/** 분류 — service_request_api.CATEGORIES 와 동일 순서. */
export const CATEGORIES = ["급여", "4대보험", "증명서", "연차·근태", "기타"]

/** 상태 — service_request_api.REQUEST_STATUSES 와 동일. */
export const REQUEST_STATUSES = ["접수", "처리중", "완료", "보류"]

/**
 * 상태 전이 규칙 — 백엔드 _ALLOWED_TRANSITIONS 미러.
 * 완료는 종결(재오픈 불가).
 */
export const ALLOWED_TRANSITIONS = {
	접수: ["처리중", "완료", "보류"],
	처리중: ["완료", "보류", "접수"],
	보류: ["처리중", "완료", "접수"],
	완료: [],
}

/** status 배지 표시 설정 — 접수=회색 / 처리중=노랑 / 완료=초록 / 보류=주황. */
export const STATUS_BADGES = {
	접수: { text: "접수", textClass: "text-gray-700", badgeClass: "bg-gray-100" },
	처리중: { text: "처리중", textClass: "text-yellow-700", badgeClass: "bg-yellow-50" },
	완료: { text: "완료", textClass: "text-green-700", badgeClass: "bg-green-50" },
	보류: { text: "보류", textClass: "text-orange-700", badgeClass: "bg-orange-50" },
}

export function statusBadge(status) {
	return (
		STATUS_BADGES[status] ?? {
			text: status ?? "-",
			textClass: "text-gray-700",
			badgeClass: "bg-gray-50",
		}
	)
}

/** 현재 상태에서 전이 가능한 다음 상태 목록(빈 배열 = 종결). */
export function nextStatusOptions(current) {
	return ALLOWED_TRANSITIONS[current] ?? []
}

/**
 * 새 요청 폼 검증 — 제목 필수 + 분류 유효.
 * @returns {{ valid: boolean, errors: Object }}
 */
export function validateRequestForm(form) {
	const errors = {}
	if (!form?.title?.trim()) errors.title = "제목을 입력하세요."
	if (!CATEGORIES.includes(form?.category)) {
		errors.category = "분류를 선택하세요."
	}
	return { valid: Object.keys(errors).length === 0, errors }
}

/** 제출 payload 생성 — 공백 트림, 선택 필드 기본값. */
export function makeCreatePayload(form) {
	return {
		company: form?.company?.trim() || "",
		title: form?.title?.trim(),
		category: form?.category,
		detail: form?.detail?.trim() || "",
	}
}
