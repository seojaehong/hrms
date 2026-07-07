#!/usr/bin/env python3
"""Tests for Korea Payroll Time Input API (F1 근무시간 제출).

FakeFrappe direct-run pattern: see test_korea_admin_dashboard_runtime_api.py.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import sys
import types
import unittest

API_MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "payroll_time_input_api.py"
)

DOCTYPE = "Korea Payroll Time Input"


class FakeDoc:
	def __init__(self, frappe, data):
		self._frappe = frappe
		self._data = data

	def __getattr__(self, name):
		data = object.__getattribute__(self, "_data")
		if name in data:
			return data[name]
		raise AttributeError(name)

	def __setattr__(self, name, value):
		if name.startswith("_"):
			object.__setattr__(self, name, value)
		else:
			self._data[name] = value

	def insert(self):
		self._frappe.docs.append(self._data)
		self._frappe.inserted.append(copy.deepcopy(self._data))
		return self

	def save(self):
		self._frappe.saved.append(copy.deepcopy(self._data))
		return self


class FakeFrappe:
	def __init__(self, *, employees=None, docs=None, allowed_roles=True, default_company="노호"):
		self.employees = list(employees or [])
		self.docs = [dict(doc) for doc in (docs or [])]
		self.inserted = []
		self.saved = []
		self.whitelisted = []
		self.only_for_calls = []
		self.allowed_roles = allowed_roles
		self.session = types.SimpleNamespace(user="hr@noho.kr")
		self.utils = types.SimpleNamespace(now=lambda: "2026-07-07 09:00:00")
		self.db = types.SimpleNamespace(
			get_single_value=lambda doctype, field: default_company
			if (doctype, field) == ("Global Defaults", "default_company")
			else None
		)

	def whitelist(self):
		def decorator(fn):
			self.whitelisted.append(fn.__name__)
			return fn

		return decorator

	def only_for(self, roles):
		self.only_for_calls.append(list(roles))
		if not self.allowed_roles:
			raise PermissionError("not permitted")

	def get_all(self, doctype, filters=None, fields=None, pluck=None):
		filters = filters or {}
		if doctype == "Employee":
			source = self.employees
		elif doctype == DOCTYPE:
			source = self.docs
		else:
			raise AssertionError(f"unexpected get_all doctype: {doctype}")
		matched = [row for row in source if all(row.get(key) == value for key, value in filters.items())]
		if pluck:
			return [row.get(pluck) for row in matched]
		if fields:
			return [{field: row.get(field) for field in fields} for row in matched]
		return [dict(row) for row in matched]

	def get_doc(self, arg, name=None):
		if isinstance(arg, dict):
			return FakeDoc(self, dict(arg))
		for row in self.docs:
			if row.get("doctype") == arg and row.get("name") == name:
				return FakeDoc(self, row)
		raise AssertionError(f"doc not found: {arg}/{name}")


def load_module(fake_frappe):
	old_frappe = sys.modules.get("frappe")
	sys.modules["frappe"] = fake_frappe
	try:
		spec = importlib.util.spec_from_file_location("korea_payroll_time_input_api", API_MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if old_frappe is not None:
			sys.modules["frappe"] = old_frappe
		else:
			sys.modules.pop("frappe", None)


EMPLOYEES = [
	{"name": "EMP-0001", "employee_name": "김철수", "company": "노호", "status": "Active"},
	{"name": "EMP-0002", "employee_name": "이영희", "company": "노호", "status": "Active"},
]


def draft_doc(employee, employee_name, *, name, status="draft", **hours):
	base = {
		"doctype": DOCTYPE,
		"name": name,
		"company": "노호",
		"period": "2026-07",
		"employee": employee,
		"employee_name": employee_name,
		"overtime_hours": 0.0,
		"night_hours": 0.0,
		"holiday_hours": 0.0,
		"part_time_hours": 0.0,
		"note": "",
		"status": status,
	}
	base.update(hours)
	return base


class TestFrameworkFreeCore(unittest.TestCase):
	def setUp(self):
		self.module = load_module(FakeFrappe())

	def test_period_validation(self):
		self.assertEqual(self.module.validate_period_text("2026-07"), "2026-07")
		self.assertEqual(self.module.validate_period_text(" 2026-12 "), "2026-12")
		for bad in ("2026-13", "2026-00", "202607", "2026-7", "", None, "26-07"):
			with self.assertRaises(ValueError):
				self.module.validate_period_text(bad)

	def test_hours_range_zero_to_400(self):
		self.assertEqual(self.module.coerce_hours(0, "overtime_hours"), 0.0)
		self.assertEqual(self.module.coerce_hours(None, "overtime_hours"), 0.0)
		self.assertEqual(self.module.coerce_hours("", "overtime_hours"), 0.0)
		self.assertEqual(self.module.coerce_hours(108.5, "overtime_hours"), 108.5)
		self.assertEqual(self.module.coerce_hours("63", "overtime_hours"), 63.0)
		self.assertEqual(self.module.coerce_hours(400, "overtime_hours"), 400.0)
		with self.assertRaisesRegex(ValueError, "overtime_hours"):
			self.module.coerce_hours(-1, "overtime_hours")
		with self.assertRaisesRegex(ValueError, "night_hours"):
			self.module.coerce_hours(400.5, "night_hours")
		with self.assertRaises(ValueError):
			self.module.coerce_hours("abc", "overtime_hours")
		with self.assertRaises(ValueError):
			self.module.coerce_hours(float("nan"), "overtime_hours")

	def test_normalize_rows_rejects_bad_shapes(self):
		with self.assertRaises(ValueError):
			self.module.normalize_time_input_rows({"employee": "EMP-0001"})
		with self.assertRaises(ValueError):
			self.module.normalize_time_input_rows([{"overtime_hours": 1}])  # employee 누락
		rows = self.module.normalize_time_input_rows(
			[{"employee": " EMP-0001 ", "overtime_hours": "108.5", "note": "5월 초과분"}]
		)
		self.assertEqual(
			rows,
			[
				{
					"employee": "EMP-0001",
					"overtime_hours": 108.5,
					"night_hours": 0.0,
					"holiday_hours": 0.0,
					"part_time_hours": 0.0,
					"note": "5월 초과분",
				}
			],
		)


class TestListTimeInputs(unittest.TestCase):
	def test_list_joins_all_active_employees_with_zero_fill(self):
		fake = FakeFrappe(
			employees=EMPLOYEES,
			docs=[draft_doc("EMP-0001", "김철수", name="KPTI-0001", overtime_hours=108.5, night_hours=4.0)],
		)
		module = load_module(fake)
		result = module.list_time_inputs(period="2026-07", company="노호")

		self.assertEqual(result["contract_type"], "korea_payroll_time_input_list_v1")
		self.assertEqual(result["company"], "노호")
		self.assertEqual(result["period"], "2026-07")
		self.assertEqual(len(result["rows"]), 2)
		by_emp = {row["employee"]: row for row in result["rows"]}
		self.assertEqual(by_emp["EMP-0001"]["overtime_hours"], 108.5)
		self.assertEqual(by_emp["EMP-0001"]["night_hours"], 4.0)
		self.assertEqual(by_emp["EMP-0001"]["status"], "draft")
		# 입력이 없던 직원도 0으로 포함
		self.assertEqual(by_emp["EMP-0002"]["overtime_hours"], 0.0)
		self.assertEqual(by_emp["EMP-0002"]["part_time_hours"], 0.0)
		self.assertEqual(by_emp["EMP-0002"]["status"], "draft")
		self.assertEqual(result["submitted_count"], 0)
		self.assertFalse(result["all_submitted"])
		self.assertEqual(fake.only_for_calls, [["HR Manager", "HR User"]])

	def test_list_falls_back_to_global_defaults_company(self):
		fake = FakeFrappe(employees=EMPLOYEES)
		module = load_module(fake)
		result = module.list_time_inputs(period="2026-07")
		self.assertEqual(result["company"], "노호")

	def test_list_reports_all_submitted(self):
		fake = FakeFrappe(
			employees=EMPLOYEES,
			docs=[
				draft_doc("EMP-0001", "김철수", name="A", status="submitted"),
				draft_doc("EMP-0002", "이영희", name="B", status="submitted"),
			],
		)
		module = load_module(fake)
		result = module.list_time_inputs(period="2026-07", company="노호")
		self.assertEqual(result["submitted_count"], 2)
		self.assertTrue(result["all_submitted"])

	def test_list_rejects_bad_period_and_roles(self):
		module = load_module(FakeFrappe(employees=EMPLOYEES))
		with self.assertRaises(ValueError):
			module.list_time_inputs(period="2026-7", company="노호")
		denied = FakeFrappe(employees=EMPLOYEES, allowed_roles=False)
		denied_module = load_module(denied)
		with self.assertRaises(PermissionError):
			denied_module.list_time_inputs(period="2026-07", company="노호")


class TestSaveTimeInputs(unittest.TestCase):
	def test_save_upserts_creates_and_updates(self):
		fake = FakeFrappe(
			employees=EMPLOYEES,
			docs=[draft_doc("EMP-0001", "김철수", name="KPTI-0001", overtime_hours=13.0)],
		)
		module = load_module(fake)
		rows = json.dumps(
			[
				{"employee": "EMP-0001", "overtime_hours": 63.0, "night_hours": 2.0},
				{"employee": "EMP-0002", "overtime_hours": 108.5, "note": "5월 누락분 소급"},
			]
		)
		result = module.save_time_inputs(period="2026-07", rows=rows, company="노호")

		self.assertEqual(result["contract_type"], "korea_payroll_time_input_save_v1")
		self.assertEqual(result["updated"], 1)
		self.assertEqual(result["created"], 1)
		# 기존 draft 63시간으로 갱신 (13시간 오적용 사고 시나리오)
		updated = next(doc for doc in fake.docs if doc["employee"] == "EMP-0001")
		self.assertEqual(updated["overtime_hours"], 63.0)
		self.assertEqual(updated["night_hours"], 2.0)
		self.assertEqual(updated["status"], "draft")
		created = fake.inserted[0]
		self.assertEqual(created["doctype"], DOCTYPE)
		self.assertEqual(created["employee"], "EMP-0002")
		self.assertEqual(created["employee_name"], "이영희")
		self.assertEqual(created["overtime_hours"], 108.5)
		self.assertEqual(created["status"], "draft")
		self.assertEqual(created["period"], "2026-07")

	def test_save_rejects_submitted_rows(self):
		fake = FakeFrappe(
			employees=EMPLOYEES,
			docs=[draft_doc("EMP-0001", "김철수", name="A", status="submitted")],
		)
		module = load_module(fake)
		with self.assertRaisesRegex(PermissionError, "submitted"):
			module.save_time_inputs(
				period="2026-07",
				rows=[{"employee": "EMP-0001", "overtime_hours": 1}],
				company="노호",
			)
		self.assertEqual(fake.saved, [])

	def test_save_rejects_unknown_employee_and_bad_hours_before_write(self):
		fake = FakeFrappe(employees=EMPLOYEES)
		module = load_module(fake)
		with self.assertRaisesRegex(ValueError, "employee"):
			module.save_time_inputs(
				period="2026-07", rows=[{"employee": "EMP-9999", "overtime_hours": 1}], company="노호"
			)
		with self.assertRaises(ValueError):
			module.save_time_inputs(
				period="2026-07", rows=[{"employee": "EMP-0001", "overtime_hours": 500}], company="노호"
			)
		with self.assertRaises(ValueError):
			module.save_time_inputs(
				period="2026-07", rows=[{"employee": "EMP-0001", "night_hours": -3}], company="노호"
			)
		self.assertEqual(fake.inserted, [])
		self.assertEqual(fake.saved, [])


class TestSubmitTimeInputs(unittest.TestCase):
	def test_submit_marks_all_drafts_submitted(self):
		fake = FakeFrappe(
			employees=EMPLOYEES,
			docs=[
				draft_doc("EMP-0001", "김철수", name="A", overtime_hours=108.5),
				draft_doc("EMP-0002", "이영희", name="B"),
			],
		)
		module = load_module(fake)
		result = module.submit_time_inputs(period="2026-07", company="노호")

		self.assertEqual(result["contract_type"], "korea_payroll_time_input_submit_v1")
		self.assertEqual(result["submitted_count"], 2)
		self.assertFalse(result["already_submitted"])
		for doc in fake.docs:
			self.assertEqual(doc["status"], "submitted")
			self.assertEqual(doc["submitted_by"], "hr@noho.kr")
			self.assertEqual(doc["submitted_at"], "2026-07-07 09:00:00")

	def test_submit_is_idempotent_when_already_submitted(self):
		fake = FakeFrappe(
			employees=EMPLOYEES,
			docs=[draft_doc("EMP-0001", "김철수", name="A", status="submitted")],
		)
		module = load_module(fake)
		result = module.submit_time_inputs(period="2026-07", company="노호")
		self.assertTrue(result["already_submitted"])
		self.assertEqual(result["submitted_count"], 0)
		self.assertEqual(fake.saved, [])

	def test_all_three_endpoints_are_whitelisted(self):
		fake = FakeFrappe()
		load_module(fake)
		self.assertEqual(
			sorted(fake.whitelisted),
			["list_time_inputs", "save_time_inputs", "submit_time_inputs"],
		)


class TestDoctypeValidate(unittest.TestCase):
	DOCTYPE_MODULE_PATH = (
		pathlib.Path(__file__).resolve().parents[1]
		/ "hr"
		/ "doctype"
		/ "korea_payroll_time_input"
		/ "korea_payroll_time_input.py"
	)

	class ThrowError(Exception):
		pass

	def load_doctype_module(self, *, exists_result=None):
		test_case = self

		class DoctypeFakeFrappe(FakeFrappe):
			def __init__(self):
				super().__init__()
				self.db = types.SimpleNamespace(exists=lambda doctype, filters: exists_result)

			def throw(self, message):
				raise test_case.ThrowError(message)

			def _(self, message):
				return message

		fake = DoctypeFakeFrappe()
		fake_model = types.ModuleType("frappe.model")
		fake_document = types.ModuleType("frappe.model.document")

		class Document:
			def __init__(self, **kwargs):
				for key, value in kwargs.items():
					setattr(self, key, value)

		fake_document.Document = Document
		old = {name: sys.modules.get(name) for name in ("frappe", "frappe.model", "frappe.model.document")}
		sys.modules["frappe"] = fake
		sys.modules["frappe.model"] = fake_model
		sys.modules["frappe.model.document"] = fake_document
		try:
			spec = importlib.util.spec_from_file_location("korea_payroll_time_input_doctype", self.DOCTYPE_MODULE_PATH)
			module = importlib.util.module_from_spec(spec)
			assert spec.loader is not None
			spec.loader.exec_module(module)
			return module
		finally:
			for name, value in old.items():
				if value is not None:
					sys.modules[name] = value
				else:
					sys.modules.pop(name, None)

	def make_doc(self, module, **overrides):
		fields = {
			"name": "KPTI-0001",
			"company": "노호",
			"period": "2026-07",
			"employee": "EMP-0001",
			"overtime_hours": 108.5,
			"night_hours": 0,
			"holiday_hours": 0,
			"part_time_hours": 0,
			"status": "draft",
		}
		fields.update(overrides)
		return module.KoreaPayrollTimeInput(**fields)

	def test_validate_passes_for_clean_draft(self):
		module = self.load_doctype_module(exists_result=None)
		self.make_doc(module).validate()

	def test_validate_blocks_duplicate_company_period_employee(self):
		module = self.load_doctype_module(exists_result="KPTI-OTHER")
		with self.assertRaisesRegex(self.ThrowError, "already exists"):
			self.make_doc(module).validate()

	def test_validate_blocks_bad_period_hours_and_status(self):
		module = self.load_doctype_module(exists_result=None)
		with self.assertRaisesRegex(self.ThrowError, "period"):
			self.make_doc(module, period="2026-13").validate()
		with self.assertRaisesRegex(self.ThrowError, "overtime_hours"):
			self.make_doc(module, overtime_hours=401).validate()
		with self.assertRaisesRegex(self.ThrowError, "status"):
			self.make_doc(module, status="approved").validate()


if __name__ == "__main__":
	unittest.main()
