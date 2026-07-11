# -*- coding: utf-8 -*-
"""연차 사용촉진 API 래퍼 테스트 — framework-free. TDD: RED 먼저.

annual_leave_promotion_api는 코어(annual_leave_promotion)에 위임하며,
웹 RPC 입력(ISO 날짜 문자열·JSON 문자열 dict·문자열 불리언)을 코어 타입으로
변환하고 JSON-safe 결과(date 객체 없음)를 반환해야 한다.

실행: python3 hrms/tests/test_korea_annual_leave_promotion_api.py
"""
from __future__ import annotations

import datetime as dt
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


_api = _load("annual_leave_promotion_api")
_core = _load("annual_leave_promotion")


class TestPromotionScheduleApi(unittest.TestCase):
	def test_prd_sample(self):
		"""표본: 입사 2020-01-01, as_of 2026-06-15 → 1차 창 2026-07-01~07-10, 2차 기한 2026-11-01."""
		result = _api.promotion_schedule_api(hire_date="2020-01-01", as_of="2026-06-15")
		self.assertEqual(result["first_notice_window_start"], "2026-07-01")
		self.assertEqual(result["first_notice_deadline"], "2026-07-10")
		self.assertEqual(result["second_notice_deadline"], "2026-11-01")
		self.assertEqual(result["expiry_date"], "2027-01-01")
		self.assertEqual(result["stage"], _core.STAGE_BEFORE_WINDOW)

	def test_matches_core(self):
		"""API 결과가 코어와 일치 (날짜는 ISO 문자열로 변환)."""
		api_result = _api.promotion_schedule_api(hire_date="2020-01-01", as_of="2026-06-15")
		core_result = _core.promotion_schedule(dt.date(2020, 1, 1), dt.date(2026, 6, 15))
		for key, core_value in core_result.items():
			expected = core_value.isoformat() if isinstance(core_value, dt.date) else core_value
			self.assertEqual(api_result[key], expected, key)

	def test_first_year_includes_proviso(self):
		"""1년 미만 특칙(is_first_year 문자열 'true' 허용) → proviso 필드 포함."""
		result = _api.promotion_schedule_api(
			hire_date="2026-01-01", as_of="2026-06-15", is_first_year="true"
		)
		self.assertTrue(result["is_first_year"])
		self.assertIn("proviso_notice_window_start", result)
		self.assertIn("proviso_stage", result)
		core_result = _core.promotion_schedule(
			dt.date(2026, 1, 1), dt.date(2026, 6, 15), is_first_year=True
		)
		self.assertEqual(result["proviso_second_deadline"], core_result["proviso_second_deadline"].isoformat())

	def test_false_string_is_general_schedule(self):
		"""Frappe RPC의 'false' 문자열은 일반 스케줄로 처리."""
		result = _api.promotion_schedule_api(
			hire_date="2020-01-01", as_of="2026-06-15", is_first_year="false"
		)
		self.assertFalse(result["is_first_year"])
		self.assertNotIn("proviso_stage", result)

	def test_json_safe(self):
		result = _api.promotion_schedule_api(hire_date="2020-01-01", as_of="2026-06-15")
		json.dumps(result)  # date 객체가 남아 있으면 예외

	def test_invalid_date_rejected(self):
		with self.assertRaises(ValueError):
			_api.promotion_schedule_api(hire_date="not-a-date", as_of="2026-06-15")


class TestPromotionNoticeApi(unittest.TestCase):
	def test_stage1_matches_core(self):
		"""worker JSON 문자열 dict 허용 — 코어 초안과 동일."""
		api_md = _api.promotion_notice_api(
			worker=json.dumps({"name": "김가상"}),
			unused_days=5,
			deadline="2026-07-10",
			stage=1,
		)
		core_md = _core.promotion_notice_draft(
			{"name": "김가상"}, 5, dt.date(2026, 7, 10), 1
		)
		self.assertEqual(api_md, core_md)
		self.assertIn("김가상", api_md)
		self.assertIn("2026-07-10", api_md)

	def test_stage2_string_stage(self):
		"""stage 문자열 '2' 허용 — 사용시기 지정 통보서."""
		api_md = _api.promotion_notice_api(
			worker="이가상", unused_days=3, deadline="2026-11-01", stage="2"
		)
		core_md = _core.promotion_notice_draft("이가상", 3, dt.date(2026, 11, 1), 2)
		self.assertEqual(api_md, core_md)

	def test_invalid_stage_rejected(self):
		with self.assertRaises(ValueError):
			_api.promotion_notice_api(
				worker="김가상", unused_days=1, deadline="2026-07-10", stage=3
			)


class TestSettleUnusedLeaveApi(unittest.TestCase):
	def test_not_completed_matches_core(self):
		api_result = _api.settle_unused_leave_api(
			monthly_base_salary=2_090_000, unused_days=5, promotion_completed="false"
		)
		core_result = _core.settle_unused_leave(2_090_000, 5, promotion_completed=False)
		self.assertEqual(api_result, core_result)
		self.assertFalse(api_result["compensation_exempt"])
		self.assertGreater(api_result["allowance_won"], 0)

	def test_completed_exempt(self):
		result = _api.settle_unused_leave_api(
			monthly_base_salary=2_090_000, unused_days=5, promotion_completed=True
		)
		self.assertTrue(result["compensation_exempt"])
		self.assertEqual(result["allowance_won"], 0)

	def test_json_safe(self):
		result = _api.settle_unused_leave_api(
			monthly_base_salary=2_090_000, unused_days=5, promotion_completed=False
		)
		json.dumps(result)


if __name__ == "__main__":
	unittest.main()
