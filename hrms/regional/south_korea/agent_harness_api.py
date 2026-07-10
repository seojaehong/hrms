# -*- coding: utf-8 -*-
"""Frappe 연동 API — Agent Harness 스킬 실행 엔드포인트 (whitelist 래퍼).

이 모듈은 Frappe RPC 레이어에 노출되는 함수를 정의한다.
내부 로직(스킬 등록·도구 실행·에이전트 루프)은 agent_harness/ 코어에 위임한다.

테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import한다 (insurance_filing_api.py 컨벤션).

안전 불변식:
  - LLM provider 미설정이면 어떤 LLM/네트워크 호출도 하지 않고 즉시 not_configured
    반환 (fail-closed). provider 해석은 config 읽기만 하며 클라이언트를 만들지 않는다.
  - 미등록 skill_name은 명시적 오류 status(unknown_skill)로 거부한다(조용한 통과 금지).
  - 확정 행위(requires_approval) 도구는 코어 tool_registry가 human_approved 게이트로 차단.
"""

from __future__ import annotations

import importlib.util as _ilu
import pathlib as _pl
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Frappe 조건부 import — framework-free 테스트 환경에서 안전하게 로드
# ---------------------------------------------------------------------------
try:
	import frappe as _frappe  # noqa: PLC0415

	_FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
	_frappe = None  # type: ignore[assignment]
	_FRAPPE_AVAILABLE = False


def _whitelist(fn):
	"""@frappe.whitelist() 데코레이터 — Frappe 없으면 no-op."""
	if _FRAPPE_AVAILABLE and _frappe is not None:
		return _frappe.whitelist()(fn)
	return fn


# ---------------------------------------------------------------------------
# agent_harness 코어 동적 로드 (importlib으로 frappe 패키지 경로 우회)
# 코어는 agent_harness/ 하위 디렉터리에 있다(래퍼 자신의 디렉터리가 아님).
# ---------------------------------------------------------------------------
_CORE_DIR = _pl.Path(__file__).resolve().parent / "agent_harness"


def _load_core(name: str):
	path = _CORE_DIR / f"{name}.py"
	spec = _ilu.spec_from_file_location(f"_korea_agent_harness_{name}_core", path)
	module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
	spec.loader.exec_module(module)  # type: ignore[union-attr]
	return module


_skill_registry = _load_core("skill_registry")
_builtin_skills = _load_core("builtin_skills")
_agent_loop = _load_core("agent_loop")

# site config 키 — 이 키가 있어야 provider가 설정된 것으로 본다(값 읽기만, 네트워크 없음).
PROVIDER_CONFIG_KEY = "korea_agent_harness_provider"


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


@_whitelist
def run_agent_skill(
	skill_name: str,
	args: dict | None = None,
	human_approved: bool | str = False,
	provider: Callable[[list], dict] | None = None,
	tool_registry: Any | None = None,
	max_steps: int = 8,
) -> dict[str, Any]:
	"""빌트인 스킬을 에이전트 루프로 실행한다(프로바이더 주입식).

	Args:
		skill_name: 실행할 빌트인 스킬 이름(hourly_closing_prep / insurance_reconcile).
		args: 스킬/도구에 전달할 인자(선택).
		human_approved: 확정 행위 도구 승인 여부(코어 tool_registry 게이트로 전파).
		provider: callable(messages)->dict. 미지정 시 site config에서 해석.
		tool_registry: 도구 레지스트리(주입식). provider가 있을 때만 사용.
		max_steps: 에이전트 루프 상한.

	Returns:
		- 미등록 스킬: {'status': 'unknown_skill', 'available': [...]} (LLM 호출 없음).
		- provider 미설정: {'status': 'not_configured', ...} (LLM/네트워크 0회).
		- 실행: {'status': 'completed'|'max_steps_exceeded', 'final_text': ..., ...}.
	"""
	args = dict(args or {})

	# --- 1) 스킬 존재 검증 (순수 in-memory 조회 — 네트워크 없음) ---
	registry = _skill_registry.SkillRegistry()
	_builtin_skills.register_builtin_skills(registry)
	if not registry.has(skill_name):
		return {
			"status": "unknown_skill",
			"skill_name": skill_name,
			"available": registry.list_skills(),
			"reason": f"미등록 스킬: '{skill_name}' (빌트인 스킬만 실행 가능).",
		}

	# --- 2) provider 해석 (config 읽기만 — 클라이언트 생성·네트워크 없음) ---
	if provider is None:
		provider = _resolve_provider()
	if provider is None:
		# fail-closed: provider 미설정이면 어떤 LLM/네트워크 호출도 하지 않는다.
		return {
			"status": "not_configured",
			"skill_name": skill_name,
			"reason": (
				f"LLM provider 미설정 — site config '{PROVIDER_CONFIG_KEY}' 없이는 "
				"스킬을 실행하지 않습니다 (네트워크 호출 0회)."
			),
			"requires_provider_config": True,
		}

	# --- 3) 실행 (provider 주입됨) — 코어 tool_registry가 승인 게이트 담당 ---
	if tool_registry is None:
		# 사이트 실행 시 도구 바인딩은 별도 배선이 필요하다(PoC 범위 밖).
		return {
			"status": "no_tools",
			"skill_name": skill_name,
			"reason": "tool_registry 미주입 — 도구 바인딩 없이는 스킬을 실행하지 않습니다.",
		}

	skill = registry.get(skill_name)
	messages = [{"role": "user", "skill": skill_name, "args": args}]
	loop_result = _agent_loop.run_agent_loop(
		provider, messages, tool_registry, max_steps=max_steps
	)
	return {
		"status": loop_result["status"],
		"skill_name": skill_name,
		"final_text": loop_result["final_text"],
		"steps": loop_result["steps"],
		"tool_calls": loop_result["tool_calls"],
	}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _resolve_provider() -> Callable[[list], dict] | None:
	"""site config에서 provider 설정을 읽는다(값 읽기만 — 클라이언트 생성·네트워크 없음).

	PoC 단계에서는 실제 LLM 클라이언트를 배선하지 않는다. config에 provider 키가
	없으면 None을 반환해 호출부가 not_configured로 거부하도록 한다.
	"""
	if not (_FRAPPE_AVAILABLE and _frappe is not None):
		return None
	conf = getattr(_frappe, "conf", None)
	if not conf:
		return None
	# config 값 존재만 확인 — 실제 클라이언트 배선은 Hermes 내재화 단계로 미룬다.
	if not conf.get(PROVIDER_CONFIG_KEY):
		return None
	return None
