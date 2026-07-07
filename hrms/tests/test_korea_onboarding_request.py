"""입사자 등록 요청(Korea Employee Onboarding Request) API 테스트 — framework-free.

실행: python3 hrms/tests/test_korea_onboarding_request.py

검증 항목:
- rrn 형식 검증(13자리·하이픈 허용·성별코드 1-8·생년월일 정합) — framework-free 함수
- rrn 마스킹 "9401**-1******" 형식
- create/list/mark_processed 어떤 응답에도 rrn 평문이 포함되지 않음 (PII 불변식)
- list는 masked_rrn만 노출하고 rrn 필드를 조회조차 하지 않음
- mark_onboarding_processed는 HR Manager 전용 + status 전이 규칙
- 제출 시 HR Manager Notification Log 생성 (best effort — 실패해도 요청은 성공)
"""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import sys
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "onboarding_request_api.py"
)

VALID_RRN = "9401011234567"
VALID_RRN_HYPHEN = "940101-1234567"
MASKED_RRN = "9401**-1******"


class FakeDoc:
	"""frappe.get_doc 스텁 — dict 기반 최소 Document."""

	def __init__(self, data, store, name=None):
		self._data = dict(data)
		self._store = store
		if name:
			self._data.setdefault("name", name)

	def __getattr__(self, key):
		try:
			return self._data[key]
		except KeyError as exc:  # pragma: no cover - attribute protocol
			raise AttributeError(key) from exc

	def get(self, key, default=None):
		return self._data.get(key, default)

	def set(self, key, value):
		self._data[key] = value

	def insert(self, ignore_permissions=False):
		doctype = self._data.get("doctype", "?")
		seq = len([d for d in self._store if d.get("doctype") == doctype]) + 1
		self._data.setdefault("name", f"{doctype}-{seq:04d}")
		self._store.append(copy.deepcopy(self._data))
		return self

	def save(self, ignore_permissions=False):
		self._store.append(copy.deepcopy(self._data))
		return self

	def as_dict(self):
		return dict(self._data)


class FakeFrappe:
	"""onboarding_request_api가 쓰는 표면만 제공하는 스텁."""

	def __init__(self, docs=None, hr_manager_users=None, notification_fails=False):
		self.docs = [dict(d) for d in (docs or [])]
		self.inserted = []
		self.get_all_calls = []
		self.only_for_calls = []
		self.hr_manager_users = hr_manager_users if hr_manager_users is not None else ["hr@noho.kr"]
		self.notification_fails = notification_fails
		self.session = type("S", (), {"user": "hruser@noho.kr"})()

	def whitelist(self):
		def decorator(fn):
			return fn

		return decorator

	def only_for(self, roles):
		self.only_for_calls.append(tuple(roles))

	def get_all(self, doctype, *, filters=None, fields=None, order_by=None):
		self.get_all_calls.append(
			{"doctype": doctype, "filters": copy.deepcopy(filters), "fields": list(fields or [])}
		)
		if doctype == "Has Role":
			return [{"parent": u} for u in self.hr_manager_users]
		if doctype == "Korea Employee Onboarding Request":
			rows = []
			for doc in self.docs:
				if filters:
					if filters.get("company") and doc.get("company") != filters["company"]:
						continue
					if filters.get("status") and doc.get("status") != filters["status"]:
						continue
				rows.append({f: copy.deepcopy(doc.get(f)) for f in fields or []})
			return rows
		return []

	def get_doc(self, arg, name=None):
		if isinstance(arg, dict):
			if self.notification_fails and arg.get("doctype") == "Notification Log":
				raise RuntimeError("notification backend down")
			return FakeDoc(arg, self.inserted)
		for doc in self.docs:
			if doc.get("name") == name:
				live = FakeDoc(doc, self.inserted)
				return live
		raise KeyError(f"{arg} {name} not found")


def load_module(fake_frappe=None):
	old_frappe = sys.modules.get("frappe")
	if fake_frappe is not None:
		sys.modules["frappe"] = fake_frappe
	else:
		sys.modules.pop("frappe", None)
	try:
		spec = importlib.util.spec_from_file_location("korea_onboarding_request_api", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if old_frappe is not None:
			sys.modules["frappe"] = old_frappe
		else:
			sys.modules.pop("frappe", None)


def valid_payload(**overrides):
	payload = {
		"company": "노호",
		"full_name": "김입사",
		"rrn": VALID_RRN_HYPHEN,
		"join_date": "2026-07-15",
		"reported_monthly_wage": 2800000,
		"contract_type": "정규직",
		"phone": "010-1234-5678",
		"note": "주방 보조",
	}
	payload.update(overrides)
	return payload


class TestRrnValidation(unittest.TestCase):
	"""framework-free rrn 검증 — frappe 없이 로드/실행 가능해야 한다."""

	def setUp(self):
		self.mod = load_module(fake_frappe=None)

	def test_valid_rrn_plain(self):
		self.assertEqual(self.mod.validate_rrn(VALID_RRN), VALID_RRN)

	def test_valid_rrn_hyphen_normalized(self):
		self.assertEqual(self.mod.validate_rrn(VALID_RRN_HYPHEN), VALID_RRN)

	def test_gender_codes_1_to_8_accepted(self):
		for code in "12345678":
			rrn = f"940101{code}234567"
			self.assertEqual(self.mod.validate_rrn(rrn), rrn)

	def test_invalid_gender_codes_rejected(self):
		for code in "09":
			with self.assertRaises(ValueError):
				self.mod.validate_rrn(f"940101{code}234567")

	def test_wrong_length_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.validate_rrn("940101123456")  # 12자리
		with self.assertRaises(ValueError):
			self.mod.validate_rrn("94010112345678")  # 14자리

	def test_non_digit_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.validate_rrn("94010a1234567")

	def test_invalid_birth_month_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.validate_rrn("9413011234567")  # 13월

	def test_invalid_birth_day_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.validate_rrn("9401321234567")  # 32일

	def test_empty_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.validate_rrn("")
		with self.assertRaises(ValueError):
			self.mod.validate_rrn(None)

	def test_error_message_never_echoes_rrn(self):
		"""검증 실패 메시지에 입력 rrn 숫자가 그대로 들어가면 로그로 새는 경로가 된다."""
		bad = "9413011234567"
		try:
			self.mod.validate_rrn(bad)
		except ValueError as exc:
			self.assertNotIn(bad, str(exc))
			self.assertNotIn("941301", str(exc))
		else:
			self.fail("ValueError expected")


class TestRrnMasking(unittest.TestCase):
	def setUp(self):
		self.mod = load_module(fake_frappe=None)

	def test_mask_format(self):
		self.assertEqual(self.mod.mask_rrn(VALID_RRN), MASKED_RRN)

	def test_mask_accepts_hyphen_input(self):
		self.assertEqual(self.mod.mask_rrn(VALID_RRN_HYPHEN), MASKED_RRN)

	def test_mask_never_contains_tail_digits(self):
		masked = self.mod.mask_rrn(VALID_RRN)
		self.assertNotIn("234567", masked)
		self.assertNotIn("0101", masked[4:])


class TestCreateOnboardingRequest(unittest.TestCase):
	def test_create_returns_summary_without_rrn(self):
		fake = FakeFrappe()
		mod = load_module(fake)
		result = mod.create_onboarding_request(valid_payload())
		self.assertEqual(result["status"], "requested")
		self.assertEqual(result["full_name"], "김입사")
		self.assertEqual(result["masked_rrn"], MASKED_RRN)
		self.assertTrue(result.get("name"))
		# PII 불변식: 응답 어디에도 rrn 평문 없음
		serialized = json.dumps(result, ensure_ascii=False, default=str)
		self.assertNotIn(VALID_RRN, serialized)
		self.assertNotIn(VALID_RRN_HYPHEN, serialized)
		self.assertNotIn("1234567", serialized)

	def test_create_accepts_json_string_payload(self):
		fake = FakeFrappe()
		mod = load_module(fake)
		result = mod.create_onboarding_request(json.dumps(valid_payload(), ensure_ascii=False))
		self.assertEqual(result["status"], "requested")

	def test_create_requires_hr_roles(self):
		fake = FakeFrappe()
		mod = load_module(fake)
		mod.create_onboarding_request(valid_payload())
		self.assertTrue(fake.only_for_calls)
		self.assertIn("HR User", fake.only_for_calls[0])
		self.assertIn("HR Manager", fake.only_for_calls[0])

	def test_create_stores_doc_with_masked_rrn_and_requester(self):
		fake = FakeFrappe()
		mod = load_module(fake)
		mod.create_onboarding_request(valid_payload())
		stored = [d for d in fake.inserted if d.get("doctype") == "Korea Employee Onboarding Request"]
		self.assertEqual(len(stored), 1)
		self.assertEqual(stored[0]["masked_rrn"], MASKED_RRN)
		self.assertEqual(stored[0]["status"], "requested")
		self.assertEqual(stored[0]["requested_by"], "hruser@noho.kr")
		# 저장 doc의 rrn은 정규화된 13자리 (Password 필드로 암호화 저장됨)
		self.assertEqual(stored[0]["rrn"], VALID_RRN)

	def test_missing_required_field_rejected(self):
		fake = FakeFrappe()
		mod = load_module(fake)
		for field in ("company", "full_name", "rrn", "join_date", "reported_monthly_wage", "contract_type"):
			payload = valid_payload()
			payload.pop(field)
			with self.assertRaises(ValueError):
				mod.create_onboarding_request(payload)

	def test_invalid_contract_type_rejected(self):
		fake = FakeFrappe()
		mod = load_module(fake)
		with self.assertRaises(ValueError):
			mod.create_onboarding_request(valid_payload(contract_type="프리랜서"))

	def test_notification_sent_to_hr_managers(self):
		fake = FakeFrappe(hr_manager_users=["mgr1@noho.kr", "mgr2@noho.kr"])
		mod = load_module(fake)
		mod.create_onboarding_request(valid_payload())
		logs = [d for d in fake.inserted if d.get("doctype") == "Notification Log"]
		self.assertEqual({log["for_user"] for log in logs}, {"mgr1@noho.kr", "mgr2@noho.kr"})
		# 알림 본문에도 rrn 평문 금지
		for log in logs:
			serialized = json.dumps(log, ensure_ascii=False, default=str)
			self.assertNotIn(VALID_RRN, serialized)
			self.assertNotIn("1234567", serialized)

	def test_notification_failure_does_not_block_request(self):
		fake = FakeFrappe(notification_fails=True)
		mod = load_module(fake)
		result = mod.create_onboarding_request(valid_payload())
		self.assertEqual(result["status"], "requested")


class TestListOnboardingRequests(unittest.TestCase):
	def _docs(self):
		return [
			{
				"name": "KR-ONB-0001", "company": "노호", "full_name": "김입사",
				"masked_rrn": MASKED_RRN, "join_date": "2026-07-15",
				"reported_monthly_wage": 2800000, "contract_type": "정규직",
				"status": "requested", "requested_by": "hruser@noho.kr",
				"processed_by": None, "processed_at": None, "employee": None,
			},
			{
				"name": "KR-ONB-0002", "company": "타사", "full_name": "박타사",
				"masked_rrn": "8803**-2******", "join_date": "2026-07-01",
				"reported_monthly_wage": 2500000, "contract_type": "파트타임",
				"status": "completed", "requested_by": "hruser@noho.kr",
				"processed_by": "mgr1@noho.kr", "processed_at": "2026-07-02 10:00:00",
				"employee": "HR-EMP-002",
			},
		]

	def test_list_returns_masked_rrn_only(self):
		fake = FakeFrappe(docs=self._docs())
		mod = load_module(fake)
		result = mod.list_onboarding_requests()
		self.assertEqual(result["count"], 2)
		serialized = json.dumps(result, ensure_ascii=False, default=str)
		self.assertNotIn(VALID_RRN, serialized)
		for row in result["requests"]:
			self.assertNotIn("rrn", row)  # masked_rrn만 존재해야 한다
			self.assertIn("masked_rrn", row)

	def test_list_never_queries_rrn_field(self):
		fake = FakeFrappe(docs=self._docs())
		mod = load_module(fake)
		mod.list_onboarding_requests()
		calls = [c for c in fake.get_all_calls if c["doctype"] == "Korea Employee Onboarding Request"]
		self.assertTrue(calls)
		for call in calls:
			self.assertNotIn("rrn", call["fields"])

	def test_list_filters_company_and_status(self):
		fake = FakeFrappe(docs=self._docs())
		mod = load_module(fake)
		result = mod.list_onboarding_requests(company="노호", status="requested")
		self.assertEqual(result["count"], 1)
		self.assertEqual(result["requests"][0]["full_name"], "김입사")


class TestMarkProcessed(unittest.TestCase):
	def _fake(self, status="requested"):
		return FakeFrappe(docs=[{
			"name": "KR-ONB-0001", "doctype": "Korea Employee Onboarding Request",
			"company": "노호", "full_name": "김입사", "masked_rrn": MASKED_RRN,
			"join_date": "2026-07-15", "reported_monthly_wage": 2800000,
			"contract_type": "정규직", "status": status,
			"requested_by": "hruser@noho.kr", "rrn": VALID_RRN,
		}])

	def test_mark_processed_is_hr_manager_only(self):
		fake = self._fake()
		mod = load_module(fake)
		mod.mark_onboarding_processed("KR-ONB-0001", employee="HR-EMP-001")
		self.assertTrue(fake.only_for_calls)
		roles = fake.only_for_calls[-1]
		self.assertIn("HR Manager", roles)
		self.assertNotIn("HR User", roles)

	def test_mark_processed_sets_processor_and_employee(self):
		fake = self._fake()
		mod = load_module(fake)
		result = mod.mark_onboarding_processed("KR-ONB-0001", employee="HR-EMP-001")
		self.assertEqual(result["status"], "completed")
		self.assertEqual(result["employee"], "HR-EMP-001")
		self.assertEqual(result["processed_by"], "hruser@noho.kr")
		self.assertTrue(result["processed_at"])
		serialized = json.dumps(result, ensure_ascii=False, default=str)
		self.assertNotIn(VALID_RRN, serialized)
		self.assertNotIn("1234567", serialized)

	def test_mark_processing_transition(self):
		fake = self._fake()
		mod = load_module(fake)
		result = mod.mark_onboarding_processed("KR-ONB-0001", status="processing")
		self.assertEqual(result["status"], "processing")

	def test_invalid_target_status_rejected(self):
		fake = self._fake()
		mod = load_module(fake)
		with self.assertRaises(ValueError):
			mod.mark_onboarding_processed("KR-ONB-0001", status="requested")

	def test_terminal_status_cannot_transition(self):
		for terminal in ("completed", "rejected"):
			fake = self._fake(status=terminal)
			mod = load_module(fake)
			with self.assertRaises(ValueError):
				mod.mark_onboarding_processed("KR-ONB-0001", status="completed")


if __name__ == "__main__":
	unittest.main()
