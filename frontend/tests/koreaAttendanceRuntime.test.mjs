/**
 * koreaAttendanceRuntime.test.mjs — Wave 3-B 단위 테스트
 *
 * Node.js 내장 assert 모듈로 실행 (추가 번들러 불필요).
 * 실행: node frontend/tests/koreaAttendanceRuntime.test.mjs
 *
 * 테스트 범주:
 *  1. isFrappeRuntimeAvailable — 런타임 감지
 *  2. fetchKoreaAttendanceSummary — preview path + fixture fallback
 *  3. fetchKoreaPremiumPreview — 가산수당 미리보기
 *  4. applyKoreaAttendanceClosing — human_approved 경계 검증
 *  5. assertKoreaAttendanceSummary — 계약 검증
 *  6. 헬퍼 함수 — extractEmployeeSummary, formatAttendanceRatio, isWeeklyOvertimeExceeded
 *  7. 라우터 파일 — KoreaAttendanceDashboard 경로 등록 확인
 *  8. Vue 화면 — 주요 라벨/바인딩 포함 확인
 */

import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import {
	isFrappeRuntimeAvailable,
	fetchKoreaAttendanceSummary,
	fetchKoreaPremiumPreview,
	applyKoreaAttendanceClosing,
	assertKoreaAttendanceSummary,
	extractEmployeeSummary,
	formatAttendanceRatio,
	isWeeklyOvertimeExceeded,
	KOREA_ATTENDANCE_FIXTURE,
	KOREA_PREMIUM_FIXTURE,
	KOREA_ATTENDANCE_PREVIEW_METHOD,
	KOREA_ATTENDANCE_APPLY_METHOD,
	KOREA_WEEKLY_AGGREGATE_METHOD,
} from "../src/data/koreaAttendanceRuntime.js"

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, "..")

// ──────────────────────────────────────────────────────────────────
// 1. isFrappeRuntimeAvailable
// ──────────────────────────────────────────────────────────────────
assert.equal(isFrappeRuntimeAvailable({}), false, "빈 객체: false")
assert.equal(isFrappeRuntimeAvailable({ frappe: {} }), false, "frappe.call 없음: false")
assert.equal(isFrappeRuntimeAvailable({ frappe: { call: () => {} } }), true, "frappe.call 있음: true")
assert.equal(isFrappeRuntimeAvailable(undefined), false, "undefined window: false")

// ──────────────────────────────────────────────────────────────────
// 2. fetchKoreaAttendanceSummary
// ──────────────────────────────────────────────────────────────────

// 2-a. Frappe 없음 → 픽스처 반환
{
	const result = await fetchKoreaAttendanceSummary({
		employee: "EMP-001",
		periodStart: "2026-05-01",
		periodEnd: "2026-05-31",
		win: {},
	})
	assert.equal(result.source, "fixture", "Frappe 없음: source=fixture")
	assert.equal(result.data.contract_type, "korea_attendance_closing_preview_v1")
	assert.match(result.error, /런타임을 사용할 수 없습니다/)
}

// 2-b. Frappe 있음 + 성공 응답
{
	const calls = []
	const win = {
		frappe: {
			call: async (payload) => {
				calls.push(payload)
				return {
					message: {
						contract_type: "korea_attendance_closing_preview_v1",
						runtime_action: "preview_only",
						requires_runtime_apply: true,
						snapshot: {
							workplace: "서울 본점",
							period_start: "2026-05-01",
							period_end: "2026-05-31",
							summary_by_employee: [
								{
									employee: "EMP-001",
									employee_name: "김근로",
									present_days: 20,
									absent_days: 0,
									leave_days: 1,
									half_day_count: 0,
									closing_days: 22,
									attendance_ratio: 0.95,
									total_regular_hours: 160,
									total_overtime_hours: 6,
									total_night_hours: 2,
									total_holiday_hours: 8,
									weekly_overtime_exceeded: false,
								},
							],
							blocking_messages: [],
						},
					},
				}
			},
		},
	}

	const result = await fetchKoreaAttendanceSummary({
		employee: "EMP-001",
		periodStart: "2026-05-01",
		periodEnd: "2026-05-31",
		win,
	})
	assert.equal(result.source, "runtime", "성공 응답: source=runtime")
	assert.equal(calls.length, 1, "API 호출 1회")
	assert.equal(calls[0].method, KOREA_ATTENDANCE_PREVIEW_METHOD, "올바른 메서드 이름")
	assert.equal(calls[0].args.period_start, "2026-05-01")
	assert.equal(calls[0].args.period_end, "2026-05-31")
	assert.equal(result.error, "")
	assert.equal(result.data.snapshot.summary_by_employee[0].employee, "EMP-001")
}

// 2-c. API 호출 실패 → 픽스처 폴백
{
	const win = {
		frappe: {
			call: async () => { throw new Error("Network error") },
		},
	}
	const result = await fetchKoreaAttendanceSummary({
		employee: "EMP-001",
		periodStart: "2026-05-01",
		periodEnd: "2026-05-31",
		win,
	})
	assert.equal(result.source, "fixture", "API 실패: source=fixture")
	assert.match(result.error, /API 호출 실패/)
	assert.match(result.error, /Network error/)
}

// ──────────────────────────────────────────────────────────────────
// 3. fetchKoreaPremiumPreview
// ──────────────────────────────────────────────────────────────────

// 3-a. Frappe 없음 → 픽스처 + 시급 계산
{
	const result = await fetchKoreaPremiumPreview({
		employee: "EMP-001",
		periodStart: "2026-05-01",
		periodEnd: "2026-05-31",
		hourlyRate: 10000,
		win: {},
	})
	assert.equal(result.source, "fixture")
	// 픽스처에 시급 계산이 반영되었는지
	assert.ok(result.data.total_premium, "total_premium 필드 있음")
}

// 3-b. hourlyRate = 0 → 즉시 픽스처 반환 (오류 없음)
{
	const win = { frappe: { call: async () => ({}) } }
	const result = await fetchKoreaPremiumPreview({
		employee: "EMP-001",
		periodStart: "2026-05-01",
		periodEnd: "2026-05-31",
		hourlyRate: 0,
		win,
	})
	assert.equal(result.data, KOREA_PREMIUM_FIXTURE)
	assert.equal(result.error, "")
}

// 3-c. 성공 응답
{
	const calls = []
	const win = {
		frappe: {
			call: async (payload) => {
				calls.push(payload)
				return {
					message: {
						week_start: "2026-05-12",
						week_end: "2026-05-16",
						total_overtime_hours: 6,
						weekly_overtime_limit_exceeded: false,
						exceeded_by_hours: 0,
					},
				}
			},
		},
	}
	const result = await fetchKoreaPremiumPreview({
		employee: "EMP-001",
		periodStart: "2026-05-01",
		periodEnd: "2026-05-31",
		hourlyRate: 12000,
		win,
	})
	assert.equal(result.source, "runtime")
	assert.equal(calls[0].method, KOREA_WEEKLY_AGGREGATE_METHOD)
}

// ──────────────────────────────────────────────────────────────────
// 4. applyKoreaAttendanceClosing — human_approved 경계
// ──────────────────────────────────────────────────────────────────

// 4-a. human_approved=false → fail-closed (즉시 반환, API 호출 없음)
{
	const calls = []
	const win = {
		frappe: {
			call: async (payload) => {
				calls.push(payload)
				return { message: { applied: true } }
			},
		},
	}
	const result = await applyKoreaAttendanceClosing({
		snapshot: { workplace: "test" },
		humanApproved: false,
		win,
	})
	assert.equal(calls.length, 0, "human_approved=false: API 호출 없음")
	assert.equal(result.data.applied, false, "human_approved=false: applied=false")
	assert.equal(result.source, "guard")
	assert.match(result.error, /승인/)
}

// 4-b. human_approved=true, Frappe 없음
{
	const result = await applyKoreaAttendanceClosing({
		snapshot: { workplace: "test" },
		humanApproved: true,
		win: {},
	})
	assert.equal(result.source, "fixture")
	assert.equal(result.data.applied, false)
}

// 4-c. human_approved=true, 성공
{
	const calls = []
	const win = {
		frappe: {
			call: async (payload) => {
				calls.push(payload)
				return {
					message: {
						contract_type: "korea_attendance_closing_runtime_apply_v1",
						applied: true,
						apply_actor: "hr_manager",
					},
				}
			},
		},
	}
	const result = await applyKoreaAttendanceClosing({
		snapshot: { workplace: "서울 본점", period_start: "2026-05-01", period_end: "2026-05-31" },
		humanApproved: true,
		actor: "manager@winhr.co.kr",
		win,
	})
	assert.equal(result.source, "runtime")
	assert.equal(calls.length, 1, "API 호출 1회")
	assert.equal(calls[0].method, KOREA_ATTENDANCE_APPLY_METHOD)
	assert.equal(calls[0].args.human_approved, true)
	assert.equal(calls[0].args.apply_actor, "manager@winhr.co.kr")
	assert.equal(result.data.applied, true)
}

// 4-d. human_approved=true, API 오류
{
	const win = {
		frappe: {
			call: async () => { throw new Error("Server error") },
		},
	}
	const result = await applyKoreaAttendanceClosing({
		snapshot: {},
		humanApproved: true,
		win,
	})
	assert.equal(result.source, "error")
	assert.equal(result.data.applied, false)
	assert.match(result.error, /마감 적용 실패/)
}

// 4-e. human_approved 타입 강건성 — 문자열 falsy
{
	const calls = []
	const win = { frappe: { call: async (p) => { calls.push(p); return {} } } }
	const result = await applyKoreaAttendanceClosing({
		snapshot: {},
		humanApproved: "",
		win,
	})
	assert.equal(calls.length, 0, "human_approved='': API 호출 없음")
	assert.equal(result.source, "guard")
}

// ──────────────────────────────────────────────────────────────────
// 5. assertKoreaAttendanceSummary 계약 검증
// ──────────────────────────────────────────────────────────────────
assert.doesNotThrow(() =>
	assertKoreaAttendanceSummary({
		contract_type: "korea_attendance_closing_preview_v1",
		runtime_action: "preview_only",
		requires_runtime_apply: true,
		snapshot: {},
	})
)

assert.throws(
	() => assertKoreaAttendanceSummary(null),
	/객체가 아닙니다/
)

assert.throws(
	() => assertKoreaAttendanceSummary({ contract_type: "wrong_contract", runtime_action: "preview_only", requires_runtime_apply: true }),
	/contract_type/
)

assert.throws(
	() => assertKoreaAttendanceSummary({ contract_type: "korea_attendance_closing_preview_v1", runtime_action: "save", requires_runtime_apply: true }),
	/runtime_action/
)

assert.throws(
	() => assertKoreaAttendanceSummary({ contract_type: "korea_attendance_closing_preview_v1", runtime_action: "preview_only", requires_runtime_apply: false }),
	/requires_runtime_apply/
)

// ──────────────────────────────────────────────────────────────────
// 6. 헬퍼 함수
// ──────────────────────────────────────────────────────────────────

// extractEmployeeSummary
{
	const data = {
		snapshot: {
			summary_by_employee: [
				{ employee: "EMP-001", present_days: 20 },
				{ employee: "EMP-002", present_days: 15 },
			],
		},
	}
	const row = extractEmployeeSummary(data, "EMP-002")
	assert.equal(row.employee, "EMP-002")
	assert.equal(row.present_days, 15)

	// 없는 직원 → 첫 번째 row 반환
	const fallback = extractEmployeeSummary(data, "EMP-999")
	assert.equal(fallback.employee, "EMP-001")

	// null 데이터
	assert.equal(extractEmployeeSummary(null, "EMP-001"), null)
}

// formatAttendanceRatio
assert.equal(formatAttendanceRatio(0.95), "95%")
assert.equal(formatAttendanceRatio(0.8), "80%")
assert.equal(formatAttendanceRatio(0.786), "79%")
assert.equal(formatAttendanceRatio(null), "—")
assert.equal(formatAttendanceRatio(undefined), "—")

// isWeeklyOvertimeExceeded
assert.equal(isWeeklyOvertimeExceeded(12), false, "12h: 한도 이내")
assert.equal(isWeeklyOvertimeExceeded(12.1), true, "12.1h: 한도 초과")
assert.equal(isWeeklyOvertimeExceeded(0), false, "0h: 한도 이내")
assert.equal(isWeeklyOvertimeExceeded(20), true, "20h: 한도 초과")

// ──────────────────────────────────────────────────────────────────
// 7. 라우터 파일 — KoreaAttendanceDashboard 경로 등록 확인
// ──────────────────────────────────────────────────────────────────
{
	const routerSource = await readFile(resolve(frontendRoot, "src/router/index.js"), "utf8")
	assert.match(routerSource, /\/dashboard\/korea-attendance/, "경로 등록됨")
	assert.match(routerSource, /KoreaAttendanceDashboard/, "라우트 이름 등록됨")
	assert.match(routerSource, /KoreaAttendanceDashboard\.vue/, "컴포넌트 lazy import")
}

// ──────────────────────────────────────────────────────────────────
// 8. Vue 화면 — 주요 요소 포함 확인
// ──────────────────────────────────────────────────────────────────
{
	const viewSource = await readFile(resolve(frontendRoot, "src/views/KoreaAttendanceDashboard.vue"), "utf8")

	// 한국어 라벨
	assert.match(viewSource, /출근 요약/, "Card 1: 출근 요약")
	assert.match(viewSource, /출근률/, "출근률 표시")
	assert.match(viewSource, /연장·야간·휴일/, "Card 2: 연장/야간/휴일")
	assert.match(viewSource, /가산수당/, "Card 3: 가산수당")
	assert.match(viewSource, /통상시급/, "통상시급 입력")
	assert.match(viewSource, /마감 상태/, "Card 4: 마감 상태")

	// 법령 참고
	assert.match(viewSource, /근기법 53조/, "근기법 53조 경고 포함")
	assert.match(viewSource, /근기법 56조/, "근기법 56조 라벨 포함")
	assert.match(viewSource, /근기법 60조/, "근기법 60조 라벨 포함")

	// 데이터 바인딩
	assert.match(viewSource, /fetchKoreaAttendanceSummary/, "runtime 함수 import")
	assert.match(viewSource, /fetchKoreaPremiumPreview/, "premium runtime 함수 import")
	assert.match(viewSource, /applyKoreaAttendanceClosing/, "apply 함수 import")
	assert.match(viewSource, /humanApproved/, "human_approved 확인 dialog")
	assert.match(viewSource, /showApplyDialog/, "적용 dialog 상태")

	// 80% 룰 경고
	assert.match(viewSource, /80% 미달/, "80% 미달 경고")
	assert.match(viewSource, /연차 감액 위험/, "연차 감액 위험 메시지")

	// 주 12h 초과 경고
	assert.match(viewSource, /주 12h 초과/, "주 12h 초과 경고")
	assert.match(viewSource, /근기법 53조 위반 위험/, "53조 위반 경고")

	// 뮤테이션 경계 안내
	assert.match(viewSource, /draft_only_no_submit_no_approve_no_send/, "뮤테이션 경계 상수")
	assert.match(viewSource, /Draft/, "Draft 저장 안내")
	assert.match(viewSource, /픽스처/, "픽스처 폴백 배너")
}

// ──────────────────────────────────────────────────────────────────
// 완료
// ──────────────────────────────────────────────────────────────────
console.log("✓ koreaAttendanceRuntime.test.mjs: 모든 테스트 통과")
