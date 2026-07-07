"""급여 엑셀 다운로드 API 테스트 — FakeFrappe (frappe 없이 python3 직접 실행).

실행: python3 hrms/tests/test_korea_payroll_excel_api.py
권한(only_for)·회사 폴백(Global Defaults)·Salary Slip 집계·File 생성 호출을 검증한다.
개인 급여액은 로그하지 않으며, 산출 File 내용(bytes)만 확인한다.
"""

from __future__ import annotations

import importlib.util
import io
import pathlib
import sys
import unittest

import openpyxl

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "payroll_excel_api.py"


class FakeChildRow(dict):
    """Salary Slip earnings/deductions 자식 행 — getattr/get 모두 지원."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover - 방어
            raise AttributeError(name) from exc


class FakeSlip:
    def __init__(self, data):
        self._data = dict(data)
        self.earnings = [FakeChildRow(r) for r in data.get("earnings", [])]
        self.deductions = [FakeChildRow(r) for r in data.get("deductions", [])]

    def get(self, key):
        return self._data.get(key)

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError as exc:  # pragma: no cover - 방어
            raise AttributeError(name) from exc


class FakeFile:
    def __init__(self, spec):
        self.spec = spec
        self.file_url = f"/private/files/{spec.get('file_name')}"
        self.inserted = False

    def insert(self, ignore_permissions=False):
        self.inserted = True
        return self


class FakeDB:
    def __init__(self, default_company):
        self._default_company = default_company

    def get_single_value(self, doctype, field):
        if (doctype, field) == ("Global Defaults", "default_company"):
            return self._default_company
        return None


class FakeFrappe:
    def __init__(self, *, slips=None, default_company=None, allowed_roles=True):
        self.db = FakeDB(default_company)
        self._slips = {s["name"]: s for s in (slips or [])}
        self.allowed_roles = allowed_roles
        self.only_for_calls = []
        self.get_all_calls = []
        self.created_files = []
        self.whitelisted = []

    def whitelist(self):
        def decorator(fn):
            self.whitelisted.append(fn.__name__)
            return fn

        return decorator

    def only_for(self, roles):
        self.only_for_calls.append(tuple(roles))
        if not self.allowed_roles:
            raise PermissionError("not permitted")

    def get_all(self, doctype, filters=None, pluck=None):
        self.get_all_calls.append({"doctype": doctype, "filters": dict(filters or {}), "pluck": pluck})
        if doctype != "Salary Slip":
            raise AssertionError(f"unexpected get_all: {doctype}")
        return list(self._slips.keys())

    def get_doc(self, first, name=None):
        if isinstance(first, dict) and first.get("doctype") == "File":
            file_doc = FakeFile(first)
            self.created_files.append(file_doc)
            return file_doc
        if first == "Salary Slip":
            return FakeSlip(self._slips[name])
        raise AssertionError(f"unexpected get_doc: {first!r}")


def load_module(fake_frappe):
    old = sys.modules.get("frappe")
    sys.modules["frappe"] = fake_frappe
    try:
        spec = importlib.util.spec_from_file_location("korea_payroll_excel_api", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        if old is not None:
            sys.modules["frappe"] = old
        else:
            sys.modules.pop("frappe", None)


SLIPS = [
    {
        "name": "SS-0001", "employee_name": "김월급", "department": "관리", "posting_date": "2025-03-01",
        "gross_pay": 3200000, "net_pay": 3015000,
        "earnings": [{"salary_component": "기본급", "amount": 3000000}, {"salary_component": "식대(비과세)", "amount": 200000}],
        "deductions": [{"salary_component": "소득세", "amount": 50000}, {"salary_component": "국민연금", "amount": 135000}],
    },
    {
        "name": "SS-0002", "employee_name": "이시급", "department": "매장", "posting_date": "2026-01-10",
        "gross_pay": 2100000, "net_pay": 2050000,
        "earnings": [{"salary_component": "기본급", "amount": 2000000}, {"salary_component": "보안수당", "amount": 100000}],
        "deductions": [{"salary_component": "소득세", "amount": 30000}, {"salary_component": "고용보험", "amount": 20000}],
    },
]


class TestDownloadPayrollWorkbook(unittest.TestCase):
    def test_creates_private_file_and_returns_url(self):
        fake = FakeFrappe(slips=SLIPS, default_company="노호")
        module = load_module(fake)

        result = module.download_payroll_workbook(period="2026-05")

        self.assertEqual(result["status"], "created")
        self.assertEqual(result["period"], "2026-05")
        self.assertEqual(result["company"], "노호")  # Global Defaults 폴백
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["file_url"], "/private/files/급여대장_2026-05.xlsx")
        # 권한 게이트가 급여 관리자급으로 호출됐는지
        self.assertEqual(fake.only_for_calls, [("System Manager", "HR Manager", "HR User")])
        # 해당 월 슬립 조회 필터
        self.assertEqual(fake.get_all_calls[0]["filters"]["start_date"], "2026-05-01")
        self.assertEqual(fake.get_all_calls[0]["filters"]["company"], "노호")
        # private File 1건 생성
        self.assertEqual(len(fake.created_files), 1)
        f = fake.created_files[0]
        self.assertEqual(f.spec["is_private"], 1)
        self.assertTrue(f.inserted)
        self.assertIn("get_doc", dir(fake))
        # 산출 xlsx 합계행이 실지급 열합과 1원 일치
        ws = openpyxl.load_workbook(io.BytesIO(f.spec["content"]), data_only=True).active
        rows = [[c.value for c in row] for row in ws.iter_rows()]
        header, total = rows[0], rows[-1]
        net_idx = header.index("실지급")
        body = rows[1:-1]
        self.assertEqual(total[net_idx], sum(int(r[net_idx] or 0) for r in body))
        self.assertEqual(total[net_idx], 3015000 + 2050000)

    def test_explicit_company_skips_fallback(self):
        fake = FakeFrappe(slips=SLIPS, default_company="노호")
        module = load_module(fake)
        result = module.download_payroll_workbook(period="2026-05", company="다른회사")
        self.assertEqual(result["company"], "다른회사")
        self.assertEqual(fake.get_all_calls[0]["filters"]["company"], "다른회사")

    def test_invalid_period_raises_before_frappe(self):
        fake = FakeFrappe(slips=SLIPS, default_company="노호")
        module = load_module(fake)
        with self.assertRaisesRegex(ValueError, "YYYY-MM"):
            module.download_payroll_workbook(period="2026/05")
        self.assertEqual(fake.only_for_calls, [])  # 형식 오류는 권한 검사 이전

    def test_missing_company_raises(self):
        fake = FakeFrappe(slips=SLIPS, default_company=None)
        module = load_module(fake)
        with self.assertRaisesRegex(ValueError, "company"):
            module.download_payroll_workbook(period="2026-05")
        self.assertEqual(len(fake.created_files), 0)

    def test_permission_denied_before_file(self):
        fake = FakeFrappe(slips=SLIPS, default_company="노호", allowed_roles=False)
        module = load_module(fake)
        with self.assertRaises(PermissionError):
            module.download_payroll_workbook(period="2026-05")
        self.assertEqual(len(fake.created_files), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
