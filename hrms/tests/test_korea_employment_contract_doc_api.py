# -*- coding: utf-8 -*-
"""근로계약서 작성 API 래퍼 테스트 — framework-free. TDD: RED 먼저.

employment_contract_doc_api는 코어(employment_contract_doc)에 위임하며,
완전 입력 시 missing=[], 임금 누락 시 missing에 해당 항목이 포함되는지
코어와 동일하게 검증한다.

실행: python3 hrms/tests/test_korea_employment_contract_doc_api.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_SK = _REPO / "hrms" / "regional" / "south_korea"


def _load(name):
	path = _SK / (name + ".py")
	spec = importlib.util.spec_from_file_location(name, path)
	m = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(m)
	return m


_api = _load("employment_contract_doc_api")
_core = _load("employment_contract_doc")


def _complete_data(**overrides):
	data = {
		"company": {
			"company_name": "가상상사",
			"representative_name": "홍길동",
			"address": "서울시 강남구 테헤란로 1",
			"business_registration_number": "123-45-67890",
		},
		"employee": {
			"employee_name": "김가상",
			"address": "서울시 서초구 서초대로 2",
		},
		"workplace": "서울시 강남구 본사",
		"job_description": "일반 사무",
		"contract_period": {"start_date": "2026-07-01", "end_date": None},
		"scheduled_work": {"start_time": "09:00", "end_time": "18:00", "work_days": "월~금", "break_time": "12:00~13:00"},
		"holidays": "주휴일 매주 일요일",
		"annual_leave": "근로기준법 제60조에 따름",
		"wage_components": [{"component": "기본급", "amount": 2100000}],
		"wage_payment_date": "매월 10일",
		"wage_payment_method": "근로자 명의 계좌 입금",
	}
	data.update(overrides)
	return data


class TestBuildEmploymentContractApi(unittest.TestCase):
	def test_matches_core_complete(self):
		data = _complete_data()
		api_result = _api.build_employment_contract_api(data)
		core_result = _core.build_employment_contract(data)
		self.assertEqual(api_result, core_result)
		self.assertEqual(api_result["missing"], [])
		self.assertTrue(api_result["required_fields_complete"])

	def test_accepts_json_string_data(self):
		"""Frappe RPC가 dict를 JSON 문자열로 전달하는 경우도 허용."""
		data = _complete_data()
		api_result = _api.build_employment_contract_api(json.dumps(data))
		core_result = _core.build_employment_contract(data)
		self.assertEqual(api_result, core_result)

	def test_missing_wage_components(self):
		data = _complete_data(wage_components=[])
		api_result = _api.build_employment_contract_api(data)
		core_result = _core.build_employment_contract(data)
		self.assertEqual(api_result, core_result)
		self.assertIn("wage_components", api_result["missing"])
		self.assertFalse(api_result["required_fields_complete"])

	def test_missing_company_fields(self):
		data = _complete_data(company={"company_name": "가상상사"})
		api_result = _api.build_employment_contract_api(data)
		core_result = _core.build_employment_contract(data)
		self.assertEqual(api_result, core_result)
		self.assertIn("company.representative_name", api_result["missing"])
		self.assertIn("company.address", api_result["missing"])
		self.assertIn("company.business_registration_number", api_result["missing"])

	def test_json_safe(self):
		result = _api.build_employment_contract_api(_complete_data())
		json.dumps(result)


class TestNewFieldsPassThroughApi(unittest.TestCase):
	"""수습/스케줄/NET 참고 필드 — 코어 위임 + JSON-safe(Decimal → float) 검증."""

	def _data_with_new_fields(self):
		return _complete_data(
			probation={"months": 3, "wage_percent": 90},
			work_schedule=[
				{"day": d, "start_time": "09:00", "end_time": "19:00", "break_minutes": 60}
				for d in ("월", "화", "수", "목", "금")
			],
			net_preview={"enabled": True, "non_taxable": 200000, "dependents": 1},
		)

	def test_new_fields_json_safe_and_values(self):
		result = _api.build_employment_contract_api(self._data_with_new_fields())
		json.dumps(result)  # Decimal이 남아 있으면 실패
		self.assertEqual(result["probation"], {"months": 3, "wage_percent": 90})
		self.assertEqual(result["schedule_summary"]["weekly_overtime_hours"], 5)
		self.assertEqual(result["schedule_summary"]["monthly_overtime_hours"], 21.73)
		self.assertEqual(
			result["net_preview"]["estimated_net"],
			result["wage_total"] - result["net_preview"]["deductions"]["total"],
		)

	def test_render_includes_new_clauses(self):
		contract = _api.build_employment_contract_api(self._data_with_new_fields())
		md = _api.render_contract_markdown_api(contract)
		self.assertIn("수습기간", md)
		self.assertIn("월 연장근로시간", md)
		self.assertIn("예상 실수령액", md)


class TestRenderContractMarkdownApi(unittest.TestCase):
	def test_matches_core(self):
		data = _complete_data()
		contract = _core.build_employment_contract(data)
		api_md = _api.render_contract_markdown_api(contract)
		core_md = _core.render_contract_markdown(contract)
		self.assertEqual(api_md, core_md)
		self.assertIn("가상상사", api_md)
		self.assertIn("김가상", api_md)

	def test_accepts_json_string_contract(self):
		data = _complete_data()
		contract = _core.build_employment_contract(data)
		api_md = _api.render_contract_markdown_api(json.dumps(contract))
		core_md = _core.render_contract_markdown(contract)
		self.assertEqual(api_md, core_md)

	def test_missing_warning_shown(self):
		data = _complete_data(wage_components=[])
		contract = _core.build_employment_contract(data)
		api_md = _api.render_contract_markdown_api(contract)
		self.assertIn("필수기재 누락 경고", api_md)


if __name__ == "__main__":
	unittest.main()
