/**
 * koreaApprovalInboxRuntime.js
 * 결재 인박스 런타임 — 백엔드 API 호출 래퍼.
 *
 * createResource 패턴 대신 명령형 함수를 사용해
 * 승인/반려 후 목록을 즉시 갱신할 수 있도록 합니다.
 */
import { createResource } from "frappe-ui"

// ---------------------------------------------------------------------------
// 결재 대기 목록
// ---------------------------------------------------------------------------

/**
 * 결재 대기 항목을 서버에서 가져옵니다.
 * @param {string|null} asOfDate - YYYY-MM-DD, 기본값: 오늘
 * @returns {Promise<Array>}
 */
export async function fetchPendingApprovals(asOfDate = null) {
	const params = {}
	if (asOfDate) params.as_of_date = asOfDate

	const resource = createResource({
		url: "hrms.regional.south_korea.approval_inbox_api.get_pending_approvals",
		params,
		auto: false,
	})
	await resource.fetch()
	if (resource.error) {
		throw resource.error
	}
	return resource.data ?? []
}

// ---------------------------------------------------------------------------
// 타 결재자 대기 카운트 (read-only, HR Manager 한정)
// ---------------------------------------------------------------------------

/**
 * 다른 결재자에게 배정된 결재 대기 건수를 가져옵니다.
 * 빈 결재함의 "다른 결재자에게 배정된 대기 N건" 보조 문구용.
 * 실패(권한 없음/서버 미지원 등) 시 null을 반환해 빈 상태 UX를 막지 않습니다.
 *
 * @param {string|null} asOfDate - YYYY-MM-DD, 기본값: 오늘
 * @returns {Promise<{total: number, by_doctype: Object}|null>}
 */
export async function fetchPendingCountForOthers(asOfDate = null) {
	const params = {}
	if (asOfDate) params.as_of_date = asOfDate

	const resource = createResource({
		url: "hrms.regional.south_korea.approval_inbox_api.count_pending_for_others",
		params,
		auto: false,
	})
	try {
		await resource.fetch()
	} catch (_) {
		return null
	}
	if (resource.error || !resource.data || typeof resource.data.total !== "number") {
		return null
	}
	return resource.data
}

// ---------------------------------------------------------------------------
// 승인
// ---------------------------------------------------------------------------

/**
 * 결재 항목을 승인합니다.
 * @param {{ doctype: string, name: string, comment?: string }} options
 * @returns {Promise<object>}
 */
export async function approveItem({ doctype, name, comment = "" }) {
	if (!doctype || !name) {
		throw new Error("doctype과 name은 필수입니다.")
	}
	const resource = createResource({
		url: "hrms.regional.south_korea.approval_inbox_api.approve_inbox_item",
		params: { doctype, name, comment: comment || null },
		auto: false,
	})
	await resource.fetch()
	if (resource.error) {
		throw resource.error
	}
	return resource.data
}

// ---------------------------------------------------------------------------
// 반려
// ---------------------------------------------------------------------------

/**
 * 결재 항목을 반려합니다.
 * @param {{ doctype: string, name: string, comment?: string }} options
 * @returns {Promise<object>}
 */
export async function rejectItem({ doctype, name, comment = "" }) {
	if (!doctype || !name) {
		throw new Error("doctype과 name은 필수입니다.")
	}
	const resource = createResource({
		url: "hrms.regional.south_korea.approval_inbox_api.reject_inbox_item",
		params: { doctype, name, comment: comment || null },
		auto: false,
	})
	await resource.fetch()
	if (resource.error) {
		throw resource.error
	}
	return resource.data
}
