# -*- coding: utf-8 -*-
"""도구 레지스트리 — 화이트리스트 바인딩 + fail-closed 승인 게이트. framework-free 코어.

에이전트 루프(agent_loop)가 소비하는 도구 실행 계약이다. 스킬 정의(skill_registry)의
step["tool"] 이름이 여기 등록된 도구명과 매칭된다.

핵심 원칙:
- 화이트리스트: register_tool로 등록된 도구만 call 가능. 미등록 호출은 차단(예외).
- fail-closed 승인 게이트: read_only=False(확정 행위) 도구는 human_approved=True가
  명시되지 않으면 fn을 호출하지 않고 거부한다. 조용한 통과 금지.
- 호출 로그: 모든 call은 구조화 로그(도구명·인자·결과요약·상태)를 누적한다.

frappe 의존 없음 → `python3 hrms/tests/test_korea_agent_harness_tool_registry.py` 직접 실행 검증.
"""
from __future__ import annotations

from typing import Any, Callable


class ToolError(Exception):
	"""도구 실행 계약 위반(미등록·비승인 write 등)."""


class ToolRegistry:
	"""이름→callable+스펙+read_only 플래그를 바인딩하는 도구 레지스트리."""

	def __init__(self) -> None:
		self._tools: dict[str, dict] = {}
		self._call_log: list[dict] = []

	def register_tool(
		self,
		name: str,
		fn: Callable[..., Any],
		spec: dict,
		read_only: bool,
		*,
		overwrite: bool = False,
	) -> None:
		"""도구를 등록한다. name→(fn, spec, read_only) 바인딩.

		read_only=True는 조회 전용(승인 불필요), False는 확정 행위(승인 게이트 필요).
		"""
		if not isinstance(name, str) or not name.strip():
			raise ValueError(f"도구 name은 non-empty str이어야 함 (got {name!r})")
		if not callable(fn):
			raise ValueError(f"도구 fn은 callable이어야 함 (도구 '{name}')")
		if not isinstance(spec, dict):
			raise ValueError(f"도구 spec은 dict여야 함 (도구 '{name}', got {type(spec).__name__})")
		# bool은 int 하위타입 → 명시 검사
		if not isinstance(read_only, bool):
			raise ValueError(f"read_only는 bool이어야 함 (도구 '{name}', got {type(read_only).__name__})")
		if name in self._tools and not overwrite:
			raise ValueError(f"이미 등록된 도구: '{name}' (overwrite=True로 덮어쓰기)")
		self._tools[name] = {"fn": fn, "spec": spec, "read_only": read_only}

	def has(self, name: str) -> bool:
		return name in self._tools

	def list_tools(self) -> list[str]:
		"""등록된 도구 name 목록(등록 순)."""
		return list(self._tools.keys())

	def get_spec(self, name: str) -> dict:
		"""등록된 도구 스펙을 반환한다. 미등록이면 KeyError."""
		if name not in self._tools:
			raise KeyError(f"미등록 도구: '{name}'")
		return self._tools[name]["spec"]

	def call(self, name: str, args: dict | None = None, *, human_approved: bool = False) -> dict:
		"""도구를 실행한다. 결과를 구조화 dict로 반환하며 호출 로그에 누적한다.

		- 미등록 도구: ToolError (fn 호출 없음).
		- read_only=False(확정 행위) + human_approved != True: 거부(fail-closed), fn 호출 없음.
		- 성공: fn(**args) 실행 후 결과 반환.

		반환 dict: {tool, args, status, result?, summary?, error?}.
		status ∈ {"ok", "blocked"}.
		"""
		args = args or {}
		if name not in self._tools:
			self._log(name, args, "blocked", error=f"미등록 도구: '{name}'")
			raise ToolError(f"미등록 도구 호출 차단: '{name}'")

		binding = self._tools[name]
		# fail-closed 승인 게이트: 확정 행위는 명시 승인 없으면 fn 미호출
		if not binding["read_only"] and human_approved is not True:
			return self._log(
				name,
				args,
				"blocked",
				error=f"확정 행위 '{name}'는 human_approved=True 필요(fail-closed)",
			)

		result = binding["fn"](**args)
		return self._log(name, args, "ok", result=result, summary=_summarize(result))

	def _log(self, name: str, args: dict, status: str, **extra: Any) -> dict:
		entry = {"tool": name, "args": args, "status": status}
		entry.update(extra)
		self._call_log.append(entry)
		return entry

	def get_call_log(self) -> list[dict]:
		"""누적된 호출 로그(호출 순)를 반환한다."""
		return list(self._call_log)


def _summarize(result: Any) -> str:
	"""결과 요약 문자열 — 로그 가독용(전체 페이로드 대신 짧은 표현)."""
	if isinstance(result, dict):
		return f"dict(keys={sorted(result.keys())})"
	if isinstance(result, (list, tuple)):
		return f"{type(result).__name__}(len={len(result)})"
	text = str(result)
	return text if len(text) <= 120 else text[:117] + "..."
