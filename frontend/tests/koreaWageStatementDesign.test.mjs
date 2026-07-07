/**
 * 임금명세서 화면 디자인 계약 — "실수령액이 주인공" 리디자인 구조 고정
 * 실행: node --test frontend/tests/koreaWageStatementDesign.test.mjs
 */
import { test } from "node:test"
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { resolve, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const src = await readFile(resolve(root, "src/views/korea/KoreaWageStatementDashboard.vue"), "utf8")

test("히어로: 실수령액이 lime 블록 상단의 주인공 (디스플레이 타입 + k-numeric)", () => {
	assert.match(src, /k-block--lime/)
	assert.match(src, /실수령액/)
	// 히어로 금액은 3xl 이상 디스플레이 스케일
	assert.match(src, /text-4xl|text-3xl/)
})

test("요약 스탯: 지급 합계 · 공제 합계 · 실수령 3단 구조", () => {
	assert.match(src, /지급 합계/)
	assert.match(src, /공제 합계/)
})

test("지급/공제 섹션이 분리된 카드(k-card)로 존재", () => {
	assert.match(src, /지급 내역/)
	assert.match(src, /공제 내역/)
	assert.match(src, /k-card/)
})

test("공제 요약 3줄(4대보험·소득세·주민세) 구조 유지", () => {
	assert.match(src, /4대보험/)
	assert.match(src, /소득세/)
	assert.match(src, /주민세\(지방소득세\)/)
})

test("금액은 tabular 숫자 정렬(k-numeric)", () => {
	assert.ok((src.match(/k-numeric/g) || []).length >= 5)
})

test("근거 고지: 근로기준법 제48조 명세서 문구 존재", () => {
	assert.match(src, /근로기준법|제48조/)
})
