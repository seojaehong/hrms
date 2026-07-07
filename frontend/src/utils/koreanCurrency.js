/**
 * 한국식 금액 축약 — 순수 JS 유틸리티
 *
 * Vue 컴포넌트와 분리하여 테스트 가능하게 유지.
 * 외부 의존성 없음 (node --test 로 직접 import 가능).
 *
 * 규칙:
 *   - 1만 미만        → 원 단위 그대로   (9500 → "9,500원")
 *   - 1만 이상 1억 미만 → 만원 단위 절사   (95940486 → "9,594만원")
 *   - 1억 이상        → 억원 소수 1자리  (120000000 → "1.2억원", 100000000 → "1억원")
 */

/**
 * 정수에 천단위 콤마를 삽입합니다. (ICU/locale 비의존 — 결정적)
 * @param {number} n
 * @returns {string}
 */
function withCommas(n) {
	return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",")
}

/**
 * 금액을 한국식으로 축약합니다.
 * @param {number} value - 원 단위 정수 금액
 * @returns {string} 예: "9,594만원", "1.2억원", "9,500원". 유효하지 않으면 "".
 */
export function formatKoreanCurrencyShort(value) {
	if (value === null || value === undefined || typeof value !== "number" || Number.isNaN(value)) {
		return ""
	}

	const negative = value < 0
	const abs = Math.abs(value)
	let out

	if (abs < 10000) {
		out = `${withCommas(Math.round(abs))}원`
	} else if (abs < 100000000) {
		const man = Math.floor(abs / 10000)
		out = `${withCommas(man)}만원`
	} else {
		const eok = Math.round((abs / 100000000) * 10) / 10
		const eokStr = Number.isInteger(eok) ? String(eok) : eok.toFixed(1)
		out = `${eokStr}억원`
	}

	return negative ? `-${out}` : out
}
