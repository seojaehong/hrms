# -*- coding: utf-8 -*-
"""CODEF 조회 레이어 테스트 — framework-free (transport 주입, 실HTTP 0회).

실행: python3 hrms/tests/test_korea_insurance_inquiry.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import unittest
from urllib.parse import quote_plus

_SK = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea"


def _load(name):
	spec = importlib.util.spec_from_file_location(name, _SK / f"{name}.py")
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


codef = _load("codef_client")
inquiry = _load("insurance_inquiry_api")


def make_transport(script):
	"""script: url substring → (status, body bytes). 호출 기록 반환."""
	calls = []

	def transport(method, url, headers, body, timeout):
		calls.append({"method": method, "url": url, "headers": headers, "body": body})
		for key, resp in script.items():
			if key in url:
				return resp
		raise AssertionError(f"unexpected url: {url}")

	return transport, calls


TOKEN_OK = (200, json.dumps({"access_token": "tok-1", "expires_in": 3600}).encode())


class TestCodefClient(unittest.TestCase):
	def test_not_configured_no_network(self):
		transport, calls = make_transport({})
		c = codef.CodefClient("", "", transport=transport)
		self.assertFalse(c.is_configured())
		with self.assertRaises(codef.CodefNotConfigured):
			c.get_token()
		self.assertEqual(calls, [])  # 네트워크 0회

	def test_token_and_product_success(self):
		data = {"result": {"code": "CF-00000"}, "data": {"list": [{"name": "김테스트"}]}}
		transport, calls = make_transport({
			"oauth.codef.io": TOKEN_OK,
			"development.codef.io": (200, quote_plus(json.dumps(data)).encode()),
		})
		c = codef.CodefClient("id", "secret", demo=True, transport=transport)
		out = c.request_product("/v1/test", {"a": 1})
		self.assertEqual(out["list"][0]["name"], "김테스트")
		self.assertEqual(len(calls), 2)  # token + product
		self.assertIn("Bearer tok-1", calls[1]["headers"]["Authorization"])

	def test_business_error_raises_with_code(self):
		data = {"result": {"code": "CF-12345", "message": "인증 실패"}}
		transport, _ = make_transport({
			"oauth.codef.io": TOKEN_OK,
			"development.codef.io": (200, json.dumps(data).encode()),  # 평문 JSON도 수용
		})
		c = codef.CodefClient("id", "secret", transport=transport)
		with self.assertRaises(codef.CodefError) as ctx:
			c.request_product("/v1/test", {})
		self.assertEqual(ctx.exception.code, "CF-12345")

	def test_401_retries_once_with_new_token(self):
		ok = {"result": {"code": "CF-00000"}, "data": {"ok": True}}
		state = {"product_calls": 0}
		calls = []

		def transport(method, url, headers, body, timeout):
			calls.append(url)
			if "oauth" in url:
				return TOKEN_OK
			state["product_calls"] += 1
			if state["product_calls"] == 1:
				return (401, b"expired")
			return (200, json.dumps(ok).encode())

		c = codef.CodefClient("id", "secret", transport=transport)
		out = c.request_product("/v1/test", {})
		self.assertTrue(out["ok"])
		self.assertEqual(state["product_calls"], 2)

	def test_token_cached(self):
		data = {"result": {"code": "CF-00000"}, "data": {}}
		transport, calls = make_transport({
			"oauth.codef.io": TOKEN_OK,
			"development.codef.io": (200, json.dumps(data).encode()),
		})
		c = codef.CodefClient("id", "secret", transport=transport)
		c.request_product("/v1/a", {})
		c.request_product("/v1/b", {})
		token_calls = [u for u in calls if "oauth" in u["url"]]
		self.assertEqual(len(token_calls), 1)  # 토큰 재사용


class TestInquiryApi(unittest.TestCase):
	def setUp(self):
		for k in ("CODEF_CLIENT_ID", "CODEF_CLIENT_SECRET", "CODEF_DEMO"):
			os.environ.pop(k, None)

	def test_not_configured_status(self):
		out = inquiry.fetch_insured_roster("11122233340")
		self.assertEqual(out["status"], "not_configured")
		st = inquiry.codef_connection_status()
		self.assertFalse(st["configured"])
		self.assertEqual(st["mode"], "demo")  # 기본 데모

	def test_configured_via_env(self):
		os.environ["CODEF_CLIENT_ID"] = "id"
		os.environ["CODEF_CLIENT_SECRET"] = "sec"
		try:
			st = inquiry.codef_connection_status()
			self.assertTrue(st["configured"])
			self.assertIn("development.codef.io", st["base"])
		finally:
			os.environ.pop("CODEF_CLIENT_ID")
			os.environ.pop("CODEF_CLIENT_SECRET")

	def test_production_mode_flag(self):
		os.environ["CODEF_CLIENT_ID"] = "id"
		os.environ["CODEF_CLIENT_SECRET"] = "sec"
		os.environ["CODEF_DEMO"] = "false"
		try:
			st = inquiry.codef_connection_status()
			self.assertEqual(st["mode"], "production")
			self.assertIn("api.codef.io", st["base"])
		finally:
			for k in ("CODEF_CLIENT_ID", "CODEF_CLIENT_SECRET", "CODEF_DEMO"):
				os.environ.pop(k)


if __name__ == "__main__":
	unittest.main()
