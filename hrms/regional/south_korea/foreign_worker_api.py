"""외국인근로자 비자 룰 — Frappe whitelist API 래퍼.

foreign_worker.py의 순수 Python 함수를 frappe.whitelist HTTP 엔드포인트로 노출.
이 파일만 frappe에 의존하며, foreign_worker.py는 framework-free.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import frappe

from hrms.regional.south_korea.foreign_worker import (
    calculate_foreign_worker_insurance,
    get_stay_expiry_warning,
    get_visa_rules,
    list_supported_visa_types,
    validate_visa_for_employment,
)

DATE_PATTERN_MSG = "날짜는 YYYY-MM-DD 형식이어야 합니다."


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _coerce_payload(payload: dict[str, Any] | None, kwargs: dict[str, Any]) -> dict[str, Any]:
    """frappe form_dict / kwargs → dict 정규화."""
    if payload is not None:
        return payload
    if kwargs:
        return kwargs
    if getattr(frappe, "local", None) and getattr(frappe.local, "form_dict", None):
        form_dict = dict(frappe.local.form_dict)
        if len(form_dict) == 1 and "payload" in form_dict and isinstance(form_dict["payload"], str):
            return json.loads(form_dict["payload"])
        return form_dict
    return {}


def _parse_date(value: Any, field_name: str) -> dt.date:
    """문자열 → dt.date. 형식 오류 시 frappe.throw."""
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        frappe.throw(f"{field_name}: {DATE_PATTERN_MSG} (입력값: {value!r})")
        raise  # 타입 체커용 (frappe.throw는 exception을 raise함)


def _as_float(value: Any, field_name: str) -> float:
    """numeric 강제 변환. 실패 시 frappe.throw."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        frappe.throw(f"{field_name}: 숫자 값이어야 합니다 (입력값: {value!r})")
        raise


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


@frappe.whitelist()
def api_get_visa_rules(visa_type: str | None = None) -> dict[str, Any]:
    """비자 코드로 룰 dict 조회.

    GET /api/method/hrms.regional.south_korea._api.api_get_visa_rules?visa_type=E-9

    Returns:
        {
            "visa_type": str,
            "rules": dict,          # 빈 dict이면 미지원 코드
            "supported_types": list[str],
        }
    """
    if not visa_type:
        frappe.throw("visa_type은 필수 파라미터입니다.")

    rules = get_visa_rules(str(visa_type).strip())
    return {
        "visa_type": visa_type,
        "rules": rules,
        "supported_types": list_supported_visa_types(),
    }


@frappe.whitelist()
def api_validate_visa_for_employment(payload: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
    """비자별 고용 적합성 검증.

    POST /api/method/hrms.regional.south_korea._api.api_validate_visa_for_employment

    Request body (JSON):
        {
            "employee": {
                "visa_type": "E-9",
                "country_of_origin": "VN",
                "visa_expiry_date": "2026-12-31",       // optional
                "date_of_joining": "2025-01-01",        // optional
                "workplace_changes_this_year": 0,       // optional, E-9 전용
            },
            "employment_terms": {
                "weekly_overtime_hours": 8,
                "job_category": null,                   // optional, F-4 체크용
            }
        }
    """
    payload = _coerce_payload(payload, kwargs)

    employee = payload.get("employee")
    employment_terms = payload.get("employment_terms")

    if not isinstance(employee, dict):
        frappe.throw("employee 필드가 필요하며 객체(dict) 형식이어야 합니다.")
    if not employee.get("visa_type"):
        frappe.throw("employee.visa_type은 필수입니다.")
    if not isinstance(employment_terms, dict):
        frappe.throw("employment_terms 필드가 필요하며 객체(dict) 형식이어야 합니다.")

    # weekly_overtime_hours 숫자 검증
    ot_raw = employment_terms.get("weekly_overtime_hours", 0)
    employment_terms = dict(employment_terms)
    employment_terms["weekly_overtime_hours"] = _as_float(ot_raw, "employment_terms.weekly_overtime_hours")

    return validate_visa_for_employment(
        employee=employee,
        employment_terms=employment_terms,
    )


@frappe.whitelist()
def api_calculate_foreign_worker_insurance(payload: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
    """외국인 4대보험 월 부담액 계산.

    POST /api/method/hrms.regional.south_korea._api.api_calculate_foreign_worker_insurance

    Request body (JSON):
        {
            "visa_type": "E-9",
            "country_of_origin": "VN",
            "monthly_base_salary": 2500000,
            "pension_treaty_country": false      // optional
        }
    """
    payload = _coerce_payload(payload, kwargs)

    visa_type = payload.get("visa_type")
    country_of_origin = payload.get("country_of_origin")
    monthly_base_salary = payload.get("monthly_base_salary")
    pension_treaty_country = bool(payload.get("pension_treaty_country", False))

    if not visa_type:
        frappe.throw("visa_type은 필수입니다.")
    if not country_of_origin:
        frappe.throw("country_of_origin은 필수입니다.")
    if monthly_base_salary is None:
        frappe.throw("monthly_base_salary는 필수입니다.")

    salary = _as_float(monthly_base_salary, "monthly_base_salary")
    if salary < 0:
        frappe.throw("monthly_base_salary는 0 이상이어야 합니다.")

    return calculate_foreign_worker_insurance(
        visa_type=str(visa_type).strip(),
        country_of_origin=str(country_of_origin).strip(),
        monthly_base_salary=salary,
        pension_treaty_country=pension_treaty_country,
    )


@frappe.whitelist()
def api_get_stay_expiry_warning(
    visa_expiry_date: str | None = None,
    as_of_date: str | None = None,
    warning_days: int = 90,
) -> dict[str, Any]:
    """체류 만료 임박 알람.

    GET /api/method/hrms.regional.south_korea._api.api_get_stay_expiry_warning
        ?visa_expiry_date=2026-09-30&as_of_date=2026-07-01&warning_days=90
    """
    if not visa_expiry_date:
        frappe.throw("visa_expiry_date는 필수입니다.")

    expiry = _parse_date(visa_expiry_date, "visa_expiry_date")
    reference = _parse_date(as_of_date, "as_of_date") if as_of_date else dt.date.today()

    try:
        w_days = int(warning_days)
    except (TypeError, ValueError):
        frappe.throw(f"warning_days는 정수이어야 합니다 (입력값: {warning_days!r})")
        raise

    return get_stay_expiry_warning(
        visa_expiry_date=expiry,
        as_of_date=reference,
        warning_days=w_days,
    )


@frappe.whitelist()
def api_list_supported_visa_types() -> dict[str, Any]:
    """지원하는 비자 코드 목록 반환.

    GET /api/method/hrms.regional.south_korea._api.api_list_supported_visa_types
    """
    from hrms.regional.south_korea.foreign_worker import VISA_TYPES

    return {
        "supported_types": [
            {
                "code": code,
                "name": meta["name"],
                "category": meta["category"],
                "permit_employment": meta["permit_employment"],
            }
            for code, meta in VISA_TYPES.items()
        ]
    }
