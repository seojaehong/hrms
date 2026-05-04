#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "kakao_notification.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_kakao_notification", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKakaoNotificationAdapter(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_builds_template_payload_with_required_recipient_and_variables(self):
		payload = self.mod.build_kakao_template_payload(
			recipient_phone="010-1234-5678",
			template_code="PAYSLIP_READY",
			variables={"employee": "홍길동", "period": "2026-05"},
		)

		self.assertEqual(payload["recipient_phone"], "01012345678")
		self.assertEqual(payload["template_code"], "PAYSLIP_READY")
		self.assertEqual(payload["variables"], {"employee": "홍길동", "period": "2026-05"})
		self.assertEqual(payload["channel"], "kakao_alimtalk")

	def test_render_preview_replaces_template_variables(self):
		message = self.mod.render_kakao_preview("{{employee}}님 {{period}} 급여명세서가 준비되었습니다.", {"employee": "홍길동", "period": "2026-05"})

		self.assertEqual(message, "홍길동님 2026-05 급여명세서가 준비되었습니다.")

	def test_missing_template_variable_is_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.render_kakao_preview("{{employee}}님 {{period}}", {"employee": "홍길동"})

	def test_invalid_phone_is_rejected_before_external_side_effect(self):
		with self.assertRaises(ValueError):
			self.mod.build_kakao_template_payload(recipient_phone="02-1234", template_code="PAYSLIP_READY", variables={})


if __name__ == "__main__":
	unittest.main()
