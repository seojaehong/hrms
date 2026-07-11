# -*- coding: utf-8 -*-
"""HermesProvider 어댑터 테스트 — transport 주입, 실HTTP 0회.

실행: python3 hrms/tests/test_korea_agent_harness_hermes_provider.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

_MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional" / "south_korea" / "agent_harness" / "hermes_provider.py"
)
_spec = importlib.util.spec_from_file_location("hermes_provider", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

make = _mod.make_hermes_provider
Err = _mod.HermesProviderError

CREDS = {"status": "ok", "api_key": "sk-test", "model": "claude-sonnet-5", "billing": "byok"}


def transport_returning(payload, status=200, capture=None):
	def t(method, url, headers, body, timeout):
		if capture is not None:
			capture.append({"method": method, "url": url, "headers": headers, "body": json.loads(body)})
		return status, json.dumps(payload).encode()
	return t


class TestRequestShape(unittest.TestCase):
	def test_url_auth_model(self):
		calls = []
		p = make(base_url="http://127.0.0.1:8130/", credentials=CREDS,
			transport=transport_returning({"choices": [{"message": {"content": "hi"}}]}, capture=calls))
		out = p([{"role": "user", "content": "안녕"}])
		self.assertEqual(out, {"text": "hi"})
		c = calls[0]
		self.assertEqual(c["url"], "http://127.0.0.1:8130/v1/chat/completions")
		self.assertEqual(c["headers"]["Authorization"], "Bearer sk-test")
		self.assertEqual(c["body"]["model"], "claude-sonnet-5")
		self.assertEqual(c["body"]["messages"], [{"role": "user", "content": "안녕"}])

	def test_nonstandard_message_serialized(self):
		calls = []
		p = make(base_url="http://x", credentials=CREDS,
			transport=transport_returning({"choices": [{"message": {"content": "ok"}}]}, capture=calls))
		p([{"tool_result": {"gross_pay": 373810}}])
		sent = calls[0]["body"]["messages"][0]
		self.assertEqual(sent["role"], "user")
		self.assertIn("373810", sent["content"])

	def test_session_header(self):
		calls = []
		p = make(base_url="http://x", credentials=CREDS, session_id="tenant-noho-1",
			transport=transport_returning({"choices": [{"message": {"content": "ok"}}]}, capture=calls))
		p([])
		self.assertEqual(calls[0]["headers"]["X-Hermes-Session-Id"], "tenant-noho-1")


class TestResponseMapping(unittest.TestCase):
	def test_tool_call_mapped(self):
		payload = {"choices": [{"message": {"tool_calls": [
			{"function": {"name": "list_hourly_payroll_proposals", "arguments": "{\"period\": \"2026-06\"}"}}
		]}}]}
		p = make(base_url="http://x", credentials=CREDS, transport=transport_returning(payload))
		out = p([])
		self.assertEqual(out["tool_call"]["name"], "list_hourly_payroll_proposals")
		self.assertEqual(out["tool_call"]["args"], {"period": "2026-06"})

	def test_bad_tool_arguments_preserved(self):
		payload = {"choices": [{"message": {"tool_calls": [
			{"function": {"name": "x", "arguments": "{broken"}}
		]}}]}
		p = make(base_url="http://x", credentials=CREDS, transport=transport_returning(payload))
		self.assertEqual(p([])["tool_call"]["args"], {"_raw_arguments": "{broken"})


class TestPromptProtocolToolCalling(unittest.TestCase):
	"""프롬프트 프로토콜 툴콜링 — gateway가 에이전트 엔드포인트(클라이언트 tools 미전달)라
	모델이 텍스트로 {"tool_call": …} JSON을 선언하고 provider가 파싱한다."""

	SPECS = {"get_payroll_calculations": {"description": "급여 확정값 조회", "args": {}}}

	def _resp(self, content):
		return {"choices": [{"message": {"content": content}}]}

	def test_tool_specs_inject_protocol_instruction(self):
		calls = []
		p = make(base_url="http://x", credentials=CREDS, tool_specs=self.SPECS,
			transport=transport_returning(self._resp("ok"), capture=calls))
		p([{"role": "system", "content": "S"}, {"role": "user", "content": "Q"}])
		body = calls[0]["body"]
		joined = json.dumps(body["messages"], ensure_ascii=False)
		self.assertIn("tool_call", joined)
		self.assertIn("get_payroll_calculations", joined)
		# 기존 system이 첫 메시지로 유지되고 프로토콜 지시는 그 뒤에 system으로 삽입
		self.assertEqual(body["messages"][0]["content"], "S")
		self.assertEqual(body["messages"][1]["role"], "system")

	def test_text_tool_call_parsed(self):
		p = make(base_url="http://x", credentials=CREDS, tool_specs=self.SPECS,
			transport=transport_returning(self._resp('{"tool_call": {"name": "get_payroll_calculations", "args": {}}}')))
		out = p([{"role": "user", "content": "Q"}])
		self.assertEqual(out, {"tool_call": {"name": "get_payroll_calculations", "args": {}}})

	def test_fenced_tool_call_with_prose_parsed(self):
		content = (
			"도구를 호출하겠습니다.\n```json\n"
			'{"tool_call": {"name": "get_payroll_calculations", "args": {"month": "2026-07"}}}'
			"\n```"
		)
		p = make(base_url="http://x", credentials=CREDS, tool_specs=self.SPECS,
			transport=transport_returning(self._resp(content)))
		out = p([{"role": "user", "content": "Q"}])
		self.assertEqual(out["tool_call"]["name"], "get_payroll_calculations")
		self.assertEqual(out["tool_call"]["args"], {"month": "2026-07"})

	def test_unknown_tool_name_returns_text(self):
		# 스펙에 없는 도구 선언은 파싱하지 않고 텍스트로 통과 (화이트리스트는 registry가 최종 방어)
		content = '{"tool_call": {"name": "shell_exec", "args": {}}}'
		p = make(base_url="http://x", credentials=CREDS, tool_specs=self.SPECS,
			transport=transport_returning(self._resp(content)))
		out = p([{"role": "user", "content": "Q"}])
		self.assertIn("text", out)

	def test_plain_text_still_text(self):
		p = make(base_url="http://x", credentials=CREDS, tool_specs=self.SPECS,
			transport=transport_returning(self._resp("최종 답변입니다")))
		out = p([{"role": "user", "content": "Q"}])
		self.assertEqual(out, {"text": "최종 답변입니다"})

	def test_without_tool_specs_json_is_text(self):
		# 기능 미사용 시 기존 동작 불변 — JSON처럼 보여도 텍스트
		content = '{"tool_call": {"name": "get_payroll_calculations", "args": {}}}'
		p = make(base_url="http://x", credentials=CREDS,
			transport=transport_returning(self._resp(content)))
		out = p([{"role": "user", "content": "Q"}])
		self.assertEqual(out, {"text": content})


class TestErrors(unittest.TestCase):
	def test_http_error(self):
		p = make(base_url="http://x", credentials=CREDS, transport=transport_returning({}, status=500))
		with self.assertRaises(Err):
			p([])

	def test_missing_choices(self):
		p = make(base_url="http://x", credentials=CREDS, transport=transport_returning({"choices": []}))
		with self.assertRaises(Err):
			p([])

	def test_unconfigured_credentials_rejected(self):
		with self.assertRaises(Err):
			make(base_url="http://x", credentials={"status": "not_configured", "api_key": None})

	def test_missing_base_url_rejected(self):
		with self.assertRaises(Err):
			make(base_url="", credentials=CREDS)


if __name__ == "__main__":
	unittest.main()
