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


class TestProbation(unittest.TestCase):
	"""수습기간 조항 — 최저임금법 §5③(감액 하한 90%) + 시행령 §3(3개월 이내)."""

	def setUp(self):
		self.mod = load_module()

	def test_no_probation_defaults(self):
		contract = self.mod.build_employment_contract(_valid_data())
		self.assertEqual(contract["probation"], {"months": 0, "wage_percent": 100})
		self.assertEqual(contract["warnings"], [])

	def test_probation_within_limits_no_warning(self):
		data = _valid_data()
		data["probation"] = {"months": 3, "wage_percent": 90}
		contract = self.mod.build_employment_contract(data)
		self.assertEqual(contract["probation"], {"months": 3, "wage_percent": 90})
		self.assertEqual(contract["warnings"], [])

	def test_wage_percent_below_90_warns(self):
		data = _valid_data()
		data["probation"] = {"months": 3, "wage_percent": 80}
		contract = self.mod.build_employment_contract(data)
		self.assertTrue(any("최저임금법" in w for w in contract["warnings"]))

	def test_reduction_beyond_3_months_warns(self):
		data = _valid_data()
		data["probation"] = {"months": 6, "wage_percent": 90}
		contract = self.mod.build_employment_contract(data)
		self.assertTrue(any("3개월" in w for w in contract["warnings"]))

	def test_long_probation_without_reduction_no_reduction_warning(self):
		data = _valid_data()
		data["probation"] = {"months": 6, "wage_percent": 100}
		contract = self.mod.build_employment_contract(data)
		self.assertFalse(any("3개월" in w for w in contract["warnings"]))

	def test_negative_months_raises(self):
		data = _valid_data()
		data["probation"] = {"months": -1, "wage_percent": 100}
		with self.assertRaises(ValueError):
			self.mod.build_employment_contract(data)

	def test_probation_clause_rendered(self):
		data = _valid_data()
		data["probation"] = {"months": 3, "wage_percent": 90}
		contract = self.mod.build_employment_contract(data)
		md = self.mod.render_contract_markdown(contract)
		self.assertIn("수습기간", md)
		self.assertIn("3개월", md)
		self.assertIn("90%", md)

	def test_no_probation_clause_when_zero_months(self):
		contract = self.mod.build_employment_contract(_valid_data())
		md = self.mod.render_contract_markdown(contract)
		self.assertNotIn("수습기간", md)


class TestComputeScheduleHours(unittest.TestCase):
	"""주간 스케줄 블록 → 주 소정/연장·월 연장시간 산출."""

	def setUp(self):
		self.mod = load_module()

	def _week(self, start, end, break_minutes, days=("월", "화", "수", "목", "금")):
		return [
			{"day": d, "start_time": start, "end_time": end, "break_minutes": break_minutes}
			for d in days
		]

	def test_standard_40h_week_no_overtime(self):
		result = self.mod.compute_schedule_hours(self._week("09:00", "18:00", 60))
		self.assertEqual(float(result["weekly_total_hours"]), 40.0)
		self.assertEqual(float(result["weekly_scheduled_hours"]), 40.0)
		self.assertEqual(float(result["weekly_overtime_hours"]), 0.0)
		self.assertEqual(float(result["monthly_overtime_hours"]), 0.0)
		self.assertEqual(result["warnings"], [])

	def test_45h_week_overtime_monthly_conversion(self):
		# 9h × 5일 = 45h → 소정 40h + 연장 5h, 월 연장 = 5 × (365÷12÷7) ≈ 21.73
		result = self.mod.compute_schedule_hours(self._week("09:00", "19:00", 60))
		self.assertEqual(float(result["weekly_scheduled_hours"]), 40.0)
		self.assertEqual(float(result["weekly_overtime_hours"]), 5.0)
		self.assertEqual(float(result["monthly_overtime_hours"]), 21.73)

	def test_overnight_shift_crosses_midnight(self):
		# 22:00~07:00 휴게 60분 = 8h
		result = self.mod.compute_schedule_hours(
			[{"day": "월", "start_time": "22:00", "end_time": "07:00", "break_minutes": 60}]
		)
		self.assertEqual(float(result["weekly_total_hours"]), 8.0)

	def test_weekly_overtime_over_12h_warns(self):
		# 10h × 6일 = 60h → 연장 20h > 12h (§53①)
		result = self.mod.compute_schedule_hours(
			self._week("09:00", "20:00", 60, days=("월", "화", "수", "목", "금", "토"))
		)
		self.assertEqual(float(result["weekly_overtime_hours"]), 20.0)
		self.assertTrue(any("12시간" in w for w in result["warnings"]))

	def test_invalid_time_raises(self):
		with self.assertRaises(ValueError):
			self.mod.compute_schedule_hours(
				[{"day": "월", "start_time": "9시", "end_time": "18:00", "break_minutes": 0}]
			)

	def test_build_includes_schedule_summary_and_render(self):
		data = _valid_data()
		data["work_schedule"] = self._week("09:00", "19:00", 60)
		contract = self.mod.build_employment_contract(data)
		summary = contract["schedule_summary"]
		self.assertEqual(float(summary["weekly_overtime_hours"]), 5.0)
		self.assertEqual(float(summary["monthly_overtime_hours"]), 21.73)
		md = self.mod.render_contract_markdown(contract)
		self.assertIn("월 연장근로시간", md)
		self.assertIn("21.73", md)

	def test_build_without_schedule_has_none_summary(self):
		contract = self.mod.build_employment_contract(_valid_data())
		self.assertIsNone(contract["schedule_summary"])

	def test_schedule_overtime_warning_propagates_to_contract(self):
		data = _valid_data()
		data["work_schedule"] = self._week(
			"09:00", "20:00", 60, days=("월", "화", "수", "목", "금", "토")
		)
		contract = self.mod.build_employment_contract(data)
		self.assertTrue(any("12시간" in w for w in contract["warnings"]))


class TestNetPreview(unittest.TestCase):
	"""예상 실수령액 참고 표기 — net_to_gross forward 공제 로직 재사용."""

	def setUp(self):
		self.mod = load_module()

	def _load_net_to_gross(self):
		path = MODULE_PATH.parent / "net_to_gross.py"
		spec = importlib.util.spec_from_file_location("korea_net_to_gross_ref", path)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module

	def test_disabled_by_default(self):
		contract = self.mod.build_employment_contract(_valid_data())
		self.assertIsNone(contract["net_preview"])
		md = self.mod.render_contract_markdown(contract)
		self.assertNotIn("예상 실수령액", md)

	def test_net_preview_matches_net_to_gross_forward(self):
		data = _valid_data()
		data["net_preview"] = {"enabled": True, "non_taxable": 200_000, "dependents": 1}
		contract = self.mod.build_employment_contract(data)
		preview = contract["net_preview"]
		gross = contract["wage_total"]

		ntg = self._load_net_to_gross()
		expected = ntg._employee_deductions(
			gross,
			non_taxable=200_000,
			dependents=1,
			children_under_8=0,
			include_pension=True,
			include_health=True,
			include_longterm_care=True,
			include_employment=True,
			pension_override=None,
		)
		self.assertEqual(preview["gross"], gross)
		self.assertEqual(preview["deductions"], expected)
		self.assertEqual(preview["estimated_net"], gross - expected["total"])
		self.assertEqual(preview["non_taxable"], 200_000)
		self.assertEqual(preview["dependents"], 1)

	def test_net_preview_rendered_as_reference_only(self):
		data = _valid_data()
		data["net_preview"] = {"enabled": True, "non_taxable": 0, "dependents": 1}
		contract = self.mod.build_employment_contract(data)
		md = self.mod.render_contract_markdown(contract)
		self.assertIn("예상 실수령액", md)
		self.assertIn("참고용", md)
		self.assertIn("부양가족 1인", md)


if __name__ == "__main__":
	unittest.main(verbosity=2)
