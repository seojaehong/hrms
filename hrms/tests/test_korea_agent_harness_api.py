# -*- coding: utf-8 -*-
"""agent_harness_api.py 테스트 — whitelist 래퍼 (조건부 frappe).

framework-free: hrms/__init__.py가 frappe를 import하므로 패키지 import 대신
spec_from_file_location으로 api 모듈을 직접 로드한다. frappe는 FakeFrappe 스텁을
sys.modules에 주입해 흉내낸다(insurance_filing_api 테스트 컨벤션).
실행: python3 hrms/tests/test_korea_agent_harness_api.py

핵심 검증:
- provider 미설정(config 없음) → not_configured, 어떤 LLM/네트워크 호출도 0회.
- 미등록 skill_name → unknown_skill(명시적 오류 status).
- provider + tool_registry 주입 시 → 에이전트 루프로 스킬을 실제 실행(completed).
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SK_DIR = _REPO_ROOT / "hrms" / "regional" / "south_korea"
API_PATH = _SK_DIR / "agent_harness_api.py"
_CORE_DIR = _SK_DIR / "agent_harness"


class FakeFrappe:
	"""whitelist no-op + conf 만 제공하는 최소 스텁 (provider config 해석용)."""

	def __init__(self, conf=None):
		self.conf = conf if conf is not None else {}

	def whitelist(self):
		def decorator(fn):
			return fn

		return decorator


def load_api(fake_frappe=None):
	old_frappe = sys.modules.get("frappe")
	if fake_frappe is not None:
		sys.modules["frappe"] = fake_frappe
	else:
		sys.modules.pop("frappe", None)
	try:
		spec = importlib.util.spec_from_file_location("korea_agent_harness_api", API_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if old_frappe is not None:
			sys.modules["frappe"] = old_frappe
		else:
			sys.modules.pop("frappe", None)


def _load_core(name):
	spec = importlib.util.spec_from_file_location(name, _CORE_DIR / f"{name}.py")
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


class TestNotConfigured(unittest.TestCase):
	def test_no_frappe_returns_not_configured(self):
		# frappe 자체가 없어도 로드 가능해야 하고, provider 미설정 → not_configured.
		mod = load_api(fake_frappe=None)
		result = mod.run_agent_skill("hourly_closing_prep")
		self.assertEqual(result["status"], "not_configured")
		self.assertTrue(result["requires_provider_config"])

	def test_empty_conf_returns_not_configured(self):
		mod = load_api(fake_frappe=FakeFrappe(conf={}))
		result = mod.run_agent_skill("insurance_reconcile")
		self.assertEqual(result["status"], "not_configured")

	def test_config_key_present_still_not_configured_in_poc(self):
		# PoC: config 키가 있어도 실제 LLM 클라이언트는 배선하지 않는다 → not_configured.
		mod = load_api(fake_frappe=FakeFrappe(conf={mod_key(): "x"}))
		result = mod.run_agent_skill("hourly_closing_prep")
		self.assertEqual(result["status"], "not_configured")


def mod_key():
	# API 모듈의 config 키 상수를 참조(하드코딩 문자열 중복 방지).
	mod = load_api(fake_frappe=None)
	return mod.PROVIDER_CONFIG_KEY


class TestUnknownSkill(unittest.TestCase):
	def test_unknown_skill_status(self):
		# 미등록 스킬은 provider 여부와 무관하게 명시적 오류 status.
		mod = load_api(fake_frappe=None)
		result = mod.run_agent_skill("does_not_exist")
		self.assertEqual(result["status"], "unknown_skill")
		self.assertEqual(result["skill_name"], "does_not_exist")
		self.assertIn("hourly_closing_prep", result["available"])

	def test_unknown_skill_checked_before_provider(self):
		# provider 미설정 상태에서도 미등록 스킬은 not_configured가 아니라 unknown_skill.
		mod = load_api(fake_frappe=FakeFrappe(conf={}))
		result = mod.run_agent_skill("nope")
		self.assertEqual(result["status"], "unknown_skill")


class TestNoTools(unittest.TestCase):
	def test_provider_injected_but_no_tools(self):
		# provider가 주입돼도 tool_registry 없으면 실행하지 않는다(도구 바인딩 필요).
		mod = load_api(fake_frappe=None)

		def provider(convo):
			return {"text": "should not run"}

		result = mod.run_agent_skill("hourly_closing_prep", provider=provider)
		self.assertEqual(result["status"], "no_tools")


class TestInjectedRun(unittest.TestCase):
	"""provider + tool_registry 주입 시 에이전트 루프가 실제 스킬을 실행하는지(happy path)."""

	def test_hourly_prep_completes_with_injected_provider(self):
		mod = load_api(fake_frappe=None)
		tool_mod = _load_core("tool_registry")
		reg = tool_mod.ToolRegistry()
		reg.register_tool(
			"list_hourly_payroll_proposals",
			lambda **kw: {"proposals": [{"emp": "A"}, {"emp": "B"}]},
			{},
			read_only=True,
		)

		def provider(convo):
			# 도구 결과가 대화에 반영되기 전이면 스킬 step대로 도구 호출
			for m in convo:
				if m.get("role") == "tool" and m.get("tool") == "list_hourly_payroll_proposals":
					count = len(m["result"]["result"]["proposals"])
					return {"text": f"시급 마감 준비 완료 — 제안 {count}명 검토 대상"}
			return {"tool_call": {"name": "list_hourly_payroll_proposals", "args": {}}}

		result = mod.run_agent_skill(
			"hourly_closing_prep", provider=provider, tool_registry=reg
		)
		self.assertEqual(result["status"], "completed")
		self.assertEqual(result["skill_name"], "hourly_closing_prep")
		self.assertEqual([c["tool"] for c in result["tool_calls"]], ["list_hourly_payroll_proposals"])
		self.assertIn("제안 2명", result["final_text"])


if __name__ == "__main__":
	unittest.main()
