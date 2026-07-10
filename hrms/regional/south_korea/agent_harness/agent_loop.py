# -*- coding: utf-8 -*-
"""에이전트 루프 코어 — provider 주입식. framework-free 코어.

LLM 벤더와 무관하게 도구 호출 루프를 돈다. provider는 callable(messages)->응답 dict로
주입되므로 테스트는 fake provider를 넘긴다(API 키·네트워크 불필요).

계약:
- provider(messages) 응답이 {"text": ...} 이면 종료(final text 반환).
- {"tool_call": {"name":..., "args":..., "human_approved"?:...}} 이면 tool_registry로
  실행 후 결과를 대화(messages)에 추가하고 계속.
- max_steps 상한 도달 시 무한루프 없이 명시적으로 종료(status로 표시).

승인 게이트: tool_call에 human_approved=True가 명시되지 않으면 tool_registry가
fail-closed로 거부한다(확정 행위). agent_loop은 승인 여부를 그대로 전파만 한다.

frappe 의존 없음 → `python3 hrms/tests/test_korea_agent_harness_agent_loop.py` 직접 실행 검증.
"""
from __future__ import annotations

from typing import Any, Callable

DEFAULT_MAX_STEPS = 8


def run_agent_loop(
	provider: Callable[[list], dict],
	messages: list,
	tool_registry: Any,
	max_steps: int = DEFAULT_MAX_STEPS,
) -> dict:
	"""provider 주입식 도구 호출 루프를 실행한다.

	provider는 현재 messages를 받아 다음 행동(dict)을 반환한다:
	- {"text": <str>} → 최종 응답. 루프 종료.
	- {"tool_call": {"name": <str>, "args": <dict>, "human_approved"?: <bool>}} →
	  tool_registry.call로 실행, 결과를 messages에 추가하고 계속.

	반환 dict: {final_text, status, steps, tool_calls, messages}.
	status ∈ {"completed", "max_steps_exceeded"}.
	tool_calls는 tool_registry가 반환한 구조화 호출 결과의 누적 리스트.
	messages는 도구 호출/결과가 반영된 대화(입력을 복사해 갱신 — 호출자 리스트 불변).
	"""
	if not callable(provider):
		raise ValueError("provider는 callable(messages)->dict 이어야 함")
	if not isinstance(messages, list):
		raise ValueError(f"messages는 list여야 함 (got {type(messages).__name__})")
	if not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps < 1:
		raise ValueError(f"max_steps는 1 이상의 int여야 함 (got {max_steps!r})")

	convo = list(messages)  # 호출자 리스트를 변형하지 않도록 복사
	tool_calls: list[dict] = []
	final_text: str | None = None
	status = "max_steps_exceeded"
	steps = 0

	while steps < max_steps:
		steps += 1
		response = provider(convo)
		if not isinstance(response, dict):
			raise ValueError(
				f"provider 응답은 dict여야 함 (step {steps}, got {type(response).__name__})"
			)

		if "text" in response:
			final_text = response["text"]
			convo.append({"role": "assistant", "text": final_text})
			status = "completed"
			break

		if "tool_call" in response:
			call = response["tool_call"]
			if not isinstance(call, dict) or not call.get("name"):
				raise ValueError(f"tool_call은 name을 가진 dict여야 함 (step {steps}, got {call!r})")
			name = call["name"]
			args = call.get("args") or {}
			human_approved = call.get("human_approved", False)
			convo.append({"role": "assistant", "tool_call": {"name": name, "args": args}})
			try:
				result = tool_registry.call(name, args, human_approved=human_approved)
			except Exception as exc:  # 미등록 도구 등(ToolError) → 대화로 피드백
				result = {"tool": name, "args": args, "status": "error", "error": str(exc)}
			tool_calls.append(result)
			convo.append({"role": "tool", "tool": name, "result": result})
			continue

		raise ValueError(
			f"provider 응답은 'text' 또는 'tool_call' 키가 필요함 (step {steps}, keys={sorted(response.keys())})"
		)

	return {
		"final_text": final_text,
		"status": status,
		"steps": steps,
		"tool_calls": tool_calls,
		"messages": convo,
	}
