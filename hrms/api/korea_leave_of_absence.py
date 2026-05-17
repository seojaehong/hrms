"""Frappe whitelist API 래퍼 — 한국 휴직 처리.

코어 로직은 hrms/regional/south_korea/leave_of_absence.py (framework-free).
이 모듈은 Frappe HTTP 진입점만 담당:
- @frappe.whitelist() 데코레이터
- 입력 coerce (JSON string → dict)
- ValueError → frappe.throw() 변환
- 날짜 파싱
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import frappe

from hrms.regional.south_korea.leave_of_absence import (
    adjust_average_wage_for_leave,
    approve_leave_of_absence,
    calculate_childcare_benefit,
    calculate_insurance_during_leave,
    request_leave_of_absence,
)

DATE_PATTERN_MSG = "날짜 형식은 YYYY-MM-DD이어야 합니다."


# ---------------------------------------------------------------------------
# Whitelist 엔드포인트
# ---------------------------------------------------------------------------


@frappe.whitelist()
def api_request_leave_of_absence(payload: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
    """휴직 신청 API.

    payload 필드:
        employee (str, required)
        leave_type (str, required): childcare | maternity | sick_paid | sick_unpaid | personal
        start_date (str, required): YYYY-MM-DD
        end_date (str, optional): YYYY-MM-DD
        reason (str, required)
        human_approved (bool, optional, default False)
    """
    payload = _coerce_payload(payload, kwargs)
    _reject_unknown_keys(
        payload,
        {"employee", "leave_type", "start_date", "end_date", "reason", "human_approved"},
        "payload",
    )
    _require_keys(payload, {"employee", "leave_type", "start_date", "reason"}, "payload")

    start_date = _parse_date(payload["start_date"], "start_date")
    end_date_raw = payload.get("end_date")
    end_date = _parse_date(end_date_raw, "end_date") if end_date_raw else None
    human_approved = _coerce_bool(payload.get("human_approved", False))

    try:
        result = request_leave_of_absence(
            employee=str(payload["employee"]),
            leave_type=str(payload["leave_type"]),
            start_date=start_date,
            end_date=end_date,
            reason=str(payload["reason"]),
            human_approved=human_approved,
        )
    except ValueError as exc:
        frappe.throw(str(exc))

    return result


@frappe.whitelist()
def api_approve_leave_of_absence(payload: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
    """휴직 승인 API.

    payload 필드:
        request_id (str, required)
        approver (str, required)
        human_approved (bool, required): True여야 승인 처리
    """
    payload = _coerce_payload(payload, kwargs)
    _reject_unknown_keys(payload, {"request_id", "approver", "human_approved"}, "payload")
    _require_keys(payload, {"request_id", "approver", "human_approved"}, "payload")

    human_approved = _coerce_bool(payload["human_approved"])

    try:
        result = approve_leave_of_absence(
            request_id=str(payload["request_id"]),
            approver=str(payload["approver"]),
            human_approved=human_approved,
        )
    except ValueError as exc:
        frappe.throw(str(exc))

    return result


@frappe.whitelist()
def api_calculate_insurance_during_leave(
    payload: dict[str, Any] | None = None, **kwargs
) -> dict[str, Any]:
    """휴직 기간 4대보험 변동 계산 API.

    payload 필드:
        leave_type (str, required)
        leave_start_date (str, required): YYYY-MM-DD
        leave_end_date (str, required): YYYY-MM-DD
        monthly_base_salary (float, required)
    """
    payload = _coerce_payload(payload, kwargs)
    _reject_unknown_keys(
        payload,
        {"leave_type", "leave_start_date", "leave_end_date", "monthly_base_salary"},
        "payload",
    )
    _require_keys(
        payload,
        {"leave_type", "leave_start_date", "leave_end_date", "monthly_base_salary"},
        "payload",
    )

    leave_start = _parse_date(payload["leave_start_date"], "leave_start_date")
    leave_end = _parse_date(payload["leave_end_date"], "leave_end_date")
    monthly_base_salary = _as_float(payload["monthly_base_salary"])

    try:
        result = calculate_insurance_during_leave(
            leave_type=str(payload["leave_type"]),
            leave_start_date=leave_start,
            leave_end_date=leave_end,
            monthly_base_salary=monthly_base_salary,
        )
    except ValueError as exc:
        frappe.throw(str(exc))

    return result


@frappe.whitelist()
def api_calculate_childcare_benefit(
    payload: dict[str, Any] | None = None, **kwargs
) -> dict[str, Any]:
    """육아휴직급여 계산 API.

    payload 필드:
        monthly_base_salary (float, required)
        leave_month_index (int, required): 1 이상 18 이하
    """
    payload = _coerce_payload(payload, kwargs)
    _reject_unknown_keys(payload, {"monthly_base_salary", "leave_month_index"}, "payload")
    _require_keys(payload, {"monthly_base_salary", "leave_month_index"}, "payload")

    monthly_base_salary = _as_float(payload["monthly_base_salary"])
    leave_month_index = _as_int(payload["leave_month_index"])

    try:
        result = calculate_childcare_benefit(
            monthly_base_salary=monthly_base_salary,
            leave_month_index=leave_month_index,
        )
    except ValueError as exc:
        frappe.throw(str(exc))

    return result


@frappe.whitelist()
def api_adjust_average_wage_for_leave(
    payload: dict[str, Any] | None = None, **kwargs
) -> dict[str, Any]:
    """퇴직금 평균임금 산정 시 휴직 기간 제외 계산 API.

    payload 필드:
        severance_calculation_period (dict, required):
            {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
        leave_periods (list, required):
            [{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}, ...]
    """
    payload = _coerce_payload(payload, kwargs)
    _reject_unknown_keys(
        payload, {"severance_calculation_period", "leave_periods"}, "payload"
    )
    _require_keys(payload, {"severance_calculation_period", "leave_periods"}, "payload")

    scp = payload["severance_calculation_period"]
    if not isinstance(scp, dict):
        frappe.throw("severance_calculation_period must be an object with start_date and end_date")
    _require_keys(scp, {"start_date", "end_date"}, "severance_calculation_period")

    scp_start = _parse_date(scp["start_date"], "severance_calculation_period.start_date")
    scp_end = _parse_date(scp["end_date"], "severance_calculation_period.end_date")

    leave_periods_raw = payload["leave_periods"]
    if not isinstance(leave_periods_raw, list):
        frappe.throw("leave_periods must be a list")

    leave_periods: list[tuple[dt.date, dt.date]] = []
    for i, lp in enumerate(leave_periods_raw):
        if not isinstance(lp, dict):
            frappe.throw(f"leave_periods[{i}] must be an object with start_date and end_date")
        _require_keys(lp, {"start_date", "end_date"}, f"leave_periods[{i}]")
        lp_start = _parse_date(lp["start_date"], f"leave_periods[{i}].start_date")
        lp_end = _parse_date(lp["end_date"], f"leave_periods[{i}].end_date")
        leave_periods.append((lp_start, lp_end))

    try:
        result = adjust_average_wage_for_leave(
            severance_calculation_period=(scp_start, scp_end),
            leave_periods=leave_periods,
        )
    except ValueError as exc:
        frappe.throw(str(exc))

    return result


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _coerce_payload(payload: dict[str, Any] | None, kwargs: dict[str, Any]) -> dict[str, Any]:
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


def _require_keys(payload: Any, required_keys: set[str], label: str) -> None:
    if not isinstance(payload, dict):
        frappe.throw(f"{label} must be an object")
    missing = [key for key in sorted(required_keys) if key not in payload or payload.get(key) in (None, "")]
    if missing:
        frappe.throw(f"{label} is missing required fields: {', '.join(missing)}")


def _reject_unknown_keys(payload: Any, allowed_keys: set[str], label: str) -> None:
    if not isinstance(payload, dict):
        frappe.throw(f"{label} must be an object")
    unknown = sorted(set(payload) - allowed_keys)
    if unknown:
        frappe.throw(f"{label} contains unsupported fields: {', '.join(unknown)}")


def _parse_date(value: Any, field_name: str) -> dt.date:
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.datetime):
        return value.date()
    try:
        return dt.date.fromisoformat(str(value))
    except (ValueError, TypeError):
        frappe.throw(f"{field_name}: {DATE_PATTERN_MSG} Got: {value!r}")
        raise RuntimeError(f"frappe.throw returned unexpectedly for {field_name}")


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        frappe.throw(f"Invalid numeric value: {value!r}")
        raise RuntimeError(f"frappe.throw returned unexpectedly for numeric value: {value!r}")


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        frappe.throw(f"Invalid integer value: {value!r}")
        raise RuntimeError(f"frappe.throw returned unexpectedly for integer value: {value!r}")


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
