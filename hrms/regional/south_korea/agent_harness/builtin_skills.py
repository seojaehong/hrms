# -*- coding: utf-8 -*-
"""빌트인 스킬 정의 — framework-free 코어.

실무 스킬을 US-001 스킬 스키마(skill_registry) 그대로 정의한다. 스킬 정의는
순수 데이터(dict)이며, step["tool"] 이름은 tool_registry에 등록된 도구명과 매칭된다.
빌트인 스킬은 조회/대사(read-only) 성격이라 requires_approval=False다(확정 행위 아님).

정의된 스킬(모두 freeform — 스텝 간 데이터 흐름이 필요해 고정 steps 대신 에이전트가
실 MCP 도구를 오케스트레이션):
- hourly_closing_prep : 시급 마감 준비. get_tenant_records→get_attendance_closing_period
  →summarize_attendance→estimate_hourly_pay로 시급직원 마감을 요약한다.
- insurance_reconcile : 4대보험 고지 대사. build_statutory_payroll로 computed 산출 후
  args의 공단 고지(notified)와 check_insurance_reconciliation으로 1원 단위 대조한다.
- hr_freeform_qa      : 자유 질의. 자연어 HR 질문에 실 도구(get_tenant_records·
  calculate_annual_leave·estimate_hourly_pay 등)를 필요시에만 호출해 답한다.
- leave_manage        : 연차 관리. get_tenant_records로 기초 정보를 조회하고
  calculate_annual_leave로 직원별 연차 발생일수를 산정한다.
- severance_settle    : 퇴직 정산. calculate_severance로 퇴직금을 산정하고
  build_statutory_payroll로 법정공제를 산출한다.

frappe 의존 없음 → `python3 hrms/tests/test_korea_agent_harness_builtin_skills.py` 직접 실행 검증.
"""
from __future__ import annotations


# 시급 마감 준비 — 실 도구로 시급직원 조회→근태 마감→gross 산정 후 요약(freeform).
# 스텝 간 데이터 흐름이 필요해 고정 steps 대신 freeform으로 오케스트레이션. 조회/계산 전용이라 승인 불필요.
HOURLY_CLOSING_PREP = {
	"name": "hourly_closing_prep",
	"description": (
		"시급 근로자 월 마감 준비. 실제 도구로 수행한다: get_tenant_records로 시급제 "
		"직원(Employee) 명단을 조회하고, get_attendance_closing_period로 대상 월 마감 "
		"기간을 확인한 뒤, summarize_attendance로 직원별 근태를 마감 요약하고, "
		"estimate_hourly_pay로 개별 월 gross를 산정해 검토 대상을 요약한다. 시급 미설정·"
		"근태 결측 직원은 명단으로 노출하고, 확인되지 않은 값은 지어내지 않는다."
	),
	"steps": [],
	"freeform": True,
	"requires_approval": False,
	"output_summary_template": "",
}


# 4대보험 고지 대사 — 우리 계산(computed) vs 공단 고지(notified) 대조(freeform).
# 고지 데이터 없으면 지어내지 않고 필요사항 안내. 대사(비교) 전용이라 승인 불필요.
INSURANCE_RECONCILE = {
	"name": "insurance_reconcile",
	"description": (
		"4대보험 고지내역 대사. build_statutory_payroll로 우리 계산(computed) 공제액을 "
		"산출하고, args로 제공된 공단 고지내역(notified)과 check_insurance_reconciliation "
		"으로 1원 단위 대조해 과다/과소·양방향 누락을 한국어로 요약한다. 공단 고지 "
		"데이터가 제공되지 않으면 무엇이 필요한지 안내하고 임의 값을 지어내지 않는다."
	),
	"steps": [],
	"freeform": True,
	"requires_approval": False,
	"output_summary_template": "",
}


# 자유 질의 — 고정 steps 없이(freeform) 자연어 HR 질문에 답한다. 에이전트가 실제
# 조회/계산 도구(get_tenant_records·calculate_annual_leave·estimate_hourly_pay·
# check_insurance_reconciliation 등)를 필요시에만 호출해 근거와 함께 답변한다. 조회 전용이라
# 승인 불필요. steps 강제가 아니므로 최종 답변은 template가 아니라 에이전트 응답 text에서 나온다.
HR_FREEFORM_QA = {
	"name": "hr_freeform_qa",
	"description": (
		"사용자의 자연어 HR 질문에 실제 도구(get_tenant_records·calculate_annual_leave·"
		"estimate_hourly_pay·check_insurance_reconciliation 등)를 필요시에만 호출해 "
		"근거와 함께 답변한다."
	),
	"steps": [],
	"freeform": True,
	"requires_approval": False,
	"output_summary_template": "",
}


# 연차 관리 — 직원 명단 조회→직원별 연차 발생일수 산정(freeform).
# 입사일 등 확인 안 된 값은 지어내지 않는다. 조회/계산 전용이라 승인 불필요.
LEAVE_MANAGE = {
	"name": "leave_manage",
	"description": (
		"직원 연차 관리. get_tenant_records로 대상 직원(Employee)의 입사일 등 기초 "
		"정보를 조회하고, calculate_annual_leave로 직원별 연차 발생일수를 산정해 "
		"한국어로 요약한다. 입사일이 없거나 산정 기준이 불명확한 직원은 명단으로 "
		"노출하고, 확인되지 않은 값은 지어내지 않는다."
	),
	"steps": [],
	"freeform": True,
	"requires_approval": False,
	"output_summary_template": "",
}


# 퇴직 정산 — 퇴직금 산정→법정공제 산출(freeform).
# 평균임금·재직기간 등 확인 안 된 값은 지어내지 않는다. 조회/계산 전용이라 승인 불필요.
SEVERANCE_SETTLE = {
	"name": "severance_settle",
	"description": (
		"퇴직 정산. calculate_severance로 재직기간·평균임금 기준 퇴직금을 산정하고, "
		"build_statutory_payroll로 해당 지급액의 법정공제를 산출해 한국어로 요약한다. "
		"입·퇴사일이나 평균임금 산정 기초가 불명확하면 확인 필요 항목으로 노출하고, "
		"확인되지 않은 값은 지어내지 않는다."
	),
	"steps": [],
	"freeform": True,
	"requires_approval": False,
	"output_summary_template": "",
}


def get_builtin_skills() -> list[dict]:
	"""빌트인 스킬 정의 목록을 반환한다(호출자가 변형해도 원본 불변하도록 복사)."""
	import copy

	return [
		copy.deepcopy(HOURLY_CLOSING_PREP),
		copy.deepcopy(INSURANCE_RECONCILE),
		copy.deepcopy(HR_FREEFORM_QA),
		copy.deepcopy(LEAVE_MANAGE),
		copy.deepcopy(SEVERANCE_SETTLE),
	]


def register_builtin_skills(registry: "object", *, overwrite: bool = False) -> list[str]:
	"""SkillRegistry에 빌트인 스킬을 모두 등록한다. 등록된 name 목록을 반환한다."""
	names = []
	for defn in get_builtin_skills():
		registry.register(defn, overwrite=overwrite)
		names.append(defn["name"])
	return names
