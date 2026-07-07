/**
 * koreaOnboardingRequestRuntime.js — unit tests (F2 입사자 등록 요청)
 *
 * 검증:
 * 1. API URL이 onboarding_request_api를 가리킴
 * 2. rrn 클라이언트 형식 점검 (13자리·하이픈 허용·성별코드 1-8·생년월일 정합)
 * 3. 폼 검증 — 필수 5필드
 * 4. makeCreatePayload — rrn 정규화, 평문 rrn 외 파생 필드 없음
 * 5. STATUS_BADGES — requested=대기 / processing=처리중 / completed=완료 / rejected=반려
 */

import assert from "node:assert/strict"
import { describe, it } from "node:test"

import {
	CONTRACT_TYPES,
	CREATE_URL,
	LIST_URL,
	PROCESS_URL,
	STATUS_BADGES,
	formatWage,
	isRrnShapeValid,
	makeCreatePayload,
	normalizeRrnInput,
	statusBadge,
	validateOnboardingForm,
} from "../src/data/koreaOnboardingRequestRuntime.js"

const VALID_FORM = {
	company: "노호",
	full_name: "김입사",
	rrn: "940101-1234567",
	join_date: "2026-07-15",
	reported_monthly_wage: 2800000,
	contract_type: "정규직",
	phone: "010-1234-5678",
	note: "주방 보조",
}

describe("API URLs", () => {
	it("point to onboarding_request_api", () => {
		assert.ok(CREATE_URL.includes("onboarding_request_api.create_onboarding_request"))
		assert.ok(LIST_URL.includes("onboarding_request_api.list_onboarding_requests"))
		assert.ok(PROCESS_URL.includes("onboarding_request_api.mark_onboarding_processed"))
	})
})

describe("rrn 클라이언트 점검", () => {
	it("normalizes hyphen and spaces", () => {
		assert.equal(normalizeRrnInput("940101-1234567"), "9401011234567")
		assert.equal(normalizeRrnInput(" 940101 1234567 "), "9401011234567")
	})

	it("accepts valid 13-digit rrn", () => {
		assert.equal(isRrnShapeValid("9401011234567"), true)
		assert.equal(isRrnShapeValid("940101-8234567"), true)
	})

	it("rejects wrong length / non-digit", () => {
		assert.equal(isRrnShapeValid("940101123456"), false)
		assert.equal(isRrnShapeValid("94010a1234567"), false)
		assert.equal(isRrnShapeValid(""), false)
		assert.equal(isRrnShapeValid(null), false)
	})

	it("rejects invalid gender code (0, 9)", () => {
		assert.equal(isRrnShapeValid("9401010234567"), false)
		assert.equal(isRrnShapeValid("9401019234567"), false)
	})

	it("rejects invalid birth month/day", () => {
		assert.equal(isRrnShapeValid("9413011234567"), false)
		assert.equal(isRrnShapeValid("9401321234567"), false)
	})
})

describe("validateOnboardingForm", () => {
	it("valid form passes", () => {
		const { valid, errors } = validateOnboardingForm(VALID_FORM)
		assert.equal(valid, true)
		assert.deepEqual(errors, {})
	})

	it("each required field is enforced", () => {
		for (const field of ["company", "full_name", "rrn", "join_date", "reported_monthly_wage", "contract_type"]) {
			const form = { ...VALID_FORM }
			delete form[field]
			const { valid, errors } = validateOnboardingForm(form)
			assert.equal(valid, false, `${field} missing must fail`)
			assert.ok(errors[field], `${field} must have error message`)
		}
	})

	it("bad rrn shape is flagged", () => {
		const { valid, errors } = validateOnboardingForm({ ...VALID_FORM, rrn: "123" })
		assert.equal(valid, false)
		assert.ok(errors.rrn)
	})

	it("zero wage is flagged", () => {
		const { valid } = validateOnboardingForm({ ...VALID_FORM, reported_monthly_wage: 0 })
		assert.equal(valid, false)
	})

	it("unknown contract type is flagged", () => {
		const { valid } = validateOnboardingForm({ ...VALID_FORM, contract_type: "프리랜서" })
		assert.equal(valid, false)
	})
})

describe("makeCreatePayload", () => {
	it("normalizes rrn (hyphen removed)", () => {
		const payload = makeCreatePayload(VALID_FORM)
		assert.equal(payload.rrn, "9401011234567")
	})

	it("carries required fields and trims optionals", () => {
		const payload = makeCreatePayload({ ...VALID_FORM, full_name: " 김입사 ", phone: undefined, note: "  " })
		assert.equal(payload.full_name, "김입사")
		assert.equal(payload.phone, "")
		assert.equal(payload.note, "")
		assert.equal(payload.reported_monthly_wage, 2800000)
		assert.equal(payload.contract_type, "정규직")
	})

	it("has no derived rrn fields beyond the payload rrn (masking is server-side)", () => {
		const payload = makeCreatePayload(VALID_FORM)
		assert.ok(!("masked_rrn" in payload))
		assert.ok(!("rrn_masked" in payload))
	})
})

describe("STATUS_BADGES", () => {
	it("has all four statuses with Korean labels", () => {
		assert.equal(STATUS_BADGES.requested.text, "대기")
		assert.equal(STATUS_BADGES.processing.text, "처리중")
		assert.equal(STATUS_BADGES.completed.text, "완료")
		assert.equal(STATUS_BADGES.rejected.text, "반려")
	})

	it("statusBadge falls back safely", () => {
		const badge = statusBadge("unknown_status")
		assert.equal(badge.text, "unknown_status")
		assert.ok(badge.badgeClass)
	})
})

describe("CONTRACT_TYPES / formatWage", () => {
	it("contract types match doctype select options", () => {
		assert.deepEqual(CONTRACT_TYPES, ["정규직", "계약직", "파트타임", "일용직"])
	})

	it("formats currency in ko-KR", () => {
		assert.equal(formatWage(2800000), "2,800,000원")
		assert.equal(formatWage("abc"), "-")
	})
})
