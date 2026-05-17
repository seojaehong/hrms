"""2026년 한국 법정 공제 정밀 계산 테스트.

검증 케이스:
  1. 월 200만원: 국민연금 9만, 건강보험 70,900, 장기요양 9,180, 고용 18,000, 소득세 ~5만, 지방세 약 5,000
  2. 월 500만원: 모든 항목 정확 검증
  3. 월 600만원: 국민연금 상한(5,950,000) 적용 확인
  4. 월 30만원: 국민연금 하한(380,000) 적용 확인

계산 기준:
  - 국민연금: 원단위 절사
  - 건강보험: 원단위 절사
  - 장기요양: 10원 단위 절사
  - 고용보험: 원단위 절사
  - 소득세: 간이세액표 원단위 절사
  - 지방세: 원단위 절사
"""

import importlib.util
import pathlib
import sys
import unittest

# framework-free import: statutory_2026 모듈 직접 로드
_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "hrms"
    / "regional"
    / "south_korea"
    / "statutory_2026.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("statutory_2026", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load_module()


class TestPension(unittest.TestCase):
    """국민연금 계산 테스트."""

    def test_200만원_기본(self):
        result = _mod.calculate_pension(2_000_000)
        # 2,000,000 × 4.5% = 90,000
        self.assertEqual(result["employee"], 90_000)
        self.assertEqual(result["employer"], 90_000)
        self.assertEqual(result["base"], 2_000_000)

    def test_500만원(self):
        result = _mod.calculate_pension(5_000_000)
        # 5,000,000 × 4.5% = 225,000
        self.assertEqual(result["employee"], 225_000)
        self.assertEqual(result["employer"], 225_000)
        self.assertEqual(result["base"], 5_000_000)

    def test_600만원_상한_5950000_적용(self):
        result = _mod.calculate_pension(6_000_000)
        # 상한 5,950,000 적용: 5,950,000 × 4.5% = 267,750
        self.assertEqual(result["base"], 5_950_000)
        self.assertEqual(result["employee"], 267_750)
        self.assertEqual(result["employer"], 267_750)

    def test_30만원_하한_380000_적용(self):
        result = _mod.calculate_pension(300_000)
        # 하한 380,000 적용: 380,000 × 4.5% = 17,100
        self.assertEqual(result["base"], 380_000)
        self.assertEqual(result["employee"], 17_100)
        self.assertEqual(result["employer"], 17_100)

    def test_상한_경계값(self):
        # 정확히 상한과 같을 때 — 클리핑 없음
        result = _mod.calculate_pension(5_950_000)
        self.assertEqual(result["base"], 5_950_000)
        self.assertEqual(result["employee"], 267_750)

    def test_하한_경계값(self):
        result = _mod.calculate_pension(380_000)
        self.assertEqual(result["base"], 380_000)
        self.assertEqual(result["employee"], 17_100)

    def test_절사_검증(self):
        # 기준소득이 절사가 발생하는 값: 1,111,111 × 0.045 = 50,000.0 → 50,000 (딱 떨어짐)
        # 499,999 × 0.045 = 22,499.955 → int = 22,499
        result = _mod.calculate_pension(499_999)
        self.assertEqual(result["employee"], 22_499)


class TestHealthInsurance(unittest.TestCase):
    """건강보험 + 장기요양보험 테스트."""

    def test_200만원(self):
        result = _mod.calculate_health_insurance(2_000_000)
        # 건강보험: 2,000,000 × 0.03545 = 70,900
        self.assertEqual(result["health_employee"], 70_900)
        self.assertEqual(result["health_employer"], 70_900)
        # 장기요양: 70,900 × 0.1295 = 9,181.55 → 10원 절사 = 9,180
        self.assertEqual(result["longterm_care_employee"], 9_180)
        self.assertEqual(result["longterm_care_employer"], 9_180)
        # 근로자 합계: 70,900 + 9,180 = 80,080
        self.assertEqual(result["total_employee"], 80_080)

    def test_500만원(self):
        result = _mod.calculate_health_insurance(5_000_000)
        # 건강보험: 5,000,000 × 0.03545 = 177,250
        self.assertEqual(result["health_employee"], 177_250)
        # 장기요양: 177,250 × 0.1295 = 22,953.875 → 10원 절사 = 22,950
        self.assertEqual(result["longterm_care_employee"], 22_950)
        self.assertEqual(result["total_employee"], 177_250 + 22_950)

    def test_600만원(self):
        result = _mod.calculate_health_insurance(6_000_000)
        # 건강보험: 6,000,000 × 0.03545 = 212,700
        self.assertEqual(result["health_employee"], 212_700)
        # 장기요양: 212,700 × 0.1295 = 27,544.65 → 10원 절사 = 27,540
        self.assertEqual(result["longterm_care_employee"], 27_540)

    def test_30만원(self):
        result = _mod.calculate_health_insurance(300_000)
        # 건강보험: 300,000 × 0.03545 = 10,635.0
        self.assertEqual(result["health_employee"], 10_635)
        # 장기요양: 10,635 × 0.1295 = 1,377.2325 → 10원 절사 = 1,370
        self.assertEqual(result["longterm_care_employee"], 1_370)

    def test_장기요양_10원절사(self):
        # 100,000 × 0.03545 = 3,545 → 3,545 × 0.1295 = 459.0775 → 450
        result = _mod.calculate_health_insurance(100_000)
        self.assertEqual(result["health_employee"], 3_545)
        self.assertEqual(result["longterm_care_employee"], 450)


class TestEmploymentInsurance(unittest.TestCase):
    """고용보험 테스트."""

    def test_200만원_small(self):
        result = _mod.calculate_employment_insurance(2_000_000, "small")
        # 근로자: 2,000,000 × 0.009 = 18,000
        self.assertEqual(result["employee"], 18_000)
        # 사업주 실업급여: 18,000
        self.assertEqual(result["employer_unemployment"], 18_000)
        # 사업주 고용안정(small): 2,000,000 × 0.0025 = 5,000
        self.assertEqual(result["employer_stability"], 5_000)
        self.assertEqual(result["employer_total"], 23_000)

    def test_500만원_medium(self):
        result = _mod.calculate_employment_insurance(5_000_000, "medium")
        self.assertEqual(result["employee"], 45_000)
        self.assertEqual(result["employer_unemployment"], 45_000)
        # 사업주 고용안정(medium): 5,000,000 × 0.0045 = 22,500
        self.assertEqual(result["employer_stability"], 22_500)

    def test_large_사업장(self):
        result = _mod.calculate_employment_insurance(5_000_000, "large")
        # 고용안정(large): 5,000,000 × 0.0065 = 32,500
        self.assertEqual(result["employer_stability"], 32_500)

    def test_잘못된_사업장_크기(self):
        with self.assertRaises(ValueError):
            _mod.calculate_employment_insurance(2_000_000, "gigantic")

    def test_30만원(self):
        result = _mod.calculate_employment_insurance(300_000, "small")
        # 300,000 × 0.009 = 2,700
        self.assertEqual(result["employee"], 2_700)


class TestIndustrialAccidentInsurance(unittest.TestCase):
    """산재보험 테스트."""

    def test_근로자_부담없음(self):
        result = _mod.calculate_industrial_accident_insurance(2_000_000)
        self.assertEqual(result["employee"], 0)

    def test_200만원_평균요율(self):
        result = _mod.calculate_industrial_accident_insurance(2_000_000, 0.0143)
        # 2,000,000 × 0.0143 = 28,600
        self.assertEqual(result["employer"], 28_600)

    def test_500만원(self):
        result = _mod.calculate_industrial_accident_insurance(5_000_000, 0.0143)
        # 5,000,000 × 0.0143 = 71,500
        self.assertEqual(result["employer"], 71_500)

    def test_업종별_요율(self):
        # 건설업 평균 3.5% 가정
        result = _mod.calculate_industrial_accident_insurance(3_000_000, 0.035)
        # 3,000,000 × 0.035 = 105,000
        self.assertEqual(result["employer"], 105_000)


class TestIncomeTax(unittest.TestCase):
    """소득세 (간이세액표) 테스트."""

    def _get_table_tax(self, monthly_income: float, dependents: int = 1) -> int:
        """JSON 간이세액표 기반 소득세 조회."""
        result = _mod.calculate_income_tax(monthly_income, dependents=dependents)
        return result["income_tax"]

    def test_200만원_부양1_표기반(self):
        result = _mod.calculate_income_tax(2_000_000, dependents=1)
        # 간이세액표 2,000,000~2,500,000 구간 부양1: 54,970
        self.assertEqual(result["income_tax"], 54_970)
        # 지방세: 54,970 × 0.1 = 5,497
        self.assertEqual(result["local_income_tax"], 5_497)

    def test_500만원_부양1(self):
        result = _mod.calculate_income_tax(5_000_000, dependents=1)
        # 5,000,000~5,500,000 구간 부양1: 358,400
        self.assertEqual(result["income_tax"], 358_400)
        # 지방세: 358,400 × 0.1 = 35,840
        self.assertEqual(result["local_income_tax"], 35_840)

    def test_비과세_이하_0원(self):
        # 1,060,000 미만은 0원
        result = _mod.calculate_income_tax(1_000_000, dependents=1)
        self.assertEqual(result["income_tax"], 0)
        self.assertEqual(result["local_income_tax"], 0)

    def test_부양가족_증가시_세액_감소(self):
        tax_dep1 = _mod.calculate_income_tax(3_000_000, dependents=1)["income_tax"]
        tax_dep3 = _mod.calculate_income_tax(3_000_000, dependents=3)["income_tax"]
        self.assertGreater(tax_dep1, tax_dep3)

    def test_세액_음수없음(self):
        # 높은 부양가족 수에서도 음수 세액 없음
        result = _mod.calculate_income_tax(1_200_000, dependents=7)
        self.assertGreaterEqual(result["income_tax"], 0)

    def test_fallback_작동(self):
        """simplified_table_data=None + 파일 없는 환경에서 fallback 작동."""
        # 임시로 테이블 로드를 비활성화하여 fallback 경로 검증
        import types
        original_load = _mod._load_income_tax_table
        _mod._load_income_tax_table = lambda: None
        try:
            result = _mod.calculate_income_tax(2_000_000, dependents=1)
            # fallback: 54,970
            self.assertEqual(result["source"], "fallback")
            self.assertEqual(result["income_tax"], 54_970)
        finally:
            _mod._load_income_tax_table = original_load

    def test_외부_테이블_전달(self):
        """simplified_table_data 직접 전달."""
        custom_table = {
            "brackets": [
                {
                    "income_from": 0,
                    "income_to": 10_000_000,
                    "by_dependents": {"1": 99_999}
                }
            ]
        }
        result = _mod.calculate_income_tax(
            3_000_000, dependents=1, simplified_table_data=custom_table
        )
        self.assertEqual(result["income_tax"], 99_999)
        self.assertEqual(result["source"], "table")

    def test_구간_중간소득_보간(self):
        """구간 내 중간 소득은 선형 보간으로 두 경계 사이 값이어야 함.

        2,000,000~2,500,000 구간: 54,970 ~ 95,700
        2,250,000 (중간): 비율=0.5 → 54,970 + 0.5×(95,700-54,970) = 54,970 + 20,365 = 75,335
        """
        result = _mod.calculate_income_tax(2_250_000, dependents=1)
        tax = result["income_tax"]
        # 보간값이 두 경계 세액 사이에 있어야 함
        self.assertGreater(tax, 54_970)
        self.assertLess(tax, 95_700)
        # 정확한 선형 보간: 54,970 + 0.5 × (95,700 - 54,970) = 75,335
        self.assertEqual(tax, 75_335)


class TestLocalIncomeTax(unittest.TestCase):
    """지방소득세 테스트."""

    def test_기본(self):
        # 50,000 × 0.1 = 5,000
        self.assertEqual(_mod.calculate_local_income_tax(50_000), 5_000)

    def test_절사(self):
        # 54,970 × 0.1 = 5,497.0 → 5,497
        self.assertEqual(_mod.calculate_local_income_tax(54_970), 5_497)

    def test_0원(self):
        self.assertEqual(_mod.calculate_local_income_tax(0), 0)


class TestCalculateAllStatutory(unittest.TestCase):
    """통합 계산 테스트 — calculate_all_statutory."""

    def test_200만원_전항목(self):
        result = _mod.calculate_all_statutory(
            monthly_base=2_000_000,
            dependents=1,
            company_size="small",
        )
        # 국민연금
        self.assertEqual(result["pension"]["employee"], 90_000)
        # 건강보험
        self.assertEqual(result["health"]["health_employee"], 70_900)
        # 장기요양
        self.assertEqual(result["health"]["longterm_care_employee"], 9_180)
        # 고용보험
        self.assertEqual(result["employment_insurance"]["employee"], 18_000)
        # 소득세
        self.assertEqual(result["income_tax"]["income_tax"], 54_970)
        # 지방세
        self.assertEqual(result["income_tax"]["local_income_tax"], 5_497)

        # 근로자 총 공제: 90,000 + 70,900 + 9,180 + 18,000 + 54,970 + 5,497 = 248,547
        expected_employee = 90_000 + 70_900 + 9_180 + 18_000 + 54_970 + 5_497
        self.assertEqual(result["summary"]["employee_total_deduction"], expected_employee)

    def test_500만원_전항목(self):
        result = _mod.calculate_all_statutory(
            monthly_base=5_000_000,
            dependents=1,
            company_size="small",
        )
        self.assertEqual(result["pension"]["employee"], 225_000)
        self.assertEqual(result["health"]["health_employee"], 177_250)
        self.assertEqual(result["health"]["longterm_care_employee"], 22_950)
        self.assertEqual(result["employment_insurance"]["employee"], 45_000)
        self.assertEqual(result["income_tax"]["income_tax"], 358_400)
        self.assertEqual(result["income_tax"]["local_income_tax"], 35_840)

        expected_employee = 225_000 + 177_250 + 22_950 + 45_000 + 358_400 + 35_840
        self.assertEqual(result["summary"]["employee_total_deduction"], expected_employee)

    def test_600만원_국민연금_상한_확인(self):
        result = _mod.calculate_all_statutory(
            monthly_base=6_000_000,
            dependents=1,
        )
        # 상한 5,950,000 적용 → 267,750 (270,000이 아님)
        self.assertEqual(result["pension"]["base"], 5_950_000)
        self.assertEqual(result["pension"]["employee"], 267_750)
        # 건강보험은 실제 6,000,000 기준
        self.assertEqual(result["health"]["health_employee"], 212_700)
        self.assertEqual(result["health"]["longterm_care_employee"], 27_540)

    def test_30만원_국민연금_하한_확인(self):
        result = _mod.calculate_all_statutory(
            monthly_base=300_000,
            dependents=1,
        )
        # 하한 380,000 적용 → 17,100 (13,500이 아님)
        self.assertEqual(result["pension"]["base"], 380_000)
        self.assertEqual(result["pension"]["employee"], 17_100)
        # 건강보험은 실제 300,000 기준
        self.assertEqual(result["health"]["health_employee"], 10_635)

    def test_monthly_taxable_income_별도지정(self):
        # 비과세 항목이 있는 경우: monthly_base 2,500,000 / 과세분 2,000,000
        result = _mod.calculate_all_statutory(
            monthly_base=2_500_000,
            monthly_taxable_income=2_000_000,
            dependents=1,
        )
        # 4대보험: 2,500,000 기준
        self.assertEqual(result["pension"]["base"], 2_500_000)
        self.assertEqual(result["pension"]["employee"], 112_500)
        # 소득세: 2,000,000 기준
        self.assertEqual(result["income_tax"]["income_tax"], 54_970)

    def test_사업주_부담_합계_포함(self):
        result = _mod.calculate_all_statutory(
            monthly_base=3_000_000,
            company_size="small",
        )
        # 사업주 합계: 국민연금 + 건강보험 + 고용보험 + 산재보험
        pension_employer = result["pension"]["employer"]
        health_employer = result["health"]["total_employer"]
        emp_employer = result["employment_insurance"]["employer_total"]
        accident_employer = result["industrial_accident"]["employer"]
        expected = pension_employer + health_employer + emp_employer + accident_employer
        self.assertEqual(result["summary"]["employer_total_contribution"], expected)

    def test_반환_구조_필드_존재(self):
        result = _mod.calculate_all_statutory(monthly_base=3_000_000)
        required_keys = {
            "monthly_base", "monthly_taxable_income",
            "pension", "health", "employment_insurance",
            "industrial_accident", "income_tax", "summary",
        }
        self.assertTrue(required_keys.issubset(result.keys()))

    def test_pension_총합(self):
        result = _mod.calculate_all_statutory(monthly_base=2_000_000)
        p = result["pension"]
        self.assertEqual(p["total"], p["employee"] + p["employer"])


class TestRateConstants(unittest.TestCase):
    """요율 상수 검증."""

    def test_국민연금_요율(self):
        self.assertAlmostEqual(_mod.PENSION_RATE_EMPLOYEE, 0.045)
        self.assertAlmostEqual(_mod.PENSION_RATE_EMPLOYER, 0.045)

    def test_건강보험_요율(self):
        self.assertAlmostEqual(_mod.HEALTH_RATE_EMPLOYEE, 0.03545)
        self.assertAlmostEqual(_mod.HEALTH_RATE_EMPLOYER, 0.03545)

    def test_장기요양_요율(self):
        self.assertAlmostEqual(_mod.LONGTERM_CARE_RATE, 0.1295)

    def test_고용보험_요율(self):
        self.assertAlmostEqual(_mod.EMPLOYMENT_INSURANCE_RATE_EMPLOYEE, 0.009)

    def test_국민연금_상하한(self):
        self.assertEqual(_mod.PENSION_MIN_BASE, 380_000)
        self.assertEqual(_mod.PENSION_MAX_BASE, 5_950_000)

    def test_지방세_요율(self):
        self.assertAlmostEqual(_mod.LOCAL_INCOME_TAX_RATE, 0.10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
