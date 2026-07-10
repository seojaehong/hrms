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
