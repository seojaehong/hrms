import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, "..")

const viewSource = readFileSync(resolve(frontendRoot, "src/views/KoreaPayrollClosing.vue"), "utf8")
const runtimeSource = readFileSync(resolve(frontendRoot, "src/data/koreaPayrollClosingRuntime.js"), "utf8")

test("고지 대사 카드 마크업이 존재한다", () => {
	assert.match(viewSource, /INSURANCE RECONCILIATION/)
	assert.match(viewSource, /고지 대사/)
	// 상위 diffs 테이블 컬럼: 직원 · 보험 · 계산 · 고지 · 차이
	assert.match(viewSource, /직원/)
	assert.match(viewSource, />보험</)
	assert.match(viewSource, />계산</)
	assert.match(viewSource, />고지</)
	assert.match(viewSource, />차이</)
	// 차이 양수 빨강 / 음수 파랑
	assert.match(viewSource, /d\.delta > 0 \? 'text-red-600' : 'text-blue-600'/)
	// unmatched/ambiguous 배지
	assert.match(viewSource, /미매칭 \{\{ insuranceReconUnmatchedCount \}\}건/)
	assert.match(viewSource, /동명이인 \{\{ insuranceReconAmbiguousCount \}\}건/)
})

test("데이터 없으면 카드 전체를 숨기는 v-if 조건이 존재한다", () => {
	assert.match(viewSource, /v-if="insuranceReconVisible"/)
	assert.match(viewSource, /const insuranceReconVisible = computed\(\(\) => hasKoreaInsuranceReconciliationData\(insuranceRecon\.value\)\)/)
})

test("런타임 로더 함수와 has-data 헬퍼를 사용한다", () => {
	assert.match(viewSource, /loadKoreaInsuranceReconciliation/)
	assert.match(viewSource, /hasKoreaInsuranceReconciliationData/)
	assert.match(runtimeSource, /export async function loadKoreaInsuranceReconciliation/)
	assert.match(runtimeSource, /export function hasKoreaInsuranceReconciliationData/)
})

test("서버 메서드가 read-only allowlist Set에 등록되어 있다", () => {
	assert.match(
		runtimeSource,
		/export const KOREA_INSURANCE_RECONCILIATION_RUNTIME_METHOD =\s*"hrms\.regional\.south_korea\.insurance_reconciliation_runtime_api\.get_korea_insurance_reconciliation_runtime"/,
	)
	// allowlist Set 등록
	assert.match(
		runtimeSource,
		/const KOREA_PAYROLL_CLOSING_READ_ONLY_RUNTIME_METHODS = new Set\(\[[\s\S]*KOREA_INSURANCE_RECONCILIATION_RUNTIME_METHOD[\s\S]*\]\)/,
	)
})
