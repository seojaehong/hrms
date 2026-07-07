/**
 * 한국식 금액 축약 유틸리티 — 런타임 테스트
 *
 * 실행: node --test frontend/tests/koreanCurrency.test.mjs
 *
 * Vue 컴포넌트를 마운트하지 않음. koreanCurrency.js 순수 함수만 검증.
 * Node.js 18+ 내장 test runner 사용 (외부 의존성 없음).
 */

import { test, describe } from "node:test"
import assert from "node:assert/strict"

// 이 파일 위치: frontend/tests/koreanCurrency.test.mjs
// 대상 파일:   frontend/src/utils/koreanCurrency.js
const { formatKoreanCurrencyShort } = await import("../src/utils/koreanCurrency.js")

describe("formatKoreanCurrencyShort", () => {
	test("1만 미만은 원 단위 그대로 콤마 표기", () => {
		assert.equal(formatKoreanCurrencyShort(9500), "9,500원")
		assert.equal(formatKoreanCurrencyShort(500), "500원")
		assert.equal(formatKoreanCurrencyShort(9999), "9,999원")
	})

	test("1만 경계값", () => {
		assert.equal(formatKoreanCurrencyShort(10000), "1만원")
	})

	test("1만 이상 1억 미만은 만원 단위로 절사", () => {
		assert.equal(formatKoreanCurrencyShort(95940486), "9,594만원")
		assert.equal(formatKoreanCurrencyShort(99999999), "9,999만원")
	})

	test("1억 경계값은 소수 없이 억원", () => {
		assert.equal(formatKoreanCurrencyShort(100000000), "1억원")
	})

	test("1억 이상은 억원 소수 1자리", () => {
		assert.equal(formatKoreanCurrencyShort(120000000), "1.2억원")
		assert.equal(formatKoreanCurrencyShort(125000000), "1.3억원") // 1.25 → 반올림 1.3
	})

	test("0과 음수", () => {
		assert.equal(formatKoreanCurrencyShort(0), "0원")
		assert.equal(formatKoreanCurrencyShort(-95940486), "-9,594만원")
	})

	test("유효하지 않은 입력은 빈 문자열", () => {
		assert.equal(formatKoreanCurrencyShort(null), "")
		assert.equal(formatKoreanCurrencyShort(undefined), "")
		assert.equal(formatKoreanCurrencyShort(NaN), "")
		assert.equal(formatKoreanCurrencyShort("9500"), "")
	})
})
