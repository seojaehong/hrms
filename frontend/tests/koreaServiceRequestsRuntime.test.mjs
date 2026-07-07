/**
 * koreaServiceRequestsRuntime.js — unit tests (F3 요청 보드)
 *
 * 검증:
 * 1. API URL이 service_request_api 3종을 가리킴
 * 2. CATEGORIES / REQUEST_STATUSES — doctype select 옵션과 일치
 * 3. STATUS_BADGES — 접수=회색 / 처리중=노랑 / 완료=초록 / 보류=주황
 * 4. nextStatusOptions — 백엔드 전이 규칙 미러 (완료=종결)
 * 5. validateRequestForm — 제목 필수 + 분류 유효
 * 6. makeCreatePayload — 트림·선택필드 기본값
 */

import assert from "node:assert/strict"
import { describe, it } from "node:test"

import {
	ALLOWED_TRANSITIONS,
	CATEGORIES,
	CREATE_URL,
	LIST_URL,
	REQUEST_STATUSES,
	STATUS_BADGES,
	UPDATE_URL,
	makeCreatePayload,
	nextStatusOptions,
	statusBadge,
	validateRequestForm,
} from "../src/data/koreaServiceRequestsRuntime.js"

describe("API URLs", () => {
	it("point to service_request_api", () => {
		assert.ok(CREATE_URL.includes("service_request_api.create_service_request"))
		assert.ok(LIST_URL.includes("service_request_api.list_service_requests"))
		assert.ok(UPDATE_URL.includes("service_request_api.update_service_request_status"))
	})
})

describe("CATEGORIES / REQUEST_STATUSES", () => {
	it("match doctype select options", () => {
		assert.deepEqual(CATEGORIES, ["급여", "4대보험", "증명서", "연차·근태", "기타"])
		assert.deepEqual(REQUEST_STATUSES, ["접수", "처리중", "완료", "보류"])
	})
})

describe("STATUS_BADGES", () => {
	it("has all four statuses with intended colors", () => {
		assert.equal(STATUS_BADGES["접수"].text, "접수")
		assert.ok(STATUS_BADGES["접수"].badgeClass.includes("gray"))
		assert.ok(STATUS_BADGES["처리중"].badgeClass.includes("yellow"))
		assert.ok(STATUS_BADGES["완료"].badgeClass.includes("green"))
		assert.ok(STATUS_BADGES["보류"].badgeClass.includes("orange"))
	})

	it("statusBadge falls back safely", () => {
		const badge = statusBadge("unknown")
		assert.equal(badge.text, "unknown")
		assert.ok(badge.badgeClass)
	})
})

describe("nextStatusOptions", () => {
	it("mirrors backend transitions", () => {
		assert.deepEqual(nextStatusOptions("접수"), ["처리중", "완료", "보류"])
		assert.deepEqual(nextStatusOptions("처리중"), ["완료", "보류", "접수"])
		assert.deepEqual(nextStatusOptions("보류"), ["처리중", "완료", "접수"])
	})

	it("완료 is terminal (no options)", () => {
		assert.deepEqual(nextStatusOptions("완료"), [])
		assert.deepEqual(ALLOWED_TRANSITIONS["완료"], [])
	})

	it("returns empty for unknown status", () => {
		assert.deepEqual(nextStatusOptions("없음"), [])
	})
})

describe("validateRequestForm", () => {
	const VALID = { title: "5월 급여 재발급", category: "급여", detail: "명세서 재발급 요청" }

	it("valid form passes", () => {
		const { valid, errors } = validateRequestForm(VALID)
		assert.equal(valid, true)
		assert.deepEqual(errors, {})
	})

	it("title is required", () => {
		const { valid, errors } = validateRequestForm({ ...VALID, title: "   " })
		assert.equal(valid, false)
		assert.ok(errors.title)
	})

	it("category must be a known option", () => {
		const { valid, errors } = validateRequestForm({ ...VALID, category: "환불" })
		assert.equal(valid, false)
		assert.ok(errors.category)
	})

	it("missing category is flagged", () => {
		const { valid, errors } = validateRequestForm({ title: "제목만" })
		assert.equal(valid, false)
		assert.ok(errors.category)
	})
})

describe("makeCreatePayload", () => {
	it("trims and carries fields", () => {
		const payload = makeCreatePayload({
			company: " 노호 ",
			title: "  급여 문의  ",
			category: "급여",
			detail: "  내용  ",
		})
		assert.equal(payload.company, "노호")
		assert.equal(payload.title, "급여 문의")
		assert.equal(payload.category, "급여")
		assert.equal(payload.detail, "내용")
	})

	it("defaults optional fields to empty string", () => {
		const payload = makeCreatePayload({ title: "제목", category: "기타" })
		assert.equal(payload.company, "")
		assert.equal(payload.detail, "")
	})
})
