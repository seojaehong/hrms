"""NET(실수령액) → GROSS(세전 총액) 역산 코어 테스트.

frappe 미설치 환경에서 직접 실행:
    python3 hrms/tests/test_korea_net_to_gross.py

검증 원칙: 정방향 공제 엔진(statutory_2026)으로 net을 만든 뒤 역산이
그 net을 만족하는 최소 gross를 찾는지 round-trip으로 확인한다.
"""

import importlib.util
import pathlib
import sys
import unittest

_HERE = pathlib.Path(__file__).resolve()
_SK_DIR = _HERE.parents[1] / "regional" / "south_korea"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_test_{name}", _SK_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load("net_to_gross")
stat = _load("statutory_2026")


def _forward_net(gross: int, *, non_taxable: int = 0, dependents: int = 1) -> int:
    """정방향: 엔진 규칙 그대로 근로자 공제 합산 후 net 산출 (검증용 독립 구현)."""
    base = max(0, gross - non_taxable)
    if base <= 0:
        return gross
    pension = stat.calculate_pension(base)["employee"]
    health = stat.calculate_health_insurance(base)
    employment = stat.calculate_employment_insurance(base)["employee"]
    tax = stat.calculate_income_tax(base, dependents=dependents)
    total = (
        pension
        + health["health_employee"]
        + health["longterm_care_employee"]
        + employment
        + tax["income_tax"]
        + tax["local_income_tax"]
    )
    return gross - total


class TestReverseNetToGross(unittest.TestCase):
    def test_round_trip_basic(self):
        """gross 3,000,000 정방향 net → 역산하면 같은 net을 만족하는 gross."""
        gross = 3_000_000
        net = _forward_net(gross)
        result = core.reverse_net_to_gross(net)
        self.assertEqual(result["achieved_net"], net)
        self.assertTrue(result["exact"])
        # 역산 gross의 정방향 net이 target과 일치해야 한다 (자기일관성)
        self.assertEqual(_forward_net(result["gross"]), net)
        # 최소성: gross-1은 target 미달
        self.assertLess(_forward_net(result["gross"] - 1), net)

    def test_round_trip_with_non_taxable(self):
        """비과세 200,000 포함 케이스 round-trip."""
        gross = 2_800_000
        non_tax = 200_000
        net = _forward_net(gross, non_taxable=non_tax)
        result = core.reverse_net_to_gross(net, non_taxable=non_tax)
        self.assertEqual(
            _forward_net(result["gross"], non_taxable=non_tax), result["achieved_net"]
        )
        self.assertGreaterEqual(result["achieved_net"], net)

    def test_breakdown_consistency(self):
        """공제 내역 합계 == total, gross - total == achieved_net."""
        result = core.reverse_net_to_gross(3_000_000, non_taxable=200_000)
        d = result["deductions"]
        parts = (
            d["pension"]
            + d["health"]
            + d["longterm_care"]
            + d["employment"]
            + d["income_tax"]
            + d["local_income_tax"]
        )
        self.assertEqual(parts, d["total"])
        self.assertEqual(result["gross"] - d["total"], result["achieved_net"])

    def test_toggle_pension_off(self):
        """국민연금 제외(60세 이상 등) 시 pension=0, gross는 포함 시보다 작다."""
        on = core.reverse_net_to_gross(3_000_000)
        off = core.reverse_net_to_gross(3_000_000, include_pension=False)
        self.assertEqual(off["deductions"]["pension"], 0)
        self.assertLess(off["gross"], on["gross"])

    def test_toggle_employment_off(self):
        """고용보험 제외(65세 이상 등) 시 employment=0."""
        off = core.reverse_net_to_gross(3_000_000, include_employment=False)
        self.assertEqual(off["deductions"]["employment"], 0)

    def test_toggle_health_off_excludes_care(self):
        """건강보험 제외 시 장기요양도 함께 0 (건보 기반 산출이므로)."""
        off = core.reverse_net_to_gross(3_000_000, include_health=False)
        self.assertEqual(off["deductions"]["health"], 0)
        self.assertEqual(off["deductions"]["longterm_care"], 0)

    def test_pension_override(self):
        """수동 국민연금액(중도입사 등)이 그대로 공제에 반영."""
        result = core.reverse_net_to_gross(3_000_000, pension_override=123_450)
        self.assertEqual(result["deductions"]["pension"], 123_450)

    def test_dependents_reduce_tax(self):
        """부양가족 4명은 1명보다 소득세가 적어 gross가 작거나 같다."""
        one = core.reverse_net_to_gross(4_000_000, dependents=1)
        four = core.reverse_net_to_gross(4_000_000, dependents=4)
        self.assertLessEqual(four["gross"], one["gross"])
        self.assertLessEqual(
            four["deductions"]["income_tax"], one["deductions"]["income_tax"]
        )

    def test_monotonic_in_target(self):
        """target_net이 크면 gross도 크다."""
        low = core.reverse_net_to_gross(2_500_000)
        high = core.reverse_net_to_gross(3_500_000)
        self.assertLess(low["gross"], high["gross"])

    def test_invalid_target_rejected(self):
        with self.assertRaises(ValueError):
            core.reverse_net_to_gross(0)
        with self.assertRaises(ValueError):
            core.reverse_net_to_gross(-100)
        with self.assertRaises(ValueError):
            core.reverse_net_to_gross("abc")

    def test_negative_non_taxable_rejected(self):
        with self.assertRaises(ValueError):
            core.reverse_net_to_gross(3_000_000, non_taxable=-1)

    def test_result_types(self):
        """gross/achieved_net은 int (Frappe RPC 직렬화 안전)."""
        result = core.reverse_net_to_gross(3_000_000)
        self.assertIsInstance(result["gross"], int)
        self.assertIsInstance(result["achieved_net"], int)
        self.assertIsInstance(result["deductions"]["total"], int)


if __name__ == "__main__":
    unittest.main(verbosity=2)
