"""근기법 60조 4항 — 출근률 80% 기준 연차 감액 룰.

Framework-free. annual_leave.py 코어를 wrap해서 attendance_ratio를 받아
80% 미만이면 anniversary entitlement(15일+)를 0으로 만들고
monthly_accrual(월 1일, 최대 11일) 룰만 적용.

근거 조문 (근로기준법 제60조 제4항):
  사용자는 1년간 80퍼센트 이상 출근한 근로자에게 15일의 유급휴가를 주어야 한다.
  계속하여 근로한 기간이 1년 미만인 근로자 또는 1년간 80퍼센트 미만 출근한
  근로자에게는 1개월 개근 시 1일의 유급휴가를 주어야 한다.

핵심 규칙:
  - attendance_ratio >= 0.8 (threshold): 정상 연차 (anniversary 15일+)
  - attendance_ratio < 0.8: anniversary entitlement 부여 X, monthly_accrual(월차)만 적용
  - service_years < 1: attendance_ratio 무관, monthly_accrual만 (기존 로직과 동일)
"""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path
from typing import Any


def calculate_with_attendance_ratio(
    *,
    hire_date: dt.date,
    as_of_date: dt.date,
    attendance_ratio: float | None = None,
    threshold: float = 0.8,
    basis: str = "Hire Date",
    fiscal_year_start_month: int = 1,
    fiscal_year_start_day: int = 1,
    employment_end_date: dt.date | None = None,
) -> dict[str, Any]:
    """근기법 60조 4항 출근률 80% 룰을 적용한 연차 계산.

    ``annual_leave.calculate_annual_leave_entitlement``를 내부적으로 호출한 뒤
    attendance_ratio가 threshold 미만이면 anniversary 부여를 0으로 조정하고
    monthly_accrual(월차, 최대 11일)만 유효 연차로 인정한다.

    Args:
        hire_date: 입사일 (datetime.date).
        as_of_date: 계산 기준일 (datetime.date).
        attendance_ratio: 출근률 (0.0 ~ 1.0). None이면 pass-through — 조정 없이
            기존 calculate_annual_leave_entitlement 결과를 그대로 반환한다.
        threshold: 정상 연차 부여 기준 출근률 (기본값 0.8 = 80%).
            threshold 이상이면 정상 처리, 미만이면 월차 전환.
        basis: "Hire Date" 또는 "Fiscal Year".
        fiscal_year_start_month: 회계연도 시작 월 (1~12, 정수).
        fiscal_year_start_day: 회계연도 시작 일 (1~말일, 정수).
        employment_end_date: 퇴사일 (datetime.date | None).

    Returns:
        dict:
            base_entitlement (dict): 원본 annual_leave 출력 (날짜 필드 isoformat 직렬화).
            attendance_ratio (float | None): 입력받은 출근률.
            threshold (float): 적용된 임계값.
            below_threshold (bool): 출근률이 임계값 미만인지 여부.
            adjusted_annual_entitlement_days (float): 감액 후 anniversary 연차일수.
            adjusted_total_entitlement_days (float): 감액 후 총 연차일수.
            adjustment_reason (str | None): "below_attendance_threshold" 또는 None.

    Raises:
        ValueError: attendance_ratio가 0.0 미만이거나 1.0 초과인 경우.
        ValueError: attendance_ratio가 bool 타입인 경우.
        TypeError: hire_date / as_of_date가 datetime.date가 아닌 경우 (annual_leave 위임).
        ValueError: as_of_date < hire_date 등 annual_leave 검증 실패 시 (위임).

    Notes:
        - service_years >= 1 이고 attendance_ratio < threshold 인 경우:
          base monthly_accrual_days는 annual_leave 엔진에서 0을 반환하므로
          adjusted_total_entitlement_days = 0이 된다. 이는 법 조문대로
          "1년간 80% 미만 출근 시 월차 적용"이되, 연간 단위 계산에서
          월별 개근 여부는 별도 추적이 필요함을 의미한다. 본 함수는
          엔진 출력 기준으로 anniversary를 제거하는 데 집중하며,
          월별 개근 판정은 호출자 책임이다.
    """
    if attendance_ratio is not None:
        _validate_attendance_ratio(attendance_ratio)

    annual_leave = _load_sibling_module("annual_leave.py", "korea_annual_leave")
    base = annual_leave.calculate_annual_leave_entitlement(
        hire_date=hire_date,
        as_of_date=as_of_date,
        basis=basis,
        fiscal_year_start_month=fiscal_year_start_month,
        fiscal_year_start_day=fiscal_year_start_day,
        employment_end_date=employment_end_date,
    )

    # attendance_ratio가 None이면 pass-through (조정 없음)
    if attendance_ratio is None:
        return _build_result(
            base=base,
            attendance_ratio=None,
            threshold=threshold,
            below_threshold=False,
            adjusted_annual=base["annual_entitlement_days"],
            adjusted_total=base["total_entitlement_days"],
            adjustment_reason=None,
        )

    # service_years < 1이면 이미 monthly_accrual만 적용되어 있으므로 조정 불필요
    # (attendance_ratio 값에 관계없이 아래 분기에서 below_threshold=False 처리)
    service_years: int = base["service_years"]
    below_threshold = attendance_ratio < threshold

    if not below_threshold or service_years < 1:
        # 정상 처리: 기존 계산 유지
        return _build_result(
            base=base,
            attendance_ratio=attendance_ratio,
            threshold=threshold,
            below_threshold=below_threshold,
            adjusted_annual=base["annual_entitlement_days"],
            adjusted_total=base["total_entitlement_days"],
            adjustment_reason=None,
        )

    # 80% 미만 + service_years >= 1: anniversary entitlement를 0으로 감액
    # monthly_accrual은 service_years >= 1이면 annual_leave 엔진이 0을 반환하므로
    # adjusted_total = monthly_accrual_days + 0 = 0
    adjusted_annual = 0.0
    adjusted_total = round(base["monthly_accrual_days"] + adjusted_annual, 2)

    return _build_result(
        base=base,
        attendance_ratio=attendance_ratio,
        threshold=threshold,
        below_threshold=True,
        adjusted_annual=adjusted_annual,
        adjusted_total=adjusted_total,
        adjustment_reason="below_attendance_threshold",
    )


def _build_result(
    *,
    base: dict[str, Any],
    attendance_ratio: float | None,
    threshold: float,
    below_threshold: bool,
    adjusted_annual: float,
    adjusted_total: float,
    adjustment_reason: str | None,
) -> dict[str, Any]:
    return {
        "base_entitlement": _serialize_entitlement(base),
        "attendance_ratio": attendance_ratio,
        "threshold": threshold,
        "below_threshold": below_threshold,
        "adjusted_annual_entitlement_days": adjusted_annual,
        "adjusted_total_entitlement_days": adjusted_total,
        "adjustment_reason": adjustment_reason,
    }


def _serialize_entitlement(entitlement: dict[str, Any]) -> dict[str, Any]:
    """날짜 필드를 ISO 문자열로 직렬화하여 반환."""
    payload = dict(entitlement)
    for key in ("hire_date", "as_of_date", "employment_end_date", "period_start", "period_end"):
        if payload.get(key) is not None:
            payload[key] = payload[key].isoformat()
    return payload


def _validate_attendance_ratio(value: float) -> None:
    """attendance_ratio 유효성 검사."""
    if isinstance(value, bool):
        raise ValueError("attendance_ratio must be a float, not bool")
    if not isinstance(value, (int, float)):
        raise ValueError("attendance_ratio must be a float between 0.0 and 1.0")
    if value < 0.0:
        raise ValueError("attendance_ratio cannot be negative (got %s)" % value)
    if value > 1.0:
        raise ValueError("attendance_ratio cannot exceed 1.0 (got %s)" % value)


def _load_sibling_module(filename: str, module_name: str):
    """같은 디렉토리에 있는 Python 모듈을 동적으로 로드."""
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


__all__ = ["calculate_with_attendance_ratio"]
