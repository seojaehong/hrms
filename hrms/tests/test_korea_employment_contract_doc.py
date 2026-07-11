#!/usr/bin/env python3
"""Direct-run tests for build_employment_contract / render_contract_markdown.

framework-free: spec_from_file_location으로 모듈을 직접 로드한다(hrms/__init__.py가
frappe를 import하므로 패키지 경유 import는 피한다 — employment_contract 테스트 컨벤션).
실행: python3 hrms/tests/test_korea_employment_contract_doc.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional"
	/ "south_korea"
	/ "employment_contract_doc.py"
)


def load_module():
	spec = importlib.util.spec_from_file_location("korea_employment_contract_doc", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


def _valid_data() -> dict:
	return {
		"company": {
			"company_name": "가나다 주식회사",
			"representative_name": "홍길동",
			"address": "서울시 강남구 테헤란로 1",
			"business_registration_number": "123-45-67890",
		},
		"employee": {
			"employee_name": "김철수",
			"address": "서울시 송파구 올림픽로 2",
			"resident_registration_number": "900101-1234567",
		},
		"workplace": "본사 사무실",
		"job_description": "인사 관리",
		"contract_period": {"start_date": "2026-08-01", "end_date": None},
		"scheduled_work": {
			"start_time": "09:00",
			"end_time": "18:00",
			"work_days": "월~금",
			"break_time": "1시간",
		},
		"holidays": "매주 일요일 (주휴일)",
		"annual_leave": "근로기준법 제60조에 따름",
		"wage_components": [
			{"component": "기본급", "amount": 2_500_000},
			{"component": "직책수당", "amount": 200_000},
		],
		"wage_payment_date": "매월 25일",
		"wage_payment_method": "근로자 명의 계좌 입금",
	}


class TestBuildEmploymentContract(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_complete_data_has_no_missing_fields(self):
		contract = self.mod.build_employment_contract(_valid_data())
		self.assertEqual(contract["missing"], [])
		self.assertTrue(contract["required_fields_complete"])

	def test_wage_components_pass_through_and_total_computed(self):
		contract = self.mod.build_employment_contract(_valid_data())
		self.assertEqual(
			contract["wage_components"],
			[
				{"component": "기본급", "amount": 2_500_000},
				{"component": "직책수당", "amount": 200_000},
			],
		)
		self.assertEqual(contract["wage_total"], 2_700_000)

	def test_employee_rrn_is_masked(self):
		contract = self.mod.build_employment_contract(_valid_data())
		self.assertEqual(
			contract["employee"]["resident_registration_number"], "900101-******"
		)

	def test_missing_wage_components_detected(self):
		data = _valid_data()
		data["wage_components"] = []
		contract = self.mod.build_employment_contract(data)
		self.assertIn("wage_components", contract["missing"])
		self.assertFalse(contract["required_fields_complete"])

	def test_missing_holidays_detected(self):
		data = _valid_data()
		data["holidays"] = ""
		contract = self.mod.build_employment_contract(data)
		self.assertIn("holidays", contract["missing"])

	def test_missing_annual_leave_detected(self):
		data = _valid_data()
		data["annual_leave"] = ""
		contract = self.mod.build_employment_contract(data)
		self.assertIn("annual_leave", contract["missing"])

	def test_missing_scheduled_work_times_detected(self):
		data = _valid_data()
		data["scheduled_work"] = {"work_days": "월~금"}
		contract = self.mod.build_employment_contract(data)
		self.assertIn("scheduled_work.start_time", contract["missing"])
		self.assertIn("scheduled_work.end_time", contract["missing"])

	def test_missing_company_fields_detected(self):
		data = _valid_data()
		data["company"] = {"company_name": "가나다 주식회사"}
		contract = self.mod.build_employment_contract(data)
		self.assertIn("company.representative_name", contract["missing"])
		self.assertIn("company.address", contract["missing"])
		self.assertIn("company.business_registration_number", contract["missing"])

	def test_missing_contract_period_start_detected(self):
		data = _valid_data()
		data["contract_period"] = {"start_date": None, "end_date": None}
		contract = self.mod.build_employment_contract(data)
		self.assertIn("contract_period.start_date", contract["missing"])

	def test_missing_workplace_and_job_description_detected(self):
		data = _valid_data()
		data["workplace"] = ""
		data["job_description"] = ""
		contract = self.mod.build_employment_contract(data)
		self.assertIn("workplace", contract["missing"])
		self.assertIn("job_description", contract["missing"])

	def test_wage_payment_date_and_method_detected_when_missing(self):
		data = _valid_data()
		data["wage_payment_date"] = ""
		data["wage_payment_method"] = ""
		contract = self.mod.build_employment_contract(data)
		self.assertIn("wage_payment_date", contract["missing"])
		self.assertIn("wage_payment_method", contract["missing"])

	def test_not_a_dict_raises_type_error(self):
		with self.assertRaises(TypeError):
			self.mod.build_employment_contract("not a dict")


class TestRenderContractMarkdown(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_complete_contract_renders_without_warning_block(self):
		contract = self.mod.build_employment_contract(_valid_data())
		md = self.mod.render_contract_markdown(contract)
		self.assertNotIn("누락", md.split("\n")[0])
		self.assertIn("가나다 주식회사", md)
		self.assertIn("김철수", md)
		self.assertIn("기본급", md)
		self.assertIn("2,500,000", md)
		self.assertIn("직책수당", md)
		self.assertIn("근로기준법 제17조", md)

	def test_incomplete_contract_has_warning_block_at_top(self):
		data = _valid_data()
		data["holidays"] = ""
		contract = self.mod.build_employment_contract(data)
		md = self.mod.render_contract_markdown(contract)
		lines = md.strip().split("\n")
		# 경고 블록은 문서 최상단에 위치해야 한다.
		self.assertIn("누락", lines[0] + lines[1] + lines[2])
		self.assertIn("holidays", md)

	def test_rrn_masking_present_in_markdown(self):
		contract = self.mod.build_employment_contract(_valid_data())
		md = self.mod.render_contract_markdown(contract)
		self.assertIn("900101-******", md)
		self.assertNotIn("900101-1234567", md)


if __name__ == "__main__":
	unittest.main(verbosity=2)
