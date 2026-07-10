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

import copy
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


# --- US-2: merge_channel_binding / mask_binding (순수·멱등) ---

_CREDS = {
	"api_key": "khrms_key_abc",
	"api_secret": "khrms_secret_xyz",
	"frappe_url": "https://noho.safeclaw.kr",
}


class TestMergeChannelBinding(unittest.TestCase):
	def test_adds_new_binding(self):
		out = ap.merge_channel_binding({}, "12345", "noho.safeclaw.kr", _CREDS)
		self.assertIn("12345", out)
		entry = out["12345"]
		self.assertEqual(entry["site"], "noho.safeclaw.kr")
		self.assertEqual(entry["api_key"], "khrms_key_abc")
		self.assertEqual(entry["api_secret"], "khrms_secret_xyz")
		self.assertEqual(entry["frappe_url"], "https://noho.safeclaw.kr")

	def test_does_not_mutate_input_bindings(self):
		original = {"999": {"site": "old.kr", "api_key": "k0"}}
		snapshot = copy.deepcopy(original)
		out = ap.merge_channel_binding(original, "12345", "noho.safeclaw.kr", _CREDS)
		self.assertEqual(original, snapshot)  # 원본 불변
		self.assertIn("999", out)  # 기존 항목 보존
		self.assertIn("12345", out)

	def test_updates_existing_credentials_only(self):
		start = {"12345": {"site": "noho.safeclaw.kr", "api_key": "old", "api_secret": "old"}}
		new_creds = {"api_key": "new_k", "api_secret": "new_s", "frappe_url": "https://noho.safeclaw.kr"}
		out = ap.merge_channel_binding(start, "12345", "noho.safeclaw.kr", new_creds)
		self.assertEqual(out["12345"]["api_key"], "new_k")
		self.assertEqual(out["12345"]["api_secret"], "new_s")

	def test_idempotent(self):
		once = ap.merge_channel_binding({}, "12345", "noho.safeclaw.kr", _CREDS)
		twice = ap.merge_channel_binding(once, "12345", "noho.safeclaw.kr", _CREDS)
		self.assertEqual(once, twice)


class TestMaskBinding(unittest.TestCase):
	def test_masks_api_secret(self):
		b = {"site": "noho.safeclaw.kr", "api_key": "khrms_key_abc", "api_secret": "khrms_secret_xyz"}
		masked = ap.mask_binding(b)
		self.assertEqual(masked["api_secret"], "***")
		self.assertEqual(masked["api_key"], "khrms_key_abc")  # 비밀 아님 — 유지
		self.assertEqual(masked["site"], "noho.safeclaw.kr")

	def test_does_not_mutate_input(self):
		b = {"api_secret": "khrms_secret_xyz"}
		snapshot = copy.deepcopy(b)
		ap.mask_binding(b)
		self.assertEqual(b, snapshot)  # 원본 불변

	def test_no_secret_is_noop_shape(self):
		b = {"site": "noho.safeclaw.kr", "api_key": "k"}
		masked = ap.mask_binding(b)
		self.assertNotIn("api_secret", masked)
		self.assertEqual(masked["api_key"], "k")


if __name__ == "__main__":
	unittest.main()
