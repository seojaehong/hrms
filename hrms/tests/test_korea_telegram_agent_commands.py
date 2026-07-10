# -*- coding: utf-8 -*-
"""텔레그램 AI 에이전트 스킬 명령 테스트 — /스킬, /마감준비.

framework-free: mcp_server 모듈은 `import hrms`(frappe 연쇄)를 하지 않으므로
spec_from_file_location으로 channel_core.py를 직접 로드한다. frappe HTTP 전송은
주입식(callable)이라 네트워크 없이 파싱·라우팅·정형을 검증한다.
실행: python3 hrms/tests/test_korea_telegram_agent_commands.py

핵심 검증:
- 파싱: /스킬(스킬명·json인자·무인자·오형식), /마감준비(YYYY-MM 검증·오형식), 비명령 None.
- 라우팅: 스킬 명령 vs 기존 명령(/연차) 무손상.
- 미설정: 바인딩에 자격증명 없음 → 'AI 에이전트 미설정' 안내(전송 미호출).
- fake 전송자 주입 → completed면 final_text 회신, 비-completed면 status 요약.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_CHANNEL_CORE = _REPO_ROOT / "mcp_server" / "channel_core.py"


def load_channel_core():
	spec = importlib.util.spec_from_file_location("korea_channel_core", _CHANNEL_CORE)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


cc = load_channel_core()

_CREDS = {
	"site": "noho.safeclaw.kr",
	"label": "사장님",
	"api_key": "k",
	"api_secret": "s",
	"frappe_url": "https://noho.safeclaw.kr",
}


class TestParse(unittest.TestCase):
	def test_skill_with_json_args(self):
		parsed = cc.parse_agent_command('/스킬 hr_freeform_qa {"question": "연차 며칠?"}')
		self.assertEqual(parsed["skill_name"], "hr_freeform_qa")
		self.assertEqual(parsed["args"], {"question": "연차 며칠?"})

	def test_skill_no_args(self):
		parsed = cc.parse_agent_command("/스킬 hr_freeform_qa")
		self.assertEqual(parsed["skill_name"], "hr_freeform_qa")
		self.assertEqual(parsed["args"], {})

	def test_skill_missing_name(self):
		parsed = cc.parse_agent_command("/스킬")
		self.assertIn("error", parsed)

	def test_skill_bad_json(self):
		parsed = cc.parse_agent_command("/스킬 hr_freeform_qa {not json}")
		self.assertIn("error", parsed)

	def test_skill_non_object_json(self):
		parsed = cc.parse_agent_command('/스킬 hr_freeform_qa [1, 2]')
		self.assertIn("error", parsed)

	def test_closing_ok(self):
		parsed = cc.parse_agent_command("/마감준비 2026-07")
		self.assertEqual(parsed["skill_name"], "hourly_closing_prep")
		self.assertEqual(parsed["args"], {"period": "2026-07"})

	def test_closing_bad_month(self):
		self.assertIn("error", cc.parse_agent_command("/마감준비 2026-13"))
		self.assertIn("error", cc.parse_agent_command("/마감준비 2026/07"))
		self.assertIn("error", cc.parse_agent_command("/마감준비"))

	def test_non_command_returns_none(self):
		self.assertIsNone(cc.parse_agent_command("연차는 며칠 발생하나요?"))
		self.assertIsNone(cc.parse_agent_command("/연차 2024-03-02 2026-07-05"))
		self.assertIsNone(cc.parse_agent_command(""))


class TestFormat(unittest.TestCase):
	def test_completed(self):
		out = cc.format_agent_result({"status": "completed", "final_text": "연차는 15일입니다."})
		self.assertIn("연차는 15일입니다.", out)

	def test_not_configured(self):
		self.assertEqual(cc.format_agent_result({"status": "not_configured"}), cc.AGENT_NOT_CONFIGURED)

	def test_provider_error_summary(self):
		out = cc.format_agent_result({"status": "provider_error", "error": "gateway down"})
		self.assertNotIn("Traceback", out)
		self.assertIn("gateway down", out)

	def test_unknown_skill_summary(self):
		out = cc.format_agent_result({"status": "unknown_skill"})
		self.assertIn("스킬", out)


class TestRouting(unittest.TestCase):
	def test_missing_credentials_returns_not_configured(self):
		calls = []

		def send(binding, payload):
			calls.append(payload)
			return {"status": "completed", "final_text": "x"}

		reply = cc.handle_agent_command("/스킬 hr_freeform_qa {}", {"site": "x"}, send=send)
		self.assertEqual(reply, cc.AGENT_NOT_CONFIGURED)
		self.assertEqual(calls, [])  # 자격증명 없으면 전송하지 않는다

	def test_skill_command_injected_send(self):
		captured = {}

		def send(binding, payload):
			captured["payload"] = payload
			return {"status": "completed", "final_text": "필요시 도구를 호출했습니다."}

		reply = cc.handle_agent_command(
			'/스킬 hr_freeform_qa {"question": "연차?"}', _CREDS, send=send
		)
		self.assertIn("필요시 도구를 호출했습니다.", reply)
		self.assertEqual(captured["payload"]["skill_name"], "hr_freeform_qa")
		self.assertEqual(captured["payload"]["args"], {"question": "연차?"})

	def test_closing_command_maps_to_skill(self):
		captured = {}

		def send(binding, payload):
			captured["payload"] = payload
			return {"status": "completed", "final_text": "마감 준비 완료"}

		reply = cc.handle_agent_command("/마감준비 2026-07", _CREDS, send=send)
		self.assertIn("마감 준비 완료", reply)
		self.assertEqual(captured["payload"]["skill_name"], "hourly_closing_prep")
		self.assertEqual(captured["payload"]["args"], {"period": "2026-07"})

	def test_bad_format_returns_help_without_send(self):
		calls = []
		reply = cc.handle_agent_command("/마감준비 2026-13", _CREDS, send=lambda b, p: calls.append(p))
		self.assertIn("사용법", reply)
		self.assertEqual(calls, [])

	def test_send_exception_no_traceback(self):
		def send(binding, payload):
			raise RuntimeError("boom traceback details")

		reply = cc.handle_agent_command("/스킬 hr_freeform_qa {}", _CREDS, send=send)
		self.assertNotIn("boom", reply)
		self.assertNotIn("Traceback", reply)

	def test_non_skill_command_returns_none(self):
		self.assertIsNone(cc.handle_agent_command("/연차 2024-03-02 2026-07-05", _CREDS))
		self.assertIsNone(cc.handle_agent_command("연차는 며칠?", _CREDS))


class TestHandleMessageUntouched(unittest.TestCase):
	def test_help(self):
		self.assertEqual(cc.handle_message("/help", _CREDS), cc.HELP_TEXT)

	def test_existing_annual_leave_command_still_works(self):
		reply = cc.handle_message("/연차 2024-03-02 2026-07-05", _CREDS)
		self.assertIn("연차 산정", reply)


if __name__ == "__main__":
	unittest.main()
