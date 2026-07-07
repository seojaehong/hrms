"""F3 요청 보드(Korea Service Request) API 테스트 — framework-free.

실행: python3 hrms/tests/test_korea_service_request.py

검증 항목:
- category 검증(허용 목록) / 상태 전이 규칙(완료=종결) — framework-free 함수
- create_service_request: 제목 필수, category 검증, company Global Defaults 폴백,
  requested_by 기록, HR Manager Notification Log(best effort — 실패해도 제출 성공)
- list_service_requests: company/status 필터 + count
- update_service_request_status: HR Manager 전용(only_for) + 상태 전이 + 완료 시 resolved_at
"""

from __future__ import annotations

import copy
import importlib.util
import pathlib
import sys
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "service_request_api.py"
)


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


class FakeDB:
	def __init__(self, default_company=None):
		self._default_company = default_company

	def get_single_value(self, doctype, field):
		if doctype == "Global Defaults" and field == "default_company":
			return self._default_company
		return None


class FakeFrappe:
	"""service_request_api가 쓰는 표면만 제공하는 스텁."""

	def __init__(
		self,
		docs=None,
		hr_manager_users=None,
		notification_fails=False,
		default_company=None,
		session_user="client@noho.kr",
	):
		self.docs = [dict(d) for d in (docs or [])]
		self.inserted = []
		self.get_all_calls = []
		self.only_for_calls = []
		self.hr_manager_users = (
			hr_manager_users if hr_manager_users is not None else ["hr@noho.kr"]
		)
		self.notification_fails = notification_fails
		self.db = FakeDB(default_company)
		self.session = type("S", (), {"user": session_user})()

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
		if doctype == "Korea Service Request":
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
				return FakeDoc(doc, self.inserted)
		raise KeyError(f"{arg} {name} not found")


def load_module(fake_frappe=None):
	old_frappe = sys.modules.get("frappe")
	if fake_frappe is not None:
		sys.modules["frappe"] = fake_frappe
	else:
		sys.modules.pop("frappe", None)
	try:
		spec = importlib.util.spec_from_file_location("korea_service_request_api", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if old_frappe is not None:
			sys.modules["frappe"] = old_frappe
		else:
			sys.modules.pop("frappe", None)


# ──────────────────────────────────────────────
# framework-free 검증 (frappe 없이 로드/실행)
# ──────────────────────────────────────────────


class TestValidation(unittest.TestCase):
	def setUp(self):
		self.mod = load_module(fake_frappe=None)

	def test_valid_categories(self):
		for cat in ("급여", "4대보험", "증명서", "연차·근태", "기타"):
			self.assertEqual(self.mod.validate_category(cat), cat)

	def test_invalid_category(self):
		with self.assertRaises(ValueError):
			self.mod.validate_category("환불")

	def test_empty_category(self):
		with self.assertRaises(ValueError):
			self.mod.validate_category("")

	def test_status_transition_allowed(self):
		self.assertEqual(self.mod.validate_status_transition("접수", "처리중"), "처리중")
		self.assertEqual(self.mod.validate_status_transition("처리중", "완료"), "완료")

	def test_status_transition_terminal_completed(self):
		with self.assertRaises(ValueError):
			self.mod.validate_status_transition("완료", "처리중")

	def test_status_transition_unknown_target(self):
		with self.assertRaises(ValueError):
			self.mod.validate_status_transition("접수", "종료")


# ──────────────────────────────────────────────
# create_service_request
# ──────────────────────────────────────────────


class TestCreate(unittest.TestCase):
	def _payload(self, **overrides):
		payload = {"company": "노호", "title": "5월 급여 명세서 재발급", "category": "급여", "detail": "홍길동"}
		payload.update(overrides)
		return payload

	def test_create_success_records_requested_by_and_notifies(self):
		fake = FakeFrappe()
		mod = load_module(fake)
		result = mod.create_service_request(self._payload())
		self.assertEqual(result["status"], "접수")
		self.assertEqual(result["requested_by"], "client@noho.kr")
		self.assertEqual(result["category"], "급여")
		# 요청 doc + HR Manager 1인 Notification Log 삽입
		req_docs = [d for d in fake.inserted if d.get("doctype") == "Korea Service Request"]
		notif = [d for d in fake.inserted if d.get("doctype") == "Notification Log"]
		self.assertEqual(len(req_docs), 1)
		self.assertEqual(len(notif), 1)
		self.assertEqual(notif[0]["for_user"], "hr@noho.kr")

	def test_create_missing_title_rejected(self):
		fake = FakeFrappe()
		mod = load_module(fake)
		with self.assertRaises(ValueError):
			mod.create_service_request(self._payload(title="  "))
		self.assertEqual(fake.inserted, [])  # 무저장

	def test_create_invalid_category_rejected(self):
		fake = FakeFrappe()
		mod = load_module(fake)
		with self.assertRaises(ValueError):
			mod.create_service_request(self._payload(category="환불"))
		self.assertEqual(fake.inserted, [])

	def test_create_company_fallback_global_defaults(self):
		fake = FakeFrappe(default_company="노호")
		mod = load_module(fake)
		result = mod.create_service_request(self._payload(company=None))
		self.assertEqual(result["company"], "노호")

	def test_create_notification_failure_still_succeeds(self):
		fake = FakeFrappe(notification_fails=True)
		mod = load_module(fake)
		result = mod.create_service_request(self._payload())
		self.assertEqual(result["status"], "접수")  # 알림 실패해도 제출 성공
		req_docs = [d for d in fake.inserted if d.get("doctype") == "Korea Service Request"]
		self.assertEqual(len(req_docs), 1)

	def test_create_json_string_payload(self):
		import json

		fake = FakeFrappe()
		mod = load_module(fake)
		result = mod.create_service_request(json.dumps(self._payload()))
		self.assertEqual(result["title"], "5월 급여 명세서 재발급")


# ──────────────────────────────────────────────
# list_service_requests
# ──────────────────────────────────────────────


class TestList(unittest.TestCase):
	def _docs(self):
		return [
			{"name": "KR-REQ-1", "doctype": "Korea Service Request", "company": "노호", "title": "a", "category": "급여", "status": "접수"},
			{"name": "KR-REQ-2", "doctype": "Korea Service Request", "company": "노호", "title": "b", "category": "증명서", "status": "완료"},
			{"name": "KR-REQ-3", "doctype": "Korea Service Request", "company": "타사", "title": "c", "category": "기타", "status": "접수"},
		]

	def test_list_status_filter(self):
		fake = FakeFrappe(docs=self._docs())
		mod = load_module(fake)
		result = mod.list_service_requests(company="노호", status="접수")
		self.assertEqual(result["count"], 1)
		self.assertEqual(result["requests"][0]["name"], "KR-REQ-1")

	def test_list_company_fallback(self):
		fake = FakeFrappe(docs=self._docs(), default_company="노호")
		mod = load_module(fake)
		result = mod.list_service_requests()
		self.assertEqual(result["company"], "노호")
		self.assertEqual(result["count"], 2)  # 노호 2건

	def test_list_invalid_status_rejected(self):
		fake = FakeFrappe(docs=self._docs())
		mod = load_module(fake)
		with self.assertRaises(ValueError):
			mod.list_service_requests(status="종료")


# ──────────────────────────────────────────────
# update_service_request_status
# ──────────────────────────────────────────────


class TestUpdateStatus(unittest.TestCase):
	def _docs(self):
		return [
			{"name": "KR-REQ-1", "doctype": "Korea Service Request", "company": "노호", "title": "a", "category": "급여", "status": "접수"},
		]

	def test_update_requires_hr_manager(self):
		fake = FakeFrappe(docs=self._docs())
		mod = load_module(fake)
		mod.update_service_request_status("KR-REQ-1", "처리중")
		self.assertIn(("System Manager", "HR Manager"), fake.only_for_calls)

	def test_update_valid_transition(self):
		fake = FakeFrappe(docs=self._docs())
		mod = load_module(fake)
		result = mod.update_service_request_status("KR-REQ-1", "처리중")
		self.assertEqual(result["status"], "처리중")
		self.assertIsNone(result["resolved_at"])  # 완료 아님 → 미기록

	def test_update_completed_sets_resolved_at(self):
		fake = FakeFrappe(docs=self._docs())
		mod = load_module(fake)
		result = mod.update_service_request_status(
			"KR-REQ-1", "완료", resolution_note="처리 완료"
		)
		self.assertEqual(result["status"], "완료")
		self.assertIsNotNone(result["resolved_at"])
		self.assertEqual(result["resolution_note"], "처리 완료")

	def test_update_illegal_transition_rejected(self):
		fake = FakeFrappe(docs=[
			{"name": "KR-REQ-9", "doctype": "Korea Service Request", "company": "노호", "title": "z", "category": "급여", "status": "완료"},
		])
		mod = load_module(fake)
		with self.assertRaises(ValueError):
			mod.update_service_request_status("KR-REQ-9", "처리중")


if __name__ == "__main__":
	unittest.main()
