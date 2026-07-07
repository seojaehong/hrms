/**
 * koreaTimeInput.test.mjs — F1 근무시간 제출 프론트 순수 로직 테스트
 *
 * 실행: node frontend/tests/koreaTimeInput.test.mjs
 *
 * 범주:
 *  1. normalizeHoursValue — 0~400 범위 강제
 *  2. validateTimeInputRow / validateTimeInputRows — 행 검증
 *  3. sumTimeInputRows — 합계
 *  4. buildSaveRows — 저장 payload 정규화
 *  5. isValidPeriod / currentPeriod
 *  6. 라우터/홈/뷰/런타임 파일 등록 확인 (정적 검사)
 */

import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import {
	KOREA_TIME_INPUT_MAX_HOURS,
	KOREA_TIME_INPUT_HOUR_FIELDS,
	normalizeHoursValue,
	validateTimeInputRow,
	validateTimeInputRows,
	sumTimeInputRows,
	buildSaveRows,
	isValidPeriod,
	currentPeriod,
} from "../src/data/koreaTimeInputCore.js"

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, "..")

// 1. normalizeHoursValue ─────────────────────────────────────────
assert.equal(KOREA_TIME_INPUT_MAX_HOURS, 400)
assert.deepEqual(KOREA_TIME_INPUT_HOUR_FIELDS, [
	"overtime_hours",
	"night_hours",
	"holiday_hours",
	"part_time_hours",
])
assert.equal(normalizeHoursValue(""), 0, "빈 문자열 → 0")
assert.equal(normalizeHoursValue(null), 0, "null → 0")
assert.equal(normalizeHoursValue(undefined), 0, "undefined → 0")
assert.equal(normalizeHoursValue("108.5"), 108.5, "숫자 문자열 파싱")
assert.equal(normalizeHoursValue(400), 400, "상한 400 허용")
assert.equal(normalizeHoursValue(-1), null, "음수 거부")
assert.equal(normalizeHoursValue(400.5), null, "400 초과 거부")
assert.equal(normalizeHoursValue("abc"), null, "비숫자 거부")
assert.equal(normalizeHoursValue(true), null, "boolean 거부")

// 2. 행 검증 ─────────────────────────────────────────────────────
{
	const good = validateTimeInputRow({ employee: "EMP-0001", overtime_hours: 108.5 })
	assert.equal(good.valid, true, "정상 행 통과")

	const noEmployee = validateTimeInputRow({ overtime_hours: 1 })
	assert.equal(noEmployee.valid, false)
	assert.equal(noEmployee.errors[0].field, "employee")

	const badHours = validateTimeInputRow({ employee: "EMP-0001", night_hours: -3, holiday_hours: 999 })
	assert.equal(badHours.valid, false)
	assert.deepEqual(
		badHours.errors.map((e) => e.field).sort(),
		["holiday_hours", "night_hours"],
		"범위 밖 시간 필드가 모두 보고됨"
	)

	const rowsResult = validateTimeInputRows([
		{ employee: "EMP-0001", overtime_hours: 63 },
		{ employee: "EMP-0002", part_time_hours: "500" },
	])
	assert.equal(rowsResult.valid, false)
	assert.equal(rowsResult.errors[0].employee, "EMP-0002")
	assert.equal(rowsResult.errors[0].field, "part_time_hours")

	assert.equal(validateTimeInputRows("not-a-list").valid, false)
	assert.equal(validateTimeInputRows([]).valid, true, "빈 목록은 valid")
}

// 3. 합계 ────────────────────────────────────────────────────────
{
	const totals = sumTimeInputRows([
		{ employee: "A", overtime_hours: 108.5, night_hours: 2 },
		{ employee: "B", overtime_hours: "63", holiday_hours: 8, part_time_hours: 40.25 },
		{ employee: "C", overtime_hours: "invalid" }, // invalid → 0 취급
	])
	assert.equal(totals.overtime_hours, 171.5, "초과 합계 108.5+63")
	assert.equal(totals.night_hours, 2)
	assert.equal(totals.holiday_hours, 8)
	assert.equal(totals.part_time_hours, 40.25)
	assert.deepEqual(sumTimeInputRows(null), {
		overtime_hours: 0,
		night_hours: 0,
		holiday_hours: 0,
		part_time_hours: 0,
	})
}

// 4. buildSaveRows ───────────────────────────────────────────────
{
	const payload = buildSaveRows([
		{ employee: "EMP-0001", overtime_hours: "63", note: " 5월 누락분 소급 ", status: "draft", employee_name: "김철수" },
	])
	assert.deepEqual(payload, [
		{
			employee: "EMP-0001",
			overtime_hours: 63,
			night_hours: 0,
			holiday_hours: 0,
			part_time_hours: 0,
			note: "5월 누락분 소급",
		},
	])
}

// 5. period 헬퍼 ─────────────────────────────────────────────────
assert.equal(isValidPeriod("2026-07"), true)
assert.equal(isValidPeriod("2026-13"), false)
assert.equal(isValidPeriod("2026-7"), false)
assert.equal(isValidPeriod(202607), false)
assert.equal(currentPeriod(new Date(2026, 6, 7)), "2026-07")
assert.equal(currentPeriod(new Date(2026, 11, 1)), "2026-12")

// 6. 정적 파일 검사 ───────────────────────────────────────────────
{
	const router = await readFile(resolve(frontendRoot, "src/router/korea.js"), "utf-8")
	assert.match(router, /KoreaTimeInput/, "라우터에 KoreaTimeInput 등록")
	assert.match(router, /\/dashboard\/korea-time-input/, "라우터 경로 등록")

	const home = await readFile(resolve(frontendRoot, "src/views/Home.vue"), "utf-8")
	assert.match(home, /근무시간 제출/, "Home 근태 섹션 링크 라벨")
	assert.match(home, /KoreaTimeInput/, "Home 근태 섹션 링크 라우트")

	const view = await readFile(resolve(frontendRoot, "src/views/korea/KoreaTimeInput.vue"), "utf-8")
	assert.match(view, /k-block--mint/, "mint 히어로")
	assert.match(view, /TIME INPUT/, "eyebrow")
	assert.match(view, /근무시간 제출/, "타이틀")
	assert.match(view, /임시저장/, "임시저장 버튼")
	assert.match(view, /제출 후에는 수정할 수 없습니다/, "제출 확인 다이얼로그 경고")
	assert.match(view, /제출 완료/, "제출 완료 배지")

	const runtime = await readFile(resolve(frontendRoot, "src/data/koreaTimeInputRuntime.js"), "utf-8")
	assert.match(runtime, /createResource/, "createResource 패턴")
	for (const method of ["list_time_inputs", "save_time_inputs", "submit_time_inputs"]) {
		assert.match(
			runtime,
			new RegExp(`hrms\\.regional\\.south_korea\\.payroll_time_input_api\\.${method}`),
			`런타임 URL: ${method}`
		)
	}
}

console.log("koreaTimeInput.test.mjs: all assertions passed")
