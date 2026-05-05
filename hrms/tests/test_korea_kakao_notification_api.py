#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "kakao_notification_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_kakao_notification_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKakaoNotificationPreviewAPI(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_previews_registered_template_queue_item_from_json_inputs_without_sending(self):
		registry_entry = {
			"registry_type": "korea_kakao_template_registry_v1",
			"channel": "kakao_alimtalk",
			"template_code": "PAYSLIP_READY",
			"template_name": "급여명세서 발송",
			"template_body": "{{employee}}님 {{period}} 급여명세서가 준비되었습니다.",
			"required_variables": ["employee", "period"],
			"consent_purpose": "payroll_notification",
			"provider_template_keys": {"partner_alimtalk": "tpl-001"},
			"active": True,
			"requires_runtime_send": False,
		}

		preview = self.mod.preview_korea_kakao_registered_queue_item(
			recipient_phone="010-1234-5678",
			template_registry_entry=json.dumps(registry_entry, ensure_ascii=False),
			variables=json.dumps({"employee": "홍길동", "period": "2026-05"}, ensure_ascii=False),
			recipient_consent=True,
			opted_out=False,
			scheduled_at="2026-05-31T09:00:00+09:00",
			provider_key="partner_alimtalk",
			max_attempts="4",
		)

		self.assertEqual(preview["contract_type"], "korea_kakao_queue_preview_v1")
		self.assertEqual(preview["runtime_action"], "preview_only")
		self.assertTrue(preview["requires_runtime_send"])
		self.assertEqual(preview["payload"]["recipient_phone"], "01012345678")
		self.assertEqual(preview["payload"]["preview_text"], "홍길동님 2026-05 급여명세서가 준비되었습니다.")
		self.assertEqual(preview["queue_item"]["provider_key"], "partner_alimtalk")
		self.assertEqual(preview["queue_item"]["max_attempts"], 4)
		self.assertTrue(preview["queue_item"]["dedupe_key"].startswith("kakao:"))
		self.assertNotIn("01012345678", preview["queue_item"]["dedupe_key"])
		self.assertNotIn("PAYSLIP_READY", preview["queue_item"]["dedupe_key"])

	def test_previews_provider_dispatch_from_json_without_mutating_queue_item(self):
		queue_item = {
			"queue_type": "korea_kakao_send_queue_v1",
			"status": "queued",
			"channel": "kakao_alimtalk",
			"provider_key": "partner_alimtalk",
			"dedupe_key": "kakao:abc123",
			"payload": {
				"channel": "kakao_alimtalk",
				"recipient_phone": "01012345678",
				"template_code": "PAYSLIP_READY",
				"variables": {"employee": "홍길동"},
			},
			"attempt_count": 1,
			"max_attempts": 3,
			"next_attempt_at": None,
			"requires_runtime_send": True,
		}

		preview = self.mod.preview_korea_kakao_provider_dispatch(
			queue_item=json.dumps(queue_item, ensure_ascii=False),
			provider={"provider_key": "partner_alimtalk", "provider_type": "partner_api", "endpoint_key": "kakao-partner-send"},
			requested_at="2026-05-31T09:01:00+09:00",
		)
		preview["dispatch_request"]["payload"]["variables"]["employee"] = "변조"

		self.assertEqual(preview["contract_type"], "korea_kakao_dispatch_preview_v1")
		self.assertEqual(preview["runtime_action"], "preview_only")
		self.assertEqual(preview["dispatch_request"]["attempt_number"], 2)
		self.assertTrue(preview["dispatch_request"]["dispatch_request_id"].startswith("kakao-dispatch:"))
		self.assertNotIn("01012345678", preview["dispatch_request"]["dispatch_request_id"])
		self.assertEqual(queue_item["payload"]["variables"]["employee"], "홍길동")

	def test_previews_delivery_audit_event_from_json_without_mutating_queue_item(self):
		queue_item = {
			"queue_type": "korea_kakao_send_queue_v1",
			"status": "queued",
			"channel": "kakao_alimtalk",
			"provider_key": "partner_alimtalk",
			"dedupe_key": "kakao:abc123",
			"payload": {
				"channel": "kakao_alimtalk",
				"recipient_phone": "01012345678",
				"template_code": "PAYSLIP_READY",
				"variables": {"employee": "홍길동"},
			},
			"attempt_count": 1,
			"max_attempts": 3,
			"next_attempt_at": None,
			"requires_runtime_send": True,
		}

		preview = self.mod.preview_korea_kakao_delivery_audit_event(
			queue_item=json.dumps(queue_item, ensure_ascii=False),
			attempted_at="2026-05-31T09:02:00+09:00",
			provider_status="timeout",
			provider_message_id="provider-msg-001",
			error_code="TIMEOUT",
			base_retry_delay_seconds="120",
			max_retry_delay_seconds="600",
		)
		preview["audit_event"]["dedupe_key"] = "mutated"

		self.assertEqual(preview["contract_type"], "korea_kakao_delivery_audit_preview_v1")
		self.assertEqual(preview["runtime_action"], "preview_only")
		self.assertTrue(preview["requires_runtime_send"])
		self.assertEqual(preview["audit_event"]["attempt_number"], 2)
		self.assertEqual(preview["audit_event"]["provider_status"], "timeout")
		self.assertEqual(preview["audit_event"]["next_retry_at"], "2026-05-31T09:06:00+09:00")
		self.assertEqual(queue_item["dedupe_key"], "kakao:abc123")

	def test_rejects_invalid_json_and_non_mapping_inputs(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_kakao_provider_dispatch(
				queue_item="{not-json",
				provider={"provider_key": "partner_alimtalk", "provider_type": "partner_api", "endpoint_key": "send"},
				requested_at="2026-05-31T09:01:00+09:00",
			)

		with self.assertRaisesRegex(ValueError, "variables must be a dict or JSON object"):
			self.mod.preview_korea_kakao_registered_queue_item(
				recipient_phone="01012345678",
				template_registry_entry={},
				variables=[],
				recipient_consent=True,
			)

		with self.assertRaisesRegex(ValueError, "base_retry_delay_seconds must be an integer"):
			self.mod.preview_korea_kakao_delivery_audit_event(
				queue_item={
					"queue_type": "korea_kakao_send_queue_v1",
					"provider_key": "partner_alimtalk",
					"dedupe_key": "kakao:abc123",
					"payload": {"channel": "kakao_alimtalk", "recipient_phone": "01012345678", "template_code": "PAYSLIP_READY"},
					"attempt_count": 0,
					"max_attempts": 3,
				},
				attempted_at="2026-05-31T09:02:00+09:00",
				provider_status="timeout",
				base_retry_delay_seconds="not-a-number",
			)


if __name__ == "__main__":
	unittest.main()
