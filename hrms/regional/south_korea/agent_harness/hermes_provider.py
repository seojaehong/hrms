# -*- coding: utf-8 -*-
"""HermesProvider — agent_loop의 provider 계약을 Hermes gateway 호출로 구현.

Hermes gateway(api_server)는 OpenAI 호환 `/v1/chat/completions`를 노출한다
(서버: claudebot-2 ~/workspaces/hermes-agent, docs/korea_hrms/hermes-embedding.md).
이 어댑터는 우리 대화(messages)를 OpenAI 형식으로 변환해 호출하고, 응답을
agent_loop 계약({"text": ...} 또는 {"tool_call": {...}})으로 되돌린다.

- 자격증명은 llm_credentials.resolve_llm_credentials 결과를 주입(BYOK/플랫폼).
- transport 주입식(framework-free 테스트, 실HTTP 0회). 기본 transport는 requests 지연 import.
- 승인 게이트는 여기 아님 — tool_registry가 담당(모델이 human_approved를 지어내도
  read_only=False 도구는 레지스트리가 차단).
"""
from __future__ import annotations

import json
from typing import Any, Callable

DEFAULT_TIMEOUT = 300  # Hermes 풀 하네스(대형 시스템프롬프트+자체 도구) 왕복 여유
_VALID_ROLES = ("system", "user", "assistant", "tool")


class HermesProviderError(RuntimeError):
	"""gateway 호출 실패 (전송/HTTP/형식)."""


def _default_transport(method: str, url: str, headers: dict, body: bytes, timeout: int) -> tuple[int, bytes]:
	import requests  # noqa: PLC0415

	resp = requests.request(method, url, headers=headers, data=body, timeout=timeout)
	return resp.status_code, resp.content


def _to_openai_messages(messages: list) -> list[dict[str, Any]]:
	"""내부 대화 → OpenAI 메시지. 표준 role이 아니면 내용을 user 텍스트로 직렬화
	(도구 결과 dict 등 — PoC 단순화, 정보 손실 없음)."""
	out: list[dict[str, Any]] = []
	for msg in messages:
		if isinstance(msg, dict) and msg.get("role") in _VALID_ROLES and isinstance(msg.get("content"), str):
			out.append({"role": msg["role"], "content": msg["content"]})
		else:
			out.append({"role": "user", "content": json.dumps(msg, ensure_ascii=False, default=str)})
	return out


def make_hermes_provider(
	*,
	base_url: str,
	credentials: dict[str, Any],
	transport: Callable[..., tuple[int, bytes]] | None = None,
	timeout: int = DEFAULT_TIMEOUT,
	session_id: str | None = None,
) -> Callable[[list], dict]:
	"""agent_loop provider 생성.

	Args:
		base_url: Hermes gateway 주소 (예: http://127.0.0.1:8130).
		credentials: resolve_llm_credentials() 결과 — status=="ok" 필수(api_key/model 사용).
		transport: 테스트 주입용. (method, url, headers, body, timeout) -> (status, content).
		session_id: 지정 시 X-Hermes-Session-Id로 세션 연속성(선택).
	"""
	if credentials.get("status") != "ok" or not credentials.get("api_key"):
		raise HermesProviderError("자격증명 미설정 — resolve_llm_credentials status가 ok여야 함")
	base = str(base_url or "").rstrip("/")
	if not base:
		raise HermesProviderError("base_url이 필요합니다")
	send = transport or _default_transport
	model = credentials.get("model") or "hermes-agent"
	api_key = credentials["api_key"]

	def provider(messages: list) -> dict:
		headers = {
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
		}
		if session_id:
			headers["X-Hermes-Session-Id"] = str(session_id)
		payload = {"model": model, "messages": _to_openai_messages(messages)}
		status, content = send("POST", f"{base}/v1/chat/completions", headers, json.dumps(payload, ensure_ascii=False).encode(), timeout)
		if status != 200:
			raise HermesProviderError(f"gateway HTTP {status}: {content[:300]!r}")
		try:
			data = json.loads(content)
		except json.JSONDecodeError as exc:
			raise HermesProviderError(f"gateway 응답 JSON 아님: {content[:200]!r}") from exc
		choices = data.get("choices") or []
		if not choices:
			raise HermesProviderError(f"gateway 응답에 choices 없음: {data!r}")
		message = choices[0].get("message") or {}

		# OpenAI tool_calls → agent_loop tool_call 계약 (첫 호출만 — 루프가 순차 처리)
		tool_calls = message.get("tool_calls") or []
		if tool_calls:
			fn = (tool_calls[0].get("function") or {})
			try:
				args = json.loads(fn.get("arguments") or "{}")
			except json.JSONDecodeError:
				args = {"_raw_arguments": fn.get("arguments")}
			return {"tool_call": {"name": fn.get("name"), "args": args}}

		return {"text": message.get("content") or ""}

	return provider
