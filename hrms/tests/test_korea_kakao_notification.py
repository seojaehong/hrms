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

	def test_builds_side_effect_free_send_queue_item_with_consent_and_retry_policy(self):
		payload = self.mod.build_kakao_template_payload(
			recipient_phone="010-1234-5678",
			template_code="PAYSLIP_READY",
			variables={"employee": "홍길동", "period": "2026-05"},
		)

		queue_item = self.mod.build_kakao_send_queue_item(
			payload=payload,
			recipient_consent=True,
			opted_out=False,
			scheduled_at="2026-05-31T09:00:00+09:00",
			provider_key="partner_alimtalk",
			max_attempts=4,
		)

		self.assertEqual(queue_item["queue_type"], "korea_kakao_send_queue_v1")
		self.assertEqual(queue_item["status"], "queued")
		self.assertEqual(queue_item["provider_key"], "partner_alimtalk")
		self.assertEqual(queue_item["attempt_count"], 0)
		self.assertEqual(queue_item["max_attempts"], 4)
		self.assertEqual(queue_item["next_attempt_at"], "2026-05-31T09:00:00+09:00")
		self.assertEqual(queue_item["payload"], payload)
		self.assertTrue(queue_item["dedupe_key"].startswith("kakao:"))
		self.assertNotIn("PAYSLIP_READY", queue_item["dedupe_key"])
		self.assertNotIn("01012345678", queue_item["dedupe_key"])

	def test_queue_item_rejects_timezone_naive_schedule_values(self):
		payload = self.mod.build_kakao_template_payload(
			recipient_phone="01012345678", template_code="PAYSLIP_READY", variables={}
		)

		with self.assertRaisesRegex(ValueError, "scheduled_at must include timezone"):
			self.mod.build_kakao_send_queue_item(
				payload=payload,
				recipient_consent=True,
				scheduled_at="2026-05-31T09:00:00",
			)

	def test_queue_item_requires_consent_and_rejects_opted_out_recipients(self):
		payload = self.mod.build_kakao_template_payload(
			recipient_phone="01012345678", template_code="PAYSLIP_READY", variables={}
		)

		with self.assertRaisesRegex(ValueError, "recipient_consent is required"):
			self.mod.build_kakao_send_queue_item(payload=payload, recipient_consent=False)

		with self.assertRaisesRegex(ValueError, "recipient has opted out"):
			self.mod.build_kakao_send_queue_item(payload=payload, recipient_consent=True, opted_out=True)

	def test_delivery_attempt_audit_event_records_provider_result_without_mutating_queue_item(self):
		payload = self.mod.build_kakao_template_payload(
			recipient_phone="01012345678", template_code="PAYSLIP_READY", variables={}
		)
		queue_item = self.mod.build_kakao_send_queue_item(
			payload=payload,
			recipient_consent=True,
			scheduled_at="2026-05-31T09:00:00+09:00",
			provider_key="partner_alimtalk",
		)

		audit = self.mod.build_kakao_delivery_audit_event(
			queue_item=queue_item,
			attempted_at="2026-05-31T09:00:02+09:00",
			provider_status="retryable_error",
			provider_message_id="msg-123",
			error_code="TIMEOUT",
		)

		self.assertEqual(audit["event_type"], "korea_kakao_delivery_audit_v1")
		self.assertEqual(audit["dedupe_key"], queue_item["dedupe_key"])
		self.assertEqual(audit["attempt_number"], 1)
		self.assertEqual(audit["provider_key"], "partner_alimtalk")
		self.assertEqual(audit["provider_status"], "retryable_error")
		self.assertEqual(audit["next_retry_at"], "2026-05-31T09:01:02+09:00")
		self.assertEqual(queue_item["attempt_count"], 0)

	def test_non_retryable_delivery_status_does_not_schedule_retry(self):
		payload = self.mod.build_kakao_template_payload(
			recipient_phone="01012345678", template_code="PAYSLIP_READY", variables={}
		)
		queue_item = self.mod.build_kakao_send_queue_item(payload=payload, recipient_consent=True)

		audit = self.mod.build_kakao_delivery_audit_event(
			queue_item=queue_item,
			attempted_at="2026-05-31T09:00:02+09:00",
			provider_status="delivered",
		)

		self.assertIsNone(audit["next_retry_at"])

	def test_delivery_audit_rejects_timezone_naive_attempt_values(self):
		payload = self.mod.build_kakao_template_payload(
			recipient_phone="01012345678", template_code="PAYSLIP_READY", variables={}
		)
		queue_item = self.mod.build_kakao_send_queue_item(payload=payload, recipient_consent=True)

		with self.assertRaisesRegex(ValueError, "attempted_at must include timezone"):
			self.mod.build_kakao_delivery_audit_event(
				queue_item=queue_item,
				attempted_at="2026-05-31T09:00:02",
				provider_status="delivered",
			)

	def test_builds_provider_dispatch_request_without_sending_or_exposing_pii_in_request_id(self):
		payload = self.mod.build_kakao_template_payload(
			recipient_phone="010-1234-5678",
			template_code="PAYSLIP_READY",
			variables={"employee": "홍길동", "period": "2026-05"},
		)
		queue_item = self.mod.build_kakao_send_queue_item(
			payload=payload,
			recipient_consent=True,
			provider_key="partner_alimtalk",
		)

		request = self.mod.build_kakao_provider_dispatch_request(
			queue_item=queue_item,
			provider={
				"provider_key": "partner_alimtalk",
				"provider_type": "partner_api",
				"endpoint_key": "kakao-partner-send",
			},
			requested_at="2026-05-31T09:00:02+09:00",
		)

		self.assertEqual(request["request_type"], "korea_kakao_provider_dispatch_v1")
		self.assertEqual(request["runtime_action"], "send_via_provider")
		self.assertTrue(request["requires_runtime_send"])
		self.assertEqual(request["provider_key"], "partner_alimtalk")
		self.assertEqual(request["provider_type"], "partner_api")
		self.assertEqual(request["endpoint_key"], "kakao-partner-send")
		self.assertEqual(request["attempt_number"], 1)
		self.assertEqual(request["payload"], queue_item["payload"])
		self.assertTrue(request["dispatch_request_id"].startswith("kakao-dispatch:"))
		self.assertNotIn("01012345678", request["dispatch_request_id"])
		self.assertNotIn("PAYSLIP_READY", request["dispatch_request_id"])

	def test_provider_dispatch_rejects_public_api_and_provider_key_mismatch(self):
		payload = self.mod.build_kakao_template_payload(
			recipient_phone="01012345678", template_code="PAYSLIP_READY", variables={}
		)
		queue_item = self.mod.build_kakao_send_queue_item(
			payload=payload,
			recipient_consent=True,
			provider_key="partner_alimtalk",
		)

		with self.assertRaisesRegex(ValueError, "provider_type must be one of"):
			self.mod.build_kakao_provider_dispatch_request(
				queue_item=queue_item,
				provider={"provider_key": "partner_alimtalk", "provider_type": "public_api", "endpoint_key": "public-send"},
				requested_at="2026-05-31T09:00:02+09:00",
			)

		with self.assertRaisesRegex(ValueError, "provider.provider_key must match queue_item.provider_key"):
			self.mod.build_kakao_provider_dispatch_request(
				queue_item=queue_item,
				provider={"provider_key": "other_partner", "provider_type": "partner_api", "endpoint_key": "kakao-partner-send"},
				requested_at="2026-05-31T09:00:02+09:00",
			)

	def test_provider_dispatch_returns_payload_copy_without_mutating_queue_item(self):
		payload = self.mod.build_kakao_template_payload(
			recipient_phone="01012345678", template_code="PAYSLIP_READY", variables={"employee": "홍길동"}
		)
		queue_item = self.mod.build_kakao_send_queue_item(payload=payload, recipient_consent=True, provider_key="partner_alimtalk")

		request = self.mod.build_kakao_provider_dispatch_request(
			queue_item=queue_item,
			provider={"provider_key": "partner_alimtalk", "provider_type": "partner_api", "endpoint_key": "kakao-partner-send"},
			requested_at="2026-05-31T09:00:02+09:00",
		)
		request["payload"]["variables"]["employee"] = "변조"

		self.assertEqual(queue_item["payload"]["variables"]["employee"], "홍길동")

	def test_provider_dispatch_rejects_malformed_queue_payload(self):
		queue_item = {
			"queue_type": "korea_kakao_send_queue_v1",
			"dedupe_key": "kakao:abc",
			"provider_key": "partner_alimtalk",
			"attempt_count": 0,
			"max_attempts": 3,
			"payload": "not-a-dict",
		}

		with self.assertRaisesRegex(TypeError, "payload must be a dict"):
			self.mod.build_kakao_provider_dispatch_request(
				queue_item=queue_item,
				provider={"provider_key": "partner_alimtalk", "provider_type": "partner_api", "endpoint_key": "kakao-partner-send"},
				requested_at="2026-05-31T09:00:02+09:00",
			)

	def test_builds_template_registry_entry_without_provider_side_effects(self):
		entry = self.mod.build_kakao_template_registry_entry(
			template_code="PAYSLIP_READY",
			template_name="급여명세서 발송",
			template_body="{{employee}}님 {{period}} 급여명세서가 준비되었습니다.",
			required_variables=["period", "employee"],
			consent_purpose="payroll_notification",
			provider_template_keys={"partner_alimtalk": "tpl-001"},
			active=True,
		)

		self.assertEqual(entry["registry_type"], "korea_kakao_template_registry_v1")
		self.assertEqual(entry["channel"], "kakao_alimtalk")
		self.assertEqual(entry["template_code"], "PAYSLIP_READY")
		self.assertEqual(entry["template_name"], "급여명세서 발송")
		self.assertEqual(entry["required_variables"], ["employee", "period"])
		self.assertEqual(entry["consent_purpose"], "payroll_notification")
		self.assertEqual(entry["provider_template_keys"], {"partner_alimtalk": "tpl-001"})
		self.assertTrue(entry["active"])
		self.assertFalse(entry["requires_runtime_send"])

	def test_template_registry_rejects_non_bool_active_flags_at_creation(self):
		with self.assertRaisesRegex(TypeError, "active must be a bool"):
			self.mod.build_kakao_template_registry_entry(
				template_code="PAYSLIP_READY",
				template_name="급여명세서 발송",
				template_body="{{employee}}님",
				required_variables=["employee"],
				consent_purpose="payroll_notification",
				active="false",
			)

	def test_template_registry_rejects_body_variable_mismatch_and_pii_provider_keys(self):
		with self.assertRaisesRegex(ValueError, "required_variables must match body variables"):
			self.mod.build_kakao_template_registry_entry(
				template_code="PAYSLIP_READY",
				template_name="급여명세서 발송",
				template_body="{{employee}}님 {{period}}",
				required_variables=["employee"],
				consent_purpose="payroll_notification",
			)

		with self.assertRaisesRegex(ValueError, "required_variables must match body variables"):
			self.mod.build_kakao_template_registry_entry(
				template_code="PAYSLIP_READY",
				template_name="급여명세서 발송",
				template_body="{{employee}}님",
				required_variables=["employee", "unused"],
				consent_purpose="payroll_notification",
			)

		with self.assertRaisesRegex(ValueError, "template_body is required"):
			self.mod.build_kakao_template_registry_entry(
				template_code="PAYSLIP_READY",
				template_name="급여명세서 발송",
				template_body="   ",
				required_variables=["employee"],
				consent_purpose="payroll_notification",
			)

		with self.assertRaisesRegex(ValueError, "provider_template_keys must not contain phone numbers"):
			self.mod.build_kakao_template_registry_entry(
				template_code="PAYSLIP_READY",
				template_name="급여명세서 발송",
				template_body="{{employee}}님",
				required_variables=["employee"],
				consent_purpose="payroll_notification",
				provider_template_keys={"01012345678": "tpl-001"},
			)

		with self.assertRaisesRegex(ValueError, "provider_template_keys must not contain phone numbers"):
			self.mod.build_kakao_template_registry_entry(
				template_code="PAYSLIP_READY",
				template_name="급여명세서 발송",
				template_body="{{employee}}님",
				required_variables=["employee"],
				consent_purpose="payroll_notification",
				provider_template_keys={"partner_alimtalk": "tpl-010-1234-5678"},
			)

	def test_builds_registered_template_payload_and_rejects_inactive_or_missing_variables(self):
		entry = self.mod.build_kakao_template_registry_entry(
			template_code="PAYSLIP_READY",
			template_name="급여명세서 발송",
			template_body="{{employee}}님 {{period}} 급여명세서가 준비되었습니다.",
			required_variables=["employee", "period"],
			consent_purpose="payroll_notification",
		)

		payload = self.mod.build_registered_kakao_template_payload(
			recipient_phone="010-1234-5678",
			template_registry_entry=entry,
			variables={"employee": "홍길동", "period": "2026-05", "ignored": "value"},
		)

		self.assertEqual(payload["template_code"], "PAYSLIP_READY")
		self.assertEqual(payload["variables"], {"employee": "홍길동", "period": "2026-05"})
		self.assertEqual(payload["consent_purpose"], "payroll_notification")
		self.assertEqual(payload["preview_text"], "홍길동님 2026-05 급여명세서가 준비되었습니다.")

		inactive_entry = {**entry, "active": False}
		with self.assertRaisesRegex(ValueError, "template registry entry is inactive"):
			self.mod.build_registered_kakao_template_payload(
				recipient_phone="01012345678",
				template_registry_entry=inactive_entry,
				variables={"employee": "홍길동", "period": "2026-05"},
			)

		string_inactive_entry = {**entry, "active": "false"}
		with self.assertRaisesRegex(TypeError, "template_registry_entry.active must be a bool"):
			self.mod.build_registered_kakao_template_payload(
				recipient_phone="01012345678",
				template_registry_entry=string_inactive_entry,
				variables={"employee": "홍길동", "period": "2026-05"},
			)

		with self.assertRaisesRegex(ValueError, "missing template variables: period"):
			self.mod.build_registered_kakao_template_payload(
				recipient_phone="01012345678",
				template_registry_entry=entry,
				variables={"employee": "홍길동"},
			)


if __name__ == "__main__":
	unittest.main()
