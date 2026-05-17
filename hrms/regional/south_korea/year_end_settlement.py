"""
한국 연말정산 기본 계산기 (소득세법 기반, 2026년 귀속분 — 2025 과세연도)
Korea Year-End Tax Settlement Calculator — framework-free, no external dependencies.

법적 근거:
- 소득세법 47조의2: 근로소득공제
- 소득세법 47조:   인적공제 (기본공제 1인 150만원)
- 소득세법 51조:   특별소득공제 (보험료·주택자금)
- 소득세법 52조:   신용카드 등 소득공제
- 소득세법 55조:   기본세율
- 소득세법 59조:   세액공제 (근로소득·자녀·연금저축·보장성보험료·의료비·교육비·기부금)
- 소득세법 70조:   연말정산 절차
"""

from __future__ import annotations

__all__ = ["calculate_year_end_settlement"]

# ---------------------------------------------------------------------------
# 2026 적용 공제/세율 테이블 (2025년 귀속 소득세법 기준)
# ---------------------------------------------------------------------------

# 근로소득공제 구간 (소득세법 47조의2)
# (총급여 초과 하한, 총급여 이하 상한, 공제 기본액, 초과분 공제율)
# 공제 한도: 2,000만원
_EARNED_INCOME_BRACKETS: tuple[tuple[float, float, float, float], ...] = (
    (0,       5_000_000,    0,          0.70),
    (5_000_000,  15_000_000,  3_500_000,  0.40),
    (15_000_000, 45_000_000,  7_500_000,  0.15),
    (45_000_000, 100_000_000, 12_000_000, 0.05),
    (100_000_000, float("inf"), 14_750_000, 0.02),
)
_EARNED_INCOME_DEDUCTION_CAP: float = 20_000_000  # 2,000만원

# 기본세율 구간 (소득세법 55조) — 2024년 세법개정 반영 (1400만/5000만 기준)
# (과세표준 초과 하한, 과세표준 이하 상한, 누진공제액, 세율)
#
# 누진공제액 산출 공식:
#   cum[k] = cum[k-1] + boundary[k] × (rate[k] - rate[k-1])
# 이를 통해 각 구간 경계에서 산출세액 연속성 보장:
#   boundary × rate[k] − cum[k] = boundary × rate[k-1] − cum[k-1]
#
# 경계값 검증:
#   14M × 0.15 − 1,260,000  = 840,000  = 14M × 0.06 − 0         ✓
#   50M × 0.24 − 5,760,000  = 6,240,000 = 50M × 0.15 − 1,260,000 ✓
#   88M × 0.35 − 15,440,000 = 15,360,000 = 88M × 0.24 − 5,760,000 ✓
_BASE_TAX_BRACKETS: tuple[tuple[float, float, float, float], ...] = (
    (0,             14_000_000,   0,           0.06),
    (14_000_000,    50_000_000,   1_260_000,   0.15),
    (50_000_000,    88_000_000,   5_760_000,   0.24),
    (88_000_000,    150_000_000,  15_440_000,  0.35),
    (150_000_000,   300_000_000,  19_940_000,  0.38),
    (300_000_000,   500_000_000,  25_940_000,  0.40),
    (500_000_000,   1_000_000_000, 35_940_000, 0.42),
    (1_000_000_000, float("inf"), 65_940_000,  0.45),
)

# 근로소득 세액공제 (소득세법 59조 제1항)
# 산출세액 구간에 따른 공제
_EARNED_INCOME_TAX_CREDIT_BRACKETS: tuple[tuple[float, float, float, float], ...] = (
    (0,         1_300_000,  0,        0.55),   # 산출세액 130만 이하: 55%
    (1_300_000, float("inf"), 715_000, 0.30),  # 130만 초과: 71.5만 + 초과분 30%
)
_EARNED_INCOME_TAX_CREDIT_CAP_LOW: float = 740_000    # 총급여 3,300만 이하 한도
_EARNED_INCOME_TAX_CREDIT_CAP_MID: float = 660_000    # 총급여 3,300만~7,000만 이하 한도
_EARNED_INCOME_TAX_CREDIT_CAP_HIGH: float = 500_000   # 총급여 7,000만 초과 한도

# 기본공제 1인당 금액 (소득세법 47조)
_BASIC_DEDUCTION_PER_PERSON: float = 1_500_000

# 특별소득공제 — 건강보험+장기요양보험 본인부담 전액 공제 (소득세법 51조)
# insurance_premiums 파라미터는 4대보험 본인부담 전체로 받아서 공제 적용

# 주택자금 공제 (소득세법 51조 제4항) — 장기주택저당차입금 이자상환액
# v1 간소화: 이자 전액 소득공제 (실제 한도는 구조/기간에 따라 600만~2,000만원)
_HOUSING_LOAN_INTEREST_CAP: float = 20_000_000  # 최대 2,000만원

# 신용카드 등 사용금액 공제 (조세특례제한법 126조의2)
# (사용액 − 총급여 × 25%) × 15%,  한도 min(300만, 총급여 × 20%)
_CREDIT_CARD_MIN_RATIO: float = 0.25
_CREDIT_CARD_DEDUCTION_RATE: float = 0.15
_CREDIT_CARD_CAP_RATIO: float = 0.20
_CREDIT_CARD_CAP_MAX: float = 3_000_000

# 보장성보험료 세액공제 (소득세법 59조의4 제1항)
_PROTECTION_INSURANCE_CREDIT_RATE: float = 0.12
_PROTECTION_INSURANCE_CREDIT_CAP: float = 1_000_000  # 100만원 한도

# 의료비 세액공제 (소득세법 59조의4 제2항)
# 총급여 3% 초과분 × 15%
_MEDICAL_EXPENSE_THRESHOLD_RATIO: float = 0.03
_MEDICAL_EXPENSE_CREDIT_RATE: float = 0.15

# 교육비 세액공제 (소득세법 59조의4 제3항)
# 본인 교육비: 전액 × 15% (한도 없음)
_EDUCATION_EXPENSE_CREDIT_RATE: float = 0.15

# 연금저축 세액공제 (소득세법 59조의3)
# 납입액 × 12% (총급여 5,500만 이하), 또는 × 15% (총급여 5,500만 이하에서 한도 증가)
# v1 간소화: 총급여 구간에 따른 공제율, 납입 한도 600만원
_PENSION_SAVINGS_CAP: float = 6_000_000
_PENSION_SAVINGS_CREDIT_RATE_LOW: float = 0.15   # 총급여 5,500만 이하
_PENSION_SAVINGS_CREDIT_RATE_HIGH: float = 0.12  # 총급여 5,500만 초과
_PENSION_SAVINGS_SALARY_THRESHOLD: float = 55_000_000

# 자녀 세액공제 (소득세법 59조의2)
# 주의: 실제 법령은 '8세 이상 ~ 20세' 자녀에 적용. 파라미터명 children_under_8은
# 인터페이스 명세에 따른 것으로, v1에서는 해당 파라미터를 자녀 수로 취급하여
# 자녀세액공제 계산에 사용함. (자녀 수 = children_under_8 파라미터값)
# 1인: 15만원, 2인: 35만원, 3인 이상: 35만 + (초과 × 30만)
_CHILD_TAX_CREDIT_ONE: float = 150_000
_CHILD_TAX_CREDIT_TWO: float = 350_000
_CHILD_TAX_CREDIT_EXTRA: float = 300_000  # 3인 이상 추가 1인당

# 기부금 세액공제 (소득세법 59조의4 제4항)
# 법정기부금/지정기부금: 15% (3,000만 초과분 25%) — v1: 전액 15%
_DONATION_CREDIT_RATE: float = 0.15

# 지방소득세 = 소득세의 10%
_LOCAL_TAX_RATE: float = 0.10


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def calculate_year_end_settlement(
    *,
    employee: str,
    tax_year: int,
    total_salary: float,
    monthly_paid_income_tax: float,
    dependents: int = 1,
    children_under_8: int = 0,
    spouse: bool = False,
    insurance_premiums: float = 0,
    medical_expenses: float = 0,
    education_expenses: float = 0,
    housing_loan_interest: float = 0,
    pension_savings: float = 0,
    donation: float = 0,
    credit_card_usage: float = 0,
) -> dict:
    """
    연간 연말정산 결정세액 및 환급/추징액을 계산합니다.

    파라미터:
        employee:                직원 식별자 (사번 등)
        tax_year:                귀속 연도 (e.g. 2025)
        total_salary:            연간 총급여 (원)
        monthly_paid_income_tax: 월별 원천징수 소득세 납부액 합계 (지방소득세 제외)
        dependents:              기본공제 인원 수 (본인 포함). 기본값 1(본인만)
        children_under_8:        자녀세액공제 대상 자녀 수
                                 ※ 소득세법 59조의2는 8세 이상 20세 이하 자녀에 적용하나,
                                    v1에서는 파라미터명을 명세에 따라 유지하고
                                    전달된 수를 자녀세액공제 인원으로 계산함.
        spouse:                  배우자 기본공제 여부 (True 시 dependents에 추가 +1)
        insurance_premiums:      4대보험 본인부담 합계 (건강·요양·국민연금·고용보험)
        medical_expenses:        의료비 (세액공제 대상)
        education_expenses:      교육비 (세액공제 대상, 본인분)
        housing_loan_interest:   주택자금 이자상환액 (소득공제)
        pension_savings:         연금저축 납입액 (세액공제)
        donation:                기부금 (세액공제)
        credit_card_usage:       신용카드 등 사용금액 (소득공제)

    반환값:
        contract_type            항상 "korea_year_end_settlement_v1"
        tax_year                 귀속 연도
        employee                 직원 식별자
        total_salary             연간 총급여
        earned_income_deduction  근로소득공제 (소득세법 47조의2)
        earned_income            근로소득금액 = 총급여 - 근로소득공제
        personal_deduction       인적공제 합계 (소득세법 47조)
        special_income_deduction 특별소득공제 + 신용카드 소득공제 합계 (소득세법 51·52조)
        tax_base                 과세표준 = max(0, 근로소득금액 - 인적공제 - 특별소득공제)
        calculated_tax           산출세액 (소득세법 55조)
        tax_credits              세액공제 합계 (소득세법 59조)
        determined_tax           결정세액 = max(0, 산출세액 - 세액공제)
        monthly_paid_tax         기납부세액 (= monthly_paid_income_tax)
        refund_or_pay            환급(양수) 또는 추징(음수) = 기납부세액 - 결정세액
        local_tax_settlement     지방소득세 환급/추징 = refund_or_pay × 10%
    """
    total_salary = float(total_salary)
    monthly_paid_income_tax = float(monthly_paid_income_tax)
    dependents = max(int(dependents), 0)
    children_under_8 = max(int(children_under_8), 0)
    spouse = bool(spouse)
    insurance_premiums = max(float(insurance_premiums), 0)
    medical_expenses = max(float(medical_expenses), 0)
    education_expenses = max(float(education_expenses), 0)
    housing_loan_interest = max(float(housing_loan_interest), 0)
    pension_savings = max(float(pension_savings), 0)
    donation = max(float(donation), 0)
    credit_card_usage = max(float(credit_card_usage), 0)

    # 1. 근로소득공제 (소득세법 47조의2)
    earned_income_deduction = _calc_earned_income_deduction(total_salary)

    # 2. 근로소득금액
    earned_income = total_salary - earned_income_deduction

    # 3. 인적공제 (소득세법 47조)
    #    본인 포함 기본공제 인원 × 150만원 + 배우자 공제 (배우자는 별도 +1)
    total_persons = dependents + (1 if spouse else 0)
    personal_deduction = _basic_deduction(total_persons)

    # 4. 특별소득공제 + 신용카드 소득공제 (소득세법 51·52조)
    special_income_deduction = _calc_special_income_deduction(
        total_salary=total_salary,
        insurance_premiums=insurance_premiums,
        housing_loan_interest=housing_loan_interest,
        credit_card_usage=credit_card_usage,
    )

    # 5. 과세표준
    tax_base = max(0.0, earned_income - personal_deduction - special_income_deduction)

    # 6. 산출세액 (소득세법 55조)
    calculated_tax = _calc_income_tax(tax_base)

    # 7. 세액공제 (소득세법 59조)
    tax_credits = _calc_tax_credits(
        total_salary=total_salary,
        calculated_tax=calculated_tax,
        children_count=children_under_8,
        insurance_premiums=insurance_premiums,
        medical_expenses=medical_expenses,
        education_expenses=education_expenses,
        pension_savings=pension_savings,
        donation=donation,
    )

    # 8. 결정세액
    determined_tax = max(0.0, calculated_tax - tax_credits)

    # 9. 기납부세액 (소득세만, 지방소득세 제외)
    monthly_paid_tax = monthly_paid_income_tax

    # 10. 환급/추징 (양수 = 환급, 음수 = 추징)
    refund_or_pay = monthly_paid_tax - determined_tax

    # 11. 지방소득세 연말정산 (결정세액 × 10% - 기납부 지방소득세 추정)
    #     기납부 지방소득세 = monthly_paid_income_tax × 10%로 추정
    local_tax_settlement = refund_or_pay * _LOCAL_TAX_RATE

    return {
        "contract_type": "korea_year_end_settlement_v1",
        "tax_year": tax_year,
        "employee": employee,
        "total_salary": _round2(total_salary),
        "earned_income_deduction": _round2(earned_income_deduction),
        "earned_income": _round2(earned_income),
        "personal_deduction": _round2(personal_deduction),
        "special_income_deduction": _round2(special_income_deduction),
        "tax_base": _round2(tax_base),
        "calculated_tax": _round2(calculated_tax),
        "tax_credits": _round2(tax_credits),
        "determined_tax": _round2(determined_tax),
        "monthly_paid_tax": _round2(monthly_paid_tax),
        "refund_or_pay": _round2(refund_or_pay),
        "local_tax_settlement": _round2(local_tax_settlement),
    }


# ---------------------------------------------------------------------------
# 내부 계산 함수
# ---------------------------------------------------------------------------

def _calc_earned_income_deduction(total_salary: float) -> float:
    """근로소득공제 계산 (소득세법 47조의2). 한도 2,000만원."""
    deduction = 0.0
    for lower, upper, base, rate in _EARNED_INCOME_BRACKETS:
        if total_salary <= lower:
            break
        bracket_income = min(total_salary, upper) - lower
        deduction = base + bracket_income * rate
    return min(deduction, _EARNED_INCOME_DEDUCTION_CAP)


def _basic_deduction(persons: int) -> float:
    """기본공제 = 인원 × 1,500,000원 (소득세법 47조)."""
    return float(persons) * _BASIC_DEDUCTION_PER_PERSON


def _calc_special_income_deduction(
    total_salary: float,
    insurance_premiums: float,
    housing_loan_interest: float,
    credit_card_usage: float,
) -> float:
    """
    특별소득공제 합계 (소득세법 51조) + 신용카드 소득공제 (조세특례제한법 126조의2).

    구성:
    - 보험료 공제: 4대보험 본인부담 전액
    - 주택자금 이자: 한도 2,000만원
    - 신용카드 사용액: (사용액 − 총급여×25%)×15%, 한도 min(총급여×20%, 300만)
    """
    # 건강보험·국민연금 등 4대보험 본인부담 전액 공제
    ins_deduction = insurance_premiums

    # 주택자금 이자상환액 공제 (한도 2,000만원)
    housing_deduction = min(housing_loan_interest, _HOUSING_LOAN_INTEREST_CAP)

    # 신용카드 소득공제
    credit_card_deduction = _calc_credit_card_deduction(total_salary, credit_card_usage)

    return ins_deduction + housing_deduction + credit_card_deduction


def _calc_credit_card_deduction(total_salary: float, credit_card_usage: float) -> float:
    """신용카드 등 사용금액 소득공제 (조세특례제한법 126조의2)."""
    threshold = total_salary * _CREDIT_CARD_MIN_RATIO
    excess = credit_card_usage - threshold
    if excess <= 0:
        return 0.0
    cap = min(total_salary * _CREDIT_CARD_CAP_RATIO, _CREDIT_CARD_CAP_MAX)
    return min(excess * _CREDIT_CARD_DEDUCTION_RATE, cap)


def _calc_income_tax(tax_base: float) -> float:
    """산출세액 계산 (소득세법 55조 기본세율 — 누진공제 방식)."""
    if tax_base <= 0:
        return 0.0
    for lower, upper, cumulative_deduction, rate in _BASE_TAX_BRACKETS:
        if tax_base <= upper:
            return tax_base * rate - cumulative_deduction
    # tax_base가 모든 구간 초과 (이론상 마지막 구간에서 처리됨)
    lower, upper, cumulative_deduction, rate = _BASE_TAX_BRACKETS[-1]
    return tax_base * rate - cumulative_deduction


def _calc_tax_credits(
    total_salary: float,
    calculated_tax: float,
    children_count: int,
    insurance_premiums: float,
    medical_expenses: float,
    education_expenses: float,
    pension_savings: float,
    donation: float,
) -> float:
    """
    세액공제 합계 계산 (소득세법 59조).

    구성:
    - 근로소득 세액공제 (59조 1항)
    - 자녀 세액공제 (59조의2)
    - 연금저축 세액공제 (59조의3)
    - 보장성보험료 세액공제 (59조의4 제1항)
    - 의료비 세액공제 (59조의4 제2항)
    - 교육비 세액공제 (59조의4 제3항)
    - 기부금 세액공제 (59조의4 제4항)
    """
    credits = 0.0

    # (a) 근로소득 세액공제 (소득세법 59조 제1항)
    credits += _calc_earned_income_tax_credit(total_salary, calculated_tax)

    # (b) 자녀 세액공제 (소득세법 59조의2)
    credits += _calc_child_tax_credit(children_count)

    # (c) 연금저축 세액공제 (소득세법 59조의3)
    credits += _calc_pension_savings_credit(total_salary, pension_savings)

    # (d) 보장성보험료 세액공제 (소득세법 59조의4 제1항)
    #     보험료 파라미터는 4대보험(사회보험) 전체이나 보장성(민간)보험료와 구분이 필요.
    #     v1 간소화: 4대보험 본인부담액을 소득공제 처리하고,
    #               보장성보험료 세액공제는 별도 파라미터 없어 0으로 처리.
    #     (실무에서는 별도 보장성보험료 파라미터를 추가해야 함)

    # (e) 의료비 세액공제 (소득세법 59조의4 제2항)
    credits += _calc_medical_expense_credit(total_salary, medical_expenses)

    # (f) 교육비 세액공제 (소득세법 59조의4 제3항)
    credits += _calc_education_expense_credit(education_expenses)

    # (g) 기부금 세액공제 (소득세법 59조의4 제4항)
    credits += _calc_donation_credit(donation)

    return credits


def _calc_earned_income_tax_credit(total_salary: float, calculated_tax: float) -> float:
    """
    근로소득 세액공제 (소득세법 59조 제1항).

    산출세액 기준:
    - 130만원 이하: 55%
    - 130만원 초과: 71.5만원 + 초과분 × 30%

    공제 한도:
    - 총급여 3,300만 이하: 74만원
    - 총급여 3,300만~7,000만: 66만원
    - 총급여 7,000만 초과: 50만원
    """
    if calculated_tax <= 0:
        return 0.0

    raw_credit = 0.0
    for lower, upper, base, rate in _EARNED_INCOME_TAX_CREDIT_BRACKETS:
        if calculated_tax <= upper:
            raw_credit = base + (calculated_tax - lower) * rate
            break

    if total_salary <= 33_000_000:
        cap = _EARNED_INCOME_TAX_CREDIT_CAP_LOW
    elif total_salary <= 70_000_000:
        cap = _EARNED_INCOME_TAX_CREDIT_CAP_MID
    else:
        cap = _EARNED_INCOME_TAX_CREDIT_CAP_HIGH

    return min(raw_credit, cap)


def _calc_child_tax_credit(children_count: int) -> float:
    """
    자녀 세액공제 (소득세법 59조의2).

    ※ 소득세법 59조의2 기준: 8세 이상 ~ 20세 이하 자녀에 적용.
       본 함수의 children_count 파라미터는 인터페이스 명세(children_under_8)에서
       전달된 자녀 수이며, v1에서는 자녀세액공제 대상 인원으로 처리함.

    1인: 150,000원
    2인: 350,000원
    3인 이상: 350,000원 + (초과 인원 × 300,000원)
    """
    if children_count <= 0:
        return 0.0
    if children_count == 1:
        return _CHILD_TAX_CREDIT_ONE
    if children_count == 2:
        return _CHILD_TAX_CREDIT_TWO
    return _CHILD_TAX_CREDIT_TWO + (children_count - 2) * _CHILD_TAX_CREDIT_EXTRA


def _calc_pension_savings_credit(total_salary: float, pension_savings: float) -> float:
    """
    연금저축 세액공제 (소득세법 59조의3).

    - 총급여 5,500만 이하: 15%
    - 총급여 5,500만 초과: 12%
    - 납입 한도: 600만원
    """
    if pension_savings <= 0:
        return 0.0
    eligible = min(pension_savings, _PENSION_SAVINGS_CAP)
    rate = (
        _PENSION_SAVINGS_CREDIT_RATE_LOW
        if total_salary <= _PENSION_SAVINGS_SALARY_THRESHOLD
        else _PENSION_SAVINGS_CREDIT_RATE_HIGH
    )
    return eligible * rate


def _calc_medical_expense_credit(total_salary: float, medical_expenses: float) -> float:
    """
    의료비 세액공제 (소득세법 59조의4 제2항).

    총급여 × 3% 초과분 × 15%
    """
    if medical_expenses <= 0:
        return 0.0
    threshold = total_salary * _MEDICAL_EXPENSE_THRESHOLD_RATIO
    excess = medical_expenses - threshold
    if excess <= 0:
        return 0.0
    return excess * _MEDICAL_EXPENSE_CREDIT_RATE


def _calc_education_expense_credit(education_expenses: float) -> float:
    """
    교육비 세액공제 (소득세법 59조의4 제3항).

    본인 교육비 전액 × 15% (한도 없음, 본인분 기준)
    """
    if education_expenses <= 0:
        return 0.0
    return education_expenses * _EDUCATION_EXPENSE_CREDIT_RATE


def _calc_donation_credit(donation: float) -> float:
    """
    기부금 세액공제 (소득세법 59조의4 제4항).

    v1 간소화: 전액 × 15%
    (실제: 3,000만원 초과분은 25%)
    """
    if donation <= 0:
        return 0.0
    return donation * _DONATION_CREDIT_RATE


def _round2(value: float) -> float:
    """원 단위 반올림 (소수점 2자리 유지)."""
    return round(value, 2)
