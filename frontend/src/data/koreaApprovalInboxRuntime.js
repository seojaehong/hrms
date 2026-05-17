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
