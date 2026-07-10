# -*- coding: utf-8 -*-
"""에이전트 자동 프로비저닝 — 순수 플랜 빌더 테스트 (US-1).

framework-free: mcp_server/agent_provisioning.py 는 상단에서 frappe 를 import
하지 않으므로 spec_from_file_location 으로 직접 로드한다. 실제 유저/토큰/파일
생성 없이 '실행할 스텝을 데이터로 표현'한 순수 함수만 검증한다.
실행: python3 hrms/tests/test_korea_agent_provisioning.py

핵심 검증:
- 스텝 구성 순서/키: ensure_service_user → issue_mcp_token → set_site_config
  (+ telegram_chat_id 있을 때만 bind_channel).
- email 도메인은 site 에서 유도(site 그대로 도메인).
- site_config 키: korea_agent_harness_provider / hermes_gateway_url.
- 잘못된 인자(빈 site, gateway_url 누락) → ValueError.
- 순수성: 두 번 호출 동일 결과.
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE = _REPO_ROOT / "mcp_server" / "agent_provisioning.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_agent_provisioning", _MODULE)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


ap = load_module()

_GATEWAY = "https://hermes.example.com"


class TestPlanShape(unittest.TestCase):
	def test_plan_without_chat_id_has_three_steps(self):
		plan = ap.build_agent_provisioning_plan("noho.safeclaw.kr", gateway_url=_GATEWAY)
		actions = [step["action"] for step in plan]
		self.assertEqual(
			actions, ["ensure_service_user", "issue_mcp_token", "set_site_config"]
		)

	def test_plan_with_chat_id_appends_bind_channel(self):
		plan = ap.build_agent_provisioning_plan(
			"noho.safeclaw.kr", telegram_chat_id=12345, gateway_url=_GATEWAY
		)
		actions = [step["action"] for step in plan]
		self.assertEqual(
			actions,
			[
				"ensure_service_user",
				"issue_mcp_token",
				"set_site_config",
				"bind_channel",
			],
		)
		bind = plan[-1]
		self.assertEqual(bind["channel"], "telegram")
		self.assertEqual(bind["chat_id"], 12345)

	def test_service_user_email_derived_from_site(self):
		plan = ap.build_agent_provisioning_plan("noho.safeclaw.kr", gateway_url=_GATEWAY)
		user = plan[0]
		self.assertEqual(user["action"], "ensure_service_user")
		self.assertEqual(user["email"], "agent-bot@noho.safeclaw.kr")
		self.assertEqual(user["roles"], ["System Manager"])

	def test_issue_mcp_token_calc_only(self):
		plan = ap.build_agent_provisioning_plan("noho.safeclaw.kr", gateway_url=_GATEWAY)
		token = plan[1]
		self.assertEqual(token["action"], "issue_mcp_token")
		self.assertEqual(token["site"], "noho.safeclaw.kr")
		self.assertEqual(token["scope"], "calc_only")
		self.assertIn("label", token)

	def test_set_site_config_keys(self):
		plan = ap.build_agent_provisioning_plan(
			"noho.safeclaw.kr", provider="hermes", gateway_url=_GATEWAY
		)
		conf = plan[2]
		self.assertEqual(conf["action"], "set_site_config")
		keys = conf["keys"]
		self.assertEqual(keys["korea_agent_harness_provider"], "hermes")
		self.assertEqual(keys["hermes_gateway_url"], _GATEWAY)

	def test_default_provider_is_hermes(self):
		plan = ap.build_agent_provisioning_plan("noho.safeclaw.kr", gateway_url=_GATEWAY)
		self.assertEqual(
			plan[2]["keys"]["korea_agent_harness_provider"], "hermes"
		)


class TestValidation(unittest.TestCase):
	def test_empty_site_raises(self):
		with self.assertRaises(ValueError):
			ap.build_agent_provisioning_plan("", gateway_url=_GATEWAY)
		with self.assertRaises(ValueError):
			ap.build_agent_provisioning_plan("   ", gateway_url=_GATEWAY)

	def test_missing_gateway_url_raises(self):
		with self.assertRaises(ValueError):
			ap.build_agent_provisioning_plan("noho.safeclaw.kr", gateway_url="")
		with self.assertRaises(ValueError):
			ap.build_agent_provisioning_plan("noho.safeclaw.kr")


class TestPurity(unittest.TestCase):
	def test_two_calls_equal(self):
		a = ap.build_agent_provisioning_plan(
			"noho.safeclaw.kr", telegram_chat_id=7, gateway_url=_GATEWAY
		)
		b = ap.build_agent_provisioning_plan(
			"noho.safeclaw.kr", telegram_chat_id=7, gateway_url=_GATEWAY
		)
		self.assertEqual(a, b)


if __name__ == "__main__":
	unittest.main()
