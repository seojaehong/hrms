"""소셜 로그인 코어 테스트 — framework-free (plain unittest).

실행: python3 hrms/tests/test_korea_social_login.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hrms" / "regional" / "south_korea" / "social_login.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_social_login", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


mod = load_module()


class TestBuildSocialLoginKeyPayload(unittest.TestCase):
	def test_google_payload_uses_builtin_provider(self):
		payload = mod.build_social_login_key_payload("google", "cid", "secret")
		self.assertEqual(payload["social_login_provider"], "Google")
		self.assertEqual(payload["enable_social_login"], 1)
		self.assertNotIn("provider_name", payload)

	def test_kakao_payload_is_custom_provider_with_endpoints(self):
		payload = mod.build_social_login_key_payload("kakao", "cid", "secret")
		self.assertEqual(payload["social_login_provider"], "Custom")
		self.assertEqual(payload["provider_name"], "kakao")
		self.assertEqual(payload["authorize_url"], mod.KAKAO_AUTHORIZE_URL)
		self.assertEqual(payload["access_token_url"], mod.KAKAO_TOKEN_URL)
		self.assertEqual(payload["api_endpoint"], mod.KAKAO_USERINFO_URL)
		self.assertEqual(payload["redirect_url"], mod.KAKAO_CALLBACK_PATH)
		self.assertIn("account_email", payload["auth_url_data"])

	def test_unsupported_provider_rejected(self):
		with self.assertRaises(ValueError):
			mod.build_social_login_key_payload("naver", "cid", "secret")

	def test_blank_credentials_rejected(self):
		with self.assertRaises(ValueError):
			mod.build_social_login_key_payload("google", " ", "secret")
		with self.assertRaises(ValueError):
			mod.build_social_login_key_payload("kakao", "cid", "")


class TestNormalizeKakaoUserinfo(unittest.TestCase):
	def _payload(self, **account):
		return {
			"id": 12345,
			"kakao_account": {
				"email": "user@example.com",
				"profile": {"nickname": "홍길동", "profile_image_url": "https://img"},
				**account,
			},
		}

	def test_flattens_nested_email_and_profile(self):
		info = mod.normalize_kakao_userinfo(self._payload())
		self.assertEqual(info["email"], "user@example.com")
		self.assertEqual(info["id"], "12345")
		self.assertEqual(info["first_name"], "홍길동")
		self.assertEqual(info["picture"], "https://img")

	def test_missing_email_raises_explicit_error(self):
		payload = self._payload()
		del payload["kakao_account"]["email"]
		with self.assertRaises(ValueError) as ctx:
			mod.normalize_kakao_userinfo(payload)
		self.assertIn("동의항목", str(ctx.exception))

	def test_missing_id_rejected(self):
		with self.assertRaises(ValueError):
			mod.normalize_kakao_userinfo({"kakao_account": {"email": "a@b.c"}})

	def test_nickname_fallback_to_email_localpart(self):
		payload = self._payload()
		payload["kakao_account"]["profile"] = {}
		info = mod.normalize_kakao_userinfo(payload)
		self.assertEqual(info["first_name"], "user")


if __name__ == "__main__":
	unittest.main()
