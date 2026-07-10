# -*- coding: utf-8 -*-
"""agent_harness/agent_loop.py 테스트 — provider 주입식 도구 호출 루프.

framework-free: agent_loop.py/tool_registry.py는 frappe import 없음.
hrms/__init__.py가 frappe를 import하므로 spec_from_file_location으로 직접 로드.
실행: python3 hrms/tests/test_korea_agent_harness_agent_loop.py
"""
import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_CORE_DIR = _REPO_ROOT / "hrms" / "regional" / "south_korea" / "agent_harness"


def _load(name):
	spec = importlib.util.spec_from_file_location(name, _CORE_DIR / f"{name}.py")
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


_loop_mod = _load("agent_loop")
_tool_mod = _load("tool_registry")

run_agent_loop = _loop_mod.run_agent_loop
ToolRegistry = _tool_mod.ToolRegistry


class _FakeProvider:
	"""스크립트된 응답을 순서대로 반환하는 fake provider. 호출 시 messages 스냅샷 기록."""

	def __init__(self, script):
		self.script = list(script)
		self.seen_messages = []

	def __call__(self, messages):
		self.seen_messages.append(list(messages))
		return self.script.pop(0)


class _Spy:
	def __init__(self, ret):
		self.ret = ret
		self.calls = []

	def __call__(self, **kwargs):
		self.calls.append(kwargs)
		return self.ret


def _registry_with(proposals, diff):
	reg = ToolRegistry()
	reg.register_tool("list_proposals", _Spy(proposals), {}, read_only=True)
	reg.register_tool("reconcile", _Spy(diff), {}, read_only=True)
	return reg


class TestTwoToolCallsThenFinal(unittest.TestCase):
	def test_two_tools_then_summary(self):
		reg = _registry_with([{"emp": "A"}, {"emp": "B"}], [{"diff": 1}])
		provider = _FakeProvider(
			[
				{"tool_call": {"name": "list_proposals", "args": {"site": "S1"}}},
				{"tool_call": {"name": "reconcile", "args": {"month": "2026-05"}}},
				{"text": "제안 2명, diff 1건 대사 완료"},
			]
		)
		out = run_agent_loop(provider, [{"role": "user", "text": "마감 준비"}], reg)

		self.assertEqual(out["status"], "completed")
		self.assertEqual(out["final_text"], "제안 2명, diff 1건 대사 완료")
		self.assertEqual(out["steps"], 3)

		# 도구 호출 순서 검증
		self.assertEqual([c["tool"] for c in out["tool_calls"]], ["list_proposals", "reconcile"])
		self.assertEqual([c["status"] for c in out["tool_calls"]], ["ok", "ok"])
		self.assertEqual(out["tool_calls"][0]["result"], [{"emp": "A"}, {"emp": "B"}])
		self.assertEqual(out["tool_calls"][1]["result"], [{"diff": 1}])

		# messages에 도구 결과가 반영됨 (assistant tool_call + tool result 쌍 × 2 + 최종 assistant text)
		roles = [(m.get("role"), m.get("tool") or m.get("tool_call", {}).get("name")) for m in out["messages"]]
		self.assertIn(("tool", "list_proposals"), roles)
		self.assertIn(("tool", "reconcile"), roles)
		self.assertEqual(out["messages"][-1]["text"], "제안 2명, diff 1건 대사 완료")

	def test_caller_messages_not_mutated(self):
		reg = _registry_with([{"emp": "A"}], [{"diff": 1}])
		provider = _FakeProvider([{"text": "done"}])
		original = [{"role": "user", "text": "hi"}]
		run_agent_loop(provider, original, reg)
		self.assertEqual(original, [{"role": "user", "text": "hi"}])  # 불변


class TestMaxSteps(unittest.TestCase):
	def test_max_steps_exceeded_no_infinite_loop(self):
		reg = _registry_with([{"emp": "A"}], [{"diff": 1}])
		# provider가 계속 도구만 호출 → 종료 안 함 → max_steps에서 강제 종료
		provider = _FakeProvider(
			[{"tool_call": {"name": "list_proposals", "args": {}}}] * 10
		)
		out = run_agent_loop(provider, [{"role": "user", "text": "loop"}], reg, max_steps=3)
		self.assertEqual(out["status"], "max_steps_exceeded")
		self.assertIsNone(out["final_text"])
		self.assertEqual(out["steps"], 3)
		self.assertEqual(len(out["tool_calls"]), 3)


class TestWriteApprovalPropagation(unittest.TestCase):
	def test_write_without_approval_blocked_then_feedback(self):
		reg = ToolRegistry()
		spy = _Spy({"filed": True})
		reg.register_tool("file_it", spy, {}, read_only=False)
		provider = _FakeProvider(
			[
				{"tool_call": {"name": "file_it", "args": {"emp": "A"}}},  # 승인 없음
				{"text": "거부됨"},
			]
		)
		out = run_agent_loop(provider, [{"role": "user", "text": "신고"}], reg)
		self.assertEqual(out["tool_calls"][0]["status"], "blocked")
		self.assertEqual(len(spy.calls), 0)  # fn 미호출 (fail-closed)
		self.assertEqual(out["status"], "completed")

	def test_write_with_approval_executes(self):
		reg = ToolRegistry()
		spy = _Spy({"filed": True})
		reg.register_tool("file_it", spy, {}, read_only=False)
		provider = _FakeProvider(
			[
				{"tool_call": {"name": "file_it", "args": {"emp": "A"}, "human_approved": True}},
				{"text": "신고 완료"},
			]
		)
		out = run_agent_loop(provider, [{"role": "user", "text": "신고"}], reg)
		self.assertEqual(out["tool_calls"][0]["status"], "ok")
		self.assertEqual(len(spy.calls), 1)


class TestErrorsAndValidation(unittest.TestCase):
	def test_unregistered_tool_recorded_as_error(self):
		reg = ToolRegistry()
		provider = _FakeProvider(
			[
				{"tool_call": {"name": "ghost", "args": {}}},
				{"text": "미등록 처리"},
			]
		)
		out = run_agent_loop(provider, [{"role": "user", "text": "x"}], reg)
		self.assertEqual(out["tool_calls"][0]["status"], "error")
		self.assertEqual(out["status"], "completed")

	def test_bad_provider_response_raises(self):
		reg = ToolRegistry()
		provider = _FakeProvider([{"unknown": "shape"}])
		with self.assertRaises(ValueError):
			run_agent_loop(provider, [{"role": "user", "text": "x"}], reg)

	def test_provider_not_callable(self):
		reg = ToolRegistry()
		with self.assertRaises(ValueError):
			run_agent_loop("not callable", [], reg)

	def test_messages_not_list(self):
		reg = ToolRegistry()
		with self.assertRaises(ValueError):
			run_agent_loop(lambda m: {"text": "x"}, "nope", reg)

	def test_bad_max_steps(self):
		reg = ToolRegistry()
		with self.assertRaises(ValueError):
			run_agent_loop(lambda m: {"text": "x"}, [], reg, max_steps=0)


if __name__ == "__main__":
	unittest.main()
