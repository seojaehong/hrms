#!/usr/bin/env python3
"""한국 표준 고용계약서 4종 양식 테스트.

근로기준법 제17조 준수 검증:
- 4종 양식 생성 OK
- 필수 항목 누락 시 missing_required_fields에 표시
- 비정규직 종료일 필수 검증
- 단시간 근로자 주 시간 < 40 검증
- PDF generate dry-run (Frappe 없이)
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

# ---------------------------------------------------------------------------
# 모듈 로드 (framework-free)
# ---------------------------------------------------------------------------

_BASE = pathlib.Path(__file__).resolve().parents[1]
_CONTRACT_MODULE_PATH = _BASE / "regional" / "south_korea" / "employment_contract.py"


def _load_contract_module():
	spec = importlib.util.spec_from_file_location("employment_contract", _CONTRACT_MODULE_PATH)
	mod = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(mod)
	return mod


# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------

_COMPANY = {
	"company_name": "노란봉투 주식회사",
	"representative_name": "홍길동",
	"address": "서울특별시 강남구 테헤란로 123",
	"business_registration_number": "123-45-67890",
	"contact": "02-1234-5678",
}

_EMPLOYEE = {
	"employee_name": "김민준",
	"address": "서울특별시 마포구 공덕동 456",
	"contact": "010-9876-5432",
	"resident_registration_number": "900101-1234567",
}

_REGULAR_TERMS = {
	"contract_start_date": "2026-06-01",
	"workplace": "서울특별시 강남구 사무소",
	"job_description": "인사팀 HR업무",
	"work_start_time": "09:00",
	"work_end_time": "18:00",
	"work_days": "월~금",
	"holidays": "매주 일요일",
	"base_wage": "3000000",
	"wage_payment_date": "25",
	"wage_payment_method": "계좌이체",
	"annual_leave": "근로기준법에 따름",
}

_FIXED_TERM_TERMS = {
	**_REGULAR_TERMS,
	"contract_end_date": "2027-05-31",
}

_DAILY_TERMS = {
	"work_date": "2026-06-01",
	"workplace": "공사현장 A동",
	"job_description": "철근콘크리트 작업",
	"work_start_time": "08:00",
	"work_end_time": "17:00",
	"daily_wage": "180000",
	"wage_payment_date": "당일 퇴근 시",
	"wage_payment_method": "계좌이체",
}

_PART_TIME_TERMS = {
	**_REGULAR_TERMS,
	"weekly_work_hours": "20",
}


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------


class TestKoreaEmploymentContractForms(unittest.TestCase):
	def setUp(self):
		self.mod = _load_contract_module()
		self.build = self.mod.build_korea_employment_contract

	# ------------------------------------------------------------------
	# 2-E-1: 4종 양식 build OK
	# ------------------------------------------------------------------

	def test_regular_contract_builds_successfully(self):
		result = self.build(
			contract_type="regular",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=_REGULAR_TERMS,
		)
		self.assertEqual(result["contract_type"], "korea_employment_contract_draft_v1")
		self.assertEqual(result["form_type"], "regular")
		self.assertEqual(result["form_title"], "기간의 정함이 없는 근로계약서 (정규직)")
		self.assertTrue(result["required_fields_complete"])
		self.assertEqual(result["missing_required_fields"], [])
		self.assertIn("html_content", result)
		self.assertIn("기간의 정함이 없는 근로계약서", result["html_content"])

	def test_fixed_term_contract_builds_successfully(self):
		result = self.build(
			contract_type="fixed_term",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=_FIXED_TERM_TERMS,
		)
		self.assertEqual(result["form_type"], "fixed_term")
		self.assertTrue(result["required_fields_complete"])
		self.assertEqual(result["missing_required_fields"], [])
		self.assertIn("계약직", result["html_content"])

	def test_daily_contract_builds_successfully(self):
		result = self.build(
			contract_type="daily",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=_DAILY_TERMS,
		)
		self.assertEqual(result["form_type"], "daily")
		self.assertTrue(result["required_fields_complete"])
		self.assertEqual(result["missing_required_fields"], [])
		self.assertIn("일용근로계약서", result["html_content"])

	def test_part_time_contract_builds_successfully(self):
		result = self.build(
			contract_type="part_time",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=_PART_TIME_TERMS,
		)
		self.assertEqual(result["form_type"], "part_time")
		self.assertTrue(result["required_fields_complete"])
		self.assertEqual(result["missing_required_fields"], [])
		self.assertIn("단시간근로자", result["html_content"])

	# ------------------------------------------------------------------
	# 2-E-1: mutation_boundary + AI 안전 필드
	# ------------------------------------------------------------------

	def test_all_forms_carry_safety_metadata(self):
		for ct in ("regular", "fixed_term", "daily", "part_time"):
			terms = _PART_TIME_TERMS if ct == "part_time" else (
				_FIXED_TERM_TERMS if ct == "fixed_term" else (
					_DAILY_TERMS if ct == "daily" else _REGULAR_TERMS
				)
			)
			with self.subTest(contract_type=ct):
				result = self.build(
					contract_type=ct, company=_COMPANY, employee=_EMPLOYEE, contract_terms=terms
				)
				self.assertEqual(result["mutation_boundary"], "preview_only_no_submit_approve_send")
				self.assertTrue(result["requires_human_approval"])
				self.assertEqual(result["ai_role"], "assistant_only")

	# ------------------------------------------------------------------
	# 2-E-1: 근기법 17조 필수 항목 누락 → missing_required_fields에 표시
	# ------------------------------------------------------------------

	def test_missing_required_fields_reported_not_raised(self):
		"""필수 항목 누락 시 예외를 던지지 않고 missing_required_fields에 기록."""
		result = self.build(
			contract_type="regular",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms={},  # 아무것도 없음
		)
		self.assertFalse(result["required_fields_complete"])
		missing = result["missing_required_fields"]
		self.assertIn("contract_terms.workplace", missing)
		self.assertIn("contract_terms.job_description", missing)
		self.assertIn("contract_terms.work_start_time", missing)
		self.assertIn("contract_terms.work_end_time", missing)
		self.assertIn("contract_terms.work_days", missing)
		self.assertIn("contract_terms.holidays", missing)
		self.assertIn("contract_terms.base_wage", missing)
		self.assertIn("contract_terms.wage_payment_date", missing)
		self.assertIn("contract_terms.wage_payment_method", missing)
		self.assertIn("contract_terms.annual_leave", missing)

	def test_missing_company_fields_reported(self):
		result = self.build(
			contract_type="regular",
			company={},
			employee=_EMPLOYEE,
			contract_terms=_REGULAR_TERMS,
		)
		self.assertFalse(result["required_fields_complete"])
		missing = result["missing_required_fields"]
		self.assertIn("company.company_name", missing)
		self.assertIn("company.representative_name", missing)
		self.assertIn("company.address", missing)
		self.assertIn("company.business_registration_number", missing)

	def test_missing_employee_fields_reported(self):
		result = self.build(
			contract_type="regular",
			company=_COMPANY,
			employee={},
			contract_terms=_REGULAR_TERMS,
		)
		self.assertFalse(result["required_fields_complete"])
		missing = result["missing_required_fields"]
		self.assertIn("employee.employee_name", missing)
		self.assertIn("employee.address", missing)

	# ------------------------------------------------------------------
	# 2-E-1: 비정규직 종료일 필수 검증
	# ------------------------------------------------------------------

	def test_fixed_term_missing_end_date_is_reported(self):
		terms_no_end = {k: v for k, v in _FIXED_TERM_TERMS.items() if k != "contract_end_date"}
		result = self.build(
			contract_type="fixed_term",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=terms_no_end,
		)
		self.assertFalse(result["required_fields_complete"])
		self.assertIn("contract_terms.contract_end_date", result["missing_required_fields"])

	def test_fixed_term_end_before_start_is_reported(self):
		terms_bad = {**_FIXED_TERM_TERMS, "contract_end_date": "2025-01-01"}
		result = self.build(
			contract_type="fixed_term",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=terms_bad,
		)
		self.assertFalse(result["required_fields_complete"])
		# end_date before start_date should be in missing_required_fields
		self.assertTrue(
			any("contract_end_date" in f for f in result["missing_required_fields"])
		)

	# ------------------------------------------------------------------
	# 2-E-1: 단시간 근로자 주 시간 < 40 검증
	# ------------------------------------------------------------------

	def test_part_time_weekly_hours_exactly_40_is_rejected(self):
		terms_40h = {**_PART_TIME_TERMS, "weekly_work_hours": "40"}
		result = self.build(
			contract_type="part_time",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=terms_40h,
		)
		self.assertFalse(result["required_fields_complete"])
		self.assertTrue(
			any("weekly_work_hours" in f for f in result["missing_required_fields"])
		)

	def test_part_time_weekly_hours_above_40_is_rejected(self):
		terms_50h = {**_PART_TIME_TERMS, "weekly_work_hours": 52}
		result = self.build(
			contract_type="part_time",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=terms_50h,
		)
		self.assertFalse(result["required_fields_complete"])

	def test_part_time_weekly_hours_below_40_passes(self):
		terms_ok = {**_PART_TIME_TERMS, "weekly_work_hours": "15"}
		result = self.build(
			contract_type="part_time",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=terms_ok,
		)
		self.assertTrue(result["required_fields_complete"])

	def test_part_time_missing_weekly_hours_is_reported(self):
		terms_no_hours = {k: v for k, v in _PART_TIME_TERMS.items() if k != "weekly_work_hours"}
		result = self.build(
			contract_type="part_time",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=terms_no_hours,
		)
		self.assertFalse(result["required_fields_complete"])
		self.assertIn("contract_terms.weekly_work_hours", result["missing_required_fields"])

	# ------------------------------------------------------------------
	# 주민번호 마스킹
	# ------------------------------------------------------------------

	def test_rrn_masked_in_output(self):
		result = self.build(
			contract_type="regular",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=_REGULAR_TERMS,
		)
		rrn = result["employee"]["resident_registration_number"]
		self.assertNotIn("1234567", rrn, "뒷자리가 그대로 노출되면 안 됨")
		self.assertIn("******", rrn)
		self.assertTrue(rrn.startswith("900101"), "앞 6자리는 유지되어야 함")

	def test_mask_rrn_helper_with_hyphen(self):
		masked = self.mod.mask_rrn("900101-1234567")
		self.assertEqual(masked, "900101-******")

	def test_mask_rrn_helper_without_hyphen(self):
		masked = self.mod.mask_rrn("9001011234567")
		self.assertEqual(masked, "900101-******")

	def test_mask_rrn_helper_empty_string(self):
		masked = self.mod.mask_rrn("")
		self.assertIn("*", masked)

	# ------------------------------------------------------------------
	# 잘못된 contract_type 검증
	# ------------------------------------------------------------------

	def test_invalid_contract_type_raises_value_error(self):
		with self.assertRaises(ValueError):
			self.build(
				contract_type="invalid_type",
				company=_COMPANY,
				employee=_EMPLOYEE,
				contract_terms=_REGULAR_TERMS,
			)

	def test_wrong_input_type_raises_type_error(self):
		with self.assertRaises(TypeError):
			self.build(
				contract_type="regular",
				company="not a dict",  # type: ignore[arg-type]
				employee=_EMPLOYEE,
				contract_terms=_REGULAR_TERMS,
			)

	# ------------------------------------------------------------------
	# CONTRACT_TYPES 레지스트리
	# ------------------------------------------------------------------

	def test_contract_types_registry_has_all_four(self):
		ct = self.mod.CONTRACT_TYPES
		self.assertIn("regular", ct)
		self.assertIn("fixed_term", ct)
		self.assertIn("daily", ct)
		self.assertIn("part_time", ct)

	# ------------------------------------------------------------------
	# PDF generate dry-run (Frappe 없이)
	# ------------------------------------------------------------------

	def test_pdf_dryrun_html_content_is_non_empty_string(self):
		"""PDF 생성 dry-run: html_content가 실제 인쇄 가능한 HTML을 반환하는지 확인."""
		for ct, terms in [
			("regular", _REGULAR_TERMS),
			("fixed_term", _FIXED_TERM_TERMS),
			("daily", _DAILY_TERMS),
			("part_time", _PART_TIME_TERMS),
		]:
			with self.subTest(contract_type=ct):
				result = self.build(
					contract_type=ct,
					company=_COMPANY,
					employee=_EMPLOYEE,
					contract_terms=terms,
				)
				html = result["html_content"]
				self.assertIsInstance(html, str)
				self.assertGreater(len(html), 500, "HTML이 너무 짧음")
				self.assertIn("<table", html)
				self.assertIn("사업주", html)
				self.assertIn("근로자", html)

	def test_pdf_dryrun_html_includes_statute_notice(self):
		"""HTML에 근기법 17조 안내문이 포함되어야 함."""
		result = self.build(
			contract_type="regular",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=_REGULAR_TERMS,
		)
		self.assertIn("근로기준법 제17조", result["html_content"])

	def test_pdf_dryrun_employee_rrn_masked_in_html(self):
		"""HTML에 주민번호 뒷자리가 노출되지 않아야 함."""
		result = self.build(
			contract_type="regular",
			company=_COMPANY,
			employee=_EMPLOYEE,
			contract_terms=_REGULAR_TERMS,
		)
		self.assertNotIn("1234567", result["html_content"])
		self.assertIn("900101-******", result["html_content"])


# ---------------------------------------------------------------------------
# API 게이트 테스트 (employment_contract_api.py)
# human_approved 게이트 + preview 동작 검증
# ---------------------------------------------------------------------------


class _FakeFrappe:
    """Frappe 모듈 스텁 — API 레이어 격리 테스트용."""

    class _Exceptions(Exception):
        pass

    # frappe.throw → ValidationError 로 변환
    @staticmethod
    def throw(msg: str, exc_type=None):
        raise _FakeFrappe._Exceptions(msg)

    @staticmethod
    def whitelist():
        """데코레이터 스텁 — 함수를 그대로 반환."""
        def decorator(fn):
            return fn
        return decorator

    @staticmethod
    def log_error(msg: str):
        pass  # 무시


def _load_api_module():
    """employment_contract_api.py 를 Frappe 없이 로드."""
    import sys
    import types

    # Frappe 스텁 주입
    fake_frappe = _FakeFrappe()
    sys.modules["frappe"] = fake_frappe  # type: ignore[assignment]

    _API_PATH = _BASE / "regional" / "south_korea" / "employment_contract_api.py"
    spec = importlib.util.spec_from_file_location("employment_contract_api", _API_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    # frappe 스텁 제거 (다른 테스트에 영향 없도록)
    sys.modules.pop("frappe", None)
    sys.modules.pop("employment_contract_api", None)

    return mod, fake_frappe


class TestKoreaEmploymentContractAPIGate(unittest.TestCase):
    """API 레이어 — human_approved 게이트 + preview 동작 검증."""

    def setUp(self):
        self.api, self.fake_frappe = _load_api_module()

    # ------------------------------------------------------------------
    # generate_korea_employment_contract_pdf: human_approved=False 거부
    # ------------------------------------------------------------------

    def test_pdf_generate_rejected_when_not_approved(self):
        """human_approved=False 이면 PDF 생성 거부 — mutation 게이트 핵심."""
        with self.assertRaises(_FakeFrappe._Exceptions) as ctx:
            self.api.generate_korea_employment_contract_pdf(
                contract={"form_type": "regular", "html_content": "<p>test</p>"},
                human_approved=False,
            )
        self.assertIn("human_approved", str(ctx.exception).lower())

    def test_pdf_generate_rejected_string_false(self):
        """human_approved='false' (문자열) 이면 거부."""
        with self.assertRaises(_FakeFrappe._Exceptions):
            self.api.generate_korea_employment_contract_pdf(
                contract={"form_type": "regular", "html_content": "<p>test</p>"},
                human_approved="false",
            )

    def test_pdf_generate_rejected_string_no(self):
        """human_approved='no' 이면 거부."""
        with self.assertRaises(_FakeFrappe._Exceptions):
            self.api.generate_korea_employment_contract_pdf(
                contract={"form_type": "regular", "html_content": "<p>test</p>"},
                human_approved="no",
            )

    # ------------------------------------------------------------------
    # generate_korea_employment_contract_pdf: html_content 누락 거부
    # ------------------------------------------------------------------

    def test_pdf_generate_rejected_when_html_missing(self):
        """html_content 없으면 PDF 생성 거부."""
        with self.assertRaises(_FakeFrappe._Exceptions) as ctx:
            self.api.generate_korea_employment_contract_pdf(
                contract={"form_type": "regular"},  # html_content 없음
                human_approved=True,
            )
        self.assertIn("html_content", str(ctx.exception))

    # ------------------------------------------------------------------
    # generate_korea_employment_contract_pdf: 잘못된 form_type 거부
    # ------------------------------------------------------------------

    def test_pdf_generate_rejected_invalid_form_type(self):
        """form_type이 CONTRACT_TYPES에 없으면 거부."""
        with self.assertRaises(_FakeFrappe._Exceptions):
            self.api.generate_korea_employment_contract_pdf(
                contract={"form_type": "unknown_type", "html_content": "<p>test</p>"},
                human_approved=True,
            )

    # ------------------------------------------------------------------
    # generate_korea_employment_contract_pdf: get_pdf 스텁 → 정상 완료
    # ------------------------------------------------------------------

    def test_pdf_generate_succeeds_when_approved(self):
        """human_approved=True + 유효한 contract → PDF base64 반환."""
        import sys
        import base64

        # frappe.utils.pdf.get_pdf 스텁
        fake_pdf_bytes = b"%PDF-1.4 fake pdf bytes"

        fake_frappe_module = _FakeFrappe()

        # frappe.utils.pdf 모의 모듈
        import types
        fake_utils_pdf = types.ModuleType("frappe.utils.pdf")
        fake_utils_pdf.get_pdf = lambda html, **kwargs: fake_pdf_bytes  # type: ignore[attr-defined]
        sys.modules["frappe"] = fake_frappe_module  # type: ignore[assignment]
        sys.modules["frappe.utils.pdf"] = fake_utils_pdf

        try:
            _API_PATH = _BASE / "regional" / "south_korea" / "employment_contract_api.py"
            spec = importlib.util.spec_from_file_location("employment_contract_api2", _API_PATH)
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(mod)

            contract = {
                "form_type": "regular",
                "html_content": "<html><body><p>정규직 근로계약서</p></body></html>",
                "form_title": "기간의 정함이 없는 근로계약서",
                "employee": {"employee_name": "홍길동"},
            }
            result = mod.generate_korea_employment_contract_pdf(
                contract=contract,
                human_approved=True,
            )
        finally:
            sys.modules.pop("frappe", None)
            sys.modules.pop("frappe.utils.pdf", None)
            sys.modules.pop("employment_contract_api2", None)

        self.assertEqual(result["status"], "generated")
        self.assertIn("pdf_base64", result)
        # base64 디코딩 시 원본 bytes와 일치해야 함
        decoded = base64.b64decode(result["pdf_base64"])
        self.assertEqual(decoded, fake_pdf_bytes)
        self.assertEqual(result["form_type"], "regular")
        self.assertIn("filename", result)
        self.assertIn("regular", result["filename"])
        self.assertFalse(result["requires_human_approval"])

    # ------------------------------------------------------------------
    # preview_korea_employment_contract: happy path + side-effect 없음
    # ------------------------------------------------------------------

    def test_preview_returns_html_and_meta(self):
        """preview 는 HTML + print_format_name 포함 + runtime_action=preview_only."""
        result = self.api.preview_korea_employment_contract(
            contract_type="regular",
            company=_COMPANY,
            employee=_EMPLOYEE,
            contract_terms=_REGULAR_TERMS,
        )
        self.assertEqual(result["runtime_action"], "preview_only")
        self.assertEqual(result["print_format_name"], "Korea Employment Contract Regular")
        self.assertIn("html_content", result)
        self.assertTrue(result["html_content"])

    def test_preview_fixed_term_print_format(self):
        result = self.api.preview_korea_employment_contract(
            contract_type="fixed_term",
            company=_COMPANY,
            employee=_EMPLOYEE,
            contract_terms=_FIXED_TERM_TERMS,
        )
        self.assertEqual(result["print_format_name"], "Korea Employment Contract Fixed Term")

    def test_preview_daily_print_format(self):
        result = self.api.preview_korea_employment_contract(
            contract_type="daily",
            company=_COMPANY,
            employee=_EMPLOYEE,
            contract_terms=_DAILY_TERMS,
        )
        self.assertEqual(result["print_format_name"], "Korea Employment Contract Daily")

    def test_preview_part_time_print_format(self):
        result = self.api.preview_korea_employment_contract(
            contract_type="part_time",
            company=_COMPANY,
            employee=_EMPLOYEE,
            contract_terms=_PART_TIME_TERMS,
        )
        self.assertEqual(result["print_format_name"], "Korea Employment Contract Part Time")

    def test_preview_invalid_contract_type_raises(self):
        """preview 에서 잘못된 contract_type 은 예외."""
        with self.assertRaises(_FakeFrappe._Exceptions):
            self.api.preview_korea_employment_contract(
                contract_type="invalid",
                company=_COMPANY,
                employee=_EMPLOYEE,
                contract_terms=_REGULAR_TERMS,
            )

    def test_preview_json_string_company_is_coerced(self):
        """company 를 JSON 문자열로 전달해도 처리됨."""
        import json
        result = self.api.preview_korea_employment_contract(
            contract_type="regular",
            company=json.dumps(_COMPANY),
            employee=_EMPLOYEE,
            contract_terms=_REGULAR_TERMS,
        )
        self.assertEqual(result["runtime_action"], "preview_only")

    # ------------------------------------------------------------------
    # _coerce_bool 동작 검증
    # ------------------------------------------------------------------

    def test_coerce_bool_truthy_strings(self):
        """_coerce_bool: '1', 'true', 'yes', 'y' 는 True."""
        for val in ("1", "true", "True", "TRUE", "yes", "y", "Y"):
            with self.subTest(val=val):
                self.assertTrue(self.api._coerce_bool(val))

    def test_coerce_bool_falsy_strings(self):
        """_coerce_bool: 'false', 'no', '0' 등은 False."""
        for val in ("false", "False", "no", "0", "n", ""):
            with self.subTest(val=val):
                self.assertFalse(self.api._coerce_bool(val))


if __name__ == "__main__":
	unittest.main()
