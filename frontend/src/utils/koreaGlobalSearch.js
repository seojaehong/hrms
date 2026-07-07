/**
 * 한국 통합 검색 — 순수 JS 유틸리티
 *
 * Vue 컴포넌트와 분리하여 테스트 가능하게 유지.
 * 외부 LLM API 없음.
 */

// ---------------------------------------------------------------------------
// Debounce
// ---------------------------------------------------------------------------

/**
 * 함수를 debounce 합니다.
 * @param {Function} fn
 * @param {number} wait - 밀리초
 * @returns {Function}
 */
export function debounce(fn, wait = 300) {
	let timer = null
	function debounced(...args) {
		if (timer !== null) clearTimeout(timer)
		timer = setTimeout(() => {
			timer = null
			fn(...args)
		}, wait)
	}
	debounced.cancel = () => {
		if (timer !== null) {
			clearTimeout(timer)
			timer = null
		}
	}
	return debounced
}

// ---------------------------------------------------------------------------
// Snippet 렌더링 (Python build_search_snippet 과 대칭)
// ---------------------------------------------------------------------------

/**
 * **match** 마커를 <mark> 태그로 치환합니다.
 * @param {string} snippet - 백엔드에서 받은 snippet 문자열
 * @returns {string} HTML 안전한 문자열 (mark 태그 포함)
 */
export function renderSnippet(snippet) {
	if (!snippet) return ""
	// XSS 방지: ** 외 HTML 이스케이프
	const escaped = snippet
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
	return escaped.replace(/\*\*(.+?)\*\*/g, "<mark>$1</mark>")
}

// ---------------------------------------------------------------------------
// PWA 경로 변환
// ---------------------------------------------------------------------------

/**
 * 백엔드 pwa_url("/hrms/..." 절대 경로)을 vue-router 내부 경로로 변환합니다.
 * router base 가 이미 "/hrms" 이므로 prefix 를 제거해야
 * "/hrms/hrms/..." 경로 중복(빈 화면)이 발생하지 않습니다.
 *
 * @param {string|null|undefined} pwaUrl
 * @returns {string|null} router 내부 경로 (없으면 null)
 */
export function toRouterPath(pwaUrl) {
	if (!pwaUrl || typeof pwaUrl !== "string") return null
	let path = pwaUrl
	if (path === "/hrms" || path.startsWith("/hrms/")) {
		path = path.slice("/hrms".length)
	}
	if (!path.startsWith("/")) path = `/${path}`
	return path === "/" ? null : path
}

// ---------------------------------------------------------------------------
// 최근 검색어 (localStorage)
// ---------------------------------------------------------------------------

const RECENT_KEY = "hrms_korea_search_recent"
const MAX_RECENT = 5

/**
 * 최근 검색어 목록 조회 (최신순).
 * @returns {string[]}
 */
export function getRecentSearches() {
	try {
		const raw = localStorage.getItem(RECENT_KEY)
		if (!raw) return []
		const parsed = JSON.parse(raw)
		return Array.isArray(parsed) ? parsed : []
	} catch {
		return []
	}
}

/**
 * 검색어를 최근 목록 맨 앞에 추가합니다.
 * 중복은 제거하고 MAX_RECENT 개를 유지합니다.
 * @param {string} query
 */
export function addRecentSearch(query) {
	const q = (query || "").trim()
	if (!q) return
	const current = getRecentSearches().filter((s) => s !== q)
	const next = [q, ...current].slice(0, MAX_RECENT)
	try {
		localStorage.setItem(RECENT_KEY, JSON.stringify(next))
	} catch {
		// localStorage 쓰기 실패 무시
	}
}

/**
 * 최근 검색어 전체 삭제.
 */
export function clearRecentSearches() {
	try {
		localStorage.removeItem(RECENT_KEY)
	} catch {
		// 무시
	}
}

// ---------------------------------------------------------------------------
// 필터 pill 상태 관리
// ---------------------------------------------------------------------------

/** 지원하는 doctype pill 목록 */
export const FILTER_PILLS = [
	{ key: "all", label: "전체" },
	{ key: "Employee", label: "직원" },
	{ key: "Attendance", label: "근태" },
	{ key: "Salary Slip", label: "급여" },
	{ key: "Leave Application", label: "휴가" },
	{ key: "Employment Contract", label: "계약" },
	{ key: "Korea Payroll Closing Draft", label: "마감" },
	{ key: "Korea Workplace Profile", label: "사업장" },
	{ key: "Korea Employment Profile", label: "고용 프로필" },
]

/**
 * 선택된 pill 집합에서 토글합니다.
 * "전체" 선택 시 나머지 모두 해제, 특정 항목 선택 시 "전체" 해제.
 * @param {Set<string>} selected - 현재 선택된 pill key 집합
 * @param {string} key - 토글할 key
 * @returns {Set<string>} 새 집합
 */
export function toggleFilterPill(selected, key) {
	const next = new Set(selected)
	if (key === "all") {
		return new Set(["all"])
	}
	next.delete("all")
	if (next.has(key)) {
		next.delete(key)
		if (next.size === 0) next.add("all")
	} else {
		next.add(key)
	}
	return next
}

/**
 * 선택된 pill 에서 API 요청에 사용할 doctype 목록을 반환합니다.
 * "all" 선택 시 null (전체 검색).
 * @param {Set<string>} selected
 * @returns {string[]|null}
 */
export function getSelectedDoctypes(selected) {
	if (selected.has("all") || selected.size === 0) return null
	return [...selected]
}

// ---------------------------------------------------------------------------
// 결과 그룹화 (백엔드 results_by_doctype 을 UI용으로 변환)
// ---------------------------------------------------------------------------

/**
 * results_by_doctype 을 순서 있는 배열로 변환합니다.
 * @param {Object} resultsByDoctype
 * @returns {{ doctype: string, label: string, items: Object[] }[]}
 */
export function groupResults(resultsByDoctype) {
	if (!resultsByDoctype) return []
	return Object.entries(resultsByDoctype).map(([doctype, items]) => ({
		doctype,
		label: items[0]?.doctype ?? doctype,
		items,
	}))
}
