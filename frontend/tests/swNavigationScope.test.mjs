/**
 * SW 네비게이션 스코프 — /hrms 밖(데스크 /app 등)은 절대 가로채지 않는다.
 * 배경: SW가 /app/korea-hr 네비게이션을 PWA 캐시로 응답해 데스크가 납치된 사고.
 * 실행: node --test frontend/tests/swNavigationScope.test.mjs
 */
import { test } from "node:test"
import assert from "node:assert/strict"
import { isPwaNavigation } from "../src/utils/swNavigationScope.js"

test("PWA 경로는 처리한다", () => {
	assert.equal(isPwaNavigation("/hrms"), true)
	assert.equal(isPwaNavigation("/hrms/home"), true)
	assert.equal(isPwaNavigation("/hrms/dashboard/korea-payroll-closing"), true)
})

test("데스크·기타 경로는 개입하지 않는다", () => {
	assert.equal(isPwaNavigation("/app/korea-hr"), false)
	assert.equal(isPwaNavigation("/app"), false)
	assert.equal(isPwaNavigation("/desk/employee"), false)
	assert.equal(isPwaNavigation("/login"), false)
	assert.equal(isPwaNavigation("/api/method/frappe.ping"), false)
	assert.equal(isPwaNavigation("/hrmsx"), false)
	assert.equal(isPwaNavigation(undefined), false)
})
