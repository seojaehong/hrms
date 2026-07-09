# -*- coding: utf-8 -*-
"""주민등록번호(RRN) 코어 테스트 — framework-free 직접 실행.

실행: python3 hrms/tests/test_korea_rrn.py
"""
import datetime as dt
import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "hrms" / "regional" / "south_korea" / "resident_registration_number.py"
_spec = importlib.util.spec_from_file_location("rrn", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# 합성 유효값: 1990-01-01, 성별숫자 2(여, 1900s), 체크섬 7
VALID = "9001012345617"


class TestNormalize(unittest.TestCase):
	def test_strip_hyphen(self):
		self.assertEqual(_mod.normalize("900101-2345617"), VALID)

	def test_wrong_length_raises(self):
		with self.assertRaises(ValueError):
			_mod.normalize("12345")

	def test_none_raises(self):
		with self.assertRaises(ValueError):
			_mod.normalize(None)


class TestValidity(unittest.TestCase):
	def test_valid(self):
		self.assertTrue(_mod.is_valid_rrn(VALID))

	def test_bad_month(self):
		self.assertFalse(_mod.is_valid_rrn("9013012345617"))  # 13월

	def test_bad_day(self):
		self.assertFalse(_mod.is_valid_rrn("9001322345617"))  # 32일

	def test_non_numeric(self):
		self.assertFalse(_mod.is_valid_rrn("abcdefghijklm"))

	def test_twelve_digits(self):
		self.assertFalse(_mod.is_valid_rrn("900101234561"))


class TestDerivation(unittest.TestCase):
	def test_birth_date_1900s(self):
		self.assertEqual(_mod.birth_date(VALID), dt.date(1990, 1, 1))

	def test_birth_date_2000s(self):
		# 성별숫자 3(7번째 자리) → 2000s 남
		self.assertEqual(_mod.birth_date("0301013234563"), dt.date(2003, 1, 1))

	def test_gender_female(self):
		self.assertEqual(_mod.gender(VALID), "F")

	def test_gender_male(self):
		self.assertEqual(_mod.gender("9001011234567"), "M")  # 성별숫자 1


class TestChecksum(unittest.TestCase):
	def test_checksum_ok(self):
		self.assertTrue(_mod.checksum_ok(VALID))

	def test_checksum_bad(self):
		self.assertFalse(_mod.checksum_ok("9001012345610"))  # 검증숫자 변조

	def test_validity_ignores_checksum(self):
		# 체크섬 틀려도 구조가 맞으면 유효 판정(2020 개편 대응)
		self.assertTrue(_mod.is_valid_rrn("9001012345610"))


class TestMasking(unittest.TestCase):
	def test_mask(self):
		self.assertEqual(_mod.mask_rrn(VALID), "900101-2******")

	def test_format(self):
		self.assertEqual(_mod.format_rrn(VALID), "900101-2345617")


if __name__ == "__main__":
	unittest.main()
