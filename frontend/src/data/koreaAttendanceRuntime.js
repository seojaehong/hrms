/**
 * koreaAttendanceRuntime.js — Korea 근태/가산수당 PWA 런타임 데이터 레이어
 *
 * Wave 3-B: 직원 본인의 출근/연장/야간/휴일 현황 + 가산수당 미리보기 화면용.
 *
 * # 백엔드 API 의존성 (Wave 1/2-B에서 구현됨, 이 브랜치에는 미병합)
 *   - preview  : hrms.regional.south_korea.attendance_closing_api.preview_korea_attendance_closing
 *   - apply    : hrms.regional.south_korea.attendance_closing_apply_api.apply_korea_attendance_closing_api
 *   - premium  : hrms.regional.south_korea.overtime_premium_api.estimate_overtime_pay
 *               (하루 단위) / calculate_weekly_overtime_aggregate (주 집계)
 *
 * # 계약 형식 (예상 응답 구조, 실제 API 배포 후 맞춰 조정)
 *   preview 응답: {
 *     contract_type: "korea_attendance_closing_preview_v1",
 *     runtime_action: "preview_only",
 *     requires_runtime_apply: true,
 *     snapshot: {
 *       workplace, period_start, period_end,
 *       summary_by_employee: [{ employee, present_days, absent_days, ... }],
 *       blocking_messages: []
 *     }
 *   }
 *
 *   apply 응답: {
 *     contract_type: "korea_attendance_closing_runtime_apply_v1",
 *     applied: bool,
 *     apply_actor: str,
 *     snapshot_workplace: str,
 *     period_start: str,
 *     period_end: str
 *   }
 *
 *   estimate_overtime_pay 응답: {
 *     daily_breakdown: { regular_hours, overtime_hours, night_hours, holiday_hours,
 *                        holiday_overtime_hours, overtime_multiplier, night_multiplier,
 *                        holiday_multiplier },
 *     pay_estimate: { base_pay, overtime_premium, night_premium, holiday_premium,
 *                     holiday_overtime_premium, total_premium, total_pay }
 *   }
 *
 * # 픽스처 폴백
 *   frappe.call을 사용할 수 없는 환경(dev, 테스트)에서는 FIXTURE가 자동 반환됩니다.
 *   production에서도 API 호출 실패 시 픽스처로 폴백하고 error 메시지를 반환합니다.
 */

// ──────────────────────────────────────────────────────────────────
// API 메서드 이름 상수 (contract anchor — 실제 Frappe 메서드명)
// ──────────────────────────────────────────────────────────────────
export const KOREA_ATTENDANCE_PREVIEW_METHOD =
	"hrms.regional.south_korea.attendance_closing_api.preview_korea_attendance_closing"

export const KOREA_ATTENDANCE_APPLY_METHOD =
	"hrms.regional.south_korea.attendance_closing_apply_api.apply_korea_attendance_closing_api"

export const KOREA_OVERTIME_ESTIMATE_METHOD =
	"hrms.regional.south_korea.overtime_premium_api.estimate_overtime_pay"

export const KOREA_WEEKLY_AGGREGATE_METHOD =
	"hrms.regional.south_korea.overtime_premium_api.calculate_weekly_overtime_aggregate"

// 근태 read-only 메서드 allowlist — frappe.call 폴리필(fallback)에서 허용되는 메서드.
// mutation(apply)은 폴리필에서 차단한다 (fail-closed).
// 다른 Korea 런타임 폴리필(연차/마감)의 allowlist에도 동일 세트가 포함된다
// (koreaAnnualLeaveRuntime.js / koreaPayrollClosingRuntime.js).
export const KOREA_ATTENDANCE_READ_ONLY_METHODS = Object.freeze([
	KOREA_ATTENDANCE_PREVIEW_METHOD,
	KOREA_OVERTIME_ESTIMATE_METHOD,
	KOREA_WEEKLY_AGGREGATE_METHOD,
])

// 픽스처 폴백 시 사용자에게 노출하는 문구 — 기술 상세는 console.warn으로만.
export const KOREA_ATTENDANCE_FALLBACK_NOTICE = "실데이터 연결 대기 — 예시 데이터를 표시합니다."

// ──────────────────────────────────────────────────────────────────
// 픽스처 데이터 (API 없을 때 fallback)
// ──────────────────────────────────────────────────────────────────
export const KOREA_ATTENDANCE_FIXTURE = {
	contract_type: "korea_attendance_closing_preview_v1",
	runtime_action: "preview_only",
	requires_runtime_apply: true,
	snapshot: {
		contract_type: "korea_attendance_closing_preview_v1",
		workplace: "(픽스처) 위너스 본점",
		period_start: "2026-05-01",
		period_end: "2026-05-31",
		summary_by_employee: [
			{
				employee: "EMP-DEMO-01",
				employee_name: "홍길동 (데모)",
				present_days: 18,
				absent_days: 1,
				leave_days: 2,
				half_day_count: 1,
				closing_days: 22,
				attendance_ratio: 0.86,
				total_regular_hours: 144.0,
				total_overtime_hours: 8.5,
				total_night_hours: 3.0,
				total_holiday_hours: 4.0,
				weekly_overtime_exceeded: false,
			},
		],
		blocking_messages: [],
	},
}

export const KOREA_PREMIUM_FIXTURE = {
	contract_type: "korea_attendance_premium_preview_fixture_v1",
	source: "fixture",
	daily: [
		{
			work_date: "2026-05-16",
			regular_hours: 8.0,
			overtime_hours: 2.0,
			night_hours: 0.5,
			holiday_hours: 0.0,
			holiday_overtime_hours: 0.0,
		},
	],
	weekly_aggregate: {
		week_start: "2026-05-12",
		week_end: "2026-05-16",
		total_overtime_hours: 8.5,
		weekly_overtime_limit_exceeded: false,
		exceeded_by_hours: 0.0,
	},
	total_premium: {
		base_pay: 0,
		overtime_premium: 0,
		night_premium: 0,
		holiday_premium: 0,
		holiday_overtime_premium: 0,
		total_premium: 0,
		total_pay: 0,
	},
}

// ──────────────────────────────────────────────────────────────────
// 런타임 감지 헬퍼
// ──────────────────────────────────────────────────────────────────
export function isFrappeRuntimeAvailable(win = globalThis.window) {
	return Boolean(win?.frappe && typeof win.frappe.call === "function")
}

/**
 * frappe.call 폴리필 설치 — window.frappe는 있으나 frappe.call이 없는
 * PWA 브라우저 환경용. read-only 근태 메서드만 허용한다.
 * (패턴: koreaAnnualLeaveRuntime.ensureKoreaAnnualLeaveFrappeCallRuntime)
 */
export function ensureKoreaAttendanceFrappeCallRuntime(win = globalThis.window) {
	if (!win?.frappe || typeof win.fetch !== "function") return false
	if (typeof win.frappe.call === "function") return true
	win.frappe.call = async ({ method, args = {} } = {}) => {
		if (typeof method !== "string" || !method.trim()) throw new Error("frappe.call method is required")
		if (!KOREA_ATTENDANCE_READ_ONLY_METHODS.includes(method)) {
			throw new Error("frappe.call fallback only allows Korea attendance read-only runtime methods")
		}
		const body = new URLSearchParams()
		for (const [key, value] of Object.entries(args || {})) {
			if (value !== undefined && value !== null) body.append(key, typeof value === "object" ? JSON.stringify(value) : String(value))
		}
		const response = await win.fetch(`/api/method/${method}`, {
			method: "POST",
			headers: {
				"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
				"X-Frappe-CSRF-Token": win.csrf_token || "",
			},
			body,
			credentials: "same-origin",
		})
		const payload = await response.json()
		if (!response.ok) throw new Error(payload?._server_messages || payload?.exc || `frappe.call failed with HTTP ${response.status}`)
		return payload
	}
	return true
}

// ──────────────────────────────────────────────────────────────────
// 3-B-2 공개 API: fetchKoreaAttendanceSummary
// ──────────────────────────────────────────────────────────────────
/**
 * 직원의 이번 달 출근 요약 (preview_korea_attendance_closing) 조회.
 *
 * @param {Object} params
 * @param {string} params.employee     - Frappe Employee doctype name
 * @param {string} params.periodStart  - YYYY-MM-DD
 * @param {string} params.periodEnd    - YYYY-MM-DD
 * @param {string} [params.workplace]  - 사업장 이름 (기본: employee.company)
 * @param {Window} [params.win]        - 테스트 주입용 window 대체
 * @returns {Promise<{ source: string, data: Object, error: string }>}
 *   source = "runtime" | "fixture"
 */
export async function fetchKoreaAttendanceSummary({
	employee,
	periodStart,
	periodEnd,
	workplace = "",
	win = globalThis.window,
} = {}) {
	ensureKoreaAttendanceFrappeCallRuntime(win)
	if (!isFrappeRuntimeAvailable(win)) {
		return { source: "fixture", data: KOREA_ATTENDANCE_FIXTURE, error: "Frappe 런타임을 사용할 수 없습니다. 픽스처 데이터를 표시합니다." }
	}

	try {
		const response = await win.frappe.call({
			method: KOREA_ATTENDANCE_PREVIEW_METHOD,
			args: {
				workplace: workplace || employee,
				period_start: periodStart,
				period_end: periodEnd,
				// records/policy는 백엔드에서 employee 필터로 처리 예정
				employee,
				records: [],
				policy: {
					attendance_cutoff_day: 25,
					standard_work_hours_per_day: 8.0,
					close_on_missing_attendance: false,
				},
			},
		})
		const data = response?.message ?? response
		assertKoreaAttendanceSummary(data)
		return { source: "runtime", data, error: "" }
	} catch (err) {
		const message = err instanceof Error ? err.message : String(err)
		// 기술 상세는 콘솔에만 — 사용자에게는 한글 요약만 노출
		console.warn(`[koreaAttendanceRuntime] 근태 요약 API 호출 실패 (픽스처 폴백): ${message}`)
		return { source: "fixture", data: KOREA_ATTENDANCE_FIXTURE, error: KOREA_ATTENDANCE_FALLBACK_NOTICE }
	}
}

// ──────────────────────────────────────────────────────────────────
// 3-B-2 공개 API: fetchKoreaPremiumPreview
// ──────────────────────────────────────────────────────────────────
/**
 * 가산수당 금액 미리보기 (통상시급 기준).
 * 복수 근무일 데이터를 주 단위로 집계합니다.
 *
 * @param {Object} params
 * @param {string} params.employee     - Frappe Employee doctype name
 * @param {string} params.periodStart  - YYYY-MM-DD
 * @param {string} params.periodEnd    - YYYY-MM-DD
 * @param {number} params.hourlyRate   - 통상시급 (원)
 * @param {Array}  [params.sessions]   - WorkSession 배열 (없으면 빈 배열)
 * @param {Window} [params.win]        - 테스트 주입용
 * @returns {Promise<{ source: string, data: Object, error: string }>}
 */
export async function fetchKoreaPremiumPreview({
	employee,
	periodStart,
	periodEnd,
	hourlyRate,
	sessions = [],
	win = globalThis.window,
} = {}) {
	ensureKoreaAttendanceFrappeCallRuntime(win)
	if (!isFrappeRuntimeAvailable(win)) {
		const fixture = _buildPremiumFixtureWithRate(hourlyRate)
		return { source: "fixture", data: fixture, error: "Frappe 런타임을 사용할 수 없습니다. 픽스처 데이터를 표시합니다." }
	}

	if (!hourlyRate || Number(hourlyRate) <= 0) {
		return { source: "fixture", data: KOREA_PREMIUM_FIXTURE, error: "" }
	}

	try {
		const response = await win.frappe.call({
			method: KOREA_WEEKLY_AGGREGATE_METHOD,
			args: {
				sessions_data: sessions.length
					? sessions
					: _buildDefaultSessionsFromPeriod(employee, periodStart, periodEnd),
			},
		})
		const data = response?.message ?? response
		// 시급이 주어진 경우 각 일별 금액 계산
		const premiumData = _enrichWithHourlyRate(data, Number(hourlyRate))
		return { source: "runtime", data: premiumData, error: "" }
	} catch (err) {
		const message = err instanceof Error ? err.message : String(err)
		console.warn(`[koreaAttendanceRuntime] 가산수당 API 호출 실패 (픽스처 폴백): ${message}`)
		const fixture = _buildPremiumFixtureWithRate(hourlyRate)
		return { source: "fixture", data: fixture, error: KOREA_ATTENDANCE_FALLBACK_NOTICE }
	}
}

// ──────────────────────────────────────────────────────────────────
// 3-B-2 공개 API: applyKoreaAttendanceClosing
// ──────────────────────────────────────────────────────────────────
/**
 * 근태 마감 적용 (mutation). human_approved=true 필수.
 *
 * # 뮤테이션 경계
 *   - .insert() / .save() 만 — .submit() / .cancel() / .approve() / send 없음
 *   - human_approved=false → fail-closed (아무 것도 저장하지 않음)
 *
 * @param {Object} params
 * @param {Object} params.snapshot       - preview 결과의 snapshot 필드
 * @param {boolean} params.humanApproved - 반드시 true여야 적용
 * @param {string} [params.actor]        - 적용자 식별자 (선택)
 * @param {Window} [params.win]          - 테스트 주입용
 * @returns {Promise<{ source: string, data: Object, error: string }>}
 *
 * # 계약 문서: apply_korea_attendance_closing_api 참고
 *   (hrms/regional/south_korea/attendance_closing_apply_api.py)
 */
export async function applyKoreaAttendanceClosing({
	snapshot,
	humanApproved,
	actor = null,
	win = globalThis.window,
} = {}) {
	// fail-closed: human_approved 없으면 즉시 반환
	if (!humanApproved) {
		return {
			source: "guard",
			data: {
				applied: false,
				reason: "human_approved가 필요합니다.",
				mutation_boundary: "draft_only_no_submit_no_approve_no_send",
			},
			error: "마감 적용을 위해 관리자 승인이 필요합니다.",
		}
	}

	if (!isFrappeRuntimeAvailable(win)) {
		return {
			source: "fixture",
			data: { applied: false, reason: "Frappe 런타임 없음 (픽스처 환경)" },
			error: "Frappe 런타임을 사용할 수 없습니다.",
		}
	}

	try {
		const response = await win.frappe.call({
			method: KOREA_ATTENDANCE_APPLY_METHOD,
			args: {
				snapshot: snapshot,
				human_approved: true,
				apply_actor: actor || null,
			},
		})
		const data = response?.message ?? response
		return { source: "runtime", data, error: "" }
	} catch (err) {
		const message = err instanceof Error ? err.message : String(err)
		return {
			source: "error",
			data: { applied: false, reason: message },
			error: `마감 적용 실패: ${message}`,
		}
	}
}

// ──────────────────────────────────────────────────────────────────
// 계약 검증
// ──────────────────────────────────────────────────────────────────
export function assertKoreaAttendanceSummary(data) {
	if (!data || typeof data !== "object") {
		throw new Error("Korea 근태 요약 응답이 객체가 아닙니다.")
	}
	if (data.contract_type !== "korea_attendance_closing_preview_v1") {
		throw new Error(`예상하지 못한 contract_type: ${data.contract_type}`)
	}
	if (data.runtime_action !== "preview_only") {
		throw new Error(`예상하지 못한 runtime_action: ${data.runtime_action}`)
	}
	if (data.requires_runtime_apply !== true) {
		throw new Error("근태 요약 미리보기는 requires_runtime_apply=true이어야 합니다.")
	}
	return data
}

// ──────────────────────────────────────────────────────────────────
// 헬퍼: 직원 요약 한 건 추출
// ──────────────────────────────────────────────────────────────────
/**
 * summary_by_employee 배열에서 직원 한 건을 추출합니다.
 * @param {Object} previewData - fetchKoreaAttendanceSummary 반환값의 data
 * @param {string} employee    - Frappe Employee name
 * @returns {Object|null}
 */
export function extractEmployeeSummary(previewData, employee) {
	const rows = previewData?.snapshot?.summary_by_employee || []
	return rows.find((row) => row.employee === employee) || rows[0] || null
}

/**
 * attendance_ratio를 퍼센트 문자열로 변환
 * @param {number} ratio
 * @returns {string}
 */
export function formatAttendanceRatio(ratio) {
	if (ratio == null) return "—"
	return `${Math.round(Number(ratio) * 100)}%`
}

/**
 * 주 12시간 초과 여부 감지 (근기법 53조)
 * @param {number} weeklyOvertimeHours
 * @returns {boolean}
 */
export function isWeeklyOvertimeExceeded(weeklyOvertimeHours) {
	return Number(weeklyOvertimeHours) > 12
}

// ──────────────────────────────────────────────────────────────────
// 내부 헬퍼
// ──────────────────────────────────────────────────────────────────
function _buildPremiumFixtureWithRate(hourlyRate) {
	const rate = Number(hourlyRate) || 0
	const regular = rate * 8
	const overtime = Math.round(rate * 1.5 * 8.5)
	const night = Math.round(rate * 0.5 * 3.0)
	const holiday = Math.round(rate * 1.5 * 4.0)
	return {
		...KOREA_PREMIUM_FIXTURE,
		total_premium: {
			base_pay: regular,
			overtime_premium: overtime - rate * 8.5,
			night_premium: night,
			holiday_premium: holiday - rate * 4,
			holiday_overtime_premium: 0,
			total_premium: overtime - rate * 8.5 + night + holiday - rate * 4,
			total_pay: regular + (overtime - rate * 8.5) + night + (holiday - rate * 4),
		},
	}
}

function _enrichWithHourlyRate(weeklyData, hourlyRate) {
	// API 응답에 시급 계산이 없으면 프론트에서 추정
	if (!weeklyData || typeof weeklyData !== "object") return KOREA_PREMIUM_FIXTURE
	const totalOT = Number(weeklyData.total_overtime_hours || 0)
	const premiumEstimate = Math.round(totalOT * hourlyRate * 0.5)
	return {
		...weeklyData,
		_hourly_rate: hourlyRate,
		_overtime_premium_estimate: premiumEstimate,
		_note: "프론트 추정치 — 정확한 계산은 백엔드 estimate_overtime_pay 호출 필요",
	}
}

function _buildDefaultSessionsFromPeriod(employee, periodStart, periodEnd) {
	// 실제 근무 세션 데이터 없을 때 빈 배열 반환
	// (백엔드에서 employee + period_start/end로 직접 조회 예정)
	return []
}
