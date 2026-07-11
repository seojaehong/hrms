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


def _protocol_instruction(tool_specs: dict[str, dict]) -> str:
	"""프롬프트 프로토콜 툴콜링 지시문 — gateway가 에이전트 엔드포인트라 OpenAI
	tools 파라미터가 모델에 전달되지 않으므로, 텍스트 프로토콜로 도구 호출을 선언시킨다."""
	lines = [
		"[도구 호출 프로토콜] 아래 도구가 필요하면 다른 텍스트 없이 오직 한 줄의 JSON만 출력하라:",
		'{"tool_call": {"name": "<도구명>", "args": {<인자>}}}',
		"도구 결과는 다음 메시지로 돌아온다. 더 이상 도구가 필요 없으면 일반 텍스트로 최종 답변하라.",
		"사용 가능 도구:",
	]
	for name, spec in tool_specs.items():
		desc = str((spec or {}).get("description", "")).strip()
		lines.append(f"- {name}: {desc}")
	return "\n".join(lines)


def _extract_tool_call(text: str, allowed: set[str]) -> dict | None:
	"""텍스트에서 {"tool_call": …} JSON을 관대하게 추출한다 (코드펜스·전후 산문 허용).

	allowed 밖의 도구명은 파싱하지 않고 None을 반환한다 — 화이트리스트의 최종 방어는
	tool_registry지만, 프로토콜 오염(모델이 임의 도구명을 지어내는 경우)을 여기서 차단한다.
	"""
	marker = '{"tool_call"'
	idx = text.find(marker)
	if idx < 0:
		return None
	decoder = json.JSONDecoder()
	try:
		obj, _end = decoder.raw_decode(text[idx:])
	except json.JSONDecodeError:
		return None
	call = obj.get("tool_call") if isinstance(obj, dict) else None
	if not isinstance(call, dict) or not call.get("name"):
		return None
	if str(call["name"]) not in allowed:
		return None
	args = call.get("args")
	return {"name": str(call["name"]), "args": args if isinstance(args, dict) else {}}


def make_hermes_provider(
	*,
	base_url: str,
	credentials: dict[str, Any],
	transport: Callable[..., tuple[int, bytes]] | None = None,
	timeout: int = DEFAULT_TIMEOUT,
	session_id: str | None = None,
	tool_specs: dict[str, dict] | None = None,
) -> Callable[[list], dict]:
	"""agent_loop provider 생성.

	Args:
		base_url: Hermes gateway 주소 (예: http://127.0.0.1:8130).
		credentials: resolve_llm_credentials() 결과 — status=="ok" 필수(api_key/model 사용).
		transport: 테스트 주입용. (method, url, headers, body, timeout) -> (status, content).
		session_id: 지정 시 X-Hermes-Session-Id로 세션 연속성(선택).
		tool_specs: 지정 시 프롬프트 프로토콜 툴콜링 활성화 — 모델이 텍스트로
			{"tool_call": …} JSON을 선언하면 파싱해 agent_loop 계약으로 반환.
			(gateway /v1/chat/completions는 에이전트 엔드포인트라 OpenAI tools
			파라미터가 모델에 닿지 않는다 — 2026-07-11 실측.)
	"""
	if credentials.get("status") != "ok" or not credentials.get("api_key"):
		raise HermesProviderError("자격증명 미설정 — resolve_llm_credentials status가 ok여야 함")
	base = str(base_url or "").rstrip("/")
	if not base:
		raise HermesProviderError("base_url이 필요합니다")
	send = transport or _default_transport
	model = credentials.get("model") or "hermes-agent"
	api_key = credentials["api_key"]
	protocol = _protocol_instruction(tool_specs) if tool_specs else None
	allowed_tools = set(tool_specs.keys()) if tool_specs else set()

	def provider(messages: list) -> dict:
		headers = {
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
		}
		if session_id:
			headers["X-Hermes-Session-Id"] = str(session_id)
		openai_messages = _to_openai_messages(messages)
		if protocol:
			# 기존 system(하네스 소유 프롬프트) 바로 뒤에 프로토콜 지시를 system으로 삽입
			insert_at = 1 if openai_messages and openai_messages[0].get("role") == "system" else 0
			openai_messages.insert(insert_at, {"role": "system", "content": protocol})
		payload = {"model": model, "messages": openai_messages}
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

		content = message.get("content") or ""
		if protocol:
			parsed = _extract_tool_call(content, allowed_tools)
			if parsed:
				return {"tool_call": parsed}
		return {"text": content}

	return provider
