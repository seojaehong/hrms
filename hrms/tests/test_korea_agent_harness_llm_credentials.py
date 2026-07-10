# -*- coding: utf-8 -*-
"""LLM 자격증명 라우팅(BYOK→플랫폼 폴백) 테스트 — framework-free.

실행: python3 hrms/tests/test_korea_agent_harness_llm_credentials.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

_MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "agent_harness"
	/ "llm_credentials.py"
)
_spec = importlib.util.spec_from_file_location("llm_credentials", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

resolve = _mod.resolve_llm_credentials
public = _mod.public_status


class TestPriority(unittest.TestCase):
	def test_byok_wins_over_platform(self):
		out = resolve(
			{"agent_llm_api_key": "sk-tenant", "agent_llm_provider": "openrouter"},
			{"PLATFORM_LLM_API_KEY": "sk-platform"},
		)
		self.assertEqual(out["billing"], "byok")
		self.assertEqual(out["provider"], "openrouter")
		self.assertEqual(out["api_key"], "sk-tenant")

	def test_platform_fallback(self):
		out = resolve({}, {"PLATFORM_LLM_API_KEY": "sk-platform", "PLATFORM_LLM_MODEL": "claude-opus-4-8"})
		self.assertEqual(out["billing"], "platform")
		self.assertEqual(out["model"], "claude-opus-4-8")
		self.assertEqual(out["api_key"], "sk-platform")

	def test_not_configured(self):
		out = resolve({}, {})
		self.assertEqual(out["status"], "not_configured")
		self.assertIsNone(out["api_key"])

	def test_blank_tenant_key_falls_through(self):
		out = resolve({"agent_llm_api_key": "   "}, {"PLATFORM_LLM_API_KEY": "sk-p"})
		self.assertEqual(out["billing"], "platform")

	def test_defaults(self):
		out = resolve({"agent_llm_api_key": "sk-t"}, {})
		self.assertEqual(out["provider"], "anthropic")
		self.assertEqual(out["model"], _mod.DEFAULT_MODEL)


class TestPublicStatus(unittest.TestCase):
	def test_key_never_exposed(self):
		out = public(resolve({"agent_llm_api_key": "sk-secret"}, {}))
		self.assertNotIn("api_key", out)
		self.assertTrue(out["api_key_present"])
		self.assertNotIn("sk-secret", str(out))

	def test_not_configured_public(self):
		out = public(resolve({}, {}))
		self.assertEqual(out["status"], "not_configured")
		self.assertFalse(out["api_key_present"])


if __name__ == "__main__":
	unittest.main()
