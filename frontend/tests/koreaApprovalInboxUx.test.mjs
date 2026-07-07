/**
 * koreaApprovalInboxUx.test.mjs — 데스크톱 리뷰 이슈 3
 * 마감 센터 ↔ 결재함 "0건" 혼란 UX 검증.
 *
 * 설계: 마감 draft의 결재자는 지정 결재자 한 명 — 다른 계정의 결재함이
 * 0건인 것은 정상. 이를 화면 카피로 설명한다.
 *
 * 실행: node frontend/tests/koreaApprovalInboxUx.test.mjs
 */
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

// 주의: koreaApprovalInboxRuntime.js는 frappe-ui(createResource)에 의존하므로
// node 직접 import 불가 — 소스 검증 방식 사용 (koreaComplianceRuntime.test.mjs와 동일 사유).

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, "..")

// ──────────────────────────────────────────────────────────────────
// 1. 마감 센터 — CTA 근처 결재자 명시
// ──────────────────────────────────────────────────────────────────
{
	const source = await readFile(resolve(frontendRoot, "src/views/KoreaPayrollClosing.vue"), "utf8")
	assert.match(source, /결재함에서 확정 진행/, "결재함 CTA 유지")
	assert.match(source, /결재자:/, "CTA 근처 결재자 라벨")
	assert.match(source, /지정 결재자/, "approver 없을 때 '지정 결재자' 폴백")
	assert.match(source, /selectedSession\.approver/, "세션 payload approver 필드 바인딩")
}

// ──────────────────────────────────────────────────────────────────
// 2. 결재함 — 빈 상태 카피 + 타 결재자 대기 보조 문구
// ──────────────────────────────────────────────────────────────────
{
	const source = await readFile(resolve(frontendRoot, "src/views/KoreaApprovalInbox.vue"), "utf8")
	assert.match(source, /내게 배정된 결재가 없습니다/, "빈 상태: 내게 배정 없음 카피")
	assert.match(source, /다른 결재자에게 배정된 대기/, "HR Manager 보조 문구")
	assert.match(source, /useIsAdmin/, "HR Manager 한정 노출 게이트")
	assert.match(source, /fetchPendingCountForOthers/, "read-only 카운트 API 사용")
}

// ──────────────────────────────────────────────────────────────────
// 3. 런타임 — fetchPendingCountForOthers: 실패 시 null (빈 상태 UX 비차단) + 계약 앵커
// ──────────────────────────────────────────────────────────────────
{
	const runtimeSource = await readFile(resolve(frontendRoot, "src/data/koreaApprovalInboxRuntime.js"), "utf8")
	assert.match(runtimeSource, /export async function fetchPendingCountForOthers/, "함수 export")
	assert.match(
		runtimeSource,
		/hrms\.regional\.south_korea\.approval_inbox_api\.count_pending_for_others/,
		"서버 whitelisted 함수 경로"
	)
	assert.match(runtimeSource, /return null/, "실패 시 null 반환 (보조 문구는 조용히 생략)")
}

console.log("✓ koreaApprovalInboxUx.test.mjs: 모든 테스트 통과")
