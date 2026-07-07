"""Frappe whitelist API — 퇴직금 계산 엔드포인트.

모든 계산 로직은 severance_pay.py 에 위치함.
이 파일은 입력 검증 + 타입 변환 + whitelist 래퍼만 담당.

엔드포인트
----------
  calculate_severance_preview   퇴직금 사전 계산 (wage_records 포함)
  estimate_irp_preview          IRP 의무이체 사전 확인
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import frappe

from hrms.regional.south_korea import severance_pay as _severance_core
from hrms.regional.south_korea.severance_pay import (
    calculate_average_wage,
    calculate_severance_pay,
    estimate_irp_contribution,
)

DATE_FMT = "%Y-%m-%d"


# ---------------------------------------------------------------------------
# 내부 헬퍼 (korea_integration.py 스타일 통일)
# ---------------------------------------------------------------------------

def _as_float(value: Any, label: str = "value") -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        frappe.throw(f"{label}은(는) 숫자여야 합니다: {value!r}")
        raise RuntimeError("frappe.throw returned unexpectedly")


def _parse_date(value: Any, label: str) -> dt.date:
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.datetime):
        return value.date()
    try:
        return dt.datetime.strptime(str(value), DATE_FMT).date()
    except (TypeError, ValueError):
        frappe.throw(f"{label}은(는) YYYY-MM-DD 형식이어야 합니다: {value!r}")
        raise RuntimeError("frappe.throw returned unexpectedly")


def _require_keys(payload: Any, required_keys: set[str], label: str) -> None:
    if not isinstance(payload, dict):
        frappe.throw(f"{label}은(는) 객체여야 합니다")
    missing = [k for k in sorted(required_keys) if k not in payload or payload[k] in (None, "")]
    if missing:
        frappe.throw(f"{label}에 필수 필드가 없습니다: {', '.join(missing)}")


def _reject_unknown_keys(payload: Any, allowed_keys: set[str], label: str) -> None:
    if not isinstance(payload, dict):
        frappe.throw(f"{label}은(는) 객체여야 합니다")
    unknown = sorted(set(payload) - allowed_keys)
    if unknown:
        frappe.throw(f"{label}에 허용되지 않는 필드가 있습니다: {', '.join(unknown)}")


def _coerce_payload(payload: dict | None, kwargs: dict) -> dict:
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


def _parse_wage_records(raw: Any, label: str = "wage_records") -> list[dict[str, Any]]:
    """wage_records JSON 배열 파싱 및 검증."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            frappe.throw(f"{label}은(는) 유효한 JSON 배열이어야 합니다")
    if not isinstance(raw, list):
        frappe.throw(f"{label}은(는) 배열이어야 합니다")
    parsed = []
    for i, item in enumerate(raw):
        _require_keys(item, {"date", "amount"}, f"{label}[{i}]")
        _reject_unknown_keys(item, {"date", "amount", "wage_type"}, f"{label}[{i}]")
        parsed.append(
            {
                "date": _parse_date(item["date"], f"{label}[{i}].date"),
                "amount": _as_float(item["amount"], f"{label}[{i}].amount"),
                "wage_type": str(item.get("wage_type", "base")),
            }
        )
    return parsed


def _parse_exclusions(raw: Any, label: str = "exclusions") -> list[tuple[dt.date, dt.date]]:
    """exclusions JSON 배열 파싱.

    각 항목: {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            frappe.throw(f"{label}은(는) 유효한 JSON 배열이어야 합니다")
    if not isinstance(raw, list):
        frappe.throw(f"{label}은(는) 배열이어야 합니다")
    result = []
    for i, item in enumerate(raw):
        _require_keys(item, {"from", "to"}, f"{label}[{i}]")
        start = _parse_date(item["from"], f"{label}[{i}].from")
        end = _parse_date(item["to"], f"{label}[{i}].to")
        if start > end:
            frappe.throw(f"{label}[{i}]: from({start}) > to({end}) 는 허용되지 않습니다")
        result.append((start, end))
    return result


# ---------------------------------------------------------------------------
# PWA 사이트 어댑터 (KoreaSeverancePreview 프론트 계약)
# ---------------------------------------------------------------------------

# 프론트(koreaSeverancePreviewRuntime.js) 요청 계약
_EMPLOYEE_CONTRACT_KEYS = {"employee", "assumed_retirement_date", "ordinary_wage_override"}
# frappe RPC 레이어가 varkw 함수에 흘려보낼 수 있는 표준 키 — 계약 판정에서 무시
_FRAPPE_STD_KEYS = {"cmd", "data", "ignore_permissions"}


def build_wage_records_from_salary_slips(slips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Salary Slip 행 → 코어 wage_records (framework-free 순수 함수).

    각 슬립을 wage_type "base" 1건으로: date=start_date, amount=gross_pay.
    """
    records = []
    for i, slip in enumerate(slips or []):
        records.append(
            {
                "date": _parse_date(slip.get("start_date"), f"slips[{i}].start_date"),
                "amount": _as_float(slip.get("gross_pay"), f"slips[{i}].gross_pay"),
                "wage_type": "base",
            }
        )
    return records


def map_severance_core_to_preview(
    *,
    hire_date: dt.date,
    assumed_retirement_date: dt.date,
    avg_result: dict[str, Any],
    sev_result: dict[str, Any],
    irp_result: dict[str, Any],
) -> dict[str, Any]:
    """코어 응답 → 프론트(KoreaSeverancePreview)가 읽는 키 (framework-free 순수 함수)."""
    return {
        "severance_pay": sev_result["severance_pay_amount"],
        "average_daily_wage": avg_result["average_wage_per_day"],
        "ordinary_daily_wage": sev_result.get("ordinary_wage_per_day"),
        "continuous_service_days": sev_result["continuous_service_days"],
        "date_of_joining": hire_date.isoformat(),
        "assumed_retirement_date": assumed_retirement_date.isoformat(),
        "formula_description": sev_result["calculation_formula"],
        "irp_transfer_amount": irp_result["irp_transfer_amount"],
        # 코어에는 별도 '이체 한도' 개념이 없어 법정 의무이체 기준액(300만원)을 매핑
        "irp_transfer_limit": irp_result["irp_mandatory_threshold"],
    }


def _check_employee_scope(employee: str) -> None:
    """본인(session user 의 Employee) 또는 HR Manager 만 허용. 그 외 PermissionError."""
    user = getattr(getattr(frappe, "session", None), "user", None)
    if user == "Administrator":
        return
    roles: set[str] = set()
    get_roles = getattr(frappe, "get_roles", None)
    if callable(get_roles):
        roles = set(get_roles(user) if user else get_roles())
    if "HR Manager" in roles or "System Manager" in roles:
        return
    own_employee = frappe.db.get_value("Employee", {"user_id": user}, "name") if user else None
    if own_employee and own_employee == employee:
        return
    exc = getattr(frappe, "PermissionError", PermissionError)
    raise exc("본인 퇴직금만 미리볼 수 있습니다 (HR Manager 제외)")


def _calculate_severance_preview_for_employee(payload: dict[str, Any]) -> dict[str, Any]:
    """프론트 계약 {employee, assumed_retirement_date, ordinary_wage_override} 처리.

    Employee.date_of_joining + 퇴직 가정일 직전 3개월 Salary Slip(gross_pay)로
    wage_records 를 구성해 기존 순수 계산 코어에 위임한다.
    ordinary_wage_override 는 **1일 통상임금** 정의 그대로 전달 (임의 월액 변환 금지).
    """
    payload = {k: v for k, v in payload.items() if k not in _FRAPPE_STD_KEYS}
    _require_keys(payload, {"employee", "assumed_retirement_date"}, "payload")
    _reject_unknown_keys(payload, _EMPLOYEE_CONTRACT_KEYS, "payload")

    employee = str(payload["employee"]).strip()
    _check_employee_scope(employee)

    assumed_retirement_date = _parse_date(payload["assumed_retirement_date"], "assumed_retirement_date")

    joining_raw = frappe.db.get_value("Employee", employee, "date_of_joining")
    if not joining_raw:
        frappe.throw(f"직원 {employee}의 입사일(date_of_joining)이 없어 계산할 수 없습니다")
    hire_date = _parse_date(joining_raw, "date_of_joining")
    if assumed_retirement_date <= hire_date:
        frappe.throw("가정 퇴직일은 입사일 이후여야 합니다")

    # 퇴직 가정일 직전 3개월 창(start_date 기준) — 코어와 동일한 calendar 역산
    window_start = _severance_core._three_months_before(assumed_retirement_date)
    window_end = assumed_retirement_date - dt.timedelta(days=1)
    slips = frappe.get_all(
        "Salary Slip",
        filters={
            "employee": employee,
            "docstatus": ["in", [0, 1]],
            "start_date": ["between", [window_start.isoformat(), window_end.isoformat()]],
        },
        fields=["start_date", "gross_pay"],
        order_by="start_date desc",
    )
    if not slips:
        frappe.throw("급여 이력이 없어 계산할 수 없습니다")

    wage_records = build_wage_records_from_salary_slips([dict(s) for s in slips])

    ordinary_wage_per_day: float | None = None
    if payload.get("ordinary_wage_override") not in (None, "", 0, "0", "null"):
        ordinary_wage_per_day = _as_float(payload["ordinary_wage_override"], "ordinary_wage_override")

    avg_result = calculate_average_wage(
        severance_date=assumed_retirement_date,
        wage_records=wage_records,
        hire_date=hire_date,
    )
    sev_result = calculate_severance_pay(
        hire_date=hire_date,
        severance_date=assumed_retirement_date,
        average_wage_per_day=avg_result["average_wage_per_day"],
        ordinary_wage_per_day=ordinary_wage_per_day,
    )
    irp_result = estimate_irp_contribution(sev_result["severance_pay_amount"])

    return map_severance_core_to_preview(
        hire_date=hire_date,
        assumed_retirement_date=assumed_retirement_date,
        avg_result=avg_result,
        sev_result=sev_result,
        irp_result=irp_result,
    )


# ---------------------------------------------------------------------------
# Whitelist 엔드포인트
# ---------------------------------------------------------------------------

@frappe.whitelist()
def calculate_severance_preview(
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """퇴직금 사전 계산 API.

    Request payload keys:
        hire_date             str  YYYY-MM-DD  입사일
        severance_date        str  YYYY-MM-DD  퇴직일 (마지막 근무일 + 1)
        wage_records          list             임금 내역 배열
        ordinary_wage_per_day float (optional) 1일 통상임금
        exclusions            list  (optional) 제외 기간 배열
        period_days           int  (optional)  평균임금 산정 총일수 override

    wage_records 항목:
        date      str   YYYY-MM-DD
        amount    float 금액 (원)
        wage_type str   "base" | "allowance" | "bonus" | "annual_leave"
                        (생략 시 "base" 처리)
                        "bonus" / "annual_leave" 는 연간 금액 → 3/12 분할 산입

    exclusions 항목:
        from  str  YYYY-MM-DD  시작일 (포함)
        to    str  YYYY-MM-DD  종료일 (포함)

    Response:
        average_wage_result   dict  calculate_average_wage 반환값
        severance_result      dict  calculate_severance_pay 반환값
    """
    payload = _coerce_payload(payload, kwargs)

    # PWA 사이트 어댑터 분기: 프론트는 {employee, assumed_retirement_date,
    # ordinary_wage_override} 계약으로 호출한다. 기존 payload 계약(hire_date 등)은
    # 아래 기존 경로 그대로 유지 (비파괴).
    if isinstance(payload, dict) and "employee" in payload and "hire_date" not in payload:
        return _calculate_severance_preview_for_employee(payload)

    _require_keys(payload, {"hire_date", "severance_date", "wage_records"}, "payload")
    _reject_unknown_keys(
        payload,
        {"hire_date", "severance_date", "wage_records", "ordinary_wage_per_day", "exclusions", "period_days"},
        "payload",
    )

    hire_date = _parse_date(payload["hire_date"], "hire_date")
    severance_date = _parse_date(payload["severance_date"], "severance_date")

    if severance_date <= hire_date:
        frappe.throw("severance_date는 hire_date 이후여야 합니다")

    wage_records = _parse_wage_records(payload["wage_records"])
    exclusions = _parse_exclusions(payload.get("exclusions"))

    ordinary_wage_per_day: float | None = None
    if payload.get("ordinary_wage_per_day") not in (None, "", 0):
        ordinary_wage_per_day = _as_float(payload["ordinary_wage_per_day"], "ordinary_wage_per_day")

    period_days: int | None = None
    if payload.get("period_days") not in (None, ""):
        try:
            period_days = int(payload["period_days"])
        except (TypeError, ValueError):
            frappe.throw("period_days는 정수여야 합니다")

    avg_result = calculate_average_wage(
        severance_date=severance_date,
        wage_records=wage_records,
        period_days=period_days,
        hire_date=hire_date,
        exclusions=exclusions,
    )

    sev_result = calculate_severance_pay(
        hire_date=hire_date,
        severance_date=severance_date,
        average_wage_per_day=avg_result["average_wage_per_day"],
        ordinary_wage_per_day=ordinary_wage_per_day,
        exclusions=exclusions,
    )

    return {
        "average_wage_result": avg_result,
        "severance_result": sev_result,
    }


@frappe.whitelist()
def estimate_irp_preview(
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """IRP 의무이체 사전 확인 API.

    Request payload keys:
        severance_pay_amount   float  퇴직금 총액
        irp_account_required   bool   (optional, 기본 True)

    Response:
        dict  estimate_irp_contribution 반환값
    """
    payload = _coerce_payload(payload, kwargs)
    _require_keys(payload, {"severance_pay_amount"}, "payload")
    _reject_unknown_keys(payload, {"severance_pay_amount", "irp_account_required"}, "payload")

    amount = _as_float(payload["severance_pay_amount"], "severance_pay_amount")

    irp_required = True
    if "irp_account_required" in payload:
        v = payload["irp_account_required"]
        if isinstance(v, bool):
            irp_required = v
        elif isinstance(v, str):
            irp_required = v.strip().lower() in {"1", "true", "yes", "y"}
        else:
            irp_required = bool(v)

    return estimate_irp_contribution(amount, irp_required)
