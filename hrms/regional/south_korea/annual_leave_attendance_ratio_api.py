"""Frappe-facing preview API — 근기법 60조 4항 출근률 80% 연차 감액.

이 모듈은 preview-only: 데이터 저장·제출·Frappe 문서 변경 없이
출근률을 반영한 연차 계산 초안(draft payload)만 반환한다.
Frappe bench 내에서는 whitelist 함수로 등록되고,
직접 파일 실행(bench 없이 테스트)에서도 동작한다.

사용 예:
    # Frappe API 호출
    frappe.call('hrms.regional.south_korea.annual_leave_attendance_ratio_api.preview_korea_annual_leave_with_ratio',
        employee={"name": "EMP-001", "date_of_joining": "2020-01-01"},
        as_of_date="2026-01-01",
        attendance_ratio=0.75,
    )
"""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only inside a Frappe bench
    import frappe  # type: ignore
except ImportError:  # pragma: no cover - direct-run no-bench mode
    frappe = None  # type: ignore


def _whitelist(fn):
    if frappe is None:
        return fn
    return frappe.whitelist()(fn)


@_whitelist
def preview_korea_annual_leave_with_ratio(
    *,
    employee: Any,
    as_of_date: Any,
    attendance_ratio: Any = None,
    threshold: Any = 0.8,
    basis: str = "Hire Date",
    fiscal_year_start_month: Any = 1,
    fiscal_year_start_day: Any = 1,
    existing_allocated_days: Any = 0,
) -> dict[str, Any]:
    """출근률 80% 룰을 적용한 연차 계산 preview (side-effect-free).

    Args:
        employee: 직원 정보 dict 또는 JSON 문자열.
            필수 키: name (직원 ID), date_of_joining (입사일 ISO 문자열).
            선택 키: employee_name, company, relieving_date.
        as_of_date: 계산 기준일 (ISO 문자열 또는 datetime.date).
        attendance_ratio: 출근률 0.0~1.0 (None이면 pass-through).
        threshold: 출근률 기준 임계값 (기본값 0.8).
        basis: "Hire Date" 또는 "Fiscal Year".
        fiscal_year_start_month: 회계연도 시작 월 (정수, 기본값 1).
        fiscal_year_start_day: 회계연도 시작 일 (정수, 기본값 1).
        existing_allocated_days: 이미 부여된 연차일수 (참고용, 반환 payload에 포함).

    Returns:
        dict:
            contract_type: "korea_annual_leave_attendance_ratio_preview_v1"
            runtime_action: "preview_only"
            requires_runtime_apply: True
            draft: calculate_with_attendance_ratio() 반환값
            meta: 입력 요약
    """
    ratio_module = _load_sibling_module(
        "annual_leave_attendance_ratio.py", "korea_annual_leave_attendance_ratio"
    )

    employee_dict = _coerce_mapping(employee, "employee")
    as_of_date_parsed = _coerce_date_str(as_of_date, "as_of_date")
    ratio_parsed = _coerce_optional_ratio(attendance_ratio, "attendance_ratio")
    threshold_parsed = _coerce_float_range(threshold, "threshold", 0.0, 1.0)
    fsm = _coerce_int(fiscal_year_start_month, "fiscal_year_start_month")
    fsd = _coerce_int(fiscal_year_start_day, "fiscal_year_start_day")

    import datetime as dt

    hire_date = _parse_iso_date(
        _require_text(employee_dict.get("date_of_joining"), "employee.date_of_joining"),
        "employee.date_of_joining",
    )
    as_of_dt = _parse_iso_date(as_of_date_parsed, "as_of_date")
    employment_end_date = _optional_iso_date(
        employee_dict.get("relieving_date") or employee_dict.get("employment_end_date"),
        "employee.relieving_date",
    )

    draft = ratio_module.calculate_with_attendance_ratio(
        hire_date=hire_date,
        as_of_date=as_of_dt,
        attendance_ratio=ratio_parsed,
        threshold=threshold_parsed,
        basis=basis,
        fiscal_year_start_month=fsm,
        fiscal_year_start_day=fsd,
        employment_end_date=employment_end_date,
    )

    return {
        "contract_type": "korea_annual_leave_attendance_ratio_preview_v1",
        "runtime_action": "preview_only",
        "requires_runtime_apply": True,
        "draft": deepcopy(draft),
        "meta": {
            "employee": employee_dict.get("name"),
            "as_of_date": as_of_date_parsed,
            "attendance_ratio": ratio_parsed,
            "threshold": threshold_parsed,
            "basis": basis,
            "existing_allocated_days": existing_allocated_days,
        },
    }


# ---------------------------------------------------------------------------
# Coercion helpers (framework-free)
# ---------------------------------------------------------------------------

def _coerce_mapping(value: Any, fieldname: str) -> dict[str, Any]:
    coerced = _coerce_json_if_needed(value)
    if not isinstance(coerced, dict):
        raise ValueError(f"{fieldname} must be a dict or JSON object")
    return deepcopy(coerced)


def _coerce_json_if_needed(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("JSON payload is invalid") from exc
    return value


def _coerce_int(value: Any, fieldname: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{fieldname} must be an integer")
    try:
        if isinstance(value, str):
            text = value.strip()
            if not text or "." in text:
                raise ValueError
            return int(text)
        if isinstance(value, int):
            return value
    except ValueError as exc:
        raise ValueError(f"{fieldname} must be an integer") from exc
    raise ValueError(f"{fieldname} must be an integer")


def _coerce_float_range(value: Any, fieldname: str, lo: float, hi: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{fieldname} must be a float")
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{fieldname} must be a float") from exc
    if v < lo or v > hi:
        raise ValueError(f"{fieldname} must be between {lo} and {hi}")
    return v


def _coerce_optional_ratio(value: Any, fieldname: str) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{fieldname} must be a float between 0.0 and 1.0, not bool")
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{fieldname} must be a float between 0.0 and 1.0") from exc
    if v < 0.0 or v > 1.0:
        raise ValueError(f"{fieldname} must be between 0.0 and 1.0 (got {v})")
    return v


def _coerce_date_str(value: Any, fieldname: str) -> str:
    import datetime as dt
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    return _require_text(value, fieldname)


def _require_text(value: Any, fieldname: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{fieldname} is required")
    return text


def _parse_iso_date(text: str, fieldname: str):
    import datetime as dt
    try:
        return dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{fieldname} must be a valid ISO date (YYYY-MM-DD)") from exc


def _optional_iso_date(value: Any, fieldname: str):
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    return _parse_iso_date(text, fieldname)


def _load_sibling_module(filename: str, module_name: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


__all__ = ["preview_korea_annual_leave_with_ratio"]
