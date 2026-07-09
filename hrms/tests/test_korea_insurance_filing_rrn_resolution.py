# -*- coding: utf-8 -*-
"""insurance_filing_api 주민번호 필드 해석 테스트 — framework-free.

검증 대상 (2026-07-10 암호화 필드 도입):
  - _resolve_rrn_field: 표준 필드 우선, 없으면 레거시(custom_...) 폴백, 둘 다 없으면 (None, False)
  - Password(암호화) 타입 감지 → _get_employees가 get_all 대신 복호화 경로 사용
  - 레거시 평문 필드값이 요청 키로 노출되는지

실행: python3 hrms/tests/test_korea_insurance_filing_rrn_resolution.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "insurance_filing_api.py"
)


class _MetaField:
	def __init__(self, fieldtype):
		self.fieldtype = fieldtype


class _Meta:
	def __init__(self, fields: dict):
		self._fields = fields

	def get_field(self, fieldname):
		return self._fields.get(fieldname)


class FakeFrappe(types.ModuleType):
	"""get_meta/get_all만 제공하는 최소 스텁."""

	def __init__(self, meta_fields: dict, employees: list[dict]):
		super().__init__("frappe")
		self._meta = _Meta(meta_fields)
		self._employees = employees
		self.get_all_fields_seen = None

	def whitelist(self):
		def deco(fn):
			return fn

		return deco

	def get_meta(self, doctype):
		return self._meta

	def get_all(self, doctype, filters=None, fields=None, **kw):
		if doctype == "Employee":
			self.get_all_fields_seen = list(fields or [])
			return [dict(e) for e in self._employees]
		return []


def _load_api(fake_frappe, decrypted=None):
	"""fake frappe(+utils.password 스텁) 주입 후 모듈 로드."""
	calls = []

	pw_mod = types.ModuleType("frappe.utils.password")

	def get_decrypted_password(doctype, name, fieldname, raise_exception=True):
		calls.append((doctype, name, fieldname))
		return (decrypted or {}).get(name)

	pw_mod.get_decrypted_password = get_decrypted_password
	utils_mod = types.ModuleType("frappe.utils")
	utils_mod.password = pw_mod

	# 주의: _decrypt_rrn은 '호출 시점'에 frappe.utils.password를 import하므로
	# 스텁을 복원하지 않고 유지한다(실제 frappe 미설치 환경 전용 테스트 스크립트).
	sys.modules["frappe"] = fake_frappe
	sys.modules["frappe.utils"] = utils_mod
	sys.modules["frappe.utils.password"] = pw_mod
	spec = importlib.util.spec_from_file_location("ins_api_rrn_test", MODULE_PATH)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod, calls


STD = "resident_registration_number"
LEGACY = "custom_resident_registration_number"


class TestResolveRrnField(unittest.TestCase):
	def test_standard_password_field(self):
		fake = FakeFrappe({STD: _MetaField("Password")}, [])
		mod, _ = _load_api(fake)
		self.assertEqual(mod._resolve_rrn_field(STD), (STD, True))

	def test_legacy_fallback_plain(self):
		fake = FakeFrappe({LEGACY: _MetaField("Data")}, [])
		mod, _ = _load_api(fake)
		self.assertEqual(mod._resolve_rrn_field(STD), (LEGACY, False))

	def test_no_field_anywhere(self):
		fake = FakeFrappe({}, [])
		mod, _ = _load_api(fake)
		self.assertEqual(mod._resolve_rrn_field(STD), (None, False))


class TestGetEmployeesRrnPaths(unittest.TestCase):
	def test_encrypted_field_uses_decryption_not_get_all(self):
		fake = FakeFrappe(
			{STD: _MetaField("Password")},
			[{"name": "EMP-1", "employee_name": "A"}],
		)
		mod, calls = _load_api(fake, decrypted={"EMP-1": "9001012345617"})
		emps = mod._get_employees(None, STD)
		# 암호화 필드는 get_all fields에 포함되지 않는다
		self.assertNotIn(STD, fake.get_all_fields_seen)
		# 복호화 경로 호출 + 값 주입
		self.assertEqual(calls, [("Employee", "EMP-1", STD)])
		self.assertEqual(emps[0][STD], "9001012345617")

	def test_plain_legacy_value_exposed_under_requested_key(self):
		fake = FakeFrappe(
			{LEGACY: _MetaField("Data")},
			[{"name": "EMP-1", "employee_name": "A", LEGACY: "9001012345617"}],
		)
		mod, calls = _load_api(fake)
		emps = mod._get_employees(None, STD)
		self.assertIn(LEGACY, fake.get_all_fields_seen)  # 평문은 get_all로
		self.assertEqual(calls, [])  # 복호화 안 씀
		self.assertEqual(emps[0][STD], "9001012345617")  # 요청 키로 노출

	def test_missing_field_leaves_blank(self):
		fake = FakeFrappe({}, [{"name": "EMP-1", "employee_name": "A"}])
		mod, calls = _load_api(fake)
		emps = mod._get_employees(None, STD)
		self.assertIsNone(emps[0].get(STD))
		self.assertEqual(calls, [])


if __name__ == "__main__":
	unittest.main()
