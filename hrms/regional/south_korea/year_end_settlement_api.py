"""
Frappe whitelist wrapper — 연말정산 계산기 API (3-C-3)

이 모듈은 Frappe 의존성을 격리하고,
순수 계산 엔진(year_end_settlement.py)을 HTTP 엔드포인트로 노출합니다.

엔드포인트: /api/method/hrms.regional.south_korea._api.calculate_year_end_settlement
"""

from __future__ import annotations

from typing import Any

import frappe

from hrms.regional.south_korea.year_end_settlement import (
    calculate_year_end_settlement as _calculate,
)

_ALLOWED_FIELDS = frozenset(
    {
        "employee",
        "tax_year",
        "total_salary",
        "monthly_paid_income_tax",
        "dependents",
        "children_under_8",
        "spouse",
        "insurance_premiums",
        "medical_expenses",
        "education_expenses",
        "housing_loan_interest",
        "pension_savings",
        "donation",
        "credit_card_usage",
    }
)


@frappe.whitelist()
def calculate_year_end_settlement(
    employee: str | None = None,
    tax_year: int | str | None = None,
    total_salary: float | str | None = None,
    monthly_paid_income_tax: float | str | None = None,
    dependents: int | str = 1,
    children_under_8: int | str = 0,
    spouse: bool | str = False,
    insurance_premiums: float | str = 0,
    medical_expenses: float | str = 0,
    education_expenses: float | str = 0,
    housing_loan_interest: float | str = 0,
    pension_savings: float | str = 0,
    donation: float | str = 0,
    credit_card_usage: float | str = 0,
) -> dict[str, Any]:
    """
    연말정산 결정세액·환급/추징액을 계산합니다.

    Frappe whitelist를 통해 HTTP API로 노출됩니다.
    입력값은 문자열로 전달되더라도 적절히 형변환됩니다.

    필수 파라미터:
        employee                직원 식별자 (사번 등)
        tax_year                귀속 연도 (정수, e.g. 2025)
        total_salary            연간 총급여 (원)
        monthly_paid_income_tax 이미 납부한 월별 원천징수 소득세 합계 (지방소득세 제외)

    선택 파라미터:
        dependents              기본공제 인원 수 (본인 포함, 기본값 1)
        children_under_8        자녀세액공제 대상 자녀 수 (기본값 0)
        spouse                  배우자 기본공제 여부 (기본값 False)
        insurance_premiums      4대보험 본인부담 합계 (기본값 0)
        medical_expenses        의료비 (기본값 0)
        education_expenses      교육비 (기본값 0)
        housing_loan_interest   주택자금 이자상환액 (기본값 0)
        pension_savings         연금저축 납입액 (기본값 0)
        donation                기부금 (기본값 0)
        credit_card_usage       신용카드 등 사용금액 (기본값 0)

    반환값 (dict):
        contract_type           항상 "korea_year_end_settlement_v1"
        tax_year                귀속 연도
        employee                직원 식별자
        total_salary            연간 총급여
        earned_income_deduction 근로소득공제 (소득세법 47조의2)
        earned_income           근로소득금액
        personal_deduction      인적공제 합계 (소득세법 47조)
        special_income_deduction 특별소득공제 + 신용카드 소득공제 합계
        tax_base                과세표준
        calculated_tax          산출세액 (소득세법 55조)
        tax_credits             세액공제 합계 (소득세법 59조)
        determined_tax          결정세액
        monthly_paid_tax        기납부세액
        refund_or_pay           환급(양수) 또는 추징(음수)
        local_tax_settlement    지방소득세 환급/추징
    """
    # 필수 파라미터 검증
    if not employee or str(employee).strip() == "":
        frappe.throw("employee is required")
    if tax_year is None or str(tax_year).strip() == "":
        frappe.throw("tax_year is required")
    if total_salary is None or str(total_salary).strip() == "":
        frappe.throw("total_salary is required")
    if monthly_paid_income_tax is None or str(monthly_paid_income_tax).strip() == "":
        frappe.throw("monthly_paid_income_tax is required")

    # 형변환 및 유효성 검증
    tax_year_int = _coerce_int(tax_year, "tax_year")
    if tax_year_int < 2000 or tax_year_int > 2100:
        frappe.throw("tax_year must be between 2000 and 2100")

    total_salary_f = _coerce_nonneg_float(total_salary, "total_salary")
    monthly_paid_f = _coerce_nonneg_float(monthly_paid_income_tax, "monthly_paid_income_tax")
    dependents_int = _coerce_nonneg_int(dependents, "dependents")
    children_int = _coerce_nonneg_int(children_under_8, "children_under_8")
    spouse_bool = _coerce_bool(spouse)
    insurance_f = _coerce_nonneg_float(insurance_premiums, "insurance_premiums")
    medical_f = _coerce_nonneg_float(medical_expenses, "medical_expenses")
    education_f = _coerce_nonneg_float(education_expenses, "education_expenses")
    housing_f = _coerce_nonneg_float(housing_loan_interest, "housing_loan_interest")
    pension_f = _coerce_nonneg_float(pension_savings, "pension_savings")
    donation_f = _coerce_nonneg_float(donation, "donation")
    credit_card_f = _coerce_nonneg_float(credit_card_usage, "credit_card_usage")

    try:
        return _calculate(
            employee=str(employee).strip(),
            tax_year=tax_year_int,
            total_salary=total_salary_f,
            monthly_paid_income_tax=monthly_paid_f,
            dependents=dependents_int,
            children_under_8=children_int,
            spouse=spouse_bool,
            insurance_premiums=insurance_f,
            medical_expenses=medical_f,
            education_expenses=education_f,
            housing_loan_interest=housing_f,
            pension_savings=pension_f,
            donation=donation_f,
            credit_card_usage=credit_card_f,
        )
    except Exception as exc:
        frappe.log_error(f"Korea year-end settlement calculation error: {exc}")
        frappe.throw(f"계산 중 오류가 발생했습니다: {exc}")


# ---------------------------------------------------------------------------
# 내부 형변환 유틸리티
# ---------------------------------------------------------------------------

def _coerce_int(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        frappe.throw(f"{field} must be an integer, got: {value!r}")
        raise  # unreachable — frappe.throw raises


def _coerce_nonneg_int(value: Any, field: str) -> int:
    result = _coerce_int(value, field)
    if result < 0:
        frappe.throw(f"{field} must be non-negative, got: {result}")
    return result


def _coerce_nonneg_float(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        frappe.throw(f"{field} must be a number, got: {value!r}")
        raise
    if result < 0:
        frappe.throw(f"{field} must be non-negative, got: {result}")
    return result


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)
