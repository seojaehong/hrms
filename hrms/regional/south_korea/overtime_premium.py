"""근로기준법 56조 가산수당 계산기.

framework-free. AttendanceRecord 또는 raw time 입력을 받아 가산수당을 계산.
일 8시간 초과 자동 연장, 주 12시간 한도 검증, 야간/휴일/휴일초과 중첩.

Legal basis:
    근로기준법 제53조 — 연장근로의 제한 (주 12시간 한도)
    근로기준법 제56조 — 연장·야간·휴일 근로
        1항: 연장근로 → 통상임금의 50% 이상 가산
        2항: 휴일근로 8시간 이내 → 통상임금의 50% 이상 가산
        3항: 휴일근로 8시간 초과 → 통상임금의 100% 이상 가산
        4항: 야간근로(22:00~06:00) → 통상임금의 50% 이상 가산

Stacking rule: 동일 시간에 복수 유형이 겹치면 각 가산율을 중첩 합산.
    예) 휴일 야간 = 휴일 50% + 야간 50% → 100% 가산 (총 200% 지급)

Bucket rule (상호 배타):
    - 휴일(is_holiday=True 또는 is_weekly_off=True)인 경우:
        · 전체 근로시간 → holiday + holiday_overtime 버킷
        · §53 연장근로(overtime) 버킷에는 포함 안 됨
    - 비휴일인 경우:
        · 일 소정근로시간(standard_daily_hours, 기본 8h) 이내 → regular
        · 초과분 → overtime (§56①)
    - 야간(night)은 독립 오버레이: 위 어느 버킷이든 22:00~06:00 교차시간을 추가 집계

Break assumption: break_minutes는 총 근무시간에서 공제하며, 야간 시간 계산 시에도
    같은 비율로 공제(break 배치 미지정이므로 근무 종료 직전으로 가정).
    실무상 주간 점심시간은 야간 구간과 무관하므로 보수적으로 야간 분을 raw 기준 계산 후
    break 공제는 별도 처리함 (see _calc_night_minutes docstring).
"""

from __future__ import annotations

import datetime as dt
import pathlib
from typing import Any

# 법적 근거 인용 베이스 — published 온톨로지 노드가 없을 때의 폴백 (annual_leave 패턴)
LEGAL_BASIS_BASE_FALLBACK = "근로기준법 제56조"


def legal_basis_base(wiki_root: Any = None) -> str:
    """가산수당 근거 조항 인용 베이스 — published §56 노드 우선, 폴백 상수.

    wiki_root 미지정 시 레포 wiki/ontology. 온톨로지 로더가 없거나 노드가
    draft/부재면 조용히 폴백한다 (annual_leave._legal_basis_base 패턴).
    """
    try:
        import importlib.util as _ilu

        loader_path = pathlib.Path(__file__).resolve().parent / "ontology" / "loader.py"
        spec = _ilu.spec_from_file_location("korea_ontology_loader", loader_path)
        loader = _ilu.module_from_spec(spec)
        spec.loader.exec_module(loader)

        root = (
            pathlib.Path(wiki_root)
            if wiki_root is not None
            else pathlib.Path(__file__).resolve().parents[3] / "wiki" / "ontology"
        )
        nodes, _errors = loader.load_nodes(root, review_state="published")
        for node in nodes:
            if getattr(node, "node_id", None) == "근로기준법_제56조":
                sources = getattr(node, "sources", None) or []
                if sources:
                    return sources[0]
    except Exception:
        pass
    return LEGAL_BASIS_BASE_FALLBACK


# 주 최대 연장 한도 — 근기법 §53①
WEEKLY_OVERTIME_LIMIT_HOURS: float = 12.0

# 하루 소정근로시간 기본값 (§50)
DEFAULT_STANDARD_DAILY_HOURS: float = 8.0

# 야간근로 시간대 (§56④)
DEFAULT_NIGHT_START: dt.time = dt.time(22, 0)
DEFAULT_NIGHT_END: dt.time = dt.time(6, 0)

# 가산 승수 (기본급 포함 전체 지급배율)
MULTIPLIER_REGULAR: float = 1.0
MULTIPLIER_OVERTIME: float = 1.5  # 연장: 기본 1.0 + 가산 0.5
MULTIPLIER_NIGHT_ADDEND: float = 0.5  # 야간: 0.5 추가 (기본급은 다른 버킷에서 이미 계산)
MULTIPLIER_HOLIDAY: float = 1.5  # 휴일 8h 이내: 기본 1.0 + 가산 0.5
MULTIPLIER_HOLIDAY_OVERTIME: float = 2.0  # 휴일 8h 초과: 기본 1.0 + 가산 1.0

# 휴일근로 내 야간 시작 경계 (분 기준으로 버킷 분리)
HOLIDAY_NIGHT_BOUNDARY_HOURS: float = 8.0


class WorkSession:
    """일 단위 근로 세션 (한 직원의 하루 출근/퇴근 + 휴일/주휴 여부).

    Args:
        employee: 직원 식별자.
        work_date: 근무 기준일 (출근일).
        start_time: 출근 시각.
        end_time: 퇴근 시각. start_time보다 작거나 같으면 익일 퇴근으로 처리.
        break_minutes: 휴게시간 (분). 실 근무시간에서 공제.
        is_holiday: 법정·약정 휴일 여부 (근기법 §55②).
        is_weekly_off: 주휴일 여부 (근기법 §55①). True이면 is_holiday와 동등 처리.
    """

    __slots__ = (
        "employee",
        "work_date",
        "start_time",
        "end_time",
        "break_minutes",
        "is_holiday",
        "is_weekly_off",
    )

    def __init__(
        self,
        *,
        employee: str,
        work_date: dt.date,
        start_time: dt.time,
        end_time: dt.time,
        break_minutes: int = 0,
        is_holiday: bool = False,
        is_weekly_off: bool = False,
    ) -> None:
        self.employee = employee
        self.work_date = work_date
        self.start_time = start_time
        self.end_time = end_time
        self.break_minutes = break_minutes
        self.is_holiday = is_holiday
        self.is_weekly_off = is_weekly_off

    def _start_dt(self) -> dt.datetime:
        return dt.datetime.combine(self.work_date, self.start_time)

    def _end_dt(self) -> dt.datetime:
        """퇴근 datetime. end_time <= start_time이면 익일 처리."""
        end = dt.datetime.combine(self.work_date, self.end_time)
        if self.end_time <= self.start_time:
            end += dt.timedelta(days=1)
        return end

    def total_clock_minutes(self) -> int:
        """총 클럭 경과 분 (휴게 미공제)."""
        delta = self._end_dt() - self._start_dt()
        return int(delta.total_seconds() // 60)

    def total_work_minutes(self) -> int:
        """실 근로 분 (휴게 공제)."""
        return max(0, self.total_clock_minutes() - self.break_minutes)


def _calc_night_minutes(
    start_dt: dt.datetime,
    end_dt: dt.datetime,
    work_date: dt.date,
    night_start: dt.time,
    night_end: dt.time,
) -> int:
    """야간 구간(night_start ~ 다음날 night_end)과 [start_dt, end_dt) 교차 분 수.

    근로기준법 §56④: 야간근로 = 22:00 ~ 다음날 06:00.
    이 구간은 하루 달력일을 기준으로 두 세그먼트가 됩니다:
        - 전반부: work_date 00:00 ~ work_date 06:00  (early morning)
        - 후반부: work_date 22:00 ~ work_date+1 06:00 (late evening ~ dawn)

    두 세그먼트 모두와 교차를 계산하여 합산합니다.
    이를 통해 조기 출근(예: 02:00~10:00)과 야간 연장 모두 정확히 처리합니다.

    단일 세션에서 복수의 완전한 야간 구간(예: 32h 연속근로)은 지원하지 않습니다.
    실무상 break는 주간 배치를 가정하여 야간 분에서 공제하지 않습니다.

    Args:
        start_dt: 세션 시작 datetime.
        end_dt: 세션 종료 datetime.
        work_date: 근무 기준일 (출근일).
        night_start: 야간 시작 시각 (기본 22:00).
        night_end: 야간 종료 시각 (기본 06:00 — 익일).

    Returns:
        교차 분 수 (정수).
    """
    total_night_minutes = 0

    # 세그먼트 1: work_date 00:00 ~ work_date night_end (early morning, 예: 00:00~06:00)
    early_s = dt.datetime.combine(work_date, dt.time(0, 0))
    early_e = dt.datetime.combine(work_date, night_end)
    if early_e > early_s:  # night_end > 00:00 인 경우만 (06:00)
        ov_s = max(start_dt, early_s)
        ov_e = min(end_dt, early_e)
        if ov_e > ov_s:
            total_night_minutes += int((ov_e - ov_s).total_seconds() // 60)

    # 세그먼트 2: work_date night_start ~ work_date+1 night_end (late evening, 예: 22:00~익일06:00)
    late_s = dt.datetime.combine(work_date, night_start)
    late_e = dt.datetime.combine(work_date + dt.timedelta(days=1), night_end)
    ov_s = max(start_dt, late_s)
    ov_e = min(end_dt, late_e)
    if ov_e > ov_s:
        total_night_minutes += int((ov_e - ov_s).total_seconds() // 60)

    return total_night_minutes


def calculate_daily_premium(
    session: WorkSession,
    standard_daily_hours: float = DEFAULT_STANDARD_DAILY_HOURS,
    night_start: dt.time = DEFAULT_NIGHT_START,
    night_end: dt.time = DEFAULT_NIGHT_END,
) -> dict[str, Any]:
    """하루 단위 가산수당 시간 분류.

    근로기준법 §56 기준으로 하루 근무를 버킷으로 분류합니다.

    버킷 규칙:
        - 휴일(is_holiday 또는 is_weekly_off): 전체 시간 → holiday / holiday_overtime
          §53 연장근로(overtime) 버킷 미사용.
        - 비휴일: 소정(standard_daily_hours) 이내 → regular, 초과 → overtime.
        - 야간(night): 위 버킷과 무관하게 22:00~06:00 교차 시간을 독립 집계.

    Break 처리: total_work_minutes()를 실 근로시간으로 사용.
    야간 분은 클럭 기준 교차 분에서 break를 비율 공제하지 않습니다
    (break는 주간 배치 가정 — 보수적 처리).

    Args:
        session: WorkSession 객체.
        standard_daily_hours: 일 소정근로시간 (기본 8.0h).
        night_start: 야간 시작 시각 (기본 22:00).
        night_end: 야간 종료 시각 익일 (기본 06:00).

    Returns:
        dict with keys:
            employee (str): 직원 식별자.
            work_date (str): ISO 날짜.
            is_holiday (bool): 휴일/주휴일 여부.
            total_work_hours (float): 실 근무시간 (휴게 공제).
            regular_hours (float): 통상 근로시간.
            overtime_hours (float): 연장근로시간 (비휴일, §53).
            night_hours (float): 야간근로시간 (22:00~06:00 교차, §56④).
            holiday_hours (float): 휴일 8h 이내 근로시간.
            holiday_overtime_hours (float): 휴일 8h 초과 근로시간.
            premium_multipliers (dict): 각 버킷의 지급배율.
    """
    is_off_day = session.is_holiday or session.is_weekly_off
    work_minutes = session.total_work_minutes()
    work_hours = work_minutes / 60.0

    standard_minutes = standard_daily_hours * 60

    start_dt = session._start_dt()
    end_dt = session._end_dt()
    night_raw_minutes = _calc_night_minutes(start_dt, end_dt, session.work_date, night_start, night_end)
    night_hours = night_raw_minutes / 60.0

    if is_off_day:
        # 휴일: holiday / holiday_overtime 버킷만 사용
        holiday_minutes = min(work_minutes, int(HOLIDAY_NIGHT_BOUNDARY_HOURS * 60))
        holiday_overtime_minutes = max(0, work_minutes - holiday_minutes)

        regular_hours = 0.0
        overtime_hours = 0.0
        holiday_hours = holiday_minutes / 60.0
        holiday_overtime_hours = holiday_overtime_minutes / 60.0
    else:
        # 비휴일: regular / overtime 버킷
        regular_minutes = min(work_minutes, int(standard_minutes))
        overtime_minutes = max(0, work_minutes - regular_minutes)

        regular_hours = regular_minutes / 60.0
        overtime_hours = overtime_minutes / 60.0
        holiday_hours = 0.0
        holiday_overtime_hours = 0.0

    return {
        "employee": session.employee,
        "work_date": session.work_date.isoformat(),
        "is_holiday": is_off_day,
        "total_work_hours": round(work_hours, 4),
        "regular_hours": round(regular_hours, 4),
        "overtime_hours": round(overtime_hours, 4),
        "night_hours": round(night_hours, 4),
        "holiday_hours": round(holiday_hours, 4),
        "holiday_overtime_hours": round(holiday_overtime_hours, 4),
        "premium_multipliers": {
            "regular": MULTIPLIER_REGULAR,
            "overtime": MULTIPLIER_OVERTIME,
            "night": MULTIPLIER_NIGHT_ADDEND,
            "holiday": MULTIPLIER_HOLIDAY,
            "holiday_overtime": MULTIPLIER_HOLIDAY_OVERTIME,
        },
    }


def calculate_weekly_aggregate(sessions: list[WorkSession]) -> dict[str, Any]:
    """주 단위 집계 + 근기법 §53 12시간 연장 한도 검증.

    주 단위 식별은 sessions 중 가장 이른 날과 가장 늦은 날 기준.
    §53 한도 검증 대상: overtime_hours 합계 (비휴일 연장만).
    휴일근로(holiday_overtime_hours)는 §53 한도 적용 대상 아님.

    Args:
        sessions: 하나의 주(week)에 속하는 WorkSession 리스트.

    Returns:
        dict with keys:
            week_start (str): ISO 최초 근무일.
            week_end (str): ISO 최종 근무일.
            by_day (list[dict]): 각 일별 calculate_daily_premium 결과.
            total_overtime_hours (float): 주간 연장근로 합계 (비휴일 §53).
            weekly_overtime_limit (float): 법정 한도 (12.0h).
            exceeds_weekly_limit (bool): 한도 초과 여부.
            exceed_amount_hours (float): 초과 시간량.
            compliance_warning (str | None): 초과 시 경고 메시지, 미초과 시 None.
    """
    if not sessions:
        return {
            "week_start": None,
            "week_end": None,
            "by_day": [],
            "total_overtime_hours": 0.0,
            "weekly_overtime_limit": WEEKLY_OVERTIME_LIMIT_HOURS,
            "exceeds_weekly_limit": False,
            "exceed_amount_hours": 0.0,
            "compliance_warning": None,
        }

    by_day = [calculate_daily_premium(s) for s in sessions]

    dates = [s.work_date for s in sessions]
    week_start = min(dates).isoformat()
    week_end = max(dates).isoformat()

    total_overtime = sum(d["overtime_hours"] for d in by_day)
    total_overtime = round(total_overtime, 4)

    exceeds = total_overtime > WEEKLY_OVERTIME_LIMIT_HOURS
    exceed_amount = round(max(0.0, total_overtime - WEEKLY_OVERTIME_LIMIT_HOURS), 4)

    warning: str | None = None
    if exceeds:
        warning = (
            f"근로기준법 §53 위반: 주 연장근로 {total_overtime:.2f}h"
            f" > 한도 {WEEKLY_OVERTIME_LIMIT_HOURS}h"
            f" (초과 {exceed_amount:.2f}h)"
        )

    return {
        "week_start": week_start,
        "week_end": week_end,
        "by_day": by_day,
        "total_overtime_hours": total_overtime,
        "weekly_overtime_limit": WEEKLY_OVERTIME_LIMIT_HOURS,
        "exceeds_weekly_limit": exceeds,
        "exceed_amount_hours": exceed_amount,
        "compliance_warning": warning,
    }


def estimate_premium_amount(
    daily_premium: dict[str, Any],
    hourly_rate: float,
) -> dict[str, Any]:
    """가산수당 금액 추정 (시급 기준).

    각 버킷의 지급액은 아래와 같이 산정합니다.

    지급 구조:
        regular_pay    = regular_hours  × rate × 1.0  (통상임금 100%)
        overtime_pay   = overtime_hours × rate × 1.5  (연장: 통상 + 50% 가산)
        holiday_pay    = holiday_hours  × rate × 1.5  (휴일 8h 이내: 통상 + 50%)
        holiday_overtime_pay
                       = holiday_overtime_hours × rate × 2.0
                         (휴일 8h 초과: 통상 + 100%)
        night_pay      = night_hours × rate × 0.5
                         (야간 추가분만; 야간 시간의 기본급은 위 버킷에 포함)

    total = 위 다섯 항목의 합계 (단, 야간 시간의 '통상' 부분은 중복 계산 없음)

    Args:
        daily_premium: calculate_daily_premium()의 반환값.
        hourly_rate: 통상시급 (원). 소수 가능.

    Returns:
        dict with keys:
            regular_pay (float): 통상 근로 지급액.
            overtime_pay (float): 연장수당 (50% 가산 포함 전액).
            night_pay (float): 야간 추가분 (50% 추가만).
            holiday_pay (float): 휴일수당 8h 이내 (50% 가산 포함 전액).
            holiday_overtime_pay (float): 휴일 8h 초과 수당 (100% 가산 포함 전액).
            total (float): 총 지급액.
    """
    rate = float(hourly_rate)

    regular_pay = daily_premium["regular_hours"] * rate * MULTIPLIER_REGULAR
    overtime_pay = daily_premium["overtime_hours"] * rate * MULTIPLIER_OVERTIME
    night_pay = daily_premium["night_hours"] * rate * MULTIPLIER_NIGHT_ADDEND
    holiday_pay = daily_premium["holiday_hours"] * rate * MULTIPLIER_HOLIDAY
    holiday_overtime_pay = daily_premium["holiday_overtime_hours"] * rate * MULTIPLIER_HOLIDAY_OVERTIME

    total = regular_pay + overtime_pay + night_pay + holiday_pay + holiday_overtime_pay

    return {
        "regular_pay": round(regular_pay, 2),
        "overtime_pay": round(overtime_pay, 2),
        "night_pay": round(night_pay, 2),
        "holiday_pay": round(holiday_pay, 2),
        "holiday_overtime_pay": round(holiday_overtime_pay, 2),
        "total": round(total, 2),
    }
