"""Frappe whitelist preview for 근로기준법 56조 가산수당 계산기.

이 모듈은 overtime_premium.py의 순수 Python 계산기를 Frappe API로 노출합니다.
frappe.whitelist 데코레이터로 REST endpoint 등록.

Endpoints:
    calculate_daily_overtime_premium  — 하루 단위 계산
    calculate_weekly_overtime_aggregate — 주 단위 집계 + §53 한도 검증
    estimate_overtime_pay              — 금액 추정 (시급 기준)

모든 함수는 frappe.throw()를 통해 입력값 검증 오류를 반환합니다.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import frappe

from hrms.regional.south_korea.overtime_premium import (
    WorkSession,
    calculate_daily_premium,
    calculate_weekly_aggregate,
    estimate_premium_amount,
)

_DATE_FMT = "%Y-%m-%d"
_TIME_FMT = "%H:%M"
_TIME_FMT_SEC = "%H:%M:%S"


def _parse_date(value: str, field: str) -> dt.date:
    try:
        return dt.datetime.strptime(str(value).strip(), _DATE_FMT).date()
    except (ValueError, TypeError):
        frappe.throw(f"{field}는 YYYY-MM-DD 형식이어야 합니다. 받은 값: {value!r}")
        raise  # unreachable, satisfies type checkers


def _parse_time(value: str, field: str) -> dt.time:
    for fmt in (_TIME_FMT, _TIME_FMT_SEC):
        try:
            return dt.datetime.strptime(str(value).strip(), fmt).time()
        except (ValueError, TypeError):
            continue
    frappe.throw(f"{field}는 HH:MM 형식이어야 합니다. 받은 값: {value!r}")
    raise  # unreachable


def _parse_session(data: dict[str, Any]) -> WorkSession:
    """dict → WorkSession 변환 및 입력 검증."""
    required = {"employee", "work_date", "start_time", "end_time"}
    missing = sorted(required - set(data))
    if missing:
        frappe.throw(f"필수 필드 누락: {', '.join(missing)}")

    try:
        break_minutes = int(data.get("break_minutes", 0))
    except (ValueError, TypeError):
        frappe.throw("break_minutes는 정수여야 합니다.")
        raise

    return WorkSession(
        employee=str(data["employee"]),
        work_date=_parse_date(data["work_date"], "work_date"),
        start_time=_parse_time(data["start_time"], "start_time"),
        end_time=_parse_time(data["end_time"], "end_time"),
        break_minutes=max(0, break_minutes),
        is_holiday=bool(data.get("is_holiday", False)),
        is_weekly_off=bool(data.get("is_weekly_off", False)),
    )


@frappe.whitelist()
def calculate_daily_overtime_premium(
    employee: str,
    work_date: str,
    start_time: str,
    end_time: str,
    break_minutes: int = 0,
    is_holiday: bool = False,
    is_weekly_off: bool = False,
    standard_daily_hours: float = 8.0,
) -> dict[str, Any]:
    """하루 단위 가산수당 시간 분류 (Frappe whitelist).

    근로기준법 §56 기준으로 연장/야간/휴일/휴일초과 시간을 분류합니다.

    Args:
        employee: 직원 ID (Frappe Employee doctype name).
        work_date: 근무 기준일 (YYYY-MM-DD).
        start_time: 출근 시각 (HH:MM).
        end_time: 퇴근 시각 (HH:MM). 출근보다 이르면 익일 처리.
        break_minutes: 휴게시간 (분, 기본 0).
        is_holiday: 법정·약정 휴일 여부.
        is_weekly_off: 주휴일 여부.
        standard_daily_hours: 일 소정근로시간 (기본 8.0).

    Returns:
        calculate_daily_premium() 결과 dict.
    """
    session = _parse_session(
        {
            "employee": employee,
            "work_date": work_date,
            "start_time": start_time,
            "end_time": end_time,
            "break_minutes": break_minutes,
            "is_holiday": is_holiday,
            "is_weekly_off": is_weekly_off,
        }
    )
    return calculate_daily_premium(session, standard_daily_hours=float(standard_daily_hours))


@frappe.whitelist()
def calculate_weekly_overtime_aggregate(sessions_data: list[dict[str, Any]]) -> dict[str, Any]:
    """주 단위 연장근로 집계 + §53 12시간 한도 검증 (Frappe whitelist).

    Args:
        sessions_data: WorkSession 파라미터 dict의 리스트.
            각 항목은 calculate_daily_overtime_premium의 파라미터와 동일.

    Returns:
        calculate_weekly_aggregate() 결과 dict.
    """
    if not isinstance(sessions_data, list):
        frappe.throw("sessions_data는 배열이어야 합니다.")

    sessions = []
    for idx, item in enumerate(sessions_data):
        if not isinstance(item, dict):
            frappe.throw(f"sessions_data[{idx}]는 객체여야 합니다.")
        try:
            sessions.append(_parse_session(item))
        except Exception as exc:
            frappe.throw(f"sessions_data[{idx}] 파싱 오류: {exc}")

    return calculate_weekly_aggregate(sessions)


@frappe.whitelist()
def estimate_overtime_pay(
    employee: str,
    work_date: str,
    start_time: str,
    end_time: str,
    hourly_rate: float,
    break_minutes: int = 0,
    is_holiday: bool = False,
    is_weekly_off: bool = False,
    standard_daily_hours: float = 8.0,
) -> dict[str, Any]:
    """가산수당 금액 추정 (Frappe whitelist).

    Args:
        employee: 직원 ID.
        work_date: 근무 기준일 (YYYY-MM-DD).
        start_time: 출근 시각 (HH:MM).
        end_time: 퇴근 시각 (HH:MM).
        hourly_rate: 통상시급 (원).
        break_minutes: 휴게시간 (분).
        is_holiday: 휴일 여부.
        is_weekly_off: 주휴일 여부.
        standard_daily_hours: 일 소정근로시간 (기본 8.0).

    Returns:
        {
            "daily_breakdown": calculate_daily_premium() 결과,
            "pay_estimate": estimate_premium_amount() 결과,
        }
    """
    try:
        hourly_rate = float(hourly_rate)
    except (ValueError, TypeError):
        frappe.throw("hourly_rate는 숫자여야 합니다.")
        raise

    if hourly_rate <= 0:
        frappe.throw("hourly_rate는 양수여야 합니다.")

    session = _parse_session(
        {
            "employee": employee,
            "work_date": work_date,
            "start_time": start_time,
            "end_time": end_time,
            "break_minutes": break_minutes,
            "is_holiday": is_holiday,
            "is_weekly_off": is_weekly_off,
        }
    )

    daily = calculate_daily_premium(session, standard_daily_hours=float(standard_daily_hours))
    pay = estimate_premium_amount(daily, hourly_rate=hourly_rate)

    return {
        "daily_breakdown": daily,
        "pay_estimate": pay,
    }
