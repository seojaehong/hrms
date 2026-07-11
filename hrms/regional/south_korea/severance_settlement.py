# -*- coding: utf-8 -*-
"""퇴직정산 엔진 — 퇴직소득세·건보정산·퇴직금 통합 오케스트레이션. framework-free.

개인 스킬(`~/.claude/skills/퇴직정산/`, `~/.claude/skills/건보정산/`, 읽기 전용)의
검증된 실무 수식을 이식한다. 법령 대조: 소득세법 §48(퇴직소득공제), §55②(퇴직소득세율).

법적 근거
---------
- 소득세법 §48① 1호: 근속연수공제 (5년 이하/5~10년/10~20년/20년 초과 4구간)
- 소득세법 §48① 2호: 환산급여공제 (800만/7,000만/1억/3억 4구간)
- 소득세법 §48②: 퇴직소득금액이 근속연수공제액에 미달하면 그 금액을 공제액으로 함(과세표준 0)
- 소득세법 §55①: 종합소득 기본세율(누진세율표, 8단계) — 환산산출세액 계산에 사용
- 소득세법 §55②: 퇴직소득 산출세액 = (과세표준×기본세율) ÷ 12 × 근속연수
- 건강보험법 시행령 §44①, §4: 보수총액 정산(확정보험료) — 개인 스킬 「건보정산」 실무 규칙

반올림 규칙 (개인 스킬 명세 그대로 — 법령보다 스킬이 1차 근거)
---------------------------------------------------------
- 퇴직소득세: 10원 단위 **절사**(ROUNDDOWN, 올림 아님)
- 지방소득세: 소득세 × 10%, 10원 단위 절사
- 건보정산 확정보험료(건강/장기요양): 10원 단위 절사 후 납부월수 곱

근속연수 처리
--------------
소득세법 §48①: "1년 미만의 기간이 있는 경우에는 이를 1년으로 본다" → 근속연수 계산 시
1년 미만 잔여 기간은 올림(ceiling) 처리한다. 예: 4년 3개월(=4.25년) → 5년.

스타일: hourly_wage.py 참고 — 원 단위 확정 전까지 Decimal 유지, 4대보험 요율은
statutory_2026 단일소스에서 로드(연도별 하드코딩 혼재 사고 방지 — 검증18 대책).
frappe 의존 없음 → `python3 hrms/tests/test_korea_severance_settlement.py` 직접 실행 검증 가능.
"""

from __future__ import annotations

import importlib.util as _ilu
import pathlib as _pl
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal
from typing import Any


# ---------------------------------------------------------------------------
# 요율 단일소스 로딩 (statutory_2026) — foreign_worker.py / leave_of_absence.py 와 동일 패턴
# ---------------------------------------------------------------------------

def _load_statutory_2026():
    path = _pl.Path(__file__).resolve().parent / "statutory_2026.py"
    spec = _ilu.spec_from_file_location("korea_statutory_2026_for_severance_settlement", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_severance_pay():
    path = _pl.Path(__file__).resolve().parent / "severance_pay.py"
    spec = _ilu.spec_from_file_location("korea_severance_pay_for_settlement", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_hourly_wage():
    path = _pl.Path(__file__).resolve().parent / "hourly_wage.py"
    spec = _ilu.spec_from_file_location("korea_hourly_wage_for_settlement", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_STAT = _load_statutory_2026()
_SEVERANCE_PAY = _load_severance_pay()
_HOURLY_WAGE = _load_hourly_wage()

# 건강보험/장기요양 요율 — statutory_2026 단일소스(하드코딩 금지)
HEALTH_RATE_EMPLOYEE = Decimal(str(_STAT.HEALTH_RATE_EMPLOYEE))
LONGTERM_CARE_RATE = Decimal(str(_STAT.LONGTERM_CARE_RATE))
LOCAL_INCOME_TAX_RATE = Decimal(str(_STAT.LOCAL_INCOME_TAX_RATE))


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _dec(value: Any, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number, not bool")
    try:
        return Decimal(str(value))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{name} must be numeric: {value!r}") from exc


def _floor_won(value: Decimal) -> int:
    """원 단위 절사(버림)."""
    return int(value.to_integral_value(rounding=ROUND_DOWN))


def _floor10(value: Decimal) -> int:
    """10원 단위 절사(버림) — ROUNDDOWN(value, -1)."""
    return int((value / Decimal("10")).to_integral_value(rounding=ROUND_DOWN)) * 10


# ---------------------------------------------------------------------------
# 소득세법 §48①1호 근속연수공제표
# ---------------------------------------------------------------------------

def _service_year_deduction(years: Decimal) -> Decimal:
    """근속연수공제액 (소득세법 §48①1호).

    5년 이하: 100만원 × 근속연수
    5년 초과 10년 이하: 500만원 + 200만원 × (근속연수-5년)
    10년 초과 20년 이하: 1,500만원 + 250만원 × (근속연수-10년)
    20년 초과: 4,000만원 + 300만원 × (근속연수-20년)
    """
    if years <= 5:
        return Decimal("1000000") * years
    if years <= 10:
        return Decimal("5000000") + Decimal("2000000") * (years - Decimal("5"))
    if years <= 20:
        return Decimal("15000000") + Decimal("2500000") * (years - Decimal("10"))
    return Decimal("40000000") + Decimal("3000000") * (years - Decimal("20"))


# ---------------------------------------------------------------------------
# 소득세법 §48①2호 환산급여공제표
# ---------------------------------------------------------------------------

def _converted_wage_deduction(converted_wage: Decimal) -> Decimal:
    """환산급여공제액 (소득세법 §48①2호).

    800만원 이하: 환산급여의 100%
    800만원 초과 7,000만원 이하: 800만원 + 초과분×60%
    7,000만원 초과 1억원 이하: 4,520만원 + 초과분×55%
    1억원 초과 3억원 이하: 6,170만원 + 초과분×45%
    3억원 초과: 1억5,170만원 + 초과분×35%
    """
    if converted_wage <= Decimal("8000000"):
        return converted_wage
    if converted_wage <= Decimal("70000000"):
        return Decimal("8000000") + (converted_wage - Decimal("8000000")) * Decimal("0.6")
    if converted_wage <= Decimal("100000000"):
        return Decimal("45200000") + (converted_wage - Decimal("70000000")) * Decimal("0.55")
    if converted_wage <= Decimal("300000000"):
        return Decimal("61700000") + (converted_wage - Decimal("100000000")) * Decimal("0.45")
    return Decimal("151700000") + (converted_wage - Decimal("300000000")) * Decimal("0.35")


# ---------------------------------------------------------------------------
# 소득세법 §55① 종합소득 기본세율표(2026) — 누진공제 방식
# 세액 = 과세표준 × 세율 − 누진공제액
# ---------------------------------------------------------------------------

_TAX_BRACKETS: list[tuple[Decimal | None, Decimal, Decimal]] = [
    (Decimal("14000000"), Decimal("0.06"), Decimal("0")),
    (Decimal("50000000"), Decimal("0.15"), Decimal("1260000")),
    (Decimal("88000000"), Decimal("0.24"), Decimal("5760000")),
    (Decimal("150000000"), Decimal("0.35"), Decimal("15440000")),
    (Decimal("300000000"), Decimal("0.38"), Decimal("19940000")),
    (Decimal("500000000"), Decimal("0.40"), Decimal("25940000")),
    (Decimal("1000000000"), Decimal("0.42"), Decimal("35940000")),
    (None, Decimal("0.45"), Decimal("65940000")),
]


def _progressive_tax(tax_base: Decimal) -> Decimal:
    """기본세율 적용 산출세액 (소득세법 §55①)."""
    if tax_base <= 0:
        return Decimal("0")
    for upper, rate, cumulative_deduction in _TAX_BRACKETS:
        if upper is None or tax_base <= upper:
            tax = tax_base * rate - cumulative_deduction
            return tax if tax > 0 else Decimal("0")
    return Decimal("0")  # pragma: no cover — 방어적 (마지막 구간이 upper=None 이라 도달 불가)


# ---------------------------------------------------------------------------
# 공개 API 1: 퇴직소득세
# ---------------------------------------------------------------------------

def calculate_severance_income_tax(
    severance_pay: Any,
    service_years: Any,
) -> dict[str, Any]:
    """퇴직소득세 계산 (소득세법 §48, §55②).

    계산 순서: 근속연수공제 → 환산급여 → 환산급여공제 → 과세표준 →
    환산산출세액(기본세율) → 산출세액(÷12×근속연수) → 지방소득세(10%).

    Parameters
    ----------
    severance_pay:
        퇴직소득금액(퇴직금 등, 원).
    service_years:
        근속연수(실수, 예: 4.25 = 4년3개월). 1년 미만 잔여기간은 올림 처리(§48①).

    Returns
    -------
    dict with keys:
        severance_pay              float
        service_years              float  (입력 원값)
        service_years_rounded      int    (§48① 올림 적용 근속연수)
        service_year_deduction     float
        converted_wage             float  (환산급여)
        converted_wage_deduction   float
        tax_base                   float  (퇴직소득 과세표준)
        converted_calculated_tax   float  (환산산출세액)
        income_tax                 int    (퇴직소득세, 10원 절사)
        local_income_tax           int    (지방소득세, 10원 절사)
        total_tax                  int
        calculation_formula        str
    """
    pay = _dec(severance_pay, "severance_pay")
    if pay < 0:
        raise ValueError("severance_pay must be >= 0")

    years_raw = _dec(service_years, "service_years")
    if years_raw <= 0:
        raise ValueError("service_years must be > 0")

    # §48①: 1년 미만 잔여기간은 1년으로 본다 → 올림(ceiling), 최소 1년
    years = years_raw.to_integral_value(rounding=ROUND_CEILING)
    if years < 1:
        years = Decimal("1")

    service_deduction = _service_year_deduction(years)

    # §48②: 퇴직소득금액이 근속연수공제액에 미달 → 그 금액을 공제액으로 함(과세표준 0)
    income_after_service_deduction = pay - service_deduction
    if income_after_service_deduction <= 0:
        return {
            "severance_pay": float(pay),
            "service_years": float(years_raw),
            "service_years_rounded": int(years),
            "service_year_deduction": float(service_deduction),
            "converted_wage": 0.0,
            "converted_wage_deduction": 0.0,
            "tax_base": 0.0,
            "converted_calculated_tax": 0.0,
            "income_tax": 0,
            "local_income_tax": 0,
            "total_tax": 0,
            "calculation_formula": (
                f"퇴직소득 {pay:,.0f}원 <= 근속연수공제 {service_deduction:,.0f}원 "
                f"→ 과세표준 0 (소득세법 §48②)"
            ),
        }

    converted_wage = income_after_service_deduction * 12 / years
    converted_deduction = _converted_wage_deduction(converted_wage)
    tax_base = converted_wage - converted_deduction
    if tax_base < 0:
        tax_base = Decimal("0")

    converted_calculated_tax = _progressive_tax(tax_base)

    # §55②: 산출세액 = (환산산출세액 ÷ 12) × 근속연수
    calculated_tax = converted_calculated_tax / 12 * years

    income_tax = _floor10(calculated_tax)
    local_income_tax = _floor10(Decimal(income_tax) * LOCAL_INCOME_TAX_RATE)

    formula = (
        f"퇴직소득 {pay:,.0f}원 - 근속연수공제 {service_deduction:,.0f}원 = "
        f"{income_after_service_deduction:,.0f}원 → 환산급여 {converted_wage:,.2f}원 "
        f"- 환산급여공제 {converted_deduction:,.2f}원 = 과세표준 {tax_base:,.2f}원 "
        f"→ 환산산출세액 {converted_calculated_tax:,.2f}원 ÷ 12 × {years}년 = "
        f"{calculated_tax:,.2f}원 [10원 절사] → 소득세 {income_tax:,}원 "
        f"+ 지방소득세 {local_income_tax:,}원"
    )

    return {
        "severance_pay": float(pay),
        "service_years": float(years_raw),
        "service_years_rounded": int(years),
        "service_year_deduction": float(service_deduction),
        "converted_wage": float(converted_wage),
        "converted_wage_deduction": float(converted_deduction),
        "tax_base": float(tax_base),
        "converted_calculated_tax": float(converted_calculated_tax),
        "income_tax": income_tax,
        "local_income_tax": local_income_tax,
        "total_tax": income_tax + local_income_tax,
        "calculation_formula": formula,
    }


# ---------------------------------------------------------------------------
# 공개 API 2: 건보정산(퇴사월 보수총액 정산)
# ---------------------------------------------------------------------------

def reconcile_health_insurance_on_exit(
    *,
    monthly_remuneration: list[Any],
    paid_health_total: Any = 0,
    paid_longterm_care_total: Any = 0,
    mid_month_hire: bool = False,
) -> dict[str, Any]:
    """건강보험 보수총액 정산 (개인 스킬 「건보정산」).

    보수총액 정산 = (1~퇴사월 보수총액 기준 확정보험료) - 기납부 보험료.
    장기요양은 확정 건강보험료(10원 절사값) × 2026 환산율 13.1405%(statutory_2026 단일소스).

    Parameters
    ----------
    monthly_remuneration:
        산정 대상 각 월의 보수월액 리스트(1월~퇴사월, 또는 입사월~퇴사월).
    paid_health_total, paid_longterm_care_total:
        이미 납부(공제)된 건강보험/장기요양 누계.
    mid_month_hire:
        입사일이 1일이 아닌 중도입사이면 True → 납부월수 = 산정월수 - 1
        (입사월 미납, 개인 스킬 「건보정산」 §3-3 규칙).

    Returns
    -------
    dict with keys:
        calc_months                   int   (산정월수)
        paid_months                   int   (납부월수)
        total_remuneration            float
        average_monthly_remuneration  float
        monthly_health_insurance      int   (10원 절사)
        monthly_longterm_care         int   (10원 절사)
        determined_health_insurance   int   (확정보험료 = 월액 × 납부월수)
        determined_longterm_care      int
        paid_health_insurance         int
        paid_longterm_care            int
        health_insurance_settlement   int   (양수=추가납부, 음수=환급)
        longterm_care_settlement      int
        total_settlement              int
    """
    if not monthly_remuneration:
        raise ValueError("monthly_remuneration must not be empty")

    amounts = [_dec(v, "monthly_remuneration") for v in monthly_remuneration]
    total = sum(amounts, Decimal("0"))
    calc_months = len(amounts)

    paid_months = calc_months - 1 if mid_month_hire else calc_months
    if paid_months <= 0:
        raise ValueError("paid_months must be > 0 (mid_month_hire with only 1 calc month?)")

    average_monthly = total / calc_months

    # 확정 건강보험 월액: 10원 단위 절사 (개인 스킬 「건보정산」 §3-5)
    monthly_health = _floor10(average_monthly * HEALTH_RATE_EMPLOYEE)
    # 장기요양 월액: 확정 건강보험료(위 10원 절사값) × 환산율, 다시 10원 단위 절사
    monthly_longterm = _floor10(Decimal(monthly_health) * LONGTERM_CARE_RATE)

    determined_health = monthly_health * paid_months
    determined_longterm = monthly_longterm * paid_months

    paid_health = int(_dec(paid_health_total, "paid_health_total"))
    paid_longterm = int(_dec(paid_longterm_care_total, "paid_longterm_care_total"))

    health_settlement = determined_health - paid_health
    longterm_settlement = determined_longterm - paid_longterm

    return {
        "calc_months": calc_months,
        "paid_months": paid_months,
        "total_remuneration": float(total),
        "average_monthly_remuneration": float(average_monthly),
        "monthly_health_insurance": monthly_health,
        "monthly_longterm_care": monthly_longterm,
        "determined_health_insurance": determined_health,
        "determined_longterm_care": determined_longterm,
        "paid_health_insurance": paid_health,
        "paid_longterm_care": paid_longterm,
        "health_insurance_settlement": health_settlement,
        "longterm_care_settlement": longterm_settlement,
        "total_settlement": health_settlement + longterm_settlement,
    }


# ---------------------------------------------------------------------------
# 공개 API 3: 퇴직정산 통합 오케스트레이션
# ---------------------------------------------------------------------------

def settle_retirement(
    *,
    hire_date,
    severance_date,
    average_wage_per_day: Any,
    monthly_base_salary: Any,
    ordinary_wage_per_day: Any | None = None,
    unused_leave_days: Any = 0,
    exclusions: list[tuple] | None = None,
    monthly_remuneration_for_health: list[Any] | None = None,
    paid_health_total: Any = 0,
    paid_longterm_care_total: Any = 0,
    mid_month_hire: bool = False,
) -> dict[str, Any]:
    """퇴직정산 통합 오케스트레이션 — 퇴직금 + 미사용연차수당 + 퇴직소득세 + 건보정산.

    ① `severance_pay.calculate_severance_pay` 로 퇴직금 산정
    ② `hourly_wage.unused_leave_allowance` 로 미사용연차수당 산정
       (기본급÷209×8×미사용일수 — 퇴직금과 별개의 근로소득으로, 이 함수는 퇴직소득세
       과세표준에 합산하지 않는다. 개인 스킬 「퇴직정산」: 미사용연차수당은 퇴사월 급여에
       별도 지급되는 과세소득이며 중도퇴사 연말정산(근로소득) 대상이지 퇴직소득이 아니다)
    ③ `calculate_severance_income_tax` 로 퇴직금에 대한 퇴직소득세 산정
    ④ `monthly_remuneration_for_health` 가 주어지면 `reconcile_health_insurance_on_exit` 실행

    Returns
    -------
    dict with keys:
        severance_pay              계산 결과 dict (severance_pay.calculate_severance_pay 그대로)
        unused_leave_allowance     int   (원단위 반올림)
        severance_income_tax       계산 결과 dict (calculate_severance_income_tax 그대로) | None
        health_insurance_reconciliation  계산 결과 dict | None (미입력 시 None)
        payout_summary              dict (실지급 요약)
    """
    severance_result = _SEVERANCE_PAY.calculate_severance_pay(
        hire_date=hire_date,
        severance_date=severance_date,
        average_wage_per_day=average_wage_per_day,
        ordinary_wage_per_day=ordinary_wage_per_day,
        exclusions=exclusions,
    )
    severance_amount = _dec(severance_result["severance_pay_amount"], "severance_pay_amount")

    unused_leave_amount = _HOURLY_WAGE.unused_leave_allowance(monthly_base_salary, unused_leave_days)
    unused_leave_won = int(unused_leave_amount.to_integral_value(rounding=ROUND_CEILING)) if unused_leave_amount > 0 else 0

    income_tax_result: dict[str, Any] | None = None
    income_tax = 0
    local_income_tax = 0
    if severance_result["qualified_for_severance"] and severance_amount > 0:
        service_years = Decimal(severance_result["continuous_service_days"]) / Decimal("365")
        income_tax_result = calculate_severance_income_tax(
            severance_pay=severance_amount,
            service_years=service_years,
        )
        income_tax = income_tax_result["income_tax"]
        local_income_tax = income_tax_result["local_income_tax"]

    health_result: dict[str, Any] | None = None
    health_settlement = 0
    longterm_settlement = 0
    if monthly_remuneration_for_health:
        health_result = reconcile_health_insurance_on_exit(
            monthly_remuneration=monthly_remuneration_for_health,
            paid_health_total=paid_health_total,
            paid_longterm_care_total=paid_longterm_care_total,
            mid_month_hire=mid_month_hire,
        )
        health_settlement = health_result["health_insurance_settlement"]
        longterm_settlement = health_result["longterm_care_settlement"]

    # 실지급 요약: 퇴직금 - 퇴직소득세(+지방) + 미사용연차수당(세전, 근로소득 원천징수는 이 함수 범위 밖)
    #             - 건보정산 추가납부(양수면 차감, 음수/환급이면 가산)
    net_severance_payout = int(severance_amount) - income_tax - local_income_tax
    net_payout = net_severance_payout + unused_leave_won - health_settlement - longterm_settlement

    payout_summary = {
        "severance_pay_amount": int(severance_amount),
        "unused_leave_allowance": unused_leave_won,
        "severance_income_tax": income_tax,
        "severance_local_income_tax": local_income_tax,
        "net_severance_payout": net_severance_payout,
        "health_insurance_settlement": health_settlement,
        "longterm_care_settlement": longterm_settlement,
        "net_total_payout": net_payout,
    }

    return {
        "severance_pay": severance_result,
        "unused_leave_allowance": unused_leave_won,
        "severance_income_tax": income_tax_result,
        "health_insurance_reconciliation": health_result,
        "payout_summary": payout_summary,
    }
