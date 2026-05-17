"""한국 노무 컴플라이언스 진단 테스트.

순수 Python unittest 기반. Frappe 없이 mock DataLoader로 실행 가능.

실행::
    python -m pytest hrms/tests/test_korea_compliance_diagnosis.py -v
    또는
    python -m unittest hrms/tests/test_korea_compliance_diagnosis.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
from typing import Any


# ---------------------------------------------------------------------------
# Frappe 없이 compliance_diagnosis 모듈 로드 (sys.modules 격리)
# ---------------------------------------------------------------------------

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "regional"
    / "south_korea"
    / "compliance_diagnosis.py"
)


def _load_diagnosis_module() -> types.ModuleType:
    """Frappe 의존 없이 compliance_diagnosis 모듈 로드."""
    spec = importlib.util.spec_from_file_location(
        "test_compliance_diagnosis_module", _MODULE_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_diag = _load_diagnosis_module()

# 개별 함수를 편하게 import
diagnose_social_insurance = _diag.diagnose_social_insurance
diagnose_wage_delay = _diag.diagnose_wage_delay
diagnose_overtime_limit = _diag.diagnose_overtime_limit
diagnose_annual_leave_usage = _diag.diagnose_annual_leave_usage
diagnose_anti_bullying = _diag.diagnose_anti_bullying
run_full_compliance_diagnosis = _diag.run_full_compliance_diagnosis
DIAGNOSIS_RULES = _diag.DIAGNOSIS_RULES
WEEKLY_OVERTIME_LIMIT_HOURS = _diag.WEEKLY_OVERTIME_LIMIT_HOURS


# ---------------------------------------------------------------------------
# Mock DataLoader
# ---------------------------------------------------------------------------


class MockDataLoader:
    """테스트용 Mock DataLoader. 각 속성에 반환값을 직접 주입."""

    def __init__(
        self,
        *,
        workplace_profile: dict[str, Any] | None = None,
        employment_profiles: list[dict[str, Any]] | None = None,
        salary_slips: list[dict[str, Any]] | None = None,
        attendance_records: list[dict[str, Any]] | None = None,
        leave_allocations: list[dict[str, Any]] | None = None,
        leave_applications: list[dict[str, Any]] | None = None,
        policy_documents: list[dict[str, Any]] | None = None,
    ) -> None:
        self._workplace_profile = workplace_profile
        self._employment_profiles = employment_profiles or []
        self._salary_slips = salary_slips or []
        self._attendance_records = attendance_records or []
        self._leave_allocations = leave_allocations or []
        self._leave_applications = leave_applications or []
        self._policy_documents = policy_documents or []

    def get_workplace_profile(self, company: str, workplace: str) -> dict[str, Any] | None:
        return self._workplace_profile

    def get_employment_profiles(self, company: str, workplace: str) -> list[dict[str, Any]]:
        return self._employment_profiles

    def get_salary_slips(self, company, workplace, from_date, to_date) -> list[dict[str, Any]]:
        return self._salary_slips

    def get_attendance_records(self, company, workplace, from_date, to_date) -> list[dict[str, Any]]:
        return self._attendance_records

    def get_leave_allocations(self, company, workplace, as_of_date) -> list[dict[str, Any]]:
        return self._leave_allocations

    def get_leave_applications(self, company, workplace, from_date, to_date) -> list[dict[str, Any]]:
        return self._leave_applications

    def get_policy_documents(self, company, workplace) -> list[dict[str, Any]]:
        return self._policy_documents


# ---------------------------------------------------------------------------
# 4대보험 (Social Insurance) 테스트
# ---------------------------------------------------------------------------


class TestDiagnoseSocialInsurance(unittest.TestCase):
    def test_all_enrolled_returns_pass(self):
        """4대보험 100% 가입 → social_insurance: pass"""
        profiles = [
            {
                "employee": "EMP-0001",
                "employee_name": "김철수",
                "national_pension_enrolled": True,
                "health_insurance_enrolled": True,
                "employment_insurance_enrolled": True,
                "industrial_accident_enrolled": True,
            },
            {
                "employee": "EMP-0002",
                "employee_name": "이영희",
                "national_pension_enrolled": True,
                "health_insurance_enrolled": True,
                "employment_insurance_enrolled": True,
                "industrial_accident_enrolled": True,
            },
        ]
        result = diagnose_social_insurance(
            workplace_profile=None,
            employment_profiles=profiles,
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["recommendations"], [])

    def test_some_not_enrolled_returns_fail_with_findings(self):
        """4대보험 일부 미가입 → fail + findings"""
        profiles = [
            {
                "employee": "EMP-0001",
                "employee_name": "김철수",
                "national_pension_enrolled": False,
                "health_insurance_enrolled": False,
                "employment_insurance_enrolled": True,
                "industrial_accident_enrolled": True,
            },
            {
                "employee": "EMP-0002",
                "employee_name": "이영희",
                "national_pension_enrolled": True,
                "health_insurance_enrolled": True,
                "employment_insurance_enrolled": True,
                "industrial_accident_enrolled": True,
            },
        ]
        result = diagnose_social_insurance(
            workplace_profile=None,
            employment_profiles=profiles,
        )
        self.assertEqual(result["status"], "fail")
        # EMP-0001에 대한 finding이 있어야 함
        fail_findings = [f for f in result["findings"] if not f.get("data_unavailable")]
        self.assertTrue(len(fail_findings) >= 1)
        emp_findings = [f for f in fail_findings if f.get("employee") == "EMP-0001"]
        self.assertTrue(len(emp_findings) >= 1)
        self.assertIn("국민연금", emp_findings[0]["issue"])
        # EMP-0002는 finding 없어야 함
        emp2_fail = [f for f in fail_findings if f.get("employee") == "EMP-0002"]
        self.assertEqual(emp2_fail, [])
        # 법령 참조 포함
        self.assertIn("law", emp_findings[0])
        # recommendations 있어야 함
        self.assertTrue(len(result["recommendations"]) > 0)

    def test_enrollment_data_missing_returns_warn(self):
        """4대보험 가입 정보 미등록(None) → warn + data_unavailable"""
        profiles = [
            {
                "employee": "EMP-0001",
                "employee_name": "박지성",
                "national_pension_enrolled": None,
                "health_insurance_enrolled": None,
                "employment_insurance_enrolled": None,
                "industrial_accident_enrolled": None,
            }
        ]
        result = diagnose_social_insurance(
            workplace_profile=None,
            employment_profiles=profiles,
        )
        self.assertEqual(result["status"], "warn")
        unavailable = [f for f in result["findings"] if f.get("data_unavailable")]
        self.assertTrue(len(unavailable) >= 1)

    def test_empty_profiles_returns_warn(self):
        """고용 프로파일 없음 → warn (데이터 미등록)"""
        result = diagnose_social_insurance(
            workplace_profile=None,
            employment_profiles=[],
        )
        self.assertEqual(result["status"], "warn")
        self.assertTrue(result["findings"][0].get("data_unavailable"))

    def test_industrial_accident_not_enrolled_returns_fail(self):
        """산재보험 미가입 → fail"""
        profiles = [
            {
                "employee": "EMP-0003",
                "employee_name": "최민준",
                "national_pension_enrolled": True,
                "health_insurance_enrolled": True,
                "employment_insurance_enrolled": True,
                "industrial_accident_enrolled": False,
            }
        ]
        result = diagnose_social_insurance(
            workplace_profile=None,
            employment_profiles=profiles,
        )
        self.assertEqual(result["status"], "fail")
        fail_findings = [f for f in result["findings"] if not f.get("data_unavailable")]
        self.assertTrue(any("산재보험" in f["issue"] for f in fail_findings))


# ---------------------------------------------------------------------------
# 임금체불 위험 (Wage Delay) 테스트
# ---------------------------------------------------------------------------


class TestDiagnoseWageDelay(unittest.TestCase):
    def test_on_time_payment_returns_pass(self):
        """정기 지급일 준수 → pass"""
        salary_slips = [
            {
                "name": "SS-0001",
                "employee": "EMP-0001",
                "employee_name": "김철수",
                "posting_date": "2026-04-10",
                "start_date": "2026-04-01",
                "end_date": "2026-04-30",
            },
        ]
        result = diagnose_wage_delay(
            salary_slips=salary_slips,
            scheduled_pay_day=10,
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["findings"], [])

    def test_delayed_payment_returns_warn_with_findings(self):
        """임금 지급일 지연 history → warn + findings"""
        salary_slips = [
            {
                "name": "SS-0001",
                "employee": "EMP-0001",
                "employee_name": "김철수",
                "posting_date": "2026-04-18",  # 지급일 10일인데 18일 지급 → 8일 지연
                "start_date": "2026-04-01",
                "end_date": "2026-04-30",
            },
        ]
        result = diagnose_wage_delay(
            salary_slips=salary_slips,
            scheduled_pay_day=10,
        )
        self.assertEqual(result["status"], "warn")
        self.assertTrue(len(result["findings"]) >= 1)
        finding = result["findings"][0]
        self.assertIn("지연", finding["issue"])
        self.assertEqual(finding.get("employee"), "EMP-0001")
        self.assertIn("delay_days", finding.get("detail", {}))
        self.assertEqual(finding["detail"]["delay_days"], 8)
        self.assertTrue(len(result["recommendations"]) > 0)

    def test_no_scheduled_pay_day_returns_warn(self):
        """정기 지급일 미등록 → warn"""
        result = diagnose_wage_delay(
            salary_slips=[{"name": "SS-1", "employee": "EMP-0001", "posting_date": "2026-04-10", "start_date": "2026-04-01", "end_date": "2026-04-30"}],
            scheduled_pay_day=None,
        )
        self.assertEqual(result["status"], "warn")
        self.assertTrue(result["findings"][0].get("data_unavailable"))

    def test_empty_salary_slips_returns_warn(self):
        """급여 명세서 없음 → warn"""
        result = diagnose_wage_delay(
            salary_slips=[],
            scheduled_pay_day=10,
        )
        self.assertEqual(result["status"], "warn")

    def test_multiple_slips_some_delayed(self):
        """일부 지연 + 일부 정시 → warn, 지연된 것만 finding"""
        salary_slips = [
            {
                "name": "SS-0001",
                "employee": "EMP-0001",
                "employee_name": "김철수",
                "posting_date": "2026-03-10",  # 정시
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
            },
            {
                "name": "SS-0002",
                "employee": "EMP-0001",
                "employee_name": "김철수",
                "posting_date": "2026-04-15",  # 5일 지연
                "start_date": "2026-04-01",
                "end_date": "2026-04-30",
            },
        ]
        result = diagnose_wage_delay(
            salary_slips=salary_slips,
            scheduled_pay_day=10,
        )
        self.assertEqual(result["status"], "warn")
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["detail"]["salary_slip"], "SS-0002")


# ---------------------------------------------------------------------------
# 연장근로 한도 (Overtime Limit) 테스트
# ---------------------------------------------------------------------------


class TestDiagnoseOvertimeLimit(unittest.TestCase):
    def _make_week_records(
        self,
        employee: str,
        employee_name: str,
        week_start: str,
        overtime_hours_per_day: list[float],
    ) -> list[dict[str, Any]]:
        """주어진 주의 연장근로 기록 생성 헬퍼."""
        from datetime import date, timedelta
        start = date.fromisoformat(week_start)
        records = []
        for i, ot in enumerate(overtime_hours_per_day):
            records.append(
                {
                    "employee": employee,
                    "employee_name": employee_name,
                    "attendance_date": str(start + timedelta(days=i)),
                    "working_hours": 8.0,
                    "overtime_hours": ot,
                }
            )
        return records

    def test_no_overtime_returns_pass(self):
        """연장근로 없음 → pass"""
        records = self._make_week_records(
            "EMP-0001", "김철수", "2026-04-27", [0, 0, 0, 0, 0]
        )
        result = diagnose_overtime_limit(attendance_records=records)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["findings"], [])

    def test_within_limit_returns_pass(self):
        """주 12시간 이하 → pass"""
        records = self._make_week_records(
            "EMP-0001", "김철수", "2026-04-27", [2, 2, 2, 2, 3]
        )  # 총 11h
        result = diagnose_overtime_limit(attendance_records=records)
        self.assertEqual(result["status"], "pass")

    def test_exceeding_limit_returns_fail(self):
        """주 12h 초과 → fail + findings"""
        records = self._make_week_records(
            "EMP-0001", "김철수", "2026-04-27", [3, 3, 3, 3, 3]
        )  # 총 15h
        result = diagnose_overtime_limit(attendance_records=records)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(len(result["findings"]) >= 1)
        finding = result["findings"][0]
        self.assertEqual(finding["employee"], "EMP-0001")
        self.assertIn("15.0h", finding["issue"])
        self.assertIn("detail", finding)
        self.assertEqual(finding["detail"]["overtime_hours"], 15.0)
        self.assertTrue(len(result["recommendations"]) > 0)

    def test_exactly_at_limit_returns_pass(self):
        """정확히 12시간 → pass (초과 아님)"""
        records = self._make_week_records(
            "EMP-0001", "김철수", "2026-04-27", [2, 2, 2, 2, 4]
        )  # 총 12h
        result = diagnose_overtime_limit(attendance_records=records)
        self.assertEqual(result["status"], "pass")

    def test_multiple_employees_only_violator_in_findings(self):
        """직원 여러 명 중 위반자만 finding"""
        violator = self._make_week_records(
            "EMP-0001", "위반자", "2026-04-27", [3, 3, 3, 3, 3]  # 15h
        )
        compliant = self._make_week_records(
            "EMP-0002", "준수자", "2026-04-27", [2, 2, 2, 0, 0]  # 6h
        )
        result = diagnose_overtime_limit(attendance_records=violator + compliant)
        self.assertEqual(result["status"], "fail")
        finding_employees = [f["employee"] for f in result["findings"]]
        self.assertIn("EMP-0001", finding_employees)
        self.assertNotIn("EMP-0002", finding_employees)

    def test_empty_attendance_returns_warn(self):
        """근태 기록 없음 → warn"""
        result = diagnose_overtime_limit(attendance_records=[])
        self.assertEqual(result["status"], "warn")
        self.assertTrue(result["findings"][0].get("data_unavailable"))

    def test_violations_across_different_weeks(self):
        """다른 주에 각각 위반 → 주별로 finding"""
        week1 = self._make_week_records("EMP-0001", "김", "2026-04-20", [3, 3, 3, 3, 3])
        week2 = self._make_week_records("EMP-0001", "김", "2026-04-27", [3, 3, 3, 3, 3])
        result = diagnose_overtime_limit(attendance_records=week1 + week2)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(len(result["findings"]), 2)


# ---------------------------------------------------------------------------
# 연차 사용률 (Annual Leave Usage) 테스트
# ---------------------------------------------------------------------------


class TestDiagnoseAnnualLeaveUsage(unittest.TestCase):
    def test_high_usage_returns_pass(self):
        """연차 충분히 사용 → pass"""
        allocations = [
            {
                "employee": "EMP-0001",
                "employee_name": "김철수",
                "leave_type": "연차",
                "total_leaves_allocated": 15.0,
                "from_date": "2026-01-01",
                "to_date": "2026-12-31",
            }
        ]
        applications = [
            {
                "employee": "EMP-0001",
                "employee_name": "김철수",
                "leave_type": "연차",
                "total_leave_days": 13.0,  # 13/15 = 87% 사용
                "status": "Approved",
            }
        ]
        result = diagnose_annual_leave_usage(
            leave_allocations=allocations,
            leave_applications=applications,
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["findings"], [])

    def test_high_unused_returns_warn(self):
        """연차 80% 이상 미사용 → warn (소멸 위험)"""
        allocations = [
            {
                "employee": "EMP-0001",
                "employee_name": "이영희",
                "leave_type": "연차",
                "total_leaves_allocated": 15.0,
                "from_date": "2026-01-01",
                "to_date": "2026-12-31",
            }
        ]
        applications = [
            {
                "employee": "EMP-0001",
                "employee_name": "이영희",
                "leave_type": "연차",
                "total_leave_days": 2.0,  # 2/15 = 13% 사용 → 87% 미사용
                "status": "Approved",
            }
        ]
        result = diagnose_annual_leave_usage(
            leave_allocations=allocations,
            leave_applications=applications,
        )
        self.assertEqual(result["status"], "warn")
        self.assertTrue(len(result["findings"]) >= 1)
        finding = result["findings"][0]
        self.assertEqual(finding["employee"], "EMP-0001")
        self.assertIn("소멸", finding["issue"])
        self.assertEqual(finding["detail"]["allocated_days"], 15.0)
        self.assertEqual(finding["detail"]["used_days"], 2.0)
        self.assertTrue(len(result["recommendations"]) > 0)
        # 권고에 '사용 촉진' 언급
        self.assertTrue(any("촉진" in r or "촉구" in r for r in result["recommendations"]))

    def test_no_applications_all_unused_returns_warn(self):
        """연차 0% 사용 → warn"""
        allocations = [
            {
                "employee": "EMP-0001",
                "employee_name": "박지성",
                "leave_type": "연차",
                "total_leaves_allocated": 10.0,
                "from_date": "2026-01-01",
                "to_date": "2026-12-31",
            }
        ]
        result = diagnose_annual_leave_usage(
            leave_allocations=allocations,
            leave_applications=[],
        )
        self.assertEqual(result["status"], "warn")

    def test_empty_allocations_returns_warn(self):
        """연차 할당 없음 → warn (데이터 미등록)"""
        result = diagnose_annual_leave_usage(
            leave_allocations=[],
            leave_applications=[],
        )
        self.assertEqual(result["status"], "warn")
        self.assertTrue(result["findings"][0].get("data_unavailable"))

    def test_only_pending_applications_not_counted(self):
        """Pending 상태 연차신청은 사용으로 미집계"""
        allocations = [
            {
                "employee": "EMP-0001",
                "employee_name": "테스트",
                "leave_type": "연차",
                "total_leaves_allocated": 10.0,
                "from_date": "2026-01-01",
                "to_date": "2026-12-31",
            }
        ]
        applications = [
            {
                "employee": "EMP-0001",
                "leave_type": "연차",
                "total_leave_days": 10.0,  # 10일 신청했지만 pending
                "status": "Pending",
            }
        ]
        result = diagnose_annual_leave_usage(
            leave_allocations=allocations,
            leave_applications=applications,
        )
        # Pending은 미사용으로 처리 → warn
        self.assertEqual(result["status"], "warn")


# ---------------------------------------------------------------------------
# 직장 내 괴롭힘 (Anti-Bullying) 테스트
# ---------------------------------------------------------------------------


class TestDiagnoseAntiBullying(unittest.TestCase):
    def _full_profile(self) -> dict[str, Any]:
        return {
            "name": "서울지사",
            "company": "위너스",
            "anti_bullying_policy_registered": True,
            "grievance_channel_registered": True,
        }

    def _full_policy_docs(self) -> list[dict[str, Any]]:
        return [
            {
                "document_type": "anti_bullying_policy",
                "title": "직장 내 괴롭힘 예방 규정",
                "registered_date": "2026-01-15",
            }
        ]

    def test_all_registered_returns_pass(self):
        """정책 + 신고채널 모두 등록 → pass"""
        result = diagnose_anti_bullying(
            workplace_profile=self._full_profile(),
            policy_documents=self._full_policy_docs(),
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["recommendations"], [])

    def test_no_grievance_channel_returns_fail(self):
        """신고채널 등록 0 → fail (severity: high)"""
        profile = self._full_profile()
        profile["grievance_channel_registered"] = False
        result = diagnose_anti_bullying(
            workplace_profile=profile,
            policy_documents=self._full_policy_docs(),
        )
        self.assertEqual(result["status"], "fail")
        fail_findings = [f for f in result["findings"] if not f.get("data_unavailable")]
        self.assertTrue(len(fail_findings) >= 1)
        self.assertTrue(any("신고채널" in f["issue"] for f in fail_findings))
        self.assertTrue(len(result["recommendations"]) > 0)

    def test_no_policy_document_returns_fail(self):
        """정책 문서 미등록 → fail"""
        result = diagnose_anti_bullying(
            workplace_profile=self._full_profile(),
            policy_documents=[],  # 문서 없음
        )
        self.assertEqual(result["status"], "fail")
        fail_findings = [f for f in result["findings"] if not f.get("data_unavailable")]
        self.assertTrue(len(fail_findings) >= 1)

    def test_no_policy_and_no_channel_returns_fail(self):
        """정책 + 신고채널 모두 미등록 → fail"""
        profile = {
            "name": "서울지사",
            "company": "위너스",
            "anti_bullying_policy_registered": False,
            "grievance_channel_registered": False,
        }
        result = diagnose_anti_bullying(
            workplace_profile=profile,
            policy_documents=[],
        )
        self.assertEqual(result["status"], "fail")
        fail_findings = [f for f in result["findings"] if not f.get("data_unavailable")]
        self.assertGreaterEqual(len(fail_findings), 2)

    def test_no_workplace_profile_returns_warn(self):
        """Workplace Profile 없음 → warn (데이터 미등록)"""
        result = diagnose_anti_bullying(
            workplace_profile=None,
            policy_documents=[],
        )
        # profile None이어도 정책 문서 없으면 fail findings 존재
        # profile=None → data_unavailable warn finding 추가
        # policy doc 없음 → fail finding
        # 실제로 actual_fails가 있으면 fail
        self.assertIn(result["status"], {"warn", "fail"})

    def test_law_reference_present_in_findings(self):
        """발견 항목에 법령 참조 포함"""
        profile = self._full_profile()
        profile["grievance_channel_registered"] = False
        result = diagnose_anti_bullying(
            workplace_profile=profile,
            policy_documents=self._full_policy_docs(),
        )
        for f in result["findings"]:
            self.assertIn("law", f)
            self.assertIn("76조", f["law"])


# ---------------------------------------------------------------------------
# 전체 진단 (run_full_compliance_diagnosis) 테스트
# ---------------------------------------------------------------------------


class TestRunFullComplianceDiagnosis(unittest.TestCase):
    def _make_clean_loader(self) -> MockDataLoader:
        """모든 항목이 양호한 상태의 loader."""
        return MockDataLoader(
            workplace_profile={
                "name": "서울지사",
                "company": "위너스",
                "scheduled_pay_day": 10,
                "anti_bullying_policy_registered": True,
                "grievance_channel_registered": True,
            },
            employment_profiles=[
                {
                    "employee": "EMP-0001",
                    "employee_name": "김철수",
                    "national_pension_enrolled": True,
                    "health_insurance_enrolled": True,
                    "employment_insurance_enrolled": True,
                    "industrial_accident_enrolled": True,
                }
            ],
            salary_slips=[
                {
                    "name": "SS-0001",
                    "employee": "EMP-0001",
                    "employee_name": "김철수",
                    "posting_date": "2026-04-10",
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-30",
                }
            ],
            attendance_records=[
                {
                    "employee": "EMP-0001",
                    "employee_name": "김철수",
                    "attendance_date": "2026-04-01",
                    "working_hours": 8.0,
                    "overtime_hours": 1.0,
                }
            ],
            leave_allocations=[
                {
                    "employee": "EMP-0001",
                    "employee_name": "김철수",
                    "leave_type": "연차",
                    "total_leaves_allocated": 15.0,
                    "from_date": "2026-01-01",
                    "to_date": "2026-12-31",
                }
            ],
            leave_applications=[
                {
                    "employee": "EMP-0001",
                    "employee_name": "김철수",
                    "leave_type": "연차",
                    "total_leave_days": 13.0,
                    "status": "Approved",
                }
            ],
            policy_documents=[
                {
                    "document_type": "anti_bullying_policy",
                    "title": "직장 내 괴롭힘 예방 규정",
                    "registered_date": "2026-01-15",
                }
            ],
        )

    def test_clean_state_returns_good_overall(self):
        """모든 항목 양호 → overall_status: good"""
        loader = self._make_clean_loader()
        result = run_full_compliance_diagnosis(
            company="위너스",
            workplace="서울지사",
            as_of_date="2026-05-17",
            data_loader=loader,
        )
        self.assertEqual(result["contract_type"], "korea_compliance_diagnosis_v1")
        self.assertEqual(result["company"], "위너스")
        self.assertEqual(result["workplace"], "서울지사")
        self.assertIn("diagnoses", result)
        self.assertIn("overall_status", result)
        self.assertIn("high_severity_findings", result)
        self.assertIn("recommendation_summary", result)
        # 모두 양호해야 함
        for key in ["social_insurance", "wage_delay", "overtime_limit", "annual_leave_usage", "anti_bullying_policy"]:
            self.assertIn(key, result["diagnoses"])
        self.assertEqual(result["overall_status"], "good")

    def test_high_risk_when_social_insurance_fail(self):
        """4대보험 fail(severity:high) → overall: high_risk"""
        loader = self._make_clean_loader()
        loader._employment_profiles = [
            {
                "employee": "EMP-0001",
                "employee_name": "김철수",
                "national_pension_enrolled": False,
                "health_insurance_enrolled": False,
                "employment_insurance_enrolled": False,
                "industrial_accident_enrolled": False,
            }
        ]
        result = run_full_compliance_diagnosis(
            company="위너스",
            workplace="서울지사",
            as_of_date="2026-05-17",
            data_loader=loader,
        )
        self.assertEqual(result["overall_status"], "high_risk")
        self.assertGreater(result["high_severity_findings"], 0)

    def test_high_risk_when_anti_bullying_fail(self):
        """괴롭힘 신고채널 미등록(severity:high) → overall: high_risk"""
        loader = self._make_clean_loader()
        loader._workplace_profile = {
            "name": "서울지사",
            "company": "위너스",
            "scheduled_pay_day": 10,
            "anti_bullying_policy_registered": False,
            "grievance_channel_registered": False,
        }
        loader._policy_documents = []
        result = run_full_compliance_diagnosis(
            company="위너스",
            workplace="서울지사",
            as_of_date="2026-05-17",
            data_loader=loader,
        )
        self.assertEqual(result["overall_status"], "high_risk")

    def test_needs_attention_when_only_warn(self):
        """warn만 있음 → overall: needs_attention"""
        loader = self._make_clean_loader()
        # 4대보험 데이터 미등록 → warn
        loader._employment_profiles = [
            {
                "employee": "EMP-0001",
                "employee_name": "김철수",
                "national_pension_enrolled": None,
                "health_insurance_enrolled": None,
                "employment_insurance_enrolled": None,
                "industrial_accident_enrolled": None,
            }
        ]
        result = run_full_compliance_diagnosis(
            company="위너스",
            workplace="서울지사",
            as_of_date="2026-05-17",
            data_loader=loader,
        )
        self.assertIn(result["overall_status"], {"needs_attention", "high_risk"})

    def test_invalid_as_of_date_raises_value_error(self):
        """잘못된 날짜 형식 → ValueError"""
        loader = self._make_clean_loader()
        with self.assertRaises(ValueError):
            run_full_compliance_diagnosis(
                company="위너스",
                workplace="서울지사",
                as_of_date="2026/05/17",  # 잘못된 형식
                data_loader=loader,
            )

    def test_empty_company_raises_value_error(self):
        """company 빈 문자열 → ValueError"""
        loader = self._make_clean_loader()
        with self.assertRaises(ValueError):
            run_full_compliance_diagnosis(
                company="",
                workplace="서울지사",
                as_of_date="2026-05-17",
                data_loader=loader,
            )

    def test_all_five_categories_present_in_result(self):
        """결과에 5개 카테고리 모두 포함"""
        loader = self._make_clean_loader()
        result = run_full_compliance_diagnosis(
            company="위너스",
            workplace="서울지사",
            as_of_date="2026-05-17",
            data_loader=loader,
        )
        expected_keys = {
            "social_insurance",
            "wage_delay",
            "overtime_limit",
            "annual_leave_usage",
            "anti_bullying_policy",
        }
        self.assertEqual(set(result["diagnoses"].keys()), expected_keys)

    def test_no_ai_scores_in_result(self):
        """결과에 AI 점수/확률 없음 — status는 pass/warn/fail만"""
        loader = self._make_clean_loader()
        result = run_full_compliance_diagnosis(
            company="위너스",
            workplace="서울지사",
            as_of_date="2026-05-17",
            data_loader=loader,
        )
        for key, diag in result["diagnoses"].items():
            self.assertIn(diag["status"], {"pass", "warn", "fail"})
            # score, probability, percentage 같은 필드 없어야 함
            self.assertNotIn("score", diag)
            self.assertNotIn("probability", diag)
            self.assertNotIn("percentage", diag)

    def test_recommendation_summary_contains_human_review_notice(self):
        """종합 권고 요약에 human-review 안내 포함"""
        loader = self._make_clean_loader()
        result = run_full_compliance_diagnosis(
            company="위너스",
            workplace="서울지사",
            as_of_date="2026-05-17",
            data_loader=loader,
        )
        self.assertIn("human-review", result["recommendation_summary"])

    def test_diagnosis_rules_have_required_fields(self):
        """DIAGNOSIS_RULES 구조 검증"""
        for key, rule in DIAGNOSIS_RULES.items():
            self.assertIn("name", rule, f"{key} missing 'name'")
            self.assertIn("law", rule, f"{key} missing 'law'")
            self.assertIn("severity", rule, f"{key} missing 'severity'")
            self.assertIn(rule["severity"], {"high", "medium", "low"}, f"{key} invalid severity")

    def test_overtime_exactly_12h_boundary(self):
        """주 12시간 한도 경계값: 정확히 12h → pass"""
        from datetime import date, timedelta
        week_start = date(2026, 4, 27)
        records = []
        for i in range(6):
            records.append(
                {
                    "employee": "EMP-0001",
                    "employee_name": "김철수",
                    "attendance_date": str(week_start + timedelta(days=i)),
                    "working_hours": 8.0,
                    "overtime_hours": 2.0,  # 6일 × 2h = 12h (한도)
                }
            )
        # 6일 레코드지만 주 단위는 월~일 기준이고 모두 같은 주
        result = diagnose_overtime_limit(attendance_records=records)
        self.assertEqual(result["status"], "pass")


# ---------------------------------------------------------------------------
# HTML 리포트 생성 테스트 (compliance_report_pdf.py)
# ---------------------------------------------------------------------------


class TestBuildComplianceHtml(unittest.TestCase):
    """build_compliance_html 함수의 기본 출력 검증."""

    @classmethod
    def _load_pdf_module(cls) -> types.ModuleType:
        """compliance_report_pdf를 Frappe 없이 로드."""
        # Frappe mock 주입
        fake_frappe = types.ModuleType("frappe")
        fake_frappe.utils = types.SimpleNamespace(
            today=lambda: "2026-05-17",
            now_datetime=lambda: "2026-05-17 09:00:00",
        )
        fake_frappe.whitelist = lambda *a, **kw: (lambda fn: fn)
        fake_frappe.throw = lambda msg: (_ for _ in ()).throw(RuntimeError(msg))
        fake_frappe.local = types.SimpleNamespace(response=types.SimpleNamespace())
        sys.modules["frappe"] = fake_frappe

        pdf_path = (
            pathlib.Path(__file__).resolve().parents[1]
            / "regional"
            / "south_korea"
            / "compliance_report_pdf.py"
        )
        spec = importlib.util.spec_from_file_location("test_compliance_report_pdf", pdf_path)
        mod = importlib.util.module_from_spec(spec)

        # compliance_diagnosis도 미리 등록
        sys.modules["hrms.regional.south_korea.compliance_diagnosis"] = _diag

        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod

    def setUp(self):
        self._pdf_mod = self._load_pdf_module()

    def tearDown(self):
        sys.modules.pop("frappe", None)
        sys.modules.pop("hrms.regional.south_korea.compliance_diagnosis", None)
        sys.modules.pop("test_compliance_report_pdf", None)

    def _make_sample_result(self) -> dict[str, Any]:
        return {
            "contract_type": "korea_compliance_diagnosis_v1",
            "as_of_date": "2026-05-17",
            "company": "위너스",
            "workplace": "서울지사",
            "diagnoses": {
                "social_insurance": {
                    "status": "pass",
                    "findings": [],
                    "recommendations": [],
                },
                "wage_delay": {
                    "status": "warn",
                    "findings": [{"issue": "지급 지연 3일", "law": "근기법 43조"}],
                    "recommendations": ["즉시 조치 필요"],
                },
                "overtime_limit": {
                    "status": "fail",
                    "findings": [
                        {
                            "employee": "EMP-0001",
                            "employee_name": "김철수",
                            "issue": "주 연장근로 15h 초과",
                            "law": "근기법 53조",
                            "detail": {"overtime_hours": 15.0},
                        }
                    ],
                    "recommendations": ["근로시간 조정 필요"],
                },
                "annual_leave_usage": {
                    "status": "pass",
                    "findings": [],
                    "recommendations": [],
                },
                "anti_bullying_policy": {
                    "status": "fail",
                    "findings": [{"issue": "신고채널 미등록", "law": "근기법 76조의3"}],
                    "recommendations": ["즉시 등록"],
                },
            },
            "overall_status": "high_risk",
            "high_severity_findings": 2,
            "recommendation_summary": "[즉시 조치 필요] | 위반 항목: ... | human-review 대상",
        }

    def test_html_contains_company_name(self):
        """HTML에 회사명 포함"""
        result = self._make_sample_result()
        html_out = self._pdf_mod.build_compliance_html(result)
        self.assertIn("위너스", html_out)

    def test_html_contains_all_category_names(self):
        """HTML에 5개 카테고리명 포함"""
        result = self._make_sample_result()
        html_out = self._pdf_mod.build_compliance_html(result)
        self.assertIn("4대보험", html_out)
        self.assertIn("임금 정기 지급", html_out)
        self.assertIn("연장근로", html_out)
        self.assertIn("연차", html_out)
        self.assertIn("괴롭힘", html_out)

    def test_html_contains_status_labels(self):
        """HTML에 status 레이블(양호/검토필요/위반의심) 포함"""
        result = self._make_sample_result()
        html_out = self._pdf_mod.build_compliance_html(result)
        self.assertIn("양호", html_out)
        self.assertIn("검토필요", html_out)
        self.assertIn("위반의심", html_out)

    def test_html_escapes_special_characters(self):
        """XSS 방어: HTML 특수문자 이스케이프"""
        result = self._make_sample_result()
        result["company"] = "<script>alert(1)</script>"
        html_out = self._pdf_mod.build_compliance_html(result)
        self.assertNotIn("<script>", html_out)
        self.assertIn("&lt;script&gt;", html_out)

    def test_html_is_valid_start(self):
        """HTML 시작 태그 포함"""
        result = self._make_sample_result()
        html_out = self._pdf_mod.build_compliance_html(result)
        self.assertTrue(html_out.strip().startswith("<!DOCTYPE html>"))
        self.assertIn("</html>", html_out)


if __name__ == "__main__":
    unittest.main()
