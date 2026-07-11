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
        # 2,000,000 × 4.75% = 95,000
        self.assertEqual(result["employee"], 95_000)
        self.assertEqual(result["employer"], 95_000)
        self.assertEqual(result["base"], 2_000_000)

    def test_500만원(self):
        result = _mod.calculate_pension(5_000_000)
        # 5,000,000 × 4.75% = 237,500
        self.assertEqual(result["employee"], 237_500)
        self.assertEqual(result["employer"], 237_500)
        self.assertEqual(result["base"], 5_000_000)

    def test_600만원_상한_5950000_적용(self):
        result = _mod.calculate_pension(6_000_000)
        # 상한 5,950,000 적용: 5,950,000 × 4.75% = 282,625
        self.assertEqual(result["base"], 5_950_000)
        self.assertEqual(result["employee"], 282_625)
        self.assertEqual(result["employer"], 282_625)

    def test_30만원_하한_380000_적용(self):
        result = _mod.calculate_pension(300_000)
        # 하한 380,000 적용: 380,000 × 4.75% = 18,050
        self.assertEqual(result["base"], 380_000)
        self.assertEqual(result["employee"], 18_050)
        self.assertEqual(result["employer"], 18_050)

    def test_상한_경계값(self):
        # 정확히 상한과 같을 때 — 클리핑 없음
        result = _mod.calculate_pension(5_950_000)
        self.assertEqual(result["base"], 5_950_000)
        self.assertEqual(result["employee"], 282_625)

    def test_하한_경계값(self):
        result = _mod.calculate_pension(380_000)
        self.assertEqual(result["base"], 380_000)
        self.assertEqual(result["employee"], 18_050)

    def test_절사_검증(self):
        # 기준소득이 절사가 발생하는 값: 1,111,111 × 0.0475 = 52,777.7725 → 52,777
        # 499,999 × 0.0475 = 23,749.9525 → int = 23,749
        result = _mod.calculate_pension(499_999)
        self.assertEqual(result["employee"], 23_749)


class TestHealthInsurance(unittest.TestCase):
    """건강보험 + 장기요양보험 테스트."""

    def test_200만원(self):
        result = _mod.calculate_health_insurance(2_000_000)
        # 건강보험: 2,000,000 × 0.03595 = 71,900
        self.assertEqual(result["health_employee"], 71_900)
        self.assertEqual(result["health_employer"], 71_900)
        # 장기요양: 71,900 × 0.1295 = 9,311.05 → 10원 절사 = 9,310
        self.assertEqual(result["longterm_care_employee"], 9_310)
        self.assertEqual(result["longterm_care_employer"], 9_310)
        # 근로자 합계: 71,900 + 9,310 = 81,210
        self.assertEqual(result["total_employee"], 81_210)

    def test_500만원(self):
        result = _mod.calculate_health_insurance(5_000_000)
        # 건강보험: 5,000,000 × 0.03595 = 179,750
        self.assertEqual(result["health_employee"], 179_750)
        # 장기요양: 179,750 × 0.1295 = 23,277.625 → 10원 절사 = 23,270
        self.assertEqual(result["longterm_care_employee"], 23_270)
        self.assertEqual(result["total_employee"], 179_750 + 23_270)

    def test_600만원(self):
        result = _mod.calculate_health_insurance(6_000_000)
        # 건강보험: 6,000,000 × 0.03595 = 215,700
        self.assertEqual(result["health_employee"], 215_700)
        # 장기요양: 215,700 × 0.1295 = 27,930.15 → 10원 절사 = 27,930
        self.assertEqual(result["longterm_care_employee"], 27_930)

    def test_30만원(self):
        result = _mod.calculate_health_insurance(300_000)
        # 건강보험: 300,000 × 0.03595 = 10,785.0
        self.assertEqual(result["health_employee"], 10_785)
        # 장기요양: 10,785 × 0.1295 = 1,396.6575 → 10원 절사 = 1,390
        self.assertEqual(result["longterm_care_employee"], 1_390)

    def test_장기요양_10원절사(self):
        # 100,000 × 0.03595 = 3,595 → 3,595 × 0.1295 = 465.5525 → 460
        result = _mod.calculate_health_insurance(100_000)
        self.assertEqual(result["health_employee"], 3_595)
        self.assertEqual(result["longterm_care_employee"], 460)


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
        self.assertEqual(result["pension"]["employee"], 95_000)
        # 건강보험
        self.assertEqual(result["health"]["health_employee"], 71_900)
        # 장기요양
        self.assertEqual(result["health"]["longterm_care_employee"], 9_310)
        # 고용보험
        self.assertEqual(result["employment_insurance"]["employee"], 18_000)
        # 소득세
        self.assertEqual(result["income_tax"]["income_tax"], 54_970)
        # 지방세
        self.assertEqual(result["income_tax"]["local_income_tax"], 5_497)

        # 근로자 총 공제: 90,000 + 70,900 + 9,180 + 18,000 + 54,970 + 5,497 = 248,547
        expected_employee = 95_000 + 71_900 + 9_310 + 18_000 + 54_970 + 5_497
        self.assertEqual(result["summary"]["employee_total_deduction"], expected_employee)

    def test_500만원_전항목(self):
        result = _mod.calculate_all_statutory(
            monthly_base=5_000_000,
            dependents=1,
            company_size="small",
        )
        self.assertEqual(result["pension"]["employee"], 237_500)
        self.assertEqual(result["health"]["health_employee"], 179_750)
        self.assertEqual(result["health"]["longterm_care_employee"], 23_270)
        self.assertEqual(result["employment_insurance"]["employee"], 45_000)
        self.assertEqual(result["income_tax"]["income_tax"], 358_400)
        self.assertEqual(result["income_tax"]["local_income_tax"], 35_840)

        expected_employee = 237_500 + 179_750 + 23_270 + 45_000 + 358_400 + 35_840
        self.assertEqual(result["summary"]["employee_total_deduction"], expected_employee)

    def test_600만원_국민연금_상한_확인(self):
        result = _mod.calculate_all_statutory(
            monthly_base=6_000_000,
            dependents=1,
        )
        # 상한 5,950,000 적용 → 267,750 (270,000이 아님)
        self.assertEqual(result["pension"]["base"], 5_950_000)
        self.assertEqual(result["pension"]["employee"], 282_625)
        # 건강보험은 실제 6,000,000 기준
        self.assertEqual(result["health"]["health_employee"], 215_700)
        self.assertEqual(result["health"]["longterm_care_employee"], 27_930)

    def test_30만원_국민연금_하한_확인(self):
        result = _mod.calculate_all_statutory(
            monthly_base=300_000,
            dependents=1,
        )
        # 하한 380,000 적용 → 17,100 (13,500이 아님)
        self.assertEqual(result["pension"]["base"], 380_000)
        self.assertEqual(result["pension"]["employee"], 18_050)
        # 건강보험은 실제 300,000 기준
        self.assertEqual(result["health"]["health_employee"], 10_785)

    def test_monthly_taxable_income_별도지정(self):
        # 비과세 항목이 있는 경우: monthly_base 2,500,000 / 과세분 2,000,000
        result = _mod.calculate_all_statutory(
            monthly_base=2_500_000,
            monthly_taxable_income=2_000_000,
            dependents=1,
        )
        # 4대보험: 2,500,000 기준
        self.assertEqual(result["pension"]["base"], 2_500_000)
        self.assertEqual(result["pension"]["employee"], 118_750)
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
        # 2026 연금개혁 단계인상: 각 4.75% (국민연금법 §88③ 개정, published 노드 국민연금요율_2026)
        self.assertAlmostEqual(_mod.PENSION_RATE_EMPLOYEE, 0.0475)
        self.assertAlmostEqual(_mod.PENSION_RATE_EMPLOYER, 0.0475)

    def test_건강보험_요율(self):
        # 2026 보험료율 7.19% (시행령 §44①, published 노드 건강보험요율_2026) → 근로자 3.595%
        self.assertAlmostEqual(_mod.HEALTH_RATE_EMPLOYEE, 0.03595)
        self.assertAlmostEqual(_mod.HEALTH_RATE_EMPLOYER, 0.03595)

    def test_장기요양_요율(self):
        self.assertAlmostEqual(_mod.LONGTERM_CARE_RATE, 0.1295)

    def test_고용보험_요율(self):
        self.assertAlmostEqual(_mod.EMPLOYMENT_INSURANCE_RATE_EMPLOYEE, 0.009)

    def test_국민연금_상하한(self):
        self.assertEqual(_mod.PENSION_MIN_BASE, 380_000)
        self.assertEqual(_mod.PENSION_MAX_BASE, 5_950_000)

    def test_지방세_요율(self):
        self.assertAlmostEqual(_mod.LOCAL_INCOME_TAX_RATE, 0.10)


class TestOntologyConsistency(unittest.TestCase):
    """엔진 상수 ↔ published 법정수치 노드 정합 가드 (2025 요율 잔존 사고 재발 방지)."""

    def _load_stat_ontology(self):
        path = _MODULE_PATH.parent / "ontology" / "statutory_ontology.py"
        spec = importlib.util.spec_from_file_location("statutory_ontology", path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def _published_value(self, node_id):
        wiki = _MODULE_PATH.resolve().parents[3] / "wiki" / "ontology"
        stat = self._load_stat_ontology()
        loader = stat._loader()
        nodes, _errors = loader.load_nodes(wiki, review_state="published")
        for node in nodes:
            fm = getattr(node, "frontmatter", None) or {}
            if str(fm.get("node_id") or getattr(node, "node_id", "")).strip() == node_id:
                return float(fm.get("value"))
        return None

    def test_pension_rate_matches_published_node(self):
        node_val = self._published_value("국민연금요율_2026")
        self.assertIsNotNone(node_val, "국민연금요율_2026 published 노드가 없음")
        self.assertAlmostEqual(_mod.PENSION_RATE_EMPLOYEE, node_val, places=6)

    def test_health_rate_matches_published_node(self):
        node_val = self._published_value("건강보험요율_2026")
        self.assertIsNotNone(node_val, "건강보험요율_2026 published 노드가 없음")
        self.assertAlmostEqual(_mod.HEALTH_RATE_EMPLOYEE, round(node_val / 2, 6), places=6)


class TestResolveRates(unittest.TestCase):
    """요율 노드 우선 로드 (상수 폴백) — 북극성 4단계 seed-load."""

    def test_repo_wiki_returns_node_values(self):
        wiki = _MODULE_PATH.resolve().parents[3] / "wiki" / "ontology"
        rates = _mod.resolve_rates(wiki)
        self.assertAlmostEqual(rates["pension_employee"], 0.0475)
        self.assertAlmostEqual(rates["health_employee"], round(0.0719 / 2, 6))
        self.assertEqual(rates["source"], "ontology")

    def test_no_wiki_falls_back_to_constants(self):
        rates = _mod.resolve_rates(None)
        self.assertAlmostEqual(rates["pension_employee"], _mod.PENSION_RATE_EMPLOYEE)
        self.assertAlmostEqual(rates["health_employee"], _mod.HEALTH_RATE_EMPLOYEE)
        self.assertEqual(rates["source"], "constants")

    def test_empty_wiki_falls_back(self):
        import tempfile

        rates = _mod.resolve_rates(pathlib.Path(tempfile.mkdtemp()))
        self.assertEqual(rates["source"], "constants")


if __name__ == "__main__":
    unittest.main(verbosity=2)
