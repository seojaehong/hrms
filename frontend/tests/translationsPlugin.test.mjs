/**
 * 번역 플러그인 — 엔드포인트 폴백 테스트
 *
 * 실행: node --test frontend/tests/translationsPlugin.test.mjs
 *
 * 배경(노호 런칭 검증에서 발견): Frappe 버전에 따라 번역 API 이름이 다르다.
 *   - 구버전 v15: frappe.translate.get_boot_translations
 *   - 신버전:     frappe.translate.load_all_translations
 * 플러그인이 한 이름만 부르면 반대 버전에서 조용히 영어로 폴백된다.
 * → 후보를 순서대로 시도하고, 실패(HTTP 오류·exc 페이로드)는 다음 후보로 넘어가야 한다.
 *
 * Node.js 18+ 내장 test runner 사용 (외부 의존성 없음).
 */

import { test, describe } from "node:test"
import assert from "node:assert/strict"

import {
	TRANSLATION_ENDPOINT_CANDIDATES,
	fetchTranslationMessages,
} from "../src/plugins/translationsPlugin.js"

function makeWin({ boot = {}, responses = {} } = {}) {
	const calls = []
	return {
		calls,
		frappe: { boot },
		fetch: async (url) => {
			calls.push(String(url))
			const method = String(url).match(/api\/method\/([^?]+)/)?.[1]
			const spec = responses[method]
			if (!spec) return { ok: false, status: 404, json: async () => ({ exc_type: "NotFound" }) }
			return { ok: spec.ok !== false, status: spec.status ?? 200, json: async () => spec.body }
		},
		location: { origin: "https://noho.safeclaw.kr" },
	}
}

describe("TRANSLATION_ENDPOINT_CANDIDATES", () => {
	test("구버전 get_boot_translations 를 먼저 시도한다", () => {
		assert.equal(TRANSLATION_ENDPOINT_CANDIDATES[0], "frappe.translate.get_boot_translations")
	})
	test("신버전 load_all_translations 도 후보에 있다", () => {
		assert.ok(TRANSLATION_ENDPOINT_CANDIDATES.includes("frappe.translate.load_all_translations"))
	})
})

describe("fetchTranslationMessages", () => {
	test("boot.__messages 가 있으면 fetch 없이 그대로 쓴다", async () => {
		const win = makeWin({ boot: { __messages: { Hello: "안녕" } } })
		const messages = await fetchTranslationMessages(win)
		assert.equal(messages.Hello, "안녕")
		assert.equal(win.calls.length, 0)
	})

	test("첫 후보가 성공하면 그 결과를 쓰고 lang 파라미터를 붙인다", async () => {
		const win = makeWin({
			boot: { lang: "ko" },
			responses: {
				"frappe.translate.get_boot_translations": { body: { "Quick Links": "바로가기" } },
			},
		})
		const messages = await fetchTranslationMessages(win)
		assert.equal(messages["Quick Links"], "바로가기")
		assert.equal(win.calls.length, 1)
		assert.match(win.calls[0], /lang=ko/)
	})

	test("첫 후보가 HTTP 오류면 다음 후보로 폴백한다", async () => {
		const win = makeWin({
			boot: { lang: "ko" },
			responses: {
				"frappe.translate.get_boot_translations": { ok: false, status: 417, body: { exc_type: "ValidationError" } },
				"frappe.translate.load_all_translations": { body: { Employee: "직원" } },
			},
		})
		const messages = await fetchTranslationMessages(win)
		assert.equal(messages.Employee, "직원")
		assert.equal(win.calls.length, 2)
	})

	test("HTTP 200 이라도 exc_type 페이로드면 실패로 보고 폴백한다", async () => {
		const win = makeWin({
			boot: { lang: "ko" },
			responses: {
				"frappe.translate.get_boot_translations": { body: { exc_type: "ValidationError", exception: "x" } },
				"frappe.translate.load_all_translations": { body: { Status: "상태" } },
			},
		})
		const messages = await fetchTranslationMessages(win)
		assert.equal(messages.Status, "상태")
	})

	test("frappe whitelisted 응답의 {message:{...}} 래핑을 언랩한다", async () => {
		const win = makeWin({
			boot: { lang: "ko" },
			responses: {
				"frappe.translate.get_boot_translations": { body: { message: { "Request Attendance": "요청 출근기록" } } },
			},
		})
		const messages = await fetchTranslationMessages(win)
		assert.equal(messages["Request Attendance"], "요청 출근기록")
	})

	test("전 후보 실패 시 빈 객체 (UI는 원문 폴백)", async () => {
		const win = makeWin({ boot: { lang: "ko" }, responses: {} })
		const messages = await fetchTranslationMessages(win)
		assert.deepEqual(messages, {})
	})
})
