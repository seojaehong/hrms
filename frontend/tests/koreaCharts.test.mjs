/**
 * koreaCharts — 인라인 SVG 차트 순수 좌표계산 로직 테스트 (프레임워크 무관)
 * 실행: node --test frontend/tests/koreaCharts.test.mjs
 */
import { test } from "node:test"
import assert from "node:assert/strict"

import {
	buildSparklinePath,
	buildBarChart,
	buildStackedBar,
	buildDonut,
	formatTick,
} from "../src/utils/koreaCharts.js"

// ──────────────────────────────────────────────────────────────────
// buildSparklinePath
// ──────────────────────────────────────────────────────────────────
test("buildSparklinePath: 기본 — n개 값이 균등 x간격 polyline points로 변환", () => {
	const r = buildSparklinePath([0, 50, 100], 100, 40)
	assert.equal(r.coords.length, 3)
	// x: 0 → 50 → 100
	assert.equal(r.coords[0].x, 0)
	assert.equal(r.coords[1].x, 50)
	assert.equal(r.coords[2].x, 100)
	// y: min(0)이 아래(h), max(100)가 위(0) — SVG 좌표계 반전
	assert.equal(r.coords[0].y, 40)
	assert.equal(r.coords[1].y, 20)
	assert.equal(r.coords[2].y, 0)
	assert.equal(r.points, "0,40 50,20 100,0")
})

test("buildSparklinePath: lastPoint = 마지막 좌표 (강조 원용)", () => {
	const r = buildSparklinePath([10, 30], 80, 40)
	assert.deepEqual(r.lastPoint, { x: 80, y: 0 })
})

test("buildSparklinePath: 빈 배열 → null (차트 렌더 금지 신호)", () => {
	assert.equal(buildSparklinePath([], 100, 40), null)
	assert.equal(buildSparklinePath(null, 100, 40), null)
	assert.equal(buildSparklinePath(undefined, 100, 40), null)
})

test("buildSparklinePath: 단일 값 → 중앙 수평 1점", () => {
	const r = buildSparklinePath([42], 100, 40)
	assert.equal(r.coords.length, 1)
	assert.equal(r.coords[0].x, 100) // 마지막(=유일) 점은 우측 끝
	assert.equal(r.coords[0].y, 20) // 세로 중앙
	assert.deepEqual(r.lastPoint, { x: 100, y: 20 })
})

test("buildSparklinePath: 전부 같은 값(max==min, 0-division 방어) → 중앙 수평선", () => {
	const r = buildSparklinePath([7, 7, 7], 90, 30)
	for (const c of r.coords) assert.equal(c.y, 15)
})

test("buildSparklinePath: 숫자 아닌 값 섞이면 무시하지 않고 유효값만으로 스케일", () => {
	const r = buildSparklinePath([0, null, 100], 100, 40)
	// null은 0으로 강제하지 않고 제외 — 2점만
	assert.equal(r.coords.length, 2)
	assert.equal(r.coords[1].y, 0)
})

// ──────────────────────────────────────────────────────────────────
// buildBarChart
// ──────────────────────────────────────────────────────────────────
test("buildBarChart: 기본 — rect 배열 (x/y/width/height), 최대값이 h를 가득 채움", () => {
	const bars = buildBarChart([1, 2, 4], 100, 40, 10)
	assert.equal(bars.length, 3)
	// width: (100 - 2*10) / 3 = 26.67
	for (const b of bars) assert.ok(Math.abs(b.width - 80 / 3) < 0.01)
	// x 간격 = width + gap
	assert.equal(bars[0].x, 0)
	assert.ok(Math.abs(bars[1].x - (80 / 3 + 10)) < 0.01)
	// 최대값(4) → height 40, y 0
	assert.equal(bars[2].height, 40)
	assert.equal(bars[2].y, 0)
	// 절반값(2) → height 20, y 20
	assert.equal(bars[1].height, 20)
	assert.equal(bars[1].y, 20)
})

test("buildBarChart: 빈 배열/전부 0 → null (빈 차트 렌더 금지)", () => {
	assert.equal(buildBarChart([], 100, 40, 4), null)
	assert.equal(buildBarChart([0, 0, 0], 100, 40, 4), null)
	assert.equal(buildBarChart(null, 100, 40, 4), null)
})

test("buildBarChart: 값 0인 막대는 height 0 (음수 금지)", () => {
	const bars = buildBarChart([0, 5], 50, 20, 2)
	assert.equal(bars[0].height, 0)
	assert.equal(bars[0].y, 20)
})

// ──────────────────────────────────────────────────────────────────
// buildStackedBar (구성비 가로 스택 — 출근/결근/휴가)
// ──────────────────────────────────────────────────────────────────
test("buildStackedBar: 합계 대비 비율로 x/width 세그먼트 분할", () => {
	const segs = buildStackedBar([18, 1, 1], 100)
	assert.equal(segs.length, 3)
	assert.equal(segs[0].x, 0)
	assert.equal(segs[0].width, 90)
	assert.equal(segs[1].x, 90)
	assert.equal(segs[1].width, 5)
	assert.equal(segs[2].x, 95)
	assert.equal(segs[2].width, 5)
	assert.ok(Math.abs(segs[0].ratio - 0.9) < 1e-9)
})

test("buildStackedBar: 합계 0 또는 빈 배열 → null", () => {
	assert.equal(buildStackedBar([0, 0], 100), null)
	assert.equal(buildStackedBar([], 100), null)
	assert.equal(buildStackedBar(null, 100), null)
})

test("buildStackedBar: 음수/비수치는 0으로 취급", () => {
	const segs = buildStackedBar([-5, 10, null], 100)
	assert.equal(segs[0].width, 0)
	assert.equal(segs[1].width, 100)
	assert.equal(segs[2].width, 0)
})

// ──────────────────────────────────────────────────────────────────
// buildDonut
// ──────────────────────────────────────────────────────────────────
test("buildDonut: ratio 0.25, r=40 → dasharray '둘레*0.25 둘레'", () => {
	const d = buildDonut(0.25, 40)
	const c = 2 * Math.PI * 40
	assert.ok(Math.abs(d.circumference - c) < 1e-9)
	assert.ok(Math.abs(d.filled - c * 0.25) < 1e-9)
	assert.equal(d.dashArray, `${d.filled} ${d.circumference}`)
	assert.ok(Math.abs(d.percent - 25) < 1e-9)
})

test("buildDonut: ratio 범위 클램프 (음수→0, 1 초과→1)", () => {
	assert.equal(buildDonut(-0.5, 40).filled, 0)
	const over = buildDonut(1.7, 40)
	assert.ok(Math.abs(over.filled - over.circumference) < 1e-9)
	assert.equal(over.percent, 100)
})

test("buildDonut: NaN/null ratio → 0으로 방어", () => {
	assert.equal(buildDonut(NaN, 40).filled, 0)
	assert.equal(buildDonut(null, 40).percent, 0)
})

// ──────────────────────────────────────────────────────────────────
// formatTick
// ──────────────────────────────────────────────────────────────────
test("formatTick: 만/억 단위 축약", () => {
	assert.equal(formatTick(2500000), "250만")
	assert.equal(formatTick(30000), "3만")
	assert.equal(formatTick(120000000), "1.2억")
	assert.equal(formatTick(999), "999")
	assert.equal(formatTick(0), "0")
})

test("formatTick: null/NaN → '—'", () => {
	assert.equal(formatTick(null), "—")
	assert.equal(formatTick(NaN), "—")
})
