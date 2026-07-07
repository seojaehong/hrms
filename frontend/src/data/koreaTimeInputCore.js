/**
 * koreaTimeInputCore.js — F1 근무시간 제출 순수 로직 (framework-free)
 *
 * 행 검증(0~400 시간 범위)과 합계 계산만 담당한다.
 * frappe-ui 의존이 없어 node --test로 직접 단위 테스트 가능하다.
 * 서버 계약: hrms/regional/south_korea/payroll_time_input_api.py
 */

export const KOREA_TIME_INPUT_MAX_HOURS = 400

export const KOREA_TIME_INPUT_HOUR_FIELDS = [
	"overtime_hours",
	"night_hours",
	"holiday_hours",
	"part_time_hours",
]

export const KOREA_TIME_INPUT_FIELD_LABELS = {
	overtime_hours: "초과",
	night_hours: "야간",
	holiday_hours: "휴일",
	part_time_hours: "파트",
}

/** 시간 입력값 정규화: 빈 값 → 0, 숫자 문자열 → number, 그 외 → null(invalid) */
export function normalizeHoursValue(value) {
	if (value === null || value === undefined || value === "") return 0
	if (typeof value === "boolean") return null
	const number = Number(value)
	if (Number.isNaN(number)) return null
	if (number < 0 || number > KOREA_TIME_INPUT_MAX_HOURS) return null
	return number
}

/** 단일 행 검증 → { valid, errors: [{ field, message }] } */
export function validateTimeInputRow(row) {
	const errors = []
	if (!row || typeof row !== "object") {
		return { valid: false, errors: [{ field: null, message: "행이 비어 있습니다." }] }
	}
	if (typeof row.employee !== "string" || !row.employee.trim()) {
		errors.push({ field: "employee", message: "직원이 지정되지 않았습니다." })
	}
	for (const field of KOREA_TIME_INPUT_HOUR_FIELDS) {
		if (normalizeHoursValue(row[field]) === null) {
			errors.push({
				field,
				message: `${KOREA_TIME_INPUT_FIELD_LABELS[field]} 시간은 0~${KOREA_TIME_INPUT_MAX_HOURS} 사이 숫자여야 합니다.`,
			})
		}
	}
	return { valid: errors.length === 0, errors }
}

/** 전 행 검증 → { valid, errors: [{ employee, field, message }] } */
export function validateTimeInputRows(rows) {
	if (!Array.isArray(rows)) {
		return { valid: false, errors: [{ employee: null, field: null, message: "행 목록이 아닙니다." }] }
	}
	const errors = []
	for (const row of rows) {
		const result = validateTimeInputRow(row)
		for (const error of result.errors) {
			errors.push({ employee: row?.employee ?? null, ...error })
		}
	}
	return { valid: errors.length === 0, errors }
}

/** 항목별 합계 (invalid 값은 0으로 취급) */
export function sumTimeInputRows(rows) {
	const totals = Object.fromEntries(KOREA_TIME_INPUT_HOUR_FIELDS.map((field) => [field, 0]))
	if (!Array.isArray(rows)) return totals
	for (const row of rows) {
		for (const field of KOREA_TIME_INPUT_HOUR_FIELDS) {
			const value = normalizeHoursValue(row?.[field])
			if (value !== null) totals[field] = Math.round((totals[field] + value) * 100) / 100
		}
	}
	return totals
}

/** 저장 payload 행 구성 (검증 통과를 전제로 정규화) */
export function buildSaveRows(rows) {
	return (rows || []).map((row) => ({
		employee: row.employee,
		...Object.fromEntries(
			KOREA_TIME_INPUT_HOUR_FIELDS.map((field) => [field, normalizeHoursValue(row[field]) ?? 0])
		),
		note: (row.note || "").trim(),
	}))
}

/** 'YYYY-MM' 포맷 검증 */
export function isValidPeriod(period) {
	return typeof period === "string" && /^\d{4}-(0[1-9]|1[0-2])$/.test(period)
}

/** 현재 월을 'YYYY-MM'으로 */
export function currentPeriod(date = new Date()) {
	const month = String(date.getMonth() + 1).padStart(2, "0")
	return `${date.getFullYear()}-${month}`
}
