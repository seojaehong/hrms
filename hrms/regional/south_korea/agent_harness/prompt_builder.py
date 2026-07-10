# -*- coding: utf-8 -*-
"""하네스 프롬프트 빌더 — 캐시 친화 시스템 프롬프트 조립. framework-free 코어.

모든 에이전트 호출에 불변 도메인 원칙을 강제 주입하고, prefix 캐싱을 극대화하도록
불변부(원칙·스킬·도구스펙)를 앞에, 가변부(테넌트 컨텍스트)를 마지막에 배치한다.

조립 순서(4섹션):
  ① 불변 도메인 원칙  — 모듈 상수(하드코딩). 호출자가 덮어쓸 수 없음.
  ② 스킬 정의        — skill_registry 스키마 dict.
  ③ 도구 스펙        — tool_registry.get_spec 등이 제공하는 name→spec 매핑.
  ④ 테넌트 컨텍스트   — 주입값(가변). 항상 마지막(prefix 캐시 경계).

frappe 의존 없음 → `python3 hrms/tests/test_korea_agent_harness_prompt_builder.py` 직접 실행 검증.
"""
from __future__ import annotations

from typing import Any


# 불변 도메인 원칙 — 하드코딩된 불변 텍스트. build_system_prompt가 이 상수를
# 그대로 사용하며, 호출자가 넘기는 인자로 덮어쓸 수 없다.
IMMUTABLE_DOMAIN_PRINCIPLES: tuple[str, ...] = (
	"급여·세금·퇴직금 등 모든 금액은 1원 단위로 검증한다. 반올림·추정 금지.",
	"확정 행위(신고·발송·확정 저장)는 사람 승인 게이트를 통과해야 실행한다(fail-closed).",
	"테넌트(사업장) 데이터는 격리한다. 다른 테넌트의 데이터를 참조·혼합하지 않는다.",
)

# 섹션 헤더 — 조립 순서·경계 식별용 상수.
_SECTION_PRINCIPLES = "## 불변 도메인 원칙"
_SECTION_SKILL = "## 스킬 정의"
_SECTION_TOOLS = "## 도구 스펙"
_SECTION_TENANT = "## 테넌트 컨텍스트"


def build_system_prompt(
	skill_defn: dict,
	tool_specs: dict[str, dict],
	tenant_context: dict,
) -> str:
	"""4개 섹션을 순서대로 조립한 시스템 프롬프트 문자열을 반환한다.

	불변부(①원칙 ②스킬 ③도구스펙)가 앞, 가변부(④테넌트 컨텍스트)가 마지막이다.
	같은 skill_defn·tool_specs로 빌드하면 테넌트 섹션 직전까지 prefix가 동일하다.
	"""
	if not isinstance(skill_defn, dict):
		raise ValueError(f"skill_defn은 dict여야 함 (got {type(skill_defn).__name__})")
	if not isinstance(tool_specs, dict):
		raise ValueError(f"tool_specs는 dict여야 함 (got {type(tool_specs).__name__})")
	if not isinstance(tenant_context, dict):
		raise ValueError(f"tenant_context는 dict여야 함 (got {type(tenant_context).__name__})")

	parts = [
		_render_principles(),
		_render_skill(skill_defn),
		_render_tools(tool_specs),
		_render_tenant(tenant_context),
	]
	# 불변부(앞 3섹션)와 가변부(테넌트) 사이 경계가 명확하도록 이중 개행으로 연결.
	return "\n\n".join(parts)


def _render_principles() -> str:
	"""① 불변 도메인 원칙 — 모듈 상수를 그대로 렌더(호출자 주입 불가)."""
	lines = [_SECTION_PRINCIPLES]
	for idx, principle in enumerate(IMMUTABLE_DOMAIN_PRINCIPLES, start=1):
		lines.append(f"{idx}. {principle}")
	return "\n".join(lines)


def _render_skill(skill_defn: dict) -> str:
	"""② 스킬 정의 — name/description/steps/requires_approval를 렌더."""
	name = skill_defn.get("name", "")
	description = skill_defn.get("description", "")
	requires_approval = skill_defn.get("requires_approval", False)
	steps = skill_defn.get("steps", [])

	lines = [_SECTION_SKILL]
	lines.append(f"name: {name}")
	lines.append(f"description: {description}")
	lines.append(f"requires_approval: {requires_approval}")
	lines.append("steps:")
	for idx, step in enumerate(steps, start=1):
		tool = step.get("tool", "")
		args = step.get("args", {})
		lines.append(f"  {idx}. tool={tool} args={_render_kv(args)}")
	return "\n".join(lines)


def _render_tools(tool_specs: dict[str, dict]) -> str:
	"""③ 도구 스펙 — name→spec 매핑을 정렬된 순서로 렌더(결정적 prefix)."""
	lines = [_SECTION_TOOLS]
	for name in sorted(tool_specs.keys()):
		spec = tool_specs[name]
		lines.append(f"- {name}: {_render_kv(spec)}")
	return "\n".join(lines)


def _render_tenant(tenant_context: dict) -> str:
	"""④ 테넌트 컨텍스트 — 주입 가변값(항상 마지막 섹션)."""
	lines = [_SECTION_TENANT]
	for key in sorted(tenant_context.keys()):
		lines.append(f"{key}: {tenant_context[key]}")
	return "\n".join(lines)


def _render_kv(mapping: Any) -> str:
	"""dict를 결정적(키 정렬) 문자열로 렌더 — prefix 안정성 확보."""
	if not isinstance(mapping, dict):
		return str(mapping)
	if not mapping:
		return "{}"
	items = ", ".join(f"{k}={mapping[k]}" for k in sorted(mapping.keys()))
	return "{" + items + "}"
