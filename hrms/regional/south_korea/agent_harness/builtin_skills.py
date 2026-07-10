# -*- coding: utf-8 -*-
"""빌트인 스킬 정의 2종 — framework-free 코어.

실무 스킬을 US-001 스킬 스키마(skill_registry) 그대로 정의한다. 스킬 정의는
순수 데이터(dict)이며, step["tool"] 이름은 tool_registry에 등록된 도구명과 매칭된다.
빌트인 스킬은 조회/대사(read-only) 성격이라 requires_approval=False다(확정 행위 아님).

정의된 스킬:
- hourly_closing_prep : 시급 마감 준비. list_hourly_payroll_proposals 도구로 제안을
  조회하고 output_summary_template로 요약(1 step).
- insurance_reconcile : 4대보험 고지 대사. reconcile_contributions로 대사한 뒤
  summarize_reconciliation_ko로 사람용 요약을 만든다(2 step, 둘 다 도구).

frappe 의존 없음 → `python3 hrms/tests/test_korea_agent_harness_builtin_skills.py` 직접 실행 검증.
"""
from __future__ import annotations


# 시급 마감 준비 — 제안 조회 후 요약(1 step). 조회 전용이라 승인 불필요.
HOURLY_CLOSING_PREP = {
	"name": "hourly_closing_prep",
	"description": "시급 근로자 월 마감 준비 — 급여 제안을 조회해 검토 대상을 요약한다.",
	"steps": [
		{"tool": "list_hourly_payroll_proposals", "args": {}},
	],
	"requires_approval": False,
	"output_summary_template": "시급 마감 준비 완료 — 제안 {proposal_count}명 검토 대상",
}


# 4대보험 고지 대사 — 대사 후 사람용 요약(2 step). 대사(비교) 전용이라 승인 불필요.
INSURANCE_RECONCILE = {
	"name": "insurance_reconcile",
	"description": "4대보험 고지내역 대사 — 엔진 계산 vs 공단 고지를 1원 단위로 대사하고 요약한다.",
	"steps": [
		{"tool": "reconcile_contributions", "args": {}},
		{"tool": "summarize_reconciliation_ko", "args": {}},
	],
	"requires_approval": False,
	"output_summary_template": "4대보험 대사 완료 — 불일치 {diff_count}건",
}


def get_builtin_skills() -> list[dict]:
	"""빌트인 스킬 정의 목록을 반환한다(호출자가 변형해도 원본 불변하도록 복사)."""
	import copy

	return [copy.deepcopy(HOURLY_CLOSING_PREP), copy.deepcopy(INSURANCE_RECONCILE)]


def register_builtin_skills(registry: "object", *, overwrite: bool = False) -> list[str]:
	"""SkillRegistry에 빌트인 스킬을 모두 등록한다. 등록된 name 목록을 반환한다."""
	names = []
	for defn in get_builtin_skills():
		registry.register(defn, overwrite=overwrite)
		names.append(defn["name"])
	return names
