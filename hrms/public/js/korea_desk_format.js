/**
 * 한국식 금액 축약 — Frappe 데스크 훅
 *
 * Number Card 등에서 frappe.utils.shorten_number 가 만드는
 * "KRW 95.94 M" 식 영문 축약을 한국식("9,594만원")으로 바꾼다.
 *
 * 방어적 설계: frappe 전역이 없는 환경(테스트/빌드)에서는 즉시 no-op.
 * 브라우저 데스크 로드 후 실제 표기 검증은 컨트롤러가 별도로 수행한다.
 */
(function () {
	"use strict"

	// 전역 가드 — frappe 데스크가 아니면 아무것도 하지 않는다.
	if (typeof frappe === "undefined" || !frappe || !frappe.utils) {
		return
	}

	function withCommas(n) {
		return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",")
	}

	function formatKoreanCurrencyShort(value) {
		if (value === null || value === undefined || isNaN(value)) {
			return ""
		}
		var num = Number(value)
		var negative = num < 0
		var abs = Math.abs(num)
		var out

		if (abs < 10000) {
			out = withCommas(Math.round(abs)) + "원"
		} else if (abs < 100000000) {
			out = withCommas(Math.floor(abs / 10000)) + "만원"
		} else {
			var eok = Math.round((abs / 100000000) * 10) / 10
			var eokStr = Number.isInteger(eok) ? String(eok) : eok.toFixed(1)
			out = eokStr + "억원"
		}

		return negative ? "-" + out : out
	}

	// 원본을 보존하고 KRW 통화일 때만 한국식으로 대체한다.
	var _origShorten = frappe.utils.shorten_number
	frappe.utils.shorten_number = function (number, country) {
		try {
			var currency = frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.currency
			var isKRW = currency === "KRW" || country === "South Korea"
			if (isKRW && typeof number === "number") {
				return formatKoreanCurrencyShort(number)
			}
		} catch (e) {
			// 어떤 경우에도 데스크 렌더를 막지 않는다.
		}
		return typeof _origShorten === "function"
			? _origShorten.apply(this, arguments)
			: String(number)
	}
})()
