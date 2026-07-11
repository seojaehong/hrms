# -*- coding: utf-8 -*-
"""근로기준법 §61 연차 사용촉진 — framework-free 코어 테스트.

1차 근거: wiki/ontology/급여규칙/연차_사용촉진.md (published, 노무사 승인본).
날짜 경계(각 촉구/통보 창의 시작·끝·전날)를 촘촘히 검증한다.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hrms" / "regional" / "south_korea" / "annual_leave_promotion.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_annual_leave_promotion", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class GeneralScheduleTest(unittest.TestCase):
	"""일반 근로자(§60①·④): 소멸 6개월 전 10일 촉구 / 2개월 전까지 통보."""

	def setUp(self):
		self.mod = load_module()
		self.hire_date = dt.date(2020, 1, 1)
		# as_of=2026-06-15 (mid-period, not itself an anniversary) -> service_years=6
		# -> expiry=2027-01-01
		self.as_of = dt.date(2026, 6, 15)
		self.result = self.mod.promotion_schedule(self.hire_date, self.as_of, is_first_year=False)

	def test_expiry_date(self):
		self.assertEqual(self.result["expiry_date"], dt.date(2027, 1, 1))

	def test_first_notice_window(self):
		self.assertEqual(self.result["first_notice_window_start"], dt.date(2026, 7, 1))
		self.assertEqual(self.result["first_notice_deadline"], dt.date(2026, 7, 10))

	def test_second_notice_deadline(self):
		self.assertEqual(self.result["second_notice_deadline"], dt.date(2026, 11, 1))

	def _stage_at(self, as_of):
		r = self.mod.promotion_schedule(self.hire_date, as_of, is_first_year=False)
		return r["stage"]

	def test_stage_before_window(self):
		self.assertEqual(self._stage_at(dt.date(2026, 6, 30)), "촉구_전")

	def test_stage_window_start_inclusive(self):
		self.assertEqual(self._stage_at(dt.date(2026, 7, 1)), "1차_촉구_기간")

	def test_stage_window_deadline_inclusive(self):
		self.assertEqual(self._stage_at(dt.date(2026, 7, 10)), "1차_촉구_기간")

	def test_stage_day_after_first_deadline(self):
		self.assertEqual(self._stage_at(dt.date(2026, 7, 11)), "2차_통보_기간")

	def test_stage_second_deadline_inclusive(self):
		self.assertEqual(self._stage_at(dt.date(2026, 11, 1)), "2차_통보_기간")

	def test_stage_day_after_second_deadline(self):
		self.assertEqual(self._stage_at(dt.date(2026, 11, 2)), "통보_기한_도과")

	def test_stage_day_before_expiry(self):
		self.assertEqual(self._stage_at(dt.date(2026, 12, 31)), "통보_기한_도과")

	def test_stage_on_expiry(self):
		self.assertEqual(self._stage_at(dt.date(2027, 1, 1)), "소멸")

	def test_legal_basis_cites_article_61(self):
		self.assertTrue(any("제61조" in c for c in self.result["legal_basis"]), self.result["legal_basis"])

	def test_exact_anniversary_still_reports_lapse_of_prior_period(self):
		# as_of가 정확히 다음 서비스이언(anniversary) 당일(2027-01-01)이면, 그 날은
		# "새 기간 첫날"이 아니라 "직전 기간이 막 소멸하는 날"로 취급되어야 한다.
		r = self.mod.promotion_schedule(self.hire_date, dt.date(2027, 1, 1), is_first_year=False)
		self.assertEqual(r["expiry_date"], dt.date(2027, 1, 1))
		self.assertEqual(r["stage"], "소멸")

	def test_day_after_anniversary_rolls_to_next_period(self):
		r = self.mod.promotion_schedule(self.hire_date, dt.date(2027, 1, 2), is_first_year=False)
		self.assertEqual(r["expiry_date"], dt.date(2028, 1, 1))
		self.assertEqual(r["stage"], "촉구_전")


class FirstYearScheduleTest(unittest.TestCase):
	"""1년 미만 근로자(§60② 특칙): 3개월 전 10일 / 단서분 1개월 전 5일 / 2차 1개월,10일 전까지."""

	def setUp(self):
		self.mod = load_module()
		self.hire_date = dt.date(2026, 1, 1)
		self.as_of = dt.date(2026, 6, 1)
		self.result = self.mod.promotion_schedule(self.hire_date, self.as_of, is_first_year=True)

	def test_expiry_date(self):
		self.assertEqual(self.result["expiry_date"], dt.date(2027, 1, 1))

	def test_first_notice_window(self):
		self.assertEqual(self.result["first_notice_window_start"], dt.date(2026, 10, 1))
		self.assertEqual(self.result["first_notice_deadline"], dt.date(2026, 10, 10))

	def test_second_notice_deadline(self):
		self.assertEqual(self.result["second_notice_deadline"], dt.date(2026, 12, 1))

	def test_proviso_window(self):
		self.assertEqual(self.result["proviso_notice_window_start"], dt.date(2026, 12, 1))
		self.assertEqual(self.result["proviso_notice_deadline"], dt.date(2026, 12, 5))

	def test_proviso_second_deadline(self):
		self.assertEqual(self.result["proviso_second_deadline"], dt.date(2026, 12, 22))

	def _stages_at(self, as_of):
		r = self.mod.promotion_schedule(self.hire_date, as_of, is_first_year=True)
		return r["stage"], r["proviso_stage"]

	def test_main_stage_boundaries(self):
		self.assertEqual(self._stages_at(dt.date(2026, 9, 30))[0], "촉구_전")
		self.assertEqual(self._stages_at(dt.date(2026, 10, 1))[0], "1차_촉구_기간")
		self.assertEqual(self._stages_at(dt.date(2026, 10, 10))[0], "1차_촉구_기간")
		self.assertEqual(self._stages_at(dt.date(2026, 10, 11))[0], "2차_통보_기간")
		self.assertEqual(self._stages_at(dt.date(2026, 12, 1))[0], "2차_통보_기간")
		self.assertEqual(self._stages_at(dt.date(2026, 12, 2))[0], "통보_기한_도과")
		self.assertEqual(self._stages_at(dt.date(2026, 12, 31))[0], "통보_기한_도과")
		self.assertEqual(self._stages_at(dt.date(2027, 1, 1))[0], "소멸")

	def test_proviso_stage_boundaries(self):
		self.assertEqual(self._stages_at(dt.date(2026, 11, 30))[1], "촉구_전")
		self.assertEqual(self._stages_at(dt.date(2026, 12, 1))[1], "1차_촉구_기간")
		self.assertEqual(self._stages_at(dt.date(2026, 12, 5))[1], "1차_촉구_기간")
		self.assertEqual(self._stages_at(dt.date(2026, 12, 6))[1], "2차_통보_기간")
		self.assertEqual(self._stages_at(dt.date(2026, 12, 22))[1], "2차_통보_기간")
		self.assertEqual(self._stages_at(dt.date(2026, 12, 23))[1], "통보_기한_도과")
		self.assertEqual(self._stages_at(dt.date(2027, 1, 1))[1], "소멸")


class InputValidationTest(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_as_of_before_hire_date_raises(self):
		with self.assertRaises(ValueError):
			self.mod.promotion_schedule(dt.date(2026, 1, 1), dt.date(2025, 1, 1))

	def test_non_date_raises_type_error(self):
		with self.assertRaises(TypeError):
			self.mod.promotion_schedule("2026-01-01", dt.date(2026, 1, 1))

	def test_is_first_year_false_with_under_one_year_tenure_rejected(self):
		"""근속 1년 미만인데 is_first_year=False(일반 §60①·④ 스케줄)를 요청하면,
		실제로는 §60② 1년 미만자 특칙(is_first_year=True)이 적용돼야 하는 근로자에게
		잘못된(6개월전/2개월전) 스케줄을 산출하게 되므로 명시적으로 거부한다."""
		with self.assertRaises(ValueError):
			self.mod.promotion_schedule(dt.date(2026, 1, 1), dt.date(2026, 6, 1), is_first_year=False)

	def test_is_first_year_false_exactly_at_one_year_anniversary_ok(self):
		"""만 1년 정확히 도달한 시점은 더 이상 '1년 미만'이 아니므로 허용된다."""
		result = self.mod.promotion_schedule(
			dt.date(2026, 1, 1), dt.date(2027, 1, 1), is_first_year=False
		)
		self.assertEqual(result["stage"], "소멸")

	def test_legal_basis_base_is_cached(self):
		"""legal_basis_base()는 매 호출마다 온톨로지 로더를 다시 실행하지 않고
		모듈 레벨 캐시를 재사용해야 한다."""
		first = self.mod.legal_basis_base()
		second = self.mod.legal_basis_base()
		self.assertEqual(first, second)
		self.assertTrue(hasattr(self.mod, "_LEGAL_BASIS_BASE_CACHE"))
		self.assertEqual(self.mod._LEGAL_BASIS_BASE_CACHE, first)


class NoticeDraftTest(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_first_notice_contains_required_phrase(self):
		draft = self.mod.promotion_notice_draft(
			worker={"name": "홍길동"},
			unused_days=5,
			deadline=dt.date(2026, 7, 10),
			stage=1,
		)
		self.assertIn("근로자가 사용시기 지정·통보하라", draft)
		self.assertIn("홍길동", draft)
		self.assertIn("5", draft)
		self.assertIn("2026-07-10", draft)

	def test_second_notice_contains_required_phrase(self):
		draft = self.mod.promotion_notice_draft(
			worker={"name": "홍길동"},
			unused_days=5,
			deadline=dt.date(2026, 11, 1),
			stage=2,
		)
		self.assertIn("사용시기 지정 통보", draft)

	def test_invalid_stage_raises(self):
		with self.assertRaises(ValueError):
			self.mod.promotion_notice_draft(
				worker={"name": "홍길동"}, unused_days=5, deadline=dt.date(2026, 1, 1), stage=3
			)

	def test_worker_as_plain_string(self):
		draft = self.mod.promotion_notice_draft(
			worker="김철수", unused_days=3, deadline=dt.date(2026, 1, 1), stage=1
		)
		self.assertIn("김철수", draft)


class SettleUnusedLeaveTest(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_promotion_completed_exempts_allowance(self):
		result = self.mod.settle_unused_leave(
			monthly_base_salary=2156880, unused_days=5, promotion_completed=True
		)
		self.assertEqual(result["allowance_won"], 0)
		self.assertTrue(result["compensation_exempt"])
		self.assertIn("면제", result["reason"])

	def test_promotion_incomplete_pays_allowance(self):
		result = self.mod.settle_unused_leave(
			monthly_base_salary=2156880, unused_days=5, promotion_completed=False
		)
		# 기존 hourly_wage.unused_leave_allowance 재사용 값과 일치해야 함
		# (기본급/209 x 8 x 5 = 412,800원, calc_unused_leave_allowance 회귀값과 동일)
		self.assertEqual(result["allowance_won"], 412800)
		self.assertFalse(result["compensation_exempt"])


if __name__ == "__main__":
	unittest.main()
