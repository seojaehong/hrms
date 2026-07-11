"""휴직 처리 코어 — framework-free.

법적 근거:
- 남녀고용평등법 19조: 육아휴직 (2026년 기준 최대 18개월로 확대)
- 근기법 74조: 산전·산후 휴가 (90일, 유급)
- 근기법 60조: 연차유급휴가
- 근기법 78조 이하: 업무상 재해 (산재)
- 근기법 51조 / 동법 시행령 2조: 휴직 기간 평균임금 산정 제외

No frappe dependency. Raise ValueError for invalid inputs.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

# ---------------------------------------------------------------------------
# 휴직 유형 정의
# ---------------------------------------------------------------------------

LEAVE_TYPES: dict[str, dict[str, Any]] = {
    "childcare": {
        "name": "육아휴직",
        "law": "남녀고용평등법 19조",
        "max_months": 18,          # 2026년 기준 (이전 12개월 → 18개월 확대)
        "max_days": None,
        "paid": True,              # 고용보험 육아휴직급여 (사업주가 직접 지급 아님)
        "pension_continuation": True,   # 국민연금 사업주 부담 계속
        "pension_employee_deferred": True,  # 본인 부담 납부예외 신청 가능
        "health_insurance_continuation": True,
        "employment_insurance_continues": True,
        "industrial_accident_insurance_continues": True,
        "notes": "육아휴직급여는 고용보험에서 지급. 사업주는 국민연금 사용자 부담분(4.5%) 납부 계속.",
    },
    "maternity": {
        "name": "산전·산후 휴가",
        "law": "근기법 74조",
        "max_months": None,
        "max_days": 90,            # 다태아 120일
        "paid": True,              # 최초 60일 사업주 부담, 이후 고용보험
        "pension_continuation": True,
        "pension_employee_deferred": False,
        "health_insurance_continuation": True,
        "employment_insurance_continues": True,
        "industrial_accident_insurance_continues": True,
        "notes": "최초 60일 사업주 유급, 61-90일은 고용보험 출산전후휴가급여. 4대보험 모두 유지.",
    },
    "sick_paid": {
        "name": "유급 병가",
        "law": "취업규칙/단체협약",
        "max_months": None,
        "max_days": None,          # 회사 규정에 따름
        "paid": True,
        "pension_continuation": True,
        "pension_employee_deferred": False,
        "health_insurance_continuation": True,
        "employment_insurance_continues": True,
        "industrial_accident_insurance_continues": True,
        "notes": "유급 병가 중 4대보험 정상 유지. 법정 의무 아닌 취업규칙 적용.",
    },
    "sick_unpaid": {
        "name": "무급 병가",
        "law": "취업규칙/단체협약",
        "max_months": None,
        "max_days": None,
        "paid": False,
        "pension_continuation": False,  # 납부예외 신청 가능 (국민연금법 91조)
        "pension_employee_deferred": True,
        "health_insurance_continuation": True,  # 직장가입자 자격 유지, 보험료 경감 가능
        "employment_insurance_continues": True,
        "industrial_accident_insurance_continues": True,
        "notes": "무급 병가 중 국민연금 납부예외 신청 가능. 건강보험은 직장가입자 자격 유지 (경감 신청 가능).",
    },
    "personal": {
        "name": "기타 무급휴직",
        "law": "근로기준법/취업규칙",
        "max_months": None,
        "max_days": None,
        "paid": False,
        "pension_continuation": False,  # 납부예외 신청 가능
        "pension_employee_deferred": True,
        "health_insurance_continuation": True,   # 직장가입자 자격 유지
        "employment_insurance_continues": True,
        "industrial_accident_insurance_continues": True,
        "notes": "무급휴직 중 국민연금 납부예외, 건강보험 직장가입자 자격 유지.",
    },
}

# 4대보험 요율 — statutory_2026 단일소스 (연도별 하드코딩 혼재 사고 방지)
def _load_statutory_2026():
    import importlib.util as _ilu
    import pathlib as _pl

    path = _pl.Path(__file__).resolve().parent / "statutory_2026.py"
    spec = _ilu.spec_from_file_location("korea_statutory_2026", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_STAT = _load_statutory_2026()

PENSION_EMPLOYER_RATE = _STAT.PENSION_RATE_EMPLOYER  # 국민연금 사용자 부담 (2026: 4.75%)
PENSION_EMPLOYEE_RATE = _STAT.PENSION_RATE_EMPLOYEE  # 국민연금 근로자 부담 (2026: 4.75%)
HEALTH_INSURANCE_EMPLOYER_RATE = _STAT.HEALTH_RATE_EMPLOYER  # 건강보험 사용자 부담 (2026: 3.595%)

# 육아휴직급여 구간 (leave_month_index 기준)
_CHILDCARE_BENEFIT_TIERS = [
    # (start_month, end_month, rate, cap, floor)
    (1,  3,  0.80, 2_500_000, 700_000),
    (4,  6,  0.50, 2_000_000, 0),
    (7,  12, 0.50, 1_600_000, 0),
    (13, 18, 0.50, 1_600_000, 0),   # 2026년 확대
]


# ---------------------------------------------------------------------------
# 공개 함수
# ---------------------------------------------------------------------------

def request_leave_of_absence(
    *,
    employee: str,
    leave_type: str,
    start_date: dt.date,
    end_date: dt.date | None,
    reason: str,
    human_approved: bool = False,
) -> dict[str, Any]:
    """휴직 신청.

    접수는 즉시 처리(immediate). 승인은 별도 approve_leave_of_absence()에서.
    human_approved=False가 기본이므로 신청만으로 자동 승인되지 않음.

    Args:
        employee: 직원 ID
        leave_type: LEAVE_TYPES 키 중 하나
        start_date: 휴직 시작일
        end_date: 휴직 종료일 (None = 미정)
        reason: 신청 사유
        human_approved: 신청과 동시에 승인 여부 (일반적으로 False)

    Returns:
        {
            "request_id": str,
            "employee": str,
            "leave_type": str,
            "leave_type_name": str,
            "law_basis": str,
            "start_date": str,
            "end_date": str | None,
            "status": "pending" | "approved",
            "duration_days": int | None,
            "reason": str,
            "notes": str,
        }
    """
    _validate_leave_type(leave_type)
    _validate_employee(employee)
    _validate_reason(reason)

    if end_date is not None and end_date < start_date:
        raise ValueError(f"end_date({end_date}) must be >= start_date({start_date})")

    type_def = LEAVE_TYPES[leave_type]
    duration_days: int | None = None

    if end_date is not None:
        duration_days = (end_date - start_date).days + 1
        _validate_duration(leave_type, type_def, duration_days, start_date, end_date)

    request_id = f"LOA-{uuid.uuid4().hex[:8].upper()}"
    status = "approved" if human_approved else "pending"

    return {
        "request_id": request_id,
        "employee": employee,
        "leave_type": leave_type,
        "leave_type_name": type_def["name"],
        "law_basis": type_def["law"],
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat() if end_date is not None else None,
        "status": status,
        "duration_days": duration_days,
        "reason": reason,
        "notes": type_def["notes"],
    }


def approve_leave_of_absence(
    *,
    request_id: str,
    approver: str,
    human_approved: bool,
) -> dict[str, Any]:
    """휴직 승인.

    human_approved=True 여야만 승인 처리됨. 미승인 시 ValueError.

    Args:
        request_id: request_leave_of_absence()가 반환한 request_id
        approver: 승인자 ID 또는 이름
        human_approved: True 여야 승인 완료

    Returns:
        {
            "request_id": str,
            "approver": str,
            "status": "approved" | "rejected",
            "approved_at": str,  # ISO datetime
        }
    """
    if not request_id or not isinstance(request_id, str):
        raise ValueError("request_id must be a non-empty string")
    if not approver or not isinstance(approver, str):
        raise ValueError("approver must be a non-empty string")
    if not isinstance(human_approved, bool):
        raise ValueError("human_approved must be a boolean")
    if not human_approved:
        raise ValueError(
            "human_approved must be True to approve leave of absence. "
            "휴직 승인은 반드시 담당자가 직접 확인 후 human_approved=True 로 호출해야 합니다."
        )

    return {
        "request_id": request_id,
        "approver": approver,
        "status": "approved",
        "approved_at": dt.datetime.now().isoformat(sep=" "),
    }


def calculate_insurance_during_leave(
    *,
    leave_type: str,
    leave_start_date: dt.date,
    leave_end_date: dt.date,
    monthly_base_salary: float,
) -> dict[str, Any]:
    """휴직 기간 4대보험 변동 계산.

    Args:
        leave_type: LEAVE_TYPES 키
        leave_start_date: 휴직 시작일
        leave_end_date: 휴직 종료일
        monthly_base_salary: 월 기본급 (원)

    Returns:
        {
            "pension_continues": bool,
            "pension_employer_payment": float,   # 사업주가 납부해야 할 금액 (0 = 납부예외)
            "pension_employee_deferred": bool,   # 본인 부담 납부예외 여부
            "health_insurance_continues": bool,
            "health_insurance_employer_payment": float,
            "employment_insurance_continues": bool,
            "industrial_accident_insurance_continues": bool,
            "notes": str,
        }
    """
    _validate_leave_type(leave_type)
    if leave_end_date < leave_start_date:
        raise ValueError("leave_end_date must be >= leave_start_date")
    if monthly_base_salary < 0:
        raise ValueError("monthly_base_salary must be >= 0")

    type_def = LEAVE_TYPES[leave_type]
    pension_continues = type_def["pension_continuation"]
    pension_employee_deferred = type_def["pension_employee_deferred"]
    health_insurance_continues = type_def["health_insurance_continuation"]

    # 국민연금 사업주 부담: 납부예외 대상이면 0, 아니면 기본급의 4.5%
    if pension_continues:
        pension_employer_payment = round(monthly_base_salary * PENSION_EMPLOYER_RATE)
    else:
        pension_employer_payment = 0.0

    # 건강보험 사업주 부담: 계속 유지이면 계산, 아니면 0
    if health_insurance_continues:
        health_insurance_employer_payment = round(monthly_base_salary * HEALTH_INSURANCE_EMPLOYER_RATE)
    else:
        health_insurance_employer_payment = 0.0

    return {
        "pension_continues": pension_continues,
        "pension_employer_payment": pension_employer_payment,
        "pension_employee_deferred": pension_employee_deferred,
        "health_insurance_continues": health_insurance_continues,
        "health_insurance_employer_payment": health_insurance_employer_payment,
        "employment_insurance_continues": type_def["employment_insurance_continues"],
        "industrial_accident_insurance_continues": type_def["industrial_accident_insurance_continues"],
        "notes": type_def["notes"],
    }


def calculate_childcare_benefit(
    *,
    monthly_base_salary: float,
    leave_month_index: int,
) -> dict[str, Any]:
    """육아휴직급여 계산 (고용보험법 기준, 2026년).

    구간별 급여:
    - 1-3개월:  통상임금의 80%, 상한 250만원, 하한 70만원
    - 4-6개월:  통상임금의 50%, 상한 200만원
    - 7-12개월: 통상임금의 50%, 상한 160만원
    - 13-18개월: 통상임금의 50%, 상한 160만원 (2026년 확대)

    Args:
        monthly_base_salary: 월 통상임금 (원)
        leave_month_index: 육아휴직 시작으로부터의 월 순번 (1부터)

    Returns:
        {
            "leave_month_index": int,
            "rate": float,           # 적용 비율 (0~1)
            "cap": int,              # 상한액 (원)
            "floor": int,            # 하한액 (원, 해당 없으면 0)
            "gross_benefit": float,  # 비율 적용 후 금액
            "benefit_amount": float, # 상/하한 적용 후 최종 지급액
            "tier_name": str,
        }
    """
    if monthly_base_salary < 0:
        raise ValueError("monthly_base_salary must be >= 0")
    if not isinstance(leave_month_index, int) or leave_month_index < 1:
        raise ValueError("leave_month_index must be a positive integer (1 or greater)")
    if leave_month_index > 18:
        raise ValueError(
            f"leave_month_index={leave_month_index} exceeds maximum育아휴직 기간 18개월 (2026년 기준)"
        )

    for start_m, end_m, rate, cap, floor in _CHILDCARE_BENEFIT_TIERS:
        if start_m <= leave_month_index <= end_m:
            gross_benefit = monthly_base_salary * rate
            benefit_amount = min(cap, max(floor, gross_benefit))
            tier_name = f"{start_m}~{end_m}개월 구간"
            return {
                "leave_month_index": leave_month_index,
                "rate": rate,
                "cap": cap,
                "floor": floor,
                "gross_benefit": round(gross_benefit),
                "benefit_amount": round(benefit_amount),
                "tier_name": tier_name,
            }

    # 도달 불가 (위 범위 검증에서 이미 처리됨)
    raise ValueError(f"leave_month_index={leave_month_index} is out of all defined tiers")


def adjust_average_wage_for_leave(
    *,
    severance_calculation_period: tuple[dt.date, dt.date],
    leave_periods: list[tuple[dt.date, dt.date]],
) -> dict[str, Any]:
    """퇴직금 평균임금 산정 시 휴직 기간 제외 (근기법 시행령 2조).

    퇴직 전 3개월간 평균임금 산정 시, 해당 기간 중 겹치는 휴직 기간을
    제외하여 실제 근무일 기준으로 조정.

    Args:
        severance_calculation_period: (시작일, 종료일) — 일반적으로 퇴직일 전 3개월
        leave_periods: 제외해야 할 휴직 기간 목록 [(시작, 종료), ...]

    Returns:
        {
            "original_start": str,
            "original_end": str,
            "original_days": int,
            "excluded_leave_days": int,       # 겹치는 휴직 일수
            "effective_days": int,            # 원래 기간 - 제외 일수
            "excluded_periods": list[dict],   # 제외된 각 구간 상세
            "law_basis": str,
        }
    """
    calc_start, calc_end = severance_calculation_period
    if calc_end < calc_start:
        raise ValueError("severance_calculation_period: end must be >= start")

    original_days = (calc_end - calc_start).days + 1
    excluded_leave_days = 0
    excluded_periods: list[dict[str, Any]] = []

    for leave_start, leave_end in leave_periods:
        if leave_end < leave_start:
            raise ValueError(f"leave period end ({leave_end}) must be >= start ({leave_start})")
        # 겹치는 구간 계산
        overlap_start = max(calc_start, leave_start)
        overlap_end = min(calc_end, leave_end)
        if overlap_start <= overlap_end:
            overlap_days = (overlap_end - overlap_start).days + 1
            excluded_leave_days += overlap_days
            excluded_periods.append({
                "leave_start": leave_start.isoformat(),
                "leave_end": leave_end.isoformat(),
                "overlap_start": overlap_start.isoformat(),
                "overlap_end": overlap_end.isoformat(),
                "overlap_days": overlap_days,
            })

    effective_days = original_days - excluded_leave_days

    return {
        "original_start": calc_start.isoformat(),
        "original_end": calc_end.isoformat(),
        "original_days": original_days,
        "excluded_leave_days": excluded_leave_days,
        "effective_days": effective_days,
        "excluded_periods": excluded_periods,
        "law_basis": "근로기준법 시행령 2조 (평균임금 산정 제외 기간)",
    }


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _validate_leave_type(leave_type: str) -> None:
    if leave_type not in LEAVE_TYPES:
        allowed = ", ".join(sorted(LEAVE_TYPES))
        raise ValueError(f"leave_type must be one of: {allowed}. Got: {leave_type!r}")


def _validate_employee(employee: str) -> None:
    if not employee or not isinstance(employee, str) or not employee.strip():
        raise ValueError("employee must be a non-empty string")


def _validate_reason(reason: str) -> None:
    if not reason or not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be a non-empty string")


def _calendar_month_diff(start: dt.date, end: dt.date) -> float:
    """두 날짜 사이 달력 기준 개월 수 (소수점 포함, 시작일 포함 기준)."""
    years = end.year - start.year
    months = end.month - start.month
    day_diff = end.day - start.day
    total_months = years * 12 + months + day_diff / 30.0
    return total_months


def _validate_duration(
    leave_type: str,
    type_def: dict[str, Any],
    duration_days: int,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
) -> None:
    """최대 기간 초과 여부 검증.

    max_days 기준은 일수 직접 비교.
    max_months 기준은 실제 달력 개월 수 비교 (30일 근사값 아닌 연월 계산).
    """
    max_days = type_def.get("max_days")
    max_months = type_def.get("max_months")

    if max_days is not None and duration_days > max_days:
        raise ValueError(
            f"{type_def['name']} 최대 기간 {max_days}일 초과: 신청 기간 {duration_days}일 "
            f"({type_def['law']})"
        )

    if max_months is not None and start_date is not None and end_date is not None:
        # 달력 기준: start_date 에서 max_months 더한 날짜와 비교
        # 예: 2026-01-01 + 18개월 = 2027-07-01 → end_date < 2027-07-01 이어야 함
        month = start_date.month - 1 + max_months
        target_year = start_date.year + month // 12
        target_month = month % 12 + 1
        import calendar as _cal
        max_day = min(start_date.day, _cal.monthrange(target_year, target_month)[1])
        deadline = dt.date(target_year, target_month, max_day)
        if end_date > deadline:
            raise ValueError(
                f"{type_def['name']} 최대 기간 {max_months}개월 초과: "
                f"신청 종료일({end_date.isoformat()})이 최대 허용일({deadline.isoformat()})을 넘습니다 "
                f"({type_def['law']})"
            )
    elif max_months is not None:
        # start/end 없을 때 30일 근사
        max_days_from_months = max_months * 30
        if duration_days > max_days_from_months:
            raise ValueError(
                f"{type_def['name']} 최대 기간 {max_months}개월({max_days_from_months}일) 초과: "
                f"신청 기간 {duration_days}일 ({type_def['law']})"
            )
