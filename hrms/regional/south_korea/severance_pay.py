"""근로자퇴직급여보장법 8조 퇴직금 계산기. framework-free.

법적 근거
---------
- 근로자퇴직급여보장법 8조: 계속근로기간 1년에 대해 30일분 이상의 평균임금
- 근로기준법 2조 6호: 평균임금 = 사유 발생 이전 3개월 임금총액 / 그 기간 총일수
- 1일 평균임금이 1일 통상임금보다 낮으면 통상임금 사용

반올림 룰
---------
원단위 절사 (int() truncation).  모든 중간값은 float, 최종 퇴직금만 정수 반환.

wage_type 인식 목록
-------------------
  "base"                 기본급 및 고정 수당 (3개월 전액 산입)
  "allowance"            각종 수당 (3개월 전액 산입)
  "annual_leave"         연차수당 (annual 기준, 3/12 분할 산입)
  "bonus"                상여금   (annual 기준, 3/12 분할 산입)

  위 목록 이외 wage_type은 "base" 처리 (3개월 전액 산입).

산정 기간
---------
  period_start = severance_date - 3개월 (calendar month 기준)
  period_end   = severance_date - 1일 (마지막 산정일)
  total_days   = period_end - period_start + 1  ← 양쪽 포함

  주의: 3개월 계산은 relativedelta 없이 직접 calendar month 역산하여
        2월 말일 등 월말 엣지 케이스를 명시적으로 처리함.

exclusion 처리
--------------
  exclusion 기간과 재직 기간의 교집합만 차감.
  exclusion 기간 내 wage_records 항목도 산정에서 제외.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

# IRP 의무이체 기준: 근퇴법 17조 / 시행령 9조
# 과제 설명서의 55만원은 오기(誤記)로 판단, 법정 기준 300만원 적용.
IRP_MANDATORY_THRESHOLD = 3_000_000


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _three_months_before(d: dt.date) -> dt.date:
    """severance_date 로부터 정확히 3개월 전 날짜를 반환.

    예) 2024-10-01 → 2024-07-01
        2024-03-31 → 2023-12-31 (12월 31일 → 그대로)
        2024-05-31 → 2024-02-29 (leap) 또는 2024-02-28 (non-leap)
    """
    year = d.year
    month = d.month - 3
    if month <= 0:
        month += 12
        year -= 1
    # 해당 월의 말일을 초과하지 않도록 클램핑
    day = min(d.day, _days_in_month(year, month))
    return dt.date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    """주어진 연·월의 일수 반환."""
    if month == 12:
        return 31
    return (dt.date(year, month + 1, 1) - dt.date(year, month, 1)).days


def _clamp_overlap(
    excl_start: dt.date,
    excl_end: dt.date,
    range_start: dt.date,
    range_end: dt.date,
) -> int:
    """두 기간의 교집합 일수(포함). 교집합 없으면 0."""
    start = max(excl_start, range_start)
    end = min(excl_end, range_end)
    if start > end:
        return 0
    return (end - start).days + 1


def _is_in_exclusion(record_date: dt.date, exclusions: list[tuple[dt.date, dt.date]]) -> bool:
    """record_date 가 exclusion 범위 중 하나에 속하는지 확인."""
    for excl_start, excl_end in (exclusions or []):
        if excl_start <= record_date <= excl_end:
            return True
    return False


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def calculate_continuous_service_days(
    hire_date: dt.date,
    severance_date: dt.date,
    exclusions: list[tuple[dt.date, dt.date]] | None = None,
) -> int:
    """계속근로일수 계산.

    Parameters
    ----------
    hire_date:
        입사일.
    severance_date:
        퇴직일 (근퇴법 기준: 마지막 근무일 + 1).
        재직일수 = severance_date - hire_date (당일 불포함).
    exclusions:
        무단결근·휴직 등 계속근로에서 제외되는 기간 목록.
        각 튜플은 (시작일, 종료일) 양쪽 포함.

    Returns
    -------
    int:
        계속근로일수. 음수가 되는 경우 0 반환.
    """
    if severance_date <= hire_date:
        return 0

    total = (severance_date - hire_date).days  # 마지막 날(severance_date) 미포함

    for excl_start, excl_end in (exclusions or []):
        # 재직 기간: hire_date 포함 ~ severance_date - 1일 포함
        overlap = _clamp_overlap(excl_start, excl_end, hire_date, severance_date - dt.timedelta(days=1))
        total -= overlap

    return max(total, 0)


def calculate_average_wage(
    *,
    severance_date: dt.date,
    wage_records: list[dict[str, Any]],
    period_days: int | None = None,
    hire_date: dt.date | None = None,
    exclusions: list[tuple[dt.date, dt.date]] | None = None,
) -> dict[str, Any]:
    """평균임금 산정.

    산정 기간: severance_date 전날부터 역산 3개월.
    wage_type 별 산입 방식:
      - "annual_leave", "bonus": 연간 금액의 3/12 분할 산입 (date 범위 무관)
      - 그 외("base", "allowance" 등): date 가 산정 기간 안에 있는 레코드만 전액 산입.
        date 가 None 인 레코드는 기간 무관 전액 산입.
        (호출자가 3개월치 내역만 넘기면 자연스럽게 올바름)

    exclusion 기간 처리 (분자·분모 대칭):
      - 산정 기간과 겹치는 exclusion 일수는 total_days(분모)에서도 차감.
      - exclusion 날짜 범위에 속하는 wage_records(분자)도 제외.
      - 이로써 무급휴직 구간이 평균임금을 왜곡하지 않음.

    Parameters
    ----------
    severance_date:
        퇴직일.
    wage_records:
        [{"date": dt.date, "amount": float, "wage_type": str}, ...]
    period_days:
        None (기본값) 이면 calendar 역산으로 자동 계산.
        명시적으로 지정하면 해당 값을 총일수로 사용 (override).
    hire_date:
        입사일. 재직 기간이 3개월 미만일 때 period_start 하한선으로 사용.
    exclusions:
        제외 기간 목록 (calculate_continuous_service_days 와 동일).

    Returns
    -------
    dict with keys:
        calculation_period_start  str  YYYY-MM-DD
        calculation_period_end    str  YYYY-MM-DD
        total_wage_amount         float
        total_days                int
        average_wage              float  (= average_wage_per_day, 하루 평균임금)
        average_wage_per_day      float
    """
    # 산정 기간 계산
    # period_end: 퇴직일 전날
    period_end = severance_date - dt.timedelta(days=1)
    # period_start: 3개월 전
    auto_start = _three_months_before(severance_date)

    # 재직 기간이 3개월 미만인 경우 (§6-2): hire_date 로 하한
    if hire_date is not None and hire_date > auto_start:
        period_start = hire_date
    else:
        period_start = auto_start

    # period_start 가 period_end 보다 늦으면 당일만 (최소 1일)
    if period_start > period_end:
        period_start = period_end

    if period_days is not None and period_days > 0:
        # 명시적 override
        computed_total_days = period_days
    else:
        computed_total_days = (period_end - period_start).days + 1  # 양쪽 포함

        # exclusion 기간이 산정 기간과 겹치는 일수 차감 (분자·분모 대칭)
        # 무급휴직 등 제외 기간에는 임금도 없으므로 분모에서도 대칭 제외.
        for excl_start, excl_end in (exclusions or []):
            computed_total_days -= _clamp_overlap(excl_start, excl_end, period_start, period_end)
        computed_total_days = max(computed_total_days, 1)  # zero-division 방지

    # wage_records 집계
    # 연산 편의를 위해 wage_type 별로 분리
    ANNUAL_TYPES = {"annual_leave", "bonus"}
    annual_type_total: dict[str, float] = {}  # wage_type → 연간 합계
    periodic_total = 0.0

    for rec in wage_records:
        rec_date: dt.date = rec.get("date")
        amount: float = float(rec.get("amount", 0))
        wage_type: str = rec.get("wage_type", "base")

        # exclusion 기간 안의 레코드 제외 (분자 대칭)
        if rec_date is not None and _is_in_exclusion(rec_date, exclusions):
            continue

        if wage_type in ANNUAL_TYPES:
            # 연간 상여/연차수당: type 별로 합산 후 나중에 3/12 적용.
            # date 는 지급 시점 기록용; 기간 필터를 적용하지 않음.
            annual_type_total[wage_type] = annual_type_total.get(wage_type, 0.0) + amount
        else:
            # 기본급·수당 등: 산정 기간(period_start~period_end) 내 지급분만 산입.
            # 호출자가 3개월치 레코드만 전달하면 자동으로 일치.
            # 날짜가 없는 레코드(None)는 기간 필터 없이 전액 산입.
            if rec_date is None or period_start <= rec_date <= period_end:
                periodic_total += amount

    # 연간 annual_type 합산 후 3개월 분(3/12) 산입
    annual_apportioned = sum(v * 3 / 12 for v in annual_type_total.values())

    total_wage_amount = periodic_total + annual_apportioned

    if computed_total_days <= 0:
        computed_total_days = 1  # zero-division 방지

    avg_per_day = total_wage_amount / computed_total_days

    return {
        "calculation_period_start": period_start.isoformat(),
        "calculation_period_end": period_end.isoformat(),
        "total_wage_amount": total_wage_amount,
        "total_days": computed_total_days,
        "average_wage": avg_per_day,
        "average_wage_per_day": avg_per_day,
    }


def calculate_severance_pay(
    *,
    hire_date: dt.date,
    severance_date: dt.date,
    average_wage_per_day: float,
    ordinary_wage_per_day: float | None = None,
    exclusions: list[tuple[dt.date, dt.date]] | None = None,
) -> dict[str, Any]:
    """퇴직금 계산 (근퇴법 8조).

    퇴직금 = max(평균임금, 통상임금) × 30 × (재직일수 / 365)

    1년(365일) 미만 재직 → 퇴직금 0, qualified_for_severance=False.

    Parameters
    ----------
    hire_date:
        입사일.
    severance_date:
        퇴직일 (마지막 근무일 + 1).
    average_wage_per_day:
        1일 평균임금 (calculate_average_wage 반환값 사용).
    ordinary_wage_per_day:
        1일 통상임금. 평균임금보다 높을 때 대체 사용.
        None 이면 비교 없이 평균임금 사용.
    exclusions:
        계속근로 제외 기간.

    Returns
    -------
    dict with keys:
        continuous_service_days   int
        qualified_for_severance   bool
        average_wage_per_day      float
        ordinary_wage_per_day     float | None
        wage_used_per_day         float
        wage_used_reason          "average" | "ordinary"
        severance_pay_amount      float  (원단위 절사)
        calculation_formula       str
    """
    service_days = calculate_continuous_service_days(hire_date, severance_date, exclusions)
    qualified = service_days >= 365

    # 사용 임금 결정 (통상임금 fallback)
    if ordinary_wage_per_day is not None and ordinary_wage_per_day > average_wage_per_day:
        wage_used = ordinary_wage_per_day
        wage_reason: str = "ordinary"
    else:
        wage_used = average_wage_per_day
        wage_reason = "average"

    if not qualified:
        formula = (
            f"재직일수 {service_days}일 < 365일 → 퇴직금 미발생 "
            f"(근퇴법 8조: 1년 이상 계속근로 요건 미충족)"
        )
        return {
            "continuous_service_days": service_days,
            "qualified_for_severance": False,
            "average_wage_per_day": average_wage_per_day,
            "ordinary_wage_per_day": ordinary_wage_per_day,
            "wage_used_per_day": wage_used,
            "wage_used_reason": wage_reason,
            "severance_pay_amount": 0.0,
            "calculation_formula": formula,
        }

    # 퇴직금 = wage_used × 30 × (service_days / 365), 원단위 절사
    raw = wage_used * 30 * service_days / 365
    severance_amount = float(int(raw))  # 원단위 절사

    formula = (
        f"{wage_used:,.2f}원 ({wage_reason}) × 30일 × "
        f"({service_days}일 / 365일) = {severance_amount:,.0f}원 "
        f"[원단위 절사]"
    )

    return {
        "continuous_service_days": service_days,
        "qualified_for_severance": True,
        "average_wage_per_day": average_wage_per_day,
        "ordinary_wage_per_day": ordinary_wage_per_day,
        "wage_used_per_day": wage_used,
        "wage_used_reason": wage_reason,
        "severance_pay_amount": severance_amount,
        "calculation_formula": formula,
    }


def estimate_irp_contribution(
    severance_pay_amount: float,
    irp_account_required: bool = True,
) -> dict[str, Any]:
    """IRP 의무이체 추정.

    근퇴법 17조 / 시행령 9조:
    퇴직금 300만원 이상이면 IRP 계좌로 의무 이체.
    (과제 설명서의 55만원은 오기; 법정 기준 300만원 적용)

    Parameters
    ----------
    severance_pay_amount:
        계산된 퇴직금 총액.
    irp_account_required:
        True = 법정 요건 시 IRP 이체 의무 대상으로 처리.

    Returns
    -------
    dict with keys:
        severance_pay_amount      float
        irp_mandatory_threshold   int    (3_000_000)
        requires_irp_transfer     bool
        irp_transfer_amount       float
        cash_payout_amount        float
        note                      str
    """
    threshold = IRP_MANDATORY_THRESHOLD
    requires_irp = irp_account_required and severance_pay_amount >= threshold

    if requires_irp:
        irp_amount = severance_pay_amount
        cash_amount = 0.0
        note = (
            f"퇴직금 {severance_pay_amount:,.0f}원 ≥ {threshold:,}원 → "
            "전액 IRP 계좌 의무이체 (근퇴법 17조)"
        )
    else:
        irp_amount = 0.0
        cash_amount = severance_pay_amount
        note = (
            f"퇴직금 {severance_pay_amount:,.0f}원 < {threshold:,}원 또는 "
            "IRP 의무 미적용 → 현금 지급 가능"
        )

    return {
        "severance_pay_amount": severance_pay_amount,
        "irp_mandatory_threshold": threshold,
        "requires_irp_transfer": requires_irp,
        "irp_transfer_amount": irp_amount,
        "cash_payout_amount": cash_amount,
        "note": note,
    }
