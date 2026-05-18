/**
 * 한국 통합 검색 — 런타임 유틸리티 테스트
 *
 * 실행: node --test frontend/tests/koreaGlobalSearchRuntime.test.mjs
 *
 * Vue 컴포넌트를 마운트하지 않음.
 * koreaGlobalSearch.js 의 순수 JS 유틸리티만 검증.
 *
 * Node.js 18+ 내장 test runner 사용 (외부 의존성 없음).
 */

import { test, describe, before, after, beforeEach } from "node:test"
import assert from "node:assert/strict"

// ---------------------------------------------------------------------------
// localStorage mock (Node.js 에는 없으므로 직접 구현)
// ---------------------------------------------------------------------------

const store = {}
const localStorageMock = {
	getItem: (key) => store[key] ?? null,
	setItem: (key, val) => { store[key] = String(val) },
	removeItem: (key) => { delete store[key] },
	clear: () => { Object.keys(store).forEach((k) => delete store[k]) },
}

// globalThis.localStorage 주입
Object.defineProperty(globalThis, "localStorage", {
	value: localStorageMock,
	writable: true,
})

// ---------------------------------------------------------------------------
// 모듈 로드 (ESM dynamic import — 상대 경로 기준 실행 위치)
// ---------------------------------------------------------------------------

// 이 파일 위치: frontend/tests/koreaGlobalSearchRuntime.test.mjs
// 대상 파일:   frontend/src/utils/koreaGlobalSearch.js
const mod = await import("../src/utils/koreaGlobalSearch.js")

const {
	debounce,
	renderSnippet,
	getRecentSearches,
	addRecentSearch,
	clearRecentSearches,
	FILTER_PILLS,
	toggleFilterPill,
	getSelectedDoctypes,
	groupResults,
} = mod

// ---------------------------------------------------------------------------
// debounce 테스트
// ---------------------------------------------------------------------------

describe("debounce", () => {
	test("지연 후 한 번만 호출됨", async () => {
		let count = 0
		const fn = debounce(() => count++, 50)
		fn()
		fn()
		fn()
		await new Promise((r) => setTimeout(r, 100))
		assert.equal(count, 1)
	})

	test("cancel 하면 호출되지 않음", async () => {
		let count = 0
		const fn = debounce(() => count++, 50)
		fn()
		fn.cancel()
		await new Promise((r) => setTimeout(r, 100))
		assert.equal(count, 0)
	})
})

// ---------------------------------------------------------------------------
// renderSnippet 테스트
// ---------------------------------------------------------------------------

describe("renderSnippet", () => {
	test("**match** 를 <mark> 로 치환", () => {
		const result = renderSnippet("안녕 **철수** 반가워")
		assert.ok(result.includes("<mark>철수</mark>"), `got: ${result}`)
	})

	test("빈 snippet 은 빈 문자열 반환", () => {
		assert.equal(renderSnippet(""), "")
		assert.equal(renderSnippet(null), "")
		assert.equal(renderSnippet(undefined), "")
	})

	test("XSS 방지: HTML 특수문자 이스케이프", () => {
		const result = renderSnippet("<script>alert(1)</script>")
		assert.ok(!result.includes("<script>"), `got: ${result}`)
		assert.ok(result.includes("&lt;script&gt;"), `got: ${result}`)
	})

	test("마커 없는 snippet 그대로 이스케이프만", () => {
		const result = renderSnippet("일반 텍스트")
		assert.equal(result, "일반 텍스트")
	})
})

// ---------------------------------------------------------------------------
// 최근 검색어 테스트
// ---------------------------------------------------------------------------

describe("최근 검색어", () => {
	beforeEach(() => {
		localStorageMock.clear()
	})

	test("초기 상태: 빈 배열", () => {
		assert.deepEqual(getRecentSearches(), [])
	})

	test("addRecentSearch 후 반환", () => {
		addRecentSearch("철수")
		const recent = getRecentSearches()
		assert.deepEqual(recent, ["철수"])
	})

	test("중복 제거 + 최신 우선", () => {
		addRecentSearch("철수")
		addRecentSearch("영희")
		addRecentSearch("철수")  // 중복
		const recent = getRecentSearches()
		assert.deepEqual(recent, ["철수", "영희"])
	})

	test("MAX_RECENT(5) 초과 시 오래된 것 제거", () => {
		for (let i = 1; i <= 6; i++) addRecentSearch(`검색${i}`)
		const recent = getRecentSearches()
		assert.equal(recent.length, 5)
		assert.equal(recent[0], "검색6")
		assert.ok(!recent.includes("검색1"))
	})

	test("빈 문자열 추가 무시", () => {
		addRecentSearch("")
		addRecentSearch("  ")
		assert.deepEqual(getRecentSearches(), [])
	})

	test("clearRecentSearches 후 빈 배열", () => {
		addRecentSearch("테스트")
		clearRecentSearches()
		assert.deepEqual(getRecentSearches(), [])
	})
})

// ---------------------------------------------------------------------------
// 필터 pill 테스트
// ---------------------------------------------------------------------------

describe("toggleFilterPill", () => {
	test("초기 all 선택 상태에서 특정 key 선택 시 all 해제", () => {
		const initial = new Set(["all"])
		const next = toggleFilterPill(initial, "Employee")
		assert.ok(next.has("Employee"))
		assert.ok(!next.has("all"))
	})

	test("all 선택 시 나머지 모두 해제", () => {
		const initial = new Set(["Employee", "Attendance"])
		const next = toggleFilterPill(initial, "all")
		assert.ok(next.has("all"))
		assert.equal(next.size, 1)
	})

	test("유일한 항목 해제 시 all 로 복귀", () => {
		const initial = new Set(["Employee"])
		const next = toggleFilterPill(initial, "Employee")
		assert.ok(next.has("all"))
	})

	test("여러 항목 토글", () => {
		let s = new Set(["all"])
		s = toggleFilterPill(s, "Employee")
		s = toggleFilterPill(s, "Attendance")
		assert.ok(s.has("Employee"))
		assert.ok(s.has("Attendance"))
		assert.ok(!s.has("all"))
	})
})

describe("getSelectedDoctypes", () => {
	test("all 선택이면 null 반환", () => {
		assert.equal(getSelectedDoctypes(new Set(["all"])), null)
	})

	test("빈 집합이면 null 반환", () => {
		assert.equal(getSelectedDoctypes(new Set()), null)
	})

	test("특정 항목이면 배열 반환", () => {
		const result = getSelectedDoctypes(new Set(["Employee", "Attendance"]))
		assert.ok(Array.isArray(result))
		assert.ok(result.includes("Employee"))
		assert.ok(result.includes("Attendance"))
	})
})

// ---------------------------------------------------------------------------
// FILTER_PILLS 구조 검증
// ---------------------------------------------------------------------------

describe("FILTER_PILLS", () => {
	test("all pill 이 첫 번째", () => {
		assert.equal(FILTER_PILLS[0].key, "all")
	})

	test("모든 pill 에 key, label 있음", () => {
		for (const pill of FILTER_PILLS) {
			assert.ok(pill.key, "key 누락")
			assert.ok(pill.label, "label 누락")
		}
	})
})

// ---------------------------------------------------------------------------
// groupResults 테스트
// ---------------------------------------------------------------------------

describe("groupResults", () => {
	test("빈 객체 → 빈 배열", () => {
		assert.deepEqual(groupResults({}), [])
	})

	test("null/undefined → 빈 배열", () => {
		assert.deepEqual(groupResults(null), [])
		assert.deepEqual(groupResults(undefined), [])
	})

	test("정상 결과 변환", () => {
		const input = {
			Employee: [{ name: "EMP-0001", doctype: "직원", label: "김철수" }],
			Attendance: [{ name: "ATT-0001", doctype: "출근기록", label: "출근" }],
		}
		const groups = groupResults(input)
		assert.equal(groups.length, 2)
		assert.equal(groups[0].doctype, "Employee")
		assert.equal(groups[0].label, "직원")
		assert.equal(groups[0].items.length, 1)
	})

	test("items 의 doctype 값이 없으면 doctype key 를 label 로 사용", () => {
		const input = {
			Employee: [{ name: "EMP-0001" }],  // doctype 없음
		}
		const groups = groupResults(input)
		assert.equal(groups[0].label, "Employee")
	})
})
