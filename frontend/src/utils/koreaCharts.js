/**
 * koreaCharts — 인라인 SVG 차트용 순수 좌표계산 유틸 (프레임워크 무관)
 *
 * 외부 차트 라이브러리 금지(번들 영향) 원칙에 따라 뷰에서 인라인 SVG를 직접
 * 렌더할 때 필요한 좌표/치수 계산만 담당한다. DOM/Vue 의존 없음 → node --test 가능.
 *
 * 공통 계약: 그릴 데이터가 없으면(빈 배열, 합계 0 등) null을 반환한다.
 * 뷰는 null이면 차트를 렌더하지 않는다 (빈 차트 렌더 금지).
 */

/**
 * 스파크라인 polyline 좌표 계산.
 * @param {Array<number>} values - 시계열 값 (좌→우 순서)
 * @param {number} w - SVG 폭
 * @param {number} h - SVG 높이
 * @returns {{ points: string, coords: Array<{x:number,y:number}>, lastPoint: {x:number,y:number} } | null}
 */
export function buildSparklinePath(values, w, h) {
	if (!Array.isArray(values)) return null
	const nums = values.filter((v) => typeof v === "number" && Number.isFinite(v))
	if (nums.length === 0) return null

	const min = Math.min(...nums)
	const max = Math.max(...nums)
	const span = max - min

	const coords = nums.map((v, i) => {
		// 단일 값이면 우측 끝 1점, 그 외 균등 분할
		const x = nums.length === 1 ? w : (i / (nums.length - 1)) * w
		// max==min(0-division) 방어 → 세로 중앙 수평선
		const y = span === 0 ? h / 2 : h - ((v - min) / span) * h
		return { x: round2(x), y: round2(y) }
	})

	return {
		coords,
		points: coords.map((c) => `${c.x},${c.y}`).join(" "),
		lastPoint: coords[coords.length - 1],
	}
}

/**
 * 세로 막대 차트 rect 배열 계산. 최대값이 h를 가득 채운다.
 * @param {Array<number>} values
 * @param {number} w - 전체 폭
 * @param {number} h - 전체 높이
 * @param {number} gap - 막대 사이 간격
 * @returns {Array<{x:number,y:number,width:number,height:number,value:number}> | null}
 */
export function buildBarChart(values, w, h, gap = 4) {
	if (!Array.isArray(values) || values.length === 0) return null
	const nums = values.map((v) => (typeof v === "number" && Number.isFinite(v) && v > 0 ? v : 0))
	const max = Math.max(...nums)
	if (max <= 0) return null

	const barWidth = (w - gap * (nums.length - 1)) / nums.length
	return nums.map((v, i) => {
		const height = (v / max) * h
		return {
			x: round2(i * (barWidth + gap)),
			y: round2(h - height),
			width: round2(barWidth),
			height: round2(height),
			value: v,
		}
	})
}

/**
 * 구성비 가로 스택 바 세그먼트 계산 (예: 출근/결근/휴가).
 * @param {Array<number>} values
 * @param {number} w - 전체 폭
 * @returns {Array<{x:number,width:number,ratio:number,value:number}> | null}
 */
export function buildStackedBar(values, w) {
	if (!Array.isArray(values) || values.length === 0) return null
	const nums = values.map((v) => (typeof v === "number" && Number.isFinite(v) && v > 0 ? v : 0))
	const total = nums.reduce((a, b) => a + b, 0)
	if (total <= 0) return null

	let x = 0
	return nums.map((v) => {
		const ratio = v / total
		const seg = { x: round2(x), width: round2(ratio * w), ratio, value: v }
		x += ratio * w
		return seg
	})
}

/**
 * 도넛(원형 진행) stroke-dasharray 계산.
 * @param {number} ratio - 0~1 (범위 밖은 클램프, NaN/null → 0)
 * @param {number} r - 반지름
 * @returns {{ circumference:number, filled:number, dashArray:string, percent:number }}
 */
export function buildDonut(ratio, r) {
	const safe = typeof ratio === "number" && Number.isFinite(ratio) ? Math.min(Math.max(ratio, 0), 1) : 0
	const circumference = 2 * Math.PI * r
	const filled = circumference * safe
	return {
		circumference,
		filled,
		dashArray: `${filled} ${circumference}`,
		percent: Math.round(safe * 1000) / 10,
	}
}

/**
 * 축 눈금용 한국식 축약 포맷 (만/억).
 * @param {number} value
 * @returns {string}
 */
export function formatTick(value) {
	if (typeof value !== "number" || !Number.isFinite(value)) return "—"
	const abs = Math.abs(value)
	const sign = value < 0 ? "-" : ""
	if (abs >= 1e8) return `${sign}${trimZero(abs / 1e8)}억`
	if (abs >= 1e4) return `${sign}${trimZero(abs / 1e4)}만`
	return `${sign}${abs.toLocaleString("ko-KR")}`
}

function trimZero(n) {
	// 소수 1자리까지, .0 제거 (1.2억 / 250만 / 3만)
	return String(Math.round(n * 10) / 10)
}

function round2(n) {
	return Math.round(n * 100) / 100
}
