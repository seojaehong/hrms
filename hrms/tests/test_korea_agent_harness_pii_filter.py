# -*- coding: utf-8 -*-
"""PII 필터(에이전트→LLM 직렬화 방어선) 테스트 — framework-free. TDD: RED 먼저.

보안플랜 P1-④: 하네스가 LLM에 보내는 도구 결과에서 주민번호·계좌·키류 원문을
구조적으로 차단한다(지시문이 아니라 코드로).

실행: python3 hrms/tests/test_korea_agent_harness_pii_filter.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

_MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1]
	/ "regional" / "south_korea" / "agent_harness" / "pii_filter.py"
)
_spec = importlib.util.spec_from_file_location("pii_filter", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

redact = _mod.redact_sensitive


class TestKeyDenylist(unittest.TestCase):
	def test_rrn_keys_removed(self):
		out = redact({
			"employee": "E1",
			"resident_registration_number": "9001012345617",
			"rrn_masked": "900101-2******",
		})
		self.assertEqual(out["employee"], "E1")
		self.assertEqual(out["resident_registration_number"], "[PII 제외]")
		# 마스킹된 표기는 이미 안전 — 통과 허용
		self.assertEqual(out["rrn_masked"], "900101-2******")

	def test_secret_keys_removed(self):
		out = redact({"api_key": "sk-live-abc", "client_secret": "s3cr3t", "password": "pw"})
		self.assertEqual(out["api_key"], "[PII 제외]")
		self.assertEqual(out["client_secret"], "[PII 제외]")
		self.assertEqual(out["password"], "[PII 제외]")

	def test_nested_and_lists(self):
		out = redact({
			"rows": [
				{"name": "김하늘", "resident_no": "9001012345617", "gross_pay": 3120400},
				{"name": "이서준", "bank_account": "110-123-456789"},
			]
		})
		self.assertEqual(out["rows"][0]["resident_no"], "[PII 제외]")
		self.assertEqual(out["rows"][0]["gross_pay"], 3120400)  # 금액은 보존
		self.assertEqual(out["rows"][1]["bank_account"], "[PII 제외]")


class TestValuePatternMasking(unittest.TestCase):
	def test_rrn_in_free_text_masked(self):
		# 키가 무해해도 값 안의 주민번호 패턴(6-7 하이픈)은 마스킹
		out = redact({"note": "담당자 메모: 900101-2345617 확인 요망"})
		self.assertNotIn("900101-2345617", out["note"])
		self.assertIn("900101-2******", out["note"])

	def test_plain_13_digits_not_masked(self):
		# 하이픈 없는 13자리 연속 숫자는 금액·계좌와 구분 불가 → 오탐 방지 위해 보존
		out = redact({"amount_note": "총 1234567890123원"})
		self.assertIn("1234567890123", out["amount_note"])

	def test_normal_values_untouched(self):
		data = {"employee_name": "김하늘", "gross_pay": 3120400, "period": "2026-06", "ok": True, "ratio": 0.5, "none": None}
		self.assertEqual(redact(data), data)


class TestSafety(unittest.TestCase):
	def test_input_not_mutated(self):
		src = {"api_key": "sk-1", "rows": [{"resident_no": "9001012345617"}]}
		redact(src)
		self.assertEqual(src["api_key"], "sk-1")  # 원본 불변(깊은 복사)
		self.assertEqual(src["rows"][0]["resident_no"], "9001012345617")

	def test_non_dict_root(self):
		self.assertEqual(redact([{"password": "x"}])[0]["password"], "[PII 제외]")
		self.assertEqual(redact("900101-2345617"), "900101-2******")
		self.assertEqual(redact(42), 42)


if __name__ == "__main__":
	unittest.main()
