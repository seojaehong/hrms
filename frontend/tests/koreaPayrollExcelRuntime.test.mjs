/**
 * koreaPayrollExcelRuntime.js — unit tests (F5 급여 엑셀 업/다운로드)
 *
 * 검증:
 * 1. API URL이 payroll_excel_api 3종을 가리킴
 * 2. formatWon / formatSignedWon (콤마·부호·±0)
 * 3. isValidPeriod / defaultPeriod
 * 4. buildValidationView (ok/diff, parse_error, invalid+행번호)
 * 5. hasPayrollChanges
 * 6. buildApplyView (blocked/applied/error)
 */

import assert from "node:assert/strict"
import { describe, it } from "node:test"

import {
	APPLY_URL,
	DOWNLOAD_URL,
	VALIDATE_URL,
	buildApplyView,
	buildValidationView,
	defaultPeriod,
	formatSignedWon,
	formatWon,
	hasPayrollChanges,
	isValidPeriod,
} from "../src/data/koreaPayrollExcelRuntime.js"

describe("API URLs", () => {
	it("point to payroll_excel_api", () => {
		assert.ok(DOWNLOAD_URL.includes("payroll_excel_api.download_payroll_workbook"))
		assert.ok(VALIDATE_URL.includes("payroll_excel_api.validate_payroll_upload"))
		assert.ok(APPLY_URL.includes("payroll_excel_api.apply_payroll_upload"))
	})
})

describe("formatWon / formatSignedWon", () => {
	it("formats won with commas", () => {
		assert.equal(formatWon(95940486), "95,940,486원")
		assert.equal(formatWon("abc"), "-")
	})

	it("signs deltas and shows ±0", () => {
		assert.equal(formatSignedWon(1), "+1원")
		assert.equal(formatSignedWon(-25000), "−25,000원")
		assert.equal(formatSignedWon(0), "±0원")
		assert.equal(formatSignedWon(null), "-")
	})
})

describe("period helpers", () => {
	it("validates YYYY-MM", () => {
		assert.equal(isValidPeriod("2026-05"), true)
		assert.equal(isValidPeriod("2026-13"), false)
		assert.equal(isValidPeriod("2026-00"), false)
		assert.equal(isValidPeriod("2026-5"), false)
		assert.equal(isValidPeriod(""), false)
	})

	it("defaultPeriod returns previous month", () => {
		assert.equal(defaultPeriod(new Date(2026, 6, 7)), "2026-06") // 7월 → 6월
		assert.equal(defaultPeriod(new Date(2026, 0, 15)), "2025-12") // 1월 → 전년 12월
	})
})

describe("buildValidationView", () => {
	const OK = {
		status: "ok",
		period: "2026-05",
		company: "노호",
		count: 3,
		diff: {
			new: [{ name: "김신입" }],
			changed: [
				{ name: "이변경", gross_delta: 10000, net_delta: -25000, from_net: 2000000, to_net: 1975000 },
			],
			same: ["박동일"],
			missing: [{ name: "최퇴사" }],
			counts: { new: 1, changed: 1, same: 1, missing: 1 },
		},
	}

	it("normalizes ok + diff", () => {
		const v = buildValidationView(OK)
		assert.equal(v.ok, true)
		assert.equal(v.hasError, false)
		assert.equal(v.company, "노호")
		assert.deepEqual(v.counts, { new: 1, changed: 1, same: 1, missing: 1 })
		assert.equal(v.changedRows[0].netDelta, -25000)
		assert.equal(v.changedRows[0].grossDelta, 10000)
		assert.equal(v.newRows[0].name, "김신입")
		assert.equal(v.missingRows[0].name, "최퇴사")
	})

	it("surfaces parse_error", () => {
		const v = buildValidationView({ status: "parse_error", period: "2026-05", errors: ["sheet not found"] })
		assert.equal(v.ok, false)
		assert.equal(v.hasError, true)
		assert.deepEqual(v.errors, ["sheet not found"])
	})

	it("surfaces invalid with row-number errors", () => {
		const v = buildValidationView({
			status: "invalid",
			period: "2026-05",
			count: 2,
			errors: ["행 4: gross != earnings 합"],
		})
		assert.equal(v.hasError, true)
		assert.equal(v.count, 2)
		assert.ok(v.errors[0].includes("행 4"))
	})

	it("returns empty view for null", () => {
		const v = buildValidationView(null)
		assert.equal(v.status, "none")
		assert.equal(v.ok, false)
	})
})

describe("hasPayrollChanges", () => {
	it("true when new/changed/missing present", () => {
		assert.equal(hasPayrollChanges({ counts: { new: 1, changed: 0, same: 5, missing: 0 } }), true)
		assert.equal(hasPayrollChanges({ counts: { new: 0, changed: 2, same: 0, missing: 0 } }), true)
	})

	it("false when only same", () => {
		assert.equal(hasPayrollChanges({ counts: { new: 0, changed: 0, same: 9, missing: 0 } }), false)
		assert.equal(hasPayrollChanges(null), false)
	})
})

describe("buildApplyView", () => {
	it("blocked when gate not approved", () => {
		const v = buildApplyView({ status: "blocked" })
		assert.equal(v.blocked, true)
		assert.equal(v.applied, false)
	})

	it("applied summary", () => {
		const v = buildApplyView({
			status: "applied",
			period: "2026-05",
			company: "노호",
			created: 2,
			updated: 0,
			skipped: 30,
			count: 32,
			total_gross: 95940486,
		})
		assert.equal(v.applied, true)
		assert.equal(v.created, 2)
		assert.equal(v.skipped, 30)
		assert.equal(v.totalGross, 95940486)
	})

	it("carries errors on parse/invalid", () => {
		const v = buildApplyView({ status: "invalid", errors: ["행 4: 오류"] })
		assert.equal(v.applied, false)
		assert.equal(v.blocked, false)
		assert.ok(v.errors[0].includes("행 4"))
	})
})
