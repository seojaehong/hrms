# -*- coding: utf-8 -*-
"""스킬 정의 스키마 + 레지스트리 — framework-free 코어.

에이전트가 실행할 "스킬"을 dict 정의로 등록·검증·조회한다. 스킬 정의는
프롬프트 빌더(prompt_builder)와 에이전트 루프(agent_loop)가 소비하는 계약이다.

스킬 정의 스키마:
- name (str, non-empty)            : 고유 식별자
- description (str)                 : 사람이 읽는 스킬 설명
- steps (list, non-empty)          : 각 step은 dict
    - tool (str, non-empty)          : 호출할 도구명 (tool_registry에 등록된 이름)
    - args (dict)                    : 도구 인자 매핑 (기본 {})
- requires_approval (bool)         : 확정 행위 여부 — True면 사람 승인 게이트 필요
- output_summary_template (str)    : 최종 요약 문자열 템플릿 (str.format 소비용)

선택 키:
- freeform (bool, 기본 False)      : 자유 질의 스킬 표시. True면 고정 steps를 강제하지
    않으므로 steps 빈 리스트를 허용한다(도구는 에이전트가 필요시에만 호출). 비-freeform
    스킬은 종전대로 steps 1개 이상을 요구한다(기존 계약 불변).

확정 행위는 human 승인 게이트(fail-closed) 원칙에 따라 requires_approval로 표시한다.
frappe 의존 없음 → `python3 hrms/tests/test_korea_agent_harness_skill_registry.py` 직접 실행 검증.
"""
from __future__ import annotations

from typing import Any


# 스킬 정의 필수 키 → 기대 타입
_REQUIRED_KEYS = {
	"name": str,
	"description": str,
	"steps": list,
	"requires_approval": bool,
	"output_summary_template": str,
}


def validate_skill_definition(defn: Any) -> dict:
	"""스킬 정의 dict를 검증한다. 잘못되면 ValueError(사유 포함). 통과 시 그대로 반환."""
	if not isinstance(defn, dict):
		raise ValueError(f"스킬 정의는 dict여야 함 (got {type(defn).__name__})")

	# 필수 키 존재 + 타입
	for key, expected_type in _REQUIRED_KEYS.items():
		if key not in defn:
			raise ValueError(f"스킬 정의에 필수 키 누락: '{key}'")
		value = defn[key]
		# bool은 int의 하위타입이므로 명시 검사; 그 외는 isinstance
		if expected_type is bool:
			if not isinstance(value, bool):
				raise ValueError(f"'{key}'는 bool이어야 함 (got {type(value).__name__})")
		elif not isinstance(value, expected_type):
			raise ValueError(
				f"'{key}'는 {expected_type.__name__}이어야 함 (got {type(value).__name__})"
			)

	name = defn["name"]
	if not name.strip():
		raise ValueError("'name'은 빈 문자열일 수 없음")

	# freeform(자유 질의) 스킬은 고정 steps를 강제하지 않으므로 빈 steps 허용.
	# 비-freeform은 종전 계약(steps 1개 이상)을 그대로 유지한다.
	freeform = defn.get("freeform", False)
	if not isinstance(freeform, bool):
		raise ValueError(
			f"'freeform'은 bool이어야 함 (스킬 '{name}', got {type(freeform).__name__})"
		)

	steps = defn["steps"]
	if not steps and not freeform:
		raise ValueError(f"'steps'는 빈 리스트일 수 없음 (스킬 '{name}')")

	for idx, step in enumerate(steps):
		if not isinstance(step, dict):
			raise ValueError(
				f"steps[{idx}]는 dict여야 함 (스킬 '{name}', got {type(step).__name__})"
			)
		tool = step.get("tool")
		if not isinstance(tool, str) or not tool.strip():
			raise ValueError(
				f"steps[{idx}]에 non-empty 'tool'(str) 필요 (스킬 '{name}')"
			)
		args = step.get("args", {})
		if not isinstance(args, dict):
			raise ValueError(
				f"steps[{idx}]의 'args'는 dict여야 함 (스킬 '{name}', got {type(args).__name__})"
			)

	return defn


class SkillRegistry:
	"""검증된 스킬 정의를 name으로 저장·조회하는 레지스트리."""

	def __init__(self) -> None:
		self._skills: dict[str, dict] = {}

	def register(self, defn: dict, *, overwrite: bool = False) -> dict:
		"""스킬 정의를 검증 후 등록한다. 중복 name은 overwrite=False면 ValueError."""
		validate_skill_definition(defn)
		name = defn["name"]
		if name in self._skills and not overwrite:
			raise ValueError(f"이미 등록된 스킬: '{name}' (overwrite=True로 덮어쓰기)")
		self._skills[name] = defn
		return defn

	def get(self, name: str) -> dict:
		"""등록된 스킬 정의를 반환한다. 미등록이면 KeyError."""
		if name not in self._skills:
			raise KeyError(f"미등록 스킬: '{name}'")
		return self._skills[name]

	def has(self, name: str) -> bool:
		return name in self._skills

	def list_skills(self) -> list[str]:
		"""등록된 스킬 name 목록(등록 순)."""
		return list(self._skills.keys())
