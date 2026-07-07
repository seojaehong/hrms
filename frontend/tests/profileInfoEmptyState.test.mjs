/**
 * profileInfoEmptyState.test.mjs — 데스크톱 리뷰 이슈 5
 * 프로필 "회사 정보" 등 섹션의 빈 값("-") 나열 제거.
 *
 * - 값 없는 행은 숨긴다 (filter).
 * - 전부 없으면 "회사 정보가 아직 등록되지 않았습니다" 한 줄 빈 상태.
 *
 * Vue SFC는 node에서 직접 import할 수 없어 소스 검증 방식 사용.
 * 실행: node frontend/tests/profileInfoEmptyState.test.mjs
 */
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, "..")

// ──────────────────────────────────────────────────────────────────
// 1. Profile.vue — 값 없는 행 필터링 + 섹션별 빈 상태 문구 전달
// ──────────────────────────────────────────────────────────────────
{
	const source = await readFile(resolve(frontendRoot, "src/views/Profile.vue"), "utf8")
	assert.match(source, /hasProfileValue|\.filter\(/, "값 없는 행 필터링 로직")
	assert.match(source, /회사 정보가 아직 등록되지 않았습니다/, "회사 정보 빈 상태 문구")
	assert.match(source, /emptyMessage/, "모달에 빈 상태 문구 전달")
}

// ──────────────────────────────────────────────────────────────────
// 2. ProfileInfoModal.vue — 빈 데이터면 한 줄 빈 상태 렌더
// ──────────────────────────────────────────────────────────────────
{
	const source = await readFile(resolve(frontendRoot, "src/components/ProfileInfoModal.vue"), "utf8")
	assert.match(source, /emptyMessage/, "emptyMessage prop")
	assert.match(source, /data\.length/, "빈 데이터 분기")
}

// ──────────────────────────────────────────────────────────────────
// 3. 필터 규칙 단위 검증 — Profile.vue와 동일 규칙 (null/undefined/"" 숨김, 0 유지)
// ──────────────────────────────────────────────────────────────────
{
	const source = await readFile(resolve(frontendRoot, "src/views/Profile.vue"), "utf8")
	const match = source.match(/function hasProfileValue\([\s\S]*?\n}/)
	assert.ok(match, "hasProfileValue 함수 정의")
	// eslint-disable-next-line no-new-func
	const hasProfileValue = new Function(`${match[0]}; return hasProfileValue`)()
	assert.equal(hasProfileValue(undefined), false)
	assert.equal(hasProfileValue(null), false)
	assert.equal(hasProfileValue(""), false)
	assert.equal(hasProfileValue("  "), false)
	assert.equal(hasProfileValue("영업부"), true)
	assert.equal(hasProfileValue(0), true, "숫자 0은 유효한 값으로 유지")
}

console.log("✓ profileInfoEmptyState.test.mjs: 모든 테스트 통과")
