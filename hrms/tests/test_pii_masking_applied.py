"""Phase 7-A PII 마스킹 적용 검증 테스트.

3개 영역의 PII 마스킹 실제 적용을 검증합니다:
  - 7-A-1: notification_dispatcher — Comment 본문의 전화번호 마스킹
  - 7-A-2: ai_chat — store_chat_audit_log의 질문/답변 PII 마스킹
  - 7-A-3: compliance_diagnosis — findings employee_name 마스킹 (mask_pii=True/False)

실행 (bench-free):
    python3 hrms/tests/test_pii_masking_applied.py
    python -m pytest hrms/tests/test_pii_masking_applied.py -v
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest

_SOUTH_KOREA = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea"


def _load_module(filename: str, module_name: str) -> types.ModuleType:
    """bench-free importlib 패턴 (hrms/__init__.py frappe import 우회)."""
    path = _SOUTH_KOREA / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


# ── 모듈 로드 ─────────────────────────────────────────────────────────────────

_kakao = _load_module("kakao_notification.py", "test_pii_kakao_notification")
_ai_chat = _load_module("ai_chat.py", "test_pii_ai_chat")


# compliance_diagnosis는 kakao_notification을 동적 로드하므로 별도 처리 불필요
def _load_compliance_diagnosis() -> types.ModuleType:
    return _load_module("compliance_diagnosis.py", "test_pii_compliance_diagnosis")


# ── 헬퍼 함수 임포트 ─────────────────────────────────────────────────────────

mask_phone_number = _kakao.mask_phone_number
mask_korean_name = _kakao.mask_korean_name
mask_email = _kakao.mask_email
mask_rrn = _kakao.mask_rrn

store_chat_audit_log = _ai_chat.store_chat_audit_log
_mask_pii_in_text = _ai_chat._mask_pii_in_text


# ===========================================================================
# 7-A-1: notification_dispatcher — Comment 내 전화번호 마스킹
# ===========================================================================


class TestDispatcherPhoneMasking(unittest.TestCase):
    """notification_dispatcher._insert_pending_comment가 전화번호를 마스킹하는지 확인.

    frappe import 없이 mask_phone_number 헬퍼 단위 테스트로 대체 검증.
    실제 Comment 삽입은 Frappe bench 없이 불가하므로, 마스킹 함수 자체를 검증.
    """

    def test_full_11_digit_phone_masked(self):
        result = mask_phone_number("01012345678")
        self.assertEqual(result, "010-****-5678")
        self.assertNotIn("1234", result)

    def test_full_phone_with_dashes_masked(self):
        result = mask_phone_number("010-1234-5678")
        # 숫자만 추출 후 재포맷
        self.assertIn("****", result)
        self.assertNotIn("1234", result)
        self.assertEqual(result, "010-****-5678")

    def test_10_digit_phone_masked(self):
        result = mask_phone_number("0101234567")
        self.assertIn("***", result)
        self.assertNotIn("1234", result)

    def test_empty_phone_returns_empty(self):
        self.assertEqual(mask_phone_number(""), "")

    def test_none_coerced(self):
        # mask_phone_number(None) 호출 방어
        result = mask_phone_number(None)  # type: ignore[arg-type]
        self.assertEqual(result, "")

    def test_international_phone_fallback(self):
        # 국제번호는 fallback 패턴 적용
        result = mask_phone_number("+821012345678")
        self.assertIn("****", result)
        self.assertNotIn("1234", result)

    def test_comment_content_phone_masked(self):
        """Comment 본문에 전화번호가 마스킹되어 포함되는지 시뮬레이션."""
        raw_phone = "01098765432"
        masked = mask_phone_number(raw_phone)
        content = (
            f"[카카오 알림톡 발송 대기]\n"
            f"수신자: {masked}\n"
            f"미리보기: 홍길동님의 임금명세서"
        )
        self.assertNotIn(raw_phone, content)
        self.assertIn("****", content)


# ===========================================================================
# 7-A-2: ai_chat — store_chat_audit_log PII 마스킹
# ===========================================================================


class TestAiChatAuditLogMasking(unittest.TestCase):

    def setUp(self):
        # 각 테스트 시작 시 in-memory audit log 초기화
        _ai_chat._AUDIT_LOG.clear()

    def test_phone_in_question_masked(self):
        """질문에 포함된 전화번호가 감사 로그에 마스킹되어 저장됨."""
        raw_question = "직원 홍길동(010-1234-5678)의 연차를 조회해 주세요"
        entry = store_chat_audit_log(
            session_id="sess-001",
            user_id="hr_manager",
            question=raw_question,
            answer="답변: 연차 10일 남음",
            citations=[],
        )
        self.assertNotIn("010-1234-5678", entry["question"])
        self.assertNotIn("1234", entry["question"])

    def test_rrn_in_question_masked(self):
        """질문에 포함된 주민등록번호가 감사 로그에 마스킹되어 저장됨."""
        raw_question = "주민번호 940312-1234567 직원의 퇴직금을 계산해 주세요"
        entry = store_chat_audit_log(
            session_id="sess-002",
            user_id="admin",
            question=raw_question,
            answer="퇴직금 산출 결과",
            citations=[],
        )
        self.assertNotIn("1234567", entry["question"])
        # 앞부분(940312)은 노출될 수 있으나 뒷부분은 마스킹
        self.assertIn("940312", entry["question"])  # 앞 6자리 유지
        self.assertIn("*", entry["question"])

    def test_email_in_answer_masked(self):
        """답변에 포함된 이메일이 감사 로그에 마스킹되어 저장됨."""
        raw_answer = "담당 노무사 연락처: kim.labor@winhr.co.kr 로 문의하세요."
        entry = store_chat_audit_log(
            session_id="sess-003",
            user_id="employee",
            question="담당 노무사 연락처는?",
            answer=raw_answer,
            citations=[],
        )
        self.assertNotIn("kim.labor@winhr.co.kr", entry["answer"])
        self.assertIn("@winhr.co.kr", entry["answer"])  # 도메인은 유지
        self.assertIn("*", entry["answer"])

    def test_citations_not_masked(self):
        """citations(법령 조문)은 마스킹하지 않음."""
        citations = [
            {"type": "law", "ref": "근기법 60조", "snippet": "연차 유급휴가 15일 부여"},
        ]
        entry = store_chat_audit_log(
            session_id="sess-004",
            user_id="user",
            question="연차 질문",
            answer="근기법 60조에 따라 15일 부여",
            citations=citations,
        )
        self.assertEqual(entry["citations"], citations)
        self.assertIn("근기법 60조", entry["citations"][0]["ref"])

    def test_audit_log_appended(self):
        """감사 로그가 실제로 _AUDIT_LOG 리스트에 추가됨."""
        before = len(_ai_chat._AUDIT_LOG)
        store_chat_audit_log(
            session_id="sess-005",
            user_id="user",
            question="질문",
            answer="답변",
            citations=[],
        )
        self.assertEqual(len(_ai_chat._AUDIT_LOG), before + 1)

    def test_clean_text_unchanged(self):
        """PII가 없는 텍스트는 변경되지 않음."""
        q = "연차 유급휴가 계산 방법이 궁금합니다"
        a = "근기법 60조에 따라 1년 근속 시 15일 부여됩니다"
        entry = store_chat_audit_log(
            session_id="sess-006",
            user_id="user",
            question=q,
            answer=a,
            citations=[],
        )
        self.assertEqual(entry["question"], q)
        self.assertEqual(entry["answer"], a)

    def test_phone_no_dash_in_question_masked(self):
        """공백 없는 연속 전화번호도 마스킹됨."""
        entry = store_chat_audit_log(
            session_id="sess-007",
            user_id="user",
            question="01099998888 이 번호 직원의 정보를 알려주세요",
            answer="처리 불가",
            citations=[],
        )
        self.assertNotIn("9999", entry["question"])


class TestMaskPiiInText(unittest.TestCase):
    """_mask_pii_in_text 단위 테스트."""

    def test_phone_masked(self):
        text = "연락처: 010-5555-1234 입니다"
        result = _mask_pii_in_text(text)
        self.assertNotIn("5555", result)
        self.assertIn("****", result)
        self.assertIn("1234", result)  # 마지막 4자리 유지

    def test_rrn_with_dash_masked(self):
        text = "주민번호 850101-2345678 처리"
        result = _mask_pii_in_text(text)
        self.assertIn("850101", result)
        self.assertNotIn("2345678", result)
        self.assertIn("*", result)

    def test_email_masked(self):
        text = "이메일: hongkildong@company.com 으로 발송"
        result = _mask_pii_in_text(text)
        self.assertNotIn("hongkildong@", result)
        self.assertIn("@company.com", result)

    def test_empty_string_unchanged(self):
        self.assertEqual(_mask_pii_in_text(""), "")

    def test_law_text_unchanged(self):
        text = "근기법 60조 (연차 유급휴가): 사용자는 1년간 80퍼센트 이상 출근한 근로자에게 15일의 유급휴가를 주어야 한다."
        result = _mask_pii_in_text(text)
        self.assertEqual(result, text)


# ===========================================================================
# 7-A-3: compliance_diagnosis — findings employee_name 마스킹
# ===========================================================================


class MockDataLoader:
    """컴플라이언스 진단 테스트용 mock DataLoader."""

    def get_workplace_profile(self, company, workplace):
        return {
            "name": workplace,
            "company": company,
            "scheduled_pay_day": 25,
            "anti_bullying_policy_registered": False,
            "grievance_channel_registered": False,
        }

    def get_employment_profiles(self, company, workplace):
        return [
            {
                "employee": "EMP-001",
                "employee_name": "김철수",
                "national_pension_enrolled": False,
                "health_insurance_enrolled": True,
                "employment_insurance_enrolled": True,
                "industrial_accident_enrolled": True,
            },
            {
                "employee": "EMP-002",
                "employee_name": "이영희",
                "national_pension_enrolled": True,
                "health_insurance_enrolled": True,
                "employment_insurance_enrolled": True,
                "industrial_accident_enrolled": True,
            },
        ]

    def get_salary_slips(self, company, workplace, from_date, to_date):
        return []

    def get_attendance_records(self, company, workplace, from_date, to_date):
        return []

    def get_leave_allocations(self, company, workplace, as_of_date):
        return []

    def get_leave_applications(self, company, workplace, from_date, to_date):
        return []

    def get_policy_documents(self, company, workplace):
        return []


class TestComplianceDiagnosisMaskPii(unittest.TestCase):
    """run_full_compliance_diagnosis의 mask_pii 옵션 테스트."""

    def setUp(self):
        self._diag = _load_compliance_diagnosis()
        self._loader = MockDataLoader()

    def _run(self, mask_pii: bool) -> dict:
        return self._diag.run_full_compliance_diagnosis(
            company="위너스",
            workplace="서울지사",
            as_of_date="2026-05-18",
            data_loader=self._loader,
            mask_pii=mask_pii,
        )

    def test_mask_pii_default_true_masks_employee_names(self):
        """mask_pii=True (기본값): findings에서 employee_name 마스킹됨."""
        result = self._run(mask_pii=True)
        self.assertTrue(result["pii_masked"])

        # 4대보험 미가입 finding에 김철수 이름이 마스킹되어 있어야 함
        si = result["diagnoses"]["social_insurance"]
        named_findings = [
            f for f in si["findings"] if f.get("employee_name")
        ]
        for finding in named_findings:
            name = finding["employee_name"]
            # 마스킹 패턴: 첫 글자 + * + 마지막 글자 (3자)
            self.assertNotEqual(name, "김철수")
            self.assertTrue(
                name.startswith("김") and name.endswith("수"),
                f"마스킹 패턴 오류: {name!r}",
            )
            self.assertIn("*", name)

    def test_mask_pii_false_exposes_employee_names(self):
        """mask_pii=False: findings에서 원본 employee_name 노출됨 (audit 용도)."""
        result = self._run(mask_pii=False)
        self.assertFalse(result["pii_masked"])

        si = result["diagnoses"]["social_insurance"]
        named_findings = [
            f for f in si["findings"] if f.get("employee_name")
        ]
        # 원본 이름이 그대로 노출되어야 함
        names = [f["employee_name"] for f in named_findings]
        self.assertIn("김철수", names, f"원본 이름 노출 실패: {names}")

    def test_mask_pii_true_pii_masked_flag_in_result(self):
        """결과 dict에 pii_masked 필드가 포함됨."""
        result = self._run(mask_pii=True)
        self.assertIn("pii_masked", result)
        self.assertTrue(result["pii_masked"])

    def test_mask_pii_false_pii_masked_flag_false(self):
        result = self._run(mask_pii=False)
        self.assertIn("pii_masked", result)
        self.assertFalse(result["pii_masked"])

    def test_overall_status_unaffected_by_masking(self):
        """마스킹 여부가 overall_status 판정에 영향을 주지 않음."""
        result_masked = self._run(mask_pii=True)
        result_unmasked = self._run(mask_pii=False)
        self.assertEqual(result_masked["overall_status"], result_unmasked["overall_status"])

    def test_recommendations_unaffected_by_masking(self):
        """recommendations는 마스킹 여부에 무관하게 동일."""
        result_masked = self._run(mask_pii=True)
        result_unmasked = self._run(mask_pii=False)
        for key in result_masked["diagnoses"]:
            self.assertEqual(
                result_masked["diagnoses"][key]["recommendations"],
                result_unmasked["diagnoses"][key]["recommendations"],
                f"{key}: recommendations 불일치",
            )


# ===========================================================================
# PII 마스킹 헬퍼 단위 테스트 (기존 helpers 정확성 확인)
# ===========================================================================


class TestPiiHelpers(unittest.TestCase):
    """kakao_notification.py PII mask helpers 단위 테스트."""

    # mask_phone_number
    def test_phone_11digits(self):
        self.assertEqual(mask_phone_number("01012345678"), "010-****-5678")

    def test_phone_10digits(self):
        self.assertEqual(mask_phone_number("0101234567"), "010-***-4567")

    def test_phone_empty(self):
        self.assertEqual(mask_phone_number(""), "")

    # mask_korean_name
    def test_name_3chars(self):
        self.assertEqual(mask_korean_name("홍길동"), "홍*동")

    def test_name_2chars(self):
        self.assertEqual(mask_korean_name("김민"), "김*")

    def test_name_4chars(self):
        self.assertEqual(mask_korean_name("박세재홍"), "박**홍")

    def test_name_1char(self):
        self.assertEqual(mask_korean_name("김"), "*")

    def test_name_empty(self):
        self.assertEqual(mask_korean_name(""), "")

    # mask_email
    def test_email_standard(self):
        self.assertEqual(mask_email("abc@winhr.co.kr"), "a**@winhr.co.kr")

    def test_email_no_at(self):
        self.assertEqual(mask_email("notanemail"), "***")

    def test_email_empty(self):
        self.assertEqual(mask_email(""), "***")

    def test_email_single_local(self):
        self.assertEqual(mask_email("a@b.com"), "*@b.com")

    # mask_rrn
    def test_rrn_with_dash(self):
        result = mask_rrn("940312-1234567")
        self.assertEqual(result, "940312-1******")

    def test_rrn_no_dash(self):
        result = mask_rrn("9403121234567")
        self.assertIn("*", result)
        self.assertTrue(result.startswith("9403121"))

    def test_rrn_empty(self):
        self.assertEqual(mask_rrn(""), "")


if __name__ == "__main__":
    unittest.main()
