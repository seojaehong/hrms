# -*- coding: utf-8 -*-
"""agent_harness/tool_registry.py 테스트 — 화이트리스트 + fail-closed 승인 게이트.

framework-free: tool_registry.py는 frappe import 없음.
hrms/__init__.py가 frappe를 import하므로 spec_from_file_location으로 직접 로드.
실행: python3 hrms/tests/test_korea_agent_harness_tool_registry.py
"""
import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = (
	_REPO_ROOT / "hrms" / "regional" / "south_korea" / "agent_harness" / "tool_registry.py"
)

_spec = importlib.util.spec_from_file_location("tool_registry", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ToolRegistry = _mod.ToolRegistry
ToolError = _mod.ToolError


class _Spy:
	"""fn 호출 여부·인자를 기록하는 스파이."""

	def __init__(self, ret):
		self.ret = ret
		self.called = False
		self.calls = []

	def __call__(self, **kwargs):
		self.called = True
		self.calls.append(kwargs)
		return self.ret


class TestRegisterTool(unittest.TestCase):
	def test_register_and_list(self):
		reg = ToolRegistry()
		reg.register_tool("list_proposals", lambda: [], {"desc": "조회"}, read_only=True)
		self.assertTrue(reg.has("list_proposals"))
		self.assertEqual(reg.list_tools(), ["list_proposals"])
		self.assertEqual(reg.get_spec("list_proposals"), {"desc": "조회"})

	def test_register_bad_name(self):
		reg = ToolRegistry()
		with self.assertRaises(ValueError):
			reg.register_tool("  ", lambda: None, {}, read_only=True)

	def test_register_non_callable(self):
		reg = ToolRegistry()
		with self.assertRaises(ValueError):
			reg.register_tool("t", 123, {}, read_only=True)

	def test_register_spec_not_dict(self):
		reg = ToolRegistry()
		with self.assertRaises(ValueError):
			reg.register_tool("t", lambda: None, ["bad"], read_only=True)

	def test_register_read_only_not_bool(self):
		reg = ToolRegistry()
		with self.assertRaises(ValueError):
			reg.register_tool("t", lambda: None, {}, read_only="yes")

	def test_duplicate_rejected(self):
		reg = ToolRegistry()
		reg.register_tool("t", lambda: None, {}, read_only=True)
		with self.assertRaises(ValueError):
			reg.register_tool("t", lambda: None, {}, read_only=True)

	def test_duplicate_overwrite(self):
		reg = ToolRegistry()
		reg.register_tool("t", lambda: 1, {"v": 1}, read_only=True)
		reg.register_tool("t", lambda: 2, {"v": 2}, read_only=True, overwrite=True)
		self.assertEqual(reg.get_spec("t"), {"v": 2})


class TestCall(unittest.TestCase):
	def test_read_only_call_ok(self):
		reg = ToolRegistry()
		spy = _Spy([{"emp": "A"}, {"emp": "B"}])
		reg.register_tool("list_proposals", spy, {}, read_only=True)
		res = reg.call("list_proposals", {"site": "S1"})
		self.assertTrue(spy.called)
		self.assertEqual(spy.calls[0], {"site": "S1"})
		self.assertEqual(res["status"], "ok")
		self.assertEqual(res["result"], [{"emp": "A"}, {"emp": "B"}])
		self.assertIn("len=2", res["summary"])

	def test_unregistered_blocked_and_fn_not_called(self):
		reg = ToolRegistry()
		with self.assertRaises(ToolError):
			reg.call("nope", {"x": 1})
		# 차단은 로그에 blocked로 남는다
		log = reg.get_call_log()
		self.assertEqual(len(log), 1)
		self.assertEqual(log[0]["status"], "blocked")
		self.assertEqual(log[0]["tool"], "nope")

	def test_write_without_approval_refused_fn_not_called(self):
		reg = ToolRegistry()
		spy = _Spy({"filed": True})
		reg.register_tool("file_insurance", spy, {}, read_only=False)
		res = reg.call("file_insurance", {"emp": "A"})  # human_approved 미지정
		self.assertFalse(spy.called)  # fn 미호출 증명 (fail-closed)
		self.assertEqual(res["status"], "blocked")
		self.assertIn("human_approved", res["error"])

	def test_write_with_approval_executes(self):
		reg = ToolRegistry()
		spy = _Spy({"filed": True})
		reg.register_tool("file_insurance", spy, {}, read_only=False)
		res = reg.call("file_insurance", {"emp": "A"}, human_approved=True)
		self.assertTrue(spy.called)
		self.assertEqual(res["status"], "ok")
		self.assertEqual(res["result"], {"filed": True})

	def test_write_approval_must_be_true_not_truthy(self):
		reg = ToolRegistry()
		spy = _Spy({"filed": True})
		reg.register_tool("file_insurance", spy, {}, read_only=False)
		# truthy 문자열은 True가 아님 → 여전히 거부(fail-closed 엄격)
		res = reg.call("file_insurance", {}, human_approved="yes")
		self.assertFalse(spy.called)
		self.assertEqual(res["status"], "blocked")

	def test_call_log_accumulates(self):
		reg = ToolRegistry()
		reg.register_tool("a", _Spy(1), {}, read_only=True)
		reg.register_tool("b", _Spy({"k": "v"}), {}, read_only=True)
		reg.call("a", {"p": 1})
		reg.call("b")
		log = reg.get_call_log()
		self.assertEqual([e["tool"] for e in log], ["a", "b"])
		self.assertEqual([e["status"] for e in log], ["ok", "ok"])
		self.assertEqual(log[0]["args"], {"p": 1})
		self.assertEqual(log[1]["args"], {})


if __name__ == "__main__":
	unittest.main()
