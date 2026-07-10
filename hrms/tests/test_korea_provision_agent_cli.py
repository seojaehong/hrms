# -*- coding: utf-8 -*-
"""에이전트 프로비저닝 CLI 테스트 — provision_agent.py (US-4).

framework-free: provision_agent.py 는 frappe 를 조건부 import(없어도 로드) 하므로
spec_from_file_location 으로 직접 로드한다. side-effect(유저생성·토큰발급·파일쓰기)는
주입식(deps callable)이라 fake 로 대체해 검증한다. 실제 frappe/파일/네트워크 미사용.
실행: python3 hrms/tests/test_korea_provision_agent_cli.py

핵심 검증:
- fail-safe: --apply 없으면 dry-run — 어떤 deps callable 도 호출 안 됨(부수효과 0).
- --apply 시(주입 fake deps) 각 스텝 deps 가 호출됨. chat_id 있으면 bind_channel 포함.
- dry-run 출력에 평문 api_secret 이 나오지 않음(마스킹).
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE = _REPO_ROOT / "mcp_server" / "provision_agent.py"

_GATEWAY = "https://hermes.example.com"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_provision_agent", _MODULE)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


pa = load_module()


class _Recorder:
	"""주입식 deps — action 별 호출을 기록하는 fake(부수효과 없음)."""

	def __init__(self):
		self.calls = []

	def _make(self, action):
		def fn(step):
			self.calls.append((action, step))

		return fn

	def deps(self):
		return {
			a: self._make(a)
			for a in ("ensure_service_user", "issue_mcp_token", "set_site_config", "bind_channel")
		}


def _collector():
	lines = []
	return lines, lines.append


class TestDryRunFailSafe(unittest.TestCase):
	def test_dry_run_default_calls_no_deps(self):
		rec = _Recorder()
		lines, out = _collector()
		result = pa.run(
			["noho.safeclaw.kr", "--gateway-url", _GATEWAY], deps=rec.deps(), out=out
		)
		self.assertEqual(rec.calls, [])  # 부수효과 0
		self.assertFalse(result["applied"])
		self.assertEqual(result["mode"], "dry-run")
		self.assertTrue(lines)  # 계획은 출력됨

	def test_dry_run_masks_api_secret(self):
		lines, out = _collector()
		pa.run(
			[
				"noho.safeclaw.kr",
				"--gateway-url",
				_GATEWAY,
				"--api-key",
				"khrms_key_abc",
				"--api-secret",
				"SUPERSECRET_VALUE",
			],
			deps=_Recorder().deps(),
			out=out,
		)
		joined = "\n".join(lines)
		self.assertNotIn("SUPERSECRET_VALUE", joined)  # 평문 시크릿 미노출
		self.assertIn("***", joined)


class TestApply(unittest.TestCase):
	def test_apply_calls_deps_for_each_step(self):
		rec = _Recorder()
		lines, out = _collector()
		result = pa.run(
			["noho.safeclaw.kr", "--gateway-url", _GATEWAY, "--apply"],
			deps=rec.deps(),
			out=out,
		)
		self.assertTrue(result["applied"])
		actions = [a for a, _ in rec.calls]
		self.assertEqual(
			actions, ["ensure_service_user", "issue_mcp_token", "set_site_config"]
		)

	def test_apply_with_chat_id_binds_channel(self):
		rec = _Recorder()
		lines, out = _collector()
		pa.run(
			[
				"noho.safeclaw.kr",
				"--gateway-url",
				_GATEWAY,
				"--telegram-chat-id",
				"12345",
				"--apply",
			],
			deps=rec.deps(),
			out=out,
		)
		actions = [a for a, _ in rec.calls]
		self.assertIn("bind_channel", actions)


if __name__ == "__main__":
	unittest.main()
