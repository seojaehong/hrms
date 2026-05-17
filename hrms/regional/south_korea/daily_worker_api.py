"""
Frappe whitelist API — 일용근로자 급여 계산 엔드포인트.

이 모듈은 Frappe 의존성만 포함한다.
실제 계산 로직은 framework-free 모듈 daily_worker.py 에 위치한다.
"""

from __future__ import annotations

from typing import Any

import frappe

from hrms.regional.south_korea.daily_worker import calculate_daily_worker_payroll


@frappe.whitelist()
def korea_daily_worker_payroll(
    daily_wage: float | str,
    days_worked: int | str,
    additional_wages: float | str = 0,
    employment_period_months: int | str = 0,
) -> dict[str, Any]:
    """
    일용근로자 급여·세금·4대보험 계산 API.

    Parameters
    ----------
    daily_wage : float
        일급 (원).
    days_worked : int
        근무일수.
    additional_wages : float, optional
        식대·교통비 등 별도 비과세 추가수당 총액 (원). 기본값 0.
    employment_period_months : int, optional
        동일 사업장 연속 근무 개월 수. 1 이상이면 국민연금·건강보험 적용. 기본값 0.

    Returns
    -------
    dict
        calculate_daily_worker_payroll() 반환 값과 동일한 구조.

    Raises
    ------
    frappe.ValidationError
        입력 값이 숫자로 변환 불가능하거나 음수인 경우.
    """
    try:
        daily_wage = float(daily_wage)
        days_worked = int(days_worked)
        additional_wages = float(additional_wages)
        employment_period_months = int(employment_period_months)
    except (TypeError, ValueError) as exc:
        frappe.throw(f"Invalid input: {exc}")

    try:
        return calculate_daily_worker_payroll(
            daily_wage=daily_wage,
            days_worked=days_worked,
            additional_wages=additional_wages,
            employment_period_months=employment_period_months,
        )
    except ValueError as exc:
        frappe.throw(str(exc))
