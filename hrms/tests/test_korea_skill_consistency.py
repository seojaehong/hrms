# -*- coding: utf-8 -*-
"""개인 급여 스킬 문서 규칙 ↔ Korea HRMS 엔진 정합성 스위트.

목적: `~/.claude/skills/` 아래 개인 스킬 문서(읽기 전용, 런타임 read 금지 — 규칙을
테스트에 독립 구현으로 고정하고 출처만 주석으로 추적)에 굳어진 급여 실무 규칙과
`hrms/regional/south_korea/*.py` 엔진 함수의 계산 결과를 대조한다.

이 스위트가 다루는 것: "개인 스킬 문서 규칙 vs 엔진" 관점 전용.
이미 있는 정합 가드(TestOntologyConsistency @ test_korea_statutory_2026.py,
test_korea_rate_single_source.py — 모듈 간 요율 하드코딩 가드)와 중복 검증하지 않는다.

불일치 표현 방식 (Task 2 브리프 Global Constraint 1):
  스킬↔엔진 불일치 발견 시 expectedFailure/skip 금지. 대신 "불일치 기록 테스트"로
  표현한다 — 스킬값과 엔진값을 모두 주석/변수로 명시한 채 **현재 엔진값을 assert**한다.
  (엔진 로직 변경은 이 태스크 범위 밖 — 노무사 판단 사항, docs/korea_hrms/payroll-skills-bridge.md
  §1 표 참고.)

출처: docs/korea_hrms/payroll-skills-bridge.md §1, .superpowers/sdd/task-1-report.md,
      .superpowers/sdd/research-official-rates.md (공식 출처 판정 기준)
"""

import importlib.util
import pathlib
import unittest

_SK = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SK / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_daily = _load("daily_worker")
_hourly = _load("hourly_wage")
_severance = _load("severance_pay")
_stat = _load("statutory_2026")


# =============================================================================
# 1. 일용직 결정세액
#    스킬 출처: ~/.claude/skills/일용직세금/SKILL.md §2 (일용근로소득세 계산)
#    스킬 공식: 과세표준 = MAX(일급 − 150,000, 0); 결정세액 = 과세표준 × 2.7%
#               (분리과세 6% × (1 − 세액공제 55%))
#    공식 출처: research-official-rates.md 항목6 — 국세청 nts.go.kr 일용근로소득 안내
#               (일당 200,000원, 5일 예시: (200,000−150,000)×6%×45%=1,350원/일 — 일치 확인)
# =============================================================================
class TestDailyWorkerDecidedTax(unittest.TestCase):
    def _skill_daily_tax(self, daily_wage: float) -> int:
        """스킬 공식의 독립 구현(엔진 미참조). 국세청 예시와 동일 공식."""
        taxable_base = max(0.0, daily_wage - 150_000)
        return int(taxable_base * 0.027)  # 1원 단위(스킬은 절사 방식 명시 안 함, 국세청 예시 정수)

    def test_일급_200000원_결정세액_1350원(self):
        # 국세청 예시와 동일: 과세표준 50,000 × 2.7% = 1,350
        skill_value = self._skill_daily_tax(200_000)
        self.assertEqual(skill_value, 1_350)

        result = _daily.calculate_daily_worker_payroll(daily_wage=200_000, days_worked=1)
        self.assertEqual(result["income_tax_per_day"], 1_350.0)
        # 엔진 vs 스킬 일치 (docs §1 "일치(요율)" — 이 예시는 10원 배수라 절사쟁점 미발생)
        self.assertEqual(result["income_tax_per_day"], skill_value)

    def test_일급_187000원_이하_1일_소액부징수_0원(self):
        # 187,000원 이하 → 스킬·엔진 모두 그 날 세액 0 (docs §1 "일치" 구간)
        result = _daily.calculate_daily_worker_payroll(daily_wage=187_000, days_worked=1)
        self.assertEqual(result["income_tax_per_day"], 0.0)
        self.assertEqual(result["income_tax_total"], 0.0)

    def test_일급_160000원_4일_합산_스킬규칙이면_과세_엔진은_0원_불일치기록(self):
        """불일치 기록 테스트 (docs §1 "소액부징수 판단 단위" 불일치).

        스킬 규칙(~/.claude/skills/일용직세금/SKILL.md §2): 원천징수세액을
        신고근무일수만큼 **합산**한 값이 1,000원 미만이면 소득세 0 — 즉 합산 후 판단.
        일급 160,000원(과세표준 10,000 × 2.7% = 270원/일) × 4일 합산 = 1,080원 ≥ 1,000원
        → 스킬 규칙이면 4일치 과세(1,080원, 10원 절사 시 1,080원 그대로).

        엔진(daily_worker.py:_calc_daily_income_tax): 일급 ≤ 187,000원이면 그 날 세액을
        **무조건 0**으로 처리(일급 단위 판단, 합산 판단 아님) → 4일 모두 0원, 총액도 0원.

        노무사 판단 필요(Task 1 인계). 엔진 로직 변경 금지 — 현재 엔진값만 assert.
        """
        skill_expected_if_summed = 270 * 4  # = 1,080원 (스킬 규칙이라면 과세)
        self.assertEqual(skill_expected_if_summed, 1_080)

        result = _daily.calculate_daily_worker_payroll(daily_wage=160_000, days_worked=4)
        # 현재 엔진값: 일급 160,000 ≤ 187,000 → 항상 0 (스킬 규칙과 다름, 기록만)
        self.assertEqual(result["income_tax_per_day"], 0.0)
        self.assertEqual(result["income_tax_total"], 0.0)
        self.assertNotEqual(result["income_tax_total"], skill_expected_if_summed)


# =============================================================================
# 2. 일용직 지방소득세 · 고용보험 — 10원 절사 규칙
#    스킬 출처: ~/.claude/skills/일용직세금/SKILL.md §2 (지방소득세 = ROUNDDOWN(소득세×10%, -1))
#    공식 출처: research-official-rates.md 항목6 (지방소득세는 소득세의 10%, 10원 미만 절사 실무)
# =============================================================================
class TestDailyWorkerLocalTaxRounding(unittest.TestCase):
    def _skill_local_tax_floor10(self, income_tax_total: float) -> int:
        """스킬 공식 독립 구현: ROUNDDOWN(소득세총액 × 10%, -1)."""
        raw = income_tax_total * 0.10
        return int(raw // 10) * 10

    def test_지방소득세_10원_절사_스킬과_엔진_일치(self):
        # 일급 250,000원, 3일: 과세표준(250,000-150,000)*0.027=2,700 (10원 배수)
        result = _daily.calculate_daily_worker_payroll(daily_wage=250_000, days_worked=3)
        income_tax_total = result["income_tax_total"]
        skill_local = self._skill_local_tax_floor10(income_tax_total)
        self.assertEqual(result["local_income_tax_total"], float(skill_local))

    def test_지방소득세_절사_비10원배수_케이스(self):
        # 일급 173,700원: 과세표준 23,700 × 2.7% = 639.9 → 엔진은 원단위 round 후 10원절사(640→640)
        result = _daily.calculate_daily_worker_payroll(daily_wage=173_700, days_worked=1)
        # 일별 세액 자체가 이미 10원 절사됨(640) → 지방세 = 640*10%=64 → 10원 절사 60
        expected_local = self._skill_local_tax_floor10(result["income_tax_total"])
        self.assertEqual(result["local_income_tax_total"], float(expected_local))

    def test_고용보험_금액계산_엔진미구현_bool만_반환(self):
        """docs §1 "엔진 미구현" 항목 — 고용보험 0.9% 금액 계산 없음, bool만 존재.

        스킬 규칙(~/.claude/skills/일용직세금/SKILL.md §2):
            고용보험 = ROUNDDOWN(총지급액 × 0.9%, -1)
        엔진(daily_worker.py): applies_employment_insurance는 bool(항상 True)만 반환하고
        금액 계산 필드가 없다. 존재성만 기록(구현 추가는 이 태스크 범위 밖).
        """
        result = _daily.calculate_daily_worker_payroll(daily_wage=200_000, days_worked=1)
        self.assertIn("applies_employment_insurance", result)
        self.assertIsInstance(result["applies_employment_insurance"], bool)
        self.assertNotIn("employment_insurance_amount", result)

        # 요율 0.9%는 statutory_2026에 공용 상수로 존재(엔진이 daily_worker에서 호출하지 않을 뿐)
        self.assertAlmostEqual(_stat.EMPLOYMENT_INSURANCE_RATE_EMPLOYEE, 0.009)
        # round()로 부동소수점 오차 제거 후 10원 절사(엔진 _floor10과 동일 관례)
        raw = round(200_000 * 0.009)  # ROUNDDOWN(1,800, -1) = 1,800
        skill_expected_amount = (raw // 10) * 10
        self.assertEqual(skill_expected_amount, 1_800)


# =============================================================================
# 3. 주휴수당
#    스킬 출처: ~/.claude/skills/급여관리/skill.md, ~/.claude/skills/급여검증/skill.md
#    스킬 공식: 주 15h 이상 + 개근 시 유급시간 = min(주소정근로시간, 40) ÷ 40 × 8
#    공식 출처: 근로기준법 §55, 시행령 §30, §18③ (research-official-rates.md는 4대보험/세율
#               중심이라 이 항목은 법령 원문이 1차 출처 — hourly_wage.py 상단 docstring 인용과 동일)
# =============================================================================
class TestWeeklyHolidayAllowance(unittest.TestCase):
    def test_주20시간_개근_시급10320_유급4시간_41280원(self):
        skill_paid_hours = min(20, 40) / 40 * 8  # = 4
        self.assertEqual(skill_paid_hours, 4)
        skill_amount = round(skill_paid_hours * 10_320)  # = 41,280

        engine_amount = _hourly.weekly_holiday_allowance(
            contracted_weekly_hours=20, hourly_rate=10_320, perfect_attendance=True
        )
        self.assertEqual(engine_amount, 41_280)
        self.assertEqual(engine_amount, skill_amount)

    def test_주14시간_주휴발생요건미달_0원(self):
        # 근로기준법 §18③: 주 15h 미만은 주휴 발생 자체가 없음 — 스킬·엔진 공통
        engine_amount = _hourly.weekly_holiday_allowance(
            contracted_weekly_hours=14, hourly_rate=10_320, perfect_attendance=True
        )
        self.assertEqual(engine_amount, 0)


# =============================================================================
# 4. 퇴직금 — 평균임금 vs 통상임금 MAX
#    스킬 출처: ~/.claude/skills/퇴직정산/skill.md §퇴직금 계산
#    스킬 공식: 퇴직금 = MAX(평균임금, 통상임금) × 30일 × (재직일수/365)
#    공식 출처: 근로자퇴직급여보장법 §8, 근로기준법 §2⑥ (severance_pay.py 상단 인용과 동일 1차 출처)
# =============================================================================
class TestSeverancePay(unittest.TestCase):
    def test_평균임금이_통상보다_높으면_평균사용_300만원(self):
        import datetime as dt

        result = _severance.calculate_severance_pay(
            hire_date=dt.date(2023, 1, 1),
            severance_date=dt.date(2024, 1, 1),  # 재직 365일 (2023년은 평년)
            average_wage_per_day=100_000,
            ordinary_wage_per_day=90_000,
        )
        # 스킬 공식: MAX(100,000, 90,000) × 30 × (365/365) = 3,000,000
        self.assertEqual(result["wage_used_reason"], "average")
        self.assertEqual(result["severance_pay_amount"], 3_000_000.0)

    def test_통상임금이_평균보다_높으면_통상으로_대체(self):
        import datetime as dt

        result = _severance.calculate_severance_pay(
            hire_date=dt.date(2023, 1, 1),
            severance_date=dt.date(2024, 1, 1),
            average_wage_per_day=80_000,
            ordinary_wage_per_day=90_000,
        )
        # 스킬 공식: MAX(80,000, 90,000) = 90,000 사용 → 90,000 × 30 = 2,700,000
        self.assertEqual(result["wage_used_reason"], "ordinary")
        self.assertEqual(result["severance_pay_amount"], 2_700_000.0)


# =============================================================================
# 5. 4대보험 요율 — 스킬 관점 1케이스만 (test_korea_rate_single_source.py와 중복 회피)
#    스킬 출처: ~/.claude/skills/4대보험신고/skill.md, ~/.claude/skills/급여검증/skill.md(검증17/18)
#    스킬 확정값: 국민연금 4.75%, 건강보험 3.595%, 고용보험 0.9%
#    공식 출처: research-official-rates.md 항목1(국민연금)·3(건강보험)·5(고용보험) — mohw.go.kr 등
# =============================================================================
class TestStatutoryRatesSkillView(unittest.TestCase):
    def test_스킬_확정값과_엔진_상수_일치(self):
        self.assertAlmostEqual(_stat.PENSION_RATE_EMPLOYEE, 0.0475)
        self.assertAlmostEqual(_stat.HEALTH_RATE_EMPLOYEE, 0.03595)
        self.assertAlmostEqual(_stat.EMPLOYMENT_INSURANCE_RATE_EMPLOYEE, 0.009)


# =============================================================================
# 6. 통상시급 = 기본급 ÷ 209
#    스킬 출처: ~/.claude/skills/퇴직정산/skill.md (통상시급=기본급÷209, 포괄임금 실무 규칙)
#    공식 출처: 근로기준법 시행령 §6 별표(월 소정근로시간 209h 산정 근거,
#               주40h+유급주휴 8h 기준 월평균: (40+8)×365/7/12 ≈ 209)
#    엔진 상태(docs §1 "엔진 미구현"): south_korea 모듈 전체에 209 나눗셈 계산 코드 없음
#    (Task 1: grep 209 → 데이터 JSON만 매칭). 엔진 대응 함수가 없으므로 이 스위트에
#    순수 참조 구현만 두고, 향후 엔진 구현 시 이 값과 대조할 지점으로 고정한다.
# =============================================================================
class TestOrdinaryHourlyWageReference(unittest.TestCase):
    def _skill_ordinary_hourly_wage(self, monthly_base: float) -> float:
        """스킬 공식의 순수 참조 구현 (엔진에 대응 함수 없음 — 문서 규칙 고정용)."""
        return monthly_base / 209

    def test_기본급_2156880원_통상시급_10320원(self):
        # 2026 최저임금 월환산(209h) 예시: 2,156,880 ÷ 209 = 10,320 (정확히 최저임금 시급)
        self.assertAlmostEqual(self._skill_ordinary_hourly_wage(2_156_880), 10_320.0)

    def test_엔진에_대응함수_없음_확인(self):
        # daily_worker/hourly_wage/severance_pay/statutory_2026 어디에도 209 나눗셈 함수 없음
        for mod in (_daily, _hourly, _severance, _stat):
            names = [n for n in dir(mod) if "209" in n or "ordinary_hourly" in n.lower()]
            self.assertEqual(names, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
