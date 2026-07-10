# -*- coding: utf-8 -*-
"""LLM 자격증명 라우팅 — BYOK(테넌트 자기 키) → 플랫폼 키(운영자 지불) 폴백.

Hermes 임베딩 설계(docs/korea_hrms/hermes-embedding.md)의 과금 모델:
- **byok**: 테넌트 site_config에 자기 키(`agent_llm_api_key`) — 비용은 테넌트 부담.
- **platform**: 플랫폼 환경변수(`PLATFORM_LLM_API_KEY`) — 비용은 운영자(우리) 부담.
- **not_configured**: 둘 다 없음 — 에이전트는 fail-closed(네트워크 0회).

원칙:
- 이 모듈은 **키를 읽어 dict로 돌려줄 뿐 네트워크 호출 없음** (framework-free).
- 외부 노출용 상태에는 **키 원문을 절대 포함하지 않는다**(api_key_present bool만).
- provider 문자열은 Hermes cli-config의 provider 명칭과 호환(anthropic/openrouter/openai 등).
"""
from __future__ import annotations

from typing import Any, Mapping

# 테넌트(site_config) 키 이름
TENANT_KEY = "agent_llm_api_key"
TENANT_PROVIDER = "agent_llm_provider"
TENANT_MODEL = "agent_llm_model"
# 플랫폼(환경변수) 키 이름
PLATFORM_KEY = "PLATFORM_LLM_API_KEY"
PLATFORM_PROVIDER = "PLATFORM_LLM_PROVIDER"
PLATFORM_MODEL = "PLATFORM_LLM_MODEL"

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-5"


def _clean(value: Any) -> str:
	return str(value).strip() if value not in (None, "") else ""


def resolve_llm_credentials(
	site_conf: Mapping[str, Any] | None,
	env: Mapping[str, str] | None,
) -> dict[str, Any]:
	"""자격증명 해석. 우선순위: 테넌트 BYOK → 플랫폼 → not_configured.

	Returns (키 원문 포함 — 내부 전용, 외부 응답에는 public_status()를 쓸 것):
		{"billing": "byok"|"platform"|None, "status": "ok"|"not_configured",
		 "provider": str, "model": str, "api_key": str|None, "source": str}
	"""
	site_conf = site_conf or {}
	env = env or {}

	tenant_key = _clean(site_conf.get(TENANT_KEY))
	if tenant_key:
		return {
			"status": "ok",
			"billing": "byok",
			"source": f"site_config.{TENANT_KEY}",
			"provider": _clean(site_conf.get(TENANT_PROVIDER)) or DEFAULT_PROVIDER,
			"model": _clean(site_conf.get(TENANT_MODEL)) or DEFAULT_MODEL,
			"api_key": tenant_key,
		}

	platform_key = _clean(env.get(PLATFORM_KEY))
	if platform_key:
		return {
			"status": "ok",
			"billing": "platform",
			"source": f"env.{PLATFORM_KEY}",
			"provider": _clean(env.get(PLATFORM_PROVIDER)) or DEFAULT_PROVIDER,
			"model": _clean(env.get(PLATFORM_MODEL)) or DEFAULT_MODEL,
			"api_key": platform_key,
		}

	return {
		"status": "not_configured",
		"billing": None,
		"source": None,
		"provider": None,
		"model": None,
		"api_key": None,
	}


def public_status(credentials: dict[str, Any]) -> dict[str, Any]:
	"""외부 응답용 상태 — **키 원문 제거**, 존재 여부만."""
	return {
		"status": credentials.get("status"),
		"billing": credentials.get("billing"),
		"source": credentials.get("source"),
		"provider": credentials.get("provider"),
		"model": credentials.get("model"),
		"api_key_present": bool(credentials.get("api_key")),
	}
