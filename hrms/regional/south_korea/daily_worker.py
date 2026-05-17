"""
Korean daily worker (일용근로자) payroll calculation — framework-free module.

Legal basis (2026 standards):
  - 소득세법 제22조 (일용근로소득) / 소득세법 제47조의2 (일용근로소득공제)
  - 일용근로소득 비과세 한도: 일급 187,000원 이하 (소액부징수 실질 기준)
  - 일용근로소득공제: 일당 150,000원
  - 분리과세율: 6% × (1 - 55% 세액공제) = 2.7%
  - 지방소득세: 원천징수 소득세의 10%

4대보험 일용근로자 적용 기준 (단순화 버전):
  - 국민연금 / 건강보험: 동일 사업장 1개월 이상 계속 근무 시 적용
    (실제 규정은 월 8일·60시간 이상 추가 조건 포함, 본 모듈은 개월 수 기준으로 단순화)
  - 고용보험: 1개월 미만 단기 일용직도 적용 (상시 근로자와 동일)
  - 산재보험: 사업주 100% 부담, 항상 적용

추가수당(additional_wages) 처리:
  - 식대·교통비 등 별도 비과세 항목
  - total_gross 및 net_pay에 포함되나 tax_exempt_wages / taxable_wages 계산에서 제외
  - (일급과 별개로 비과세 처리되므로 소득세 과표에 영향 없음)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 2026년 기준 상수
# ---------------------------------------------------------------------------

DAILY_TAX_EXEMPT_LIMIT = 187_000        # 소액부징수 실질 비과세 일급 한도 (원)
DAILY_WORKING_DEDUCTION_AMOUNT = 150_000  # 일용근로소득공제 (원/일)

_SEPARATION_TAX_RATE = 0.06             # 분리과세율 6%
_TAX_CREDIT_RATE = 0.55                 # 세액공제율 55%
_EFFECTIVE_TAX_RATE = _SEPARATION_TAX_RATE * (1 - _TAX_CREDIT_RATE)  # = 0.027
_LOCAL_INCOME_TAX_RATE = 0.10           # 지방소득세율 (소득세의 10%)
_TEN_WON_UNIT = 10                      # 10원 절사 단위


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def calculate_daily_worker_payroll(
    *,
    daily_wage: float,
    days_worked: int,
    additional_wages: float = 0,
    employment_period_months: int = 0,
) -> dict:
    """
    일용근로자 급여·세금·4대보험 적용 여부를 계산한다.

    Parameters
    ----------
    daily_wage : float
        일급 (원). 단일 일급 기준.
    days_worked : int
        근무일수.
    additional_wages : float, optional
        식대·교통비 등 별도 비과세 추가 수당 총액 (원).
        total_gross 및 net_pay에는 포함되나 소득세 과표 계산에는 포함되지 않는다.
    employment_period_months : int, optional
        동일 사업장 연속 근무 개월 수.
        1 이상이면 국민연금·건강보험 적용 대상.

    Returns
    -------
    dict with keys:
        contract_type               str   — 고정값 "korea_daily_worker_payroll_v1"
        daily_wage                  float
        days_worked                 int
        total_gross                 float — 일급 × 일수 + additional_wages
        tax_exempt_wages            float — min(daily_wage, 187,000) × 일수 합산
        taxable_wages               float — max(0, daily_wage − 187,000) × 일수 합산
        daily_deduction             float — 일용근로소득공제 총액 (150,000 × 일수)
        income_tax_per_day          float — 일별 분리과세 소득세 (10원 절사)
        income_tax_total            float — income_tax_per_day × 일수
        local_income_tax_total      float — income_tax_total × 10% (10원 절사)
        applies_pension             bool  — 1개월 이상 연속 근무 시 True
        applies_health_insurance    bool  — 1개월 이상 연속 근무 시 True
        applies_employment_insurance bool — 항상 True
        applies_industrial_accident bool  — 항상 True (사업주 부담)
        net_pay                     float — total_gross − income_tax_total − local_income_tax_total
    """
    daily_wage = float(daily_wage)
    days_worked = int(days_worked)
    additional_wages = float(additional_wages)
    employment_period_months = int(employment_period_months)

    if daily_wage < 0:
        raise ValueError("daily_wage must be non-negative")
    if days_worked < 0:
        raise ValueError("days_worked must be non-negative")
    if additional_wages < 0:
        raise ValueError("additional_wages must be non-negative")

    # -----------------------------------------------------------------------
    # 1. 총 지급액
    # -----------------------------------------------------------------------
    wage_total = daily_wage * days_worked
    total_gross = wage_total + additional_wages

    # -----------------------------------------------------------------------
    # 2. 비과세 / 과세 임금 (187,000원 기준, additional_wages 제외)
    # -----------------------------------------------------------------------
    exempt_per_day = min(daily_wage, DAILY_TAX_EXEMPT_LIMIT)
    taxable_per_day = max(0.0, daily_wage - DAILY_TAX_EXEMPT_LIMIT)

    tax_exempt_wages = exempt_per_day * days_worked
    taxable_wages = taxable_per_day * days_worked

    # -----------------------------------------------------------------------
    # 3. 소득세 계산 (분리과세)
    #    과세 기준: (일급 − 150,000) × 2.7%
    #    소액부징수: 일급 ≤ 187,000원이면 0원
    #    (187,000 − 150,000) × 0.027 = 999원 < 1,000원 → 0으로 처리
    # -----------------------------------------------------------------------
    income_tax_per_day = _calc_daily_income_tax(daily_wage)
    income_tax_total = income_tax_per_day * days_worked

    # -----------------------------------------------------------------------
    # 4. 지방소득세 (소득세 × 10%, 10원 절사)
    # -----------------------------------------------------------------------
    local_income_tax_total = _floor10(income_tax_total * _LOCAL_INCOME_TAX_RATE)

    # -----------------------------------------------------------------------
    # 5. 4대보험 적용 여부
    # -----------------------------------------------------------------------
    applies_pension = employment_period_months >= 1
    applies_health_insurance = employment_period_months >= 1
    applies_employment_insurance = True
    applies_industrial_accident = True

    # -----------------------------------------------------------------------
    # 6. 실수령액
    # -----------------------------------------------------------------------
    net_pay = total_gross - income_tax_total - local_income_tax_total

    return {
        "contract_type": "korea_daily_worker_payroll_v1",
        "daily_wage": daily_wage,
        "days_worked": days_worked,
        "total_gross": total_gross,
        "tax_exempt_wages": tax_exempt_wages,
        "taxable_wages": taxable_wages,
        "daily_deduction": float(DAILY_WORKING_DEDUCTION_AMOUNT * days_worked),
        "income_tax_per_day": income_tax_per_day,
        "income_tax_total": income_tax_total,
        "local_income_tax_total": local_income_tax_total,
        "applies_pension": applies_pension,
        "applies_health_insurance": applies_health_insurance,
        "applies_employment_insurance": applies_employment_insurance,
        "applies_industrial_accident": applies_industrial_accident,
        "net_pay": net_pay,
    }


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _calc_daily_income_tax(daily_wage: float) -> float:
    """
    일별 분리과세 소득세를 계산한다.

    공식:
        과세표준 = max(0, 일급 − 150,000)
        세액     = 과세표준 × 6% × (1 − 55%) = 과세표준 × 2.7%
        소액부징수: 일급 ≤ 187,000이면 0원 반환
                   (계산 결과 999원 < 1,000원, 실무상 0으로 처리)

    부동소수점 처리:
        0.027은 부동소수점으로 정확히 표현되지 않으므로
        원 단위로 반올림(round)한 뒤 10원 단위 절사를 적용한다.

    Returns
    -------
    float
        10원 단위 절사 후 일별 소득세 (원).
    """
    if daily_wage <= DAILY_TAX_EXEMPT_LIMIT:
        return 0.0

    taxable_base = daily_wage - DAILY_WORKING_DEDUCTION_AMOUNT
    if taxable_base <= 0:
        return 0.0

    raw_tax = taxable_base * _EFFECTIVE_TAX_RATE
    return _floor10(raw_tax)


def _floor10(amount: float) -> float:
    """10원 단위 절사.

    부동소수점 오차를 방지하기 위해 먼저 원 단위로 반올림한 뒤 10으로 나누어 절사한다.
    예: 1349.9999... → round → 1350 → floor10 → 1350
        2699.9999... → round → 2700 → floor10 → 2700
    """
    rounded_won = round(amount)  # 원 단위 반올림 (부동소수점 오차 제거)
    return float((rounded_won // _TEN_WON_UNIT) * _TEN_WON_UNIT)
