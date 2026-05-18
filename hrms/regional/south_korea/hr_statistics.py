"""HR 통계 계산 — framework-free.

이 모듈은 frappe / 외부 LLM 의존 없음.
Frappe 래퍼가 DB 데이터를 dict 리스트로 넘겨주면, 여기서 순수 계산만 담당한다.

확률/점수 출력 금지. status는 "low" / "normal" / "high" 세 값만.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

# ──────────────────────────────────────────────
# 정성 status 임계값 (상수로 문서화)
# ──────────────────────────────────────────────
# 이직률 (연환산, %)
TURNOVER_LOW_THRESHOLD = 5.0    # 5% 미만 → low
TURNOVER_HIGH_THRESHOLD = 15.0  # 15% 초과 → high  (중소기업 평균 ~10%)

# 연차 사용률 (%)
LEAVE_USAGE_LOW_THRESHOLD = 50.0   # 50% 미만 → low
LEAVE_USAGE_HIGH_THRESHOLD = 80.0  # 80% 이상 → high

# 주 연장근로 시간 (근로기준법 제53조: 주 12시간 한도)
OVERTIME_LEGAL_LIMIT_WEEKLY_HOURS = 12.0
OVERTIME_HIGH_THRESHOLD_WEEKLY = 10.0   # 평균 10시간↑ → high
OVERTIME_LOW_THRESHOLD_WEEKLY = 4.0     # 평균 4시간 미만 → low

# 평균 근속 (개월)
TENURE_SHORT_MONTHS = 12    # 1년 미만
TENURE_MID_MONTHS = 36      # 1-3년
TENURE_LONG_MONTHS = 60     # 3-5년
                             # 60개월 이상 → 5년+

# PII 마스킹: employee_id 앞 4자리만 노출
_PII_MASK_LENGTH = 4


def _mask_employee_id(employee_id: str) -> str:
    """PII 마스킹: 뒷자리 숨김 (예: EMP-0012-XXX → EMP-XXXX)."""
    if len(employee_id) <= _PII_MASK_LENGTH:
        return employee_id
    return employee_id[:_PII_MASK_LENGTH] + "****"


def _turnover_status(rate_pct: float) -> str:
    if rate_pct < TURNOVER_LOW_THRESHOLD:
        return "low"
    if rate_pct > TURNOVER_HIGH_THRESHOLD:
        return "high"
    return "normal"


def _leave_usage_status(rate_pct: float) -> str:
    if rate_pct < LEAVE_USAGE_LOW_THRESHOLD:
        return "low"
    if rate_pct >= LEAVE_USAGE_HIGH_THRESHOLD:
        return "high"
    return "normal"


def _overtime_status(avg_weekly_hours: float) -> str:
    if avg_weekly_hours < OVERTIME_LOW_THRESHOLD_WEEKLY:
        return "low"
    if avg_weekly_hours >= OVERTIME_HIGH_THRESHOLD_WEEKLY:
        return "high"
    return "normal"


def _parse_date(d: Any) -> dt.date:
    if isinstance(d, dt.datetime):
        return d.date()
    if isinstance(d, dt.date):
        return d
    if isinstance(d, str):
        return dt.date.fromisoformat(d)
    raise TypeError(f"Cannot parse date from {type(d)}: {d!r}")


def _date_range_dates(start: dt.date, end: dt.date, granularity: str) -> list[dt.date]:
    """주어진 기간을 granularity 단위로 분할해 시작일 리스트 반환."""
    if granularity == "daily":
        result = []
        cur = start
        while cur <= end:
            result.append(cur)
            cur += dt.timedelta(days=1)
        return result
    if granularity == "weekly":
        result = []
        cur = start - dt.timedelta(days=start.weekday())  # 해당 주 월요일
        while cur <= end:
            result.append(max(cur, start))
            cur += dt.timedelta(weeks=1)
        return result
    if granularity == "monthly":
        result = []
        cur = start.replace(day=1)
        while cur <= end:
            result.append(cur)
            # 다음 달 1일
            if cur.month == 12:
                cur = cur.replace(year=cur.year + 1, month=1)
            else:
                cur = cur.replace(month=cur.month + 1)
        return result
    raise ValueError(f"granularity must be daily/weekly/monthly, got: {granularity!r}")


# ──────────────────────────────────────────────
# 4-F-1-a. 직원수 추이
# ──────────────────────────────────────────────

def calculate_headcount_trend(
    *,
    employee_rows: list[dict],
    start_date: dt.date,
    end_date: dt.date,
    granularity: str = "monthly",
) -> dict:
    """직원수 추이 (시계열).

    Args:
        employee_rows: Frappe 래퍼가 제공하는 직원 레코드 목록.
            각 dict에는 'date_of_joining' (str/date), 'relieving_date' (str/date/None),
            'status' (str) 필드가 필요.
        start_date: 조회 시작일
        end_date: 조회 종료일
        granularity: "daily" | "weekly" | "monthly"

    Returns::

        {
            "series": [
                {"date": "2026-01-01", "headcount": 8, "joiners": 1, "leavers": 0},
                ...
            ],
            "current_headcount": int,
            "joiners_total": int,
            "leavers_total": int,
            "net_change": int,
        }
    """
    periods = _date_range_dates(start_date, end_date, granularity)

    # 다음 기간 시작일 (headcount 기준 날짜)
    def _next_period_start(idx: int) -> dt.date:
        if idx + 1 < len(periods):
            return periods[idx + 1]
        return end_date + dt.timedelta(days=1)

    series = []
    for i, period_start in enumerate(periods):
        period_end = _next_period_start(i) - dt.timedelta(days=1)
        period_end = min(period_end, end_date)
        snap_date = period_end  # 해당 기간 말 기준 headcount

        joiners = 0
        leavers = 0
        headcount = 0

        for row in employee_rows:
            doj = _parse_date(row["date_of_joining"])
            relieving = row.get("relieving_date")
            rel_date = _parse_date(relieving) if relieving else None

            # 해당 기간 말 시점 재직 여부
            active_on_snap = doj <= snap_date and (rel_date is None or rel_date > snap_date)
            if active_on_snap:
                headcount += 1

            # 해당 기간 내 입사
            if period_start <= doj <= period_end:
                joiners += 1

            # 해당 기간 내 퇴직
            if rel_date and period_start <= rel_date <= period_end:
                leavers += 1

        series.append(
            {
                "date": period_start.isoformat(),
                "headcount": headcount,
                "joiners": joiners,
                "leavers": leavers,
            }
        )

    # 전체 기간 통계
    all_joiners = sum(s["joiners"] for s in series)
    all_leavers = sum(s["leavers"] for s in series)
    current_headcount = series[-1]["headcount"] if series else 0

    return {
        "series": series,
        "current_headcount": current_headcount,
        "joiners_total": all_joiners,
        "leavers_total": all_leavers,
        "net_change": all_joiners - all_leavers,
    }


# ──────────────────────────────────────────────
# 4-F-1-b. 이직률
# ──────────────────────────────────────────────

def calculate_turnover_rate(
    *,
    employee_rows: list[dict],
    period_start: dt.date,
    period_end: dt.date,
) -> dict:
    """이직률 = (퇴직자수 / 평균재직자수) × 100.

    평균재직자수 = (기초인원 + 기말인원) / 2 (BLS 표준 방식).

    Args:
        employee_rows: date_of_joining / relieving_date / status 포함 목록
        period_start: 기간 시작일
        period_end: 기간 종료일

    Returns::

        {
            "period_start": str,
            "period_end": str,
            "leavers": int,
            "avg_headcount": float,
            "turnover_rate_pct": float,
            "status": "low" | "normal" | "high",
        }
    """
    headcount_start = 0
    headcount_end = 0
    leavers = 0

    for row in employee_rows:
        doj = _parse_date(row["date_of_joining"])
        relieving = row.get("relieving_date")
        rel_date = _parse_date(relieving) if relieving else None

        # 기초 재직
        if doj < period_start and (rel_date is None or rel_date >= period_start):
            headcount_start += 1

        # 기말 재직
        if doj <= period_end and (rel_date is None or rel_date > period_end):
            headcount_end += 1

        # 기간 내 퇴직
        if rel_date and period_start <= rel_date <= period_end:
            leavers += 1

    avg_headcount = (headcount_start + headcount_end) / 2.0
    if avg_headcount == 0:
        rate_pct = 0.0
    else:
        rate_pct = round((leavers / avg_headcount) * 100, 2)

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "leavers": leavers,
        "avg_headcount": round(avg_headcount, 1),
        "turnover_rate_pct": rate_pct,
        "status": _turnover_status(rate_pct),
    }


# ──────────────────────────────────────────────
# 4-F-1-c. 평균 근속
# ──────────────────────────────────────────────

def calculate_average_tenure(
    *,
    employee_rows: list[dict],
    as_of_date: dt.date,
) -> dict:
    """평균 근속 + 분포.

    Args:
        employee_rows: date_of_joining 포함 목록 (재직 중인 직원만 또는 전체)
        as_of_date: 기준일

    Returns::

        {
            "as_of_date": str,
            "avg_tenure_months": float,
            "distribution": {
                "under_1y": int,
                "1y_to_3y": int,
                "3y_to_5y": int,
                "over_5y": int,
            },
            "headcount": int,
        }
    """
    distribution = {"under_1y": 0, "1y_to_3y": 0, "3y_to_5y": 0, "over_5y": 0}
    tenure_months_list = []

    for row in employee_rows:
        doj = _parse_date(row["date_of_joining"])
        relieving = row.get("relieving_date")
        rel_date = _parse_date(relieving) if relieving else None

        # as_of_date 기준 재직자만
        if doj > as_of_date:
            continue
        if rel_date and rel_date <= as_of_date:
            continue

        months = (as_of_date.year - doj.year) * 12 + (as_of_date.month - doj.month)
        tenure_months_list.append(months)

        if months < TENURE_SHORT_MONTHS:
            distribution["under_1y"] += 1
        elif months < TENURE_MID_MONTHS:
            distribution["1y_to_3y"] += 1
        elif months < TENURE_LONG_MONTHS:
            distribution["3y_to_5y"] += 1
        else:
            distribution["over_5y"] += 1

    count = len(tenure_months_list)
    avg_months = round(sum(tenure_months_list) / count, 1) if count else 0.0

    return {
        "as_of_date": as_of_date.isoformat(),
        "avg_tenure_months": avg_months,
        "distribution": distribution,
        "headcount": count,
    }


# ──────────────────────────────────────────────
# 4-F-1-d. 연차 사용률
# ──────────────────────────────────────────────

def calculate_annual_leave_usage_rate(
    *,
    leave_allocation_rows: list[dict],
    leave_application_rows: list[dict],
    period_year: int,
) -> dict:
    """연차 사용률 = (사용일수 / 부여일수) × 100.

    Args:
        leave_allocation_rows: employee / total_leaves_allocated 포함 목록
            (해당 연도 연차 부여 레코드)
        leave_application_rows: employee / total_leave_days / status 포함 목록
            (해당 연도 승인된 연차 사용 레코드)
        period_year: 조회 연도 (int)

    Returns::

        {
            "period_year": int,
            "company_avg_usage_pct": float,
            "company_status": "low" | "normal" | "high",
            "total_allocated": float,
            "total_used": float,
            "per_employee": [
                {
                    "employee_id_masked": str,
                    "allocated": float,
                    "used": float,
                    "usage_pct": float,
                    "status": "low" | "normal" | "high",
                },
                ...
            ],
        }
    """
    allocated_by_emp: dict[str, float] = defaultdict(float)
    used_by_emp: dict[str, float] = defaultdict(float)

    for row in leave_allocation_rows:
        allocated_by_emp[row["employee"]] += float(row.get("total_leaves_allocated", 0))

    for row in leave_application_rows:
        if row.get("status") in ("Approved",):
            used_by_emp[row["employee"]] += float(row.get("total_leave_days", 0))

    per_employee = []
    for emp, allocated in allocated_by_emp.items():
        used = used_by_emp.get(emp, 0.0)
        usage_pct = round((used / allocated) * 100, 1) if allocated else 0.0
        per_employee.append(
            {
                "employee_id_masked": _mask_employee_id(emp),
                "allocated": allocated,
                "used": used,
                "usage_pct": usage_pct,
                "status": _leave_usage_status(usage_pct),
            }
        )

    total_allocated = sum(allocated_by_emp.values())
    total_used = sum(used_by_emp.get(e, 0.0) for e in allocated_by_emp)
    company_avg_pct = round((total_used / total_allocated) * 100, 1) if total_allocated else 0.0

    return {
        "period_year": period_year,
        "company_avg_usage_pct": company_avg_pct,
        "company_status": _leave_usage_status(company_avg_pct),
        "total_allocated": total_allocated,
        "total_used": total_used,
        "per_employee": per_employee,
    }


# ──────────────────────────────────────────────
# 4-F-1-e. 연장근로 통계
# ──────────────────────────────────────────────

def calculate_overtime_statistics(
    *,
    attendance_rows: list[dict],
    period_start: dt.date,
    period_end: dt.date,
) -> dict:
    """연장근로 통계.

    Args:
        attendance_rows: employee / attendance_date / custom_overtime_hours /
            department 포함 목록 (docstatus=1 필터링된)
        period_start: 기간 시작일
        period_end: 기간 종료일

    Returns::

        {
            "period_start": str,
            "period_end": str,
            "total_overtime_hours": float,
            "avg_weekly_hours_per_employee": float,
            "status": "low" | "normal" | "high",
            "over_legal_limit_count": int,   # 주 12시간 초과 인원수
            "by_department": [
                {"department": str, "avg_weekly_hours": float, "status": str},
                ...
            ],
        }
    """
    # 주(week) 집계: {employee: {week_key: total_overtime}}
    emp_weekly: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    dept_weekly: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for row in attendance_rows:
        att_date = _parse_date(row["attendance_date"])
        if not (period_start <= att_date <= period_end):
            continue
        emp = row["employee"]
        dept = row.get("department", "Unknown")
        ot_hours = float(row.get("custom_overtime_hours", 0) or 0)
        if ot_hours <= 0:
            continue

        # ISO 주 키 (YYYY-Www)
        week_key = att_date.strftime("%G-W%V")
        emp_weekly[emp][week_key] += ot_hours
        dept_weekly[dept][week_key] += ot_hours

    # 기간 주 수
    total_days = (period_end - period_start).days + 1
    total_weeks = max(total_days / 7.0, 1.0)

    # 회사 전체 연장근로 합계 (중복 없이 모든 att row)
    total_ot_hours = sum(
        hours for weeks in emp_weekly.values() for hours in weeks.values()
    )

    # 직원별 주 평균
    emp_weekly_avg: dict[str, float] = {}
    for emp, weeks in emp_weekly.items():
        emp_weekly_avg[emp] = sum(weeks.values()) / total_weeks

    employee_count = len(emp_weekly) or 1
    avg_per_emp = round(sum(emp_weekly_avg.values()) / employee_count, 2)

    # 주 12h 초과 인원 (어느 한 주라도)
    over_limit_count = sum(
        1 for weeks in emp_weekly.values()
        if any(h > OVERTIME_LEGAL_LIMIT_WEEKLY_HOURS for h in weeks.values())
    )

    # 부서별
    by_department = []
    for dept, weeks in dept_weekly.items():
        dept_weekly_avg = sum(weeks.values()) / total_weeks
        by_department.append(
            {
                "department": dept,
                "avg_weekly_hours": round(dept_weekly_avg, 2),
                "status": _overtime_status(dept_weekly_avg),
            }
        )
    by_department.sort(key=lambda x: x["avg_weekly_hours"], reverse=True)

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_overtime_hours": round(total_ot_hours, 2),
        "avg_weekly_hours_per_employee": avg_per_emp,
        "status": _overtime_status(avg_per_emp),
        "over_legal_limit_count": over_limit_count,
        "by_department": by_department,
    }


# ──────────────────────────────────────────────
# 4-F-1-f. 페이롤 요약
# ──────────────────────────────────────────────

def calculate_payroll_summary(
    *,
    salary_slip_rows: list[dict],
    period_start: dt.date,
    period_end: dt.date,
) -> dict:
    """총 인건비 / 평균 임금 / 인건비 추이.

    Args:
        salary_slip_rows: employee / start_date / end_date / gross_pay / net_pay /
            currency 포함 목록 (docstatus=1)
        period_start: 기간 시작일
        period_end: 기간 종료일

    Returns::

        {
            "period_start": str,
            "period_end": str,
            "total_gross_pay": float,
            "total_net_pay": float,
            "avg_gross_pay": float,
            "employee_count": int,
            "currency": str,
            "monthly_trend": [
                {"month": "2026-01", "total_gross": float, "headcount": int},
                ...
            ],
        }
    """
    monthly: dict[str, dict] = defaultdict(lambda: {"total_gross": 0.0, "employees": set()})
    total_gross = 0.0
    total_net = 0.0
    employees: set[str] = set()
    currency = ""

    for row in salary_slip_rows:
        slip_start = _parse_date(row["start_date"])
        if not (period_start <= slip_start <= period_end):
            continue
        gross = float(row.get("gross_pay", 0) or 0)
        net = float(row.get("net_pay", 0) or 0)
        emp = row["employee"]
        month_key = slip_start.strftime("%Y-%m")

        total_gross += gross
        total_net += net
        employees.add(emp)
        monthly[month_key]["total_gross"] += gross
        monthly[month_key]["employees"].add(emp)
        if not currency:
            currency = row.get("currency", "KRW")

    emp_count = len(employees) or 1
    avg_gross = round(total_gross / emp_count, 0)

    monthly_trend = [
        {
            "month": m,
            "total_gross": round(v["total_gross"], 0),
            "headcount": len(v["employees"]),
        }
        for m, v in sorted(monthly.items())
    ]

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_gross_pay": round(total_gross, 0),
        "total_net_pay": round(total_net, 0),
        "avg_gross_pay": avg_gross,
        "employee_count": len(employees),
        "currency": currency or "KRW",
        "monthly_trend": monthly_trend,
    }


# ──────────────────────────────────────────────
# 4-F-1-g. 이상 패턴 알림 생성
# ──────────────────────────────────────────────

def _build_alerts(
    leave_usage: dict,
    overtime: dict,
    turnover: dict,
) -> list[str]:
    """이상 패턴 감지 — PII 미포함."""
    alerts: list[str] = []

    # 연차 0% 사용 직원 수
    zero_leave_count = sum(
        1
        for emp in leave_usage.get("per_employee", [])
        if emp["used"] == 0 and emp["allocated"] > 0
    )
    if zero_leave_count >= 3:
        alerts.append(f"연차 미사용 직원 {zero_leave_count}명 — 사용 촉진 필요")

    # 연차 사용률 회사 전체 낮음
    if leave_usage.get("company_status") == "low":
        alerts.append(
            f"회사 평균 연차 사용률 {leave_usage['company_avg_usage_pct']}% — 촉진제도 검토 권장"
        )

    # 주 12h 초과 연장근로
    over_limit = overtime.get("over_legal_limit_count", 0)
    if over_limit > 0:
        alerts.append(
            f"주 12시간 초과 연장근로 {over_limit}명 — 근로기준법 제53조 위반 위험"
        )

    # 부서별 연장근로 high
    for dept in overtime.get("by_department", []):
        if dept["status"] == "high":
            alerts.append(
                f"부서 '{dept['department']}' 주 평균 연장 {dept['avg_weekly_hours']}h — 과부하 점검 필요"
            )

    # 이직률 high
    if turnover.get("status") == "high":
        alerts.append(
            f"이직률 {turnover['turnover_rate_pct']}% — 주의 수준 초과 (기준: {TURNOVER_HIGH_THRESHOLD}%)"
        )

    return alerts


# ──────────────────────────────────────────────
# 4-F-1-h. 통합 대시보드 페이로드
# ──────────────────────────────────────────────

def build_hr_dashboard_payload(
    *,
    company: str,
    as_of_date: dt.date,
    employee_rows: list[dict],
    attendance_rows: list[dict],
    leave_allocation_rows: list[dict],
    leave_application_rows: list[dict],
    salary_slip_rows: list[dict],
    headcount_granularity: str = "monthly",
) -> dict:
    """모든 통계 통합 dashboard payload.

    Frappe 래퍼가 데이터를 조회한 뒤 이 함수에 전달한다.

    Returns::

        {
            "contract_type": "korea_hr_dashboard_v1",
            "company": str,
            "as_of_date": str,
            "headcount": dict,
            "turnover": dict,
            "tenure": dict,
            "leave_usage": dict,
            "overtime": dict,
            "payroll_summary": dict,
            "alerts": [str],
        }
    """
    year_start = as_of_date.replace(month=1, day=1)
    year_end = as_of_date.replace(month=12, day=31)
    period_start = year_start
    period_end = as_of_date

    headcount = calculate_headcount_trend(
        employee_rows=employee_rows,
        start_date=period_start,
        end_date=period_end,
        granularity=headcount_granularity,
    )
    turnover = calculate_turnover_rate(
        employee_rows=employee_rows,
        period_start=period_start,
        period_end=period_end,
    )
    tenure = calculate_average_tenure(
        employee_rows=employee_rows,
        as_of_date=as_of_date,
    )
    leave_usage = calculate_annual_leave_usage_rate(
        leave_allocation_rows=leave_allocation_rows,
        leave_application_rows=leave_application_rows,
        period_year=as_of_date.year,
    )
    overtime = calculate_overtime_statistics(
        attendance_rows=attendance_rows,
        period_start=period_start,
        period_end=period_end,
    )
    payroll_summary = calculate_payroll_summary(
        salary_slip_rows=salary_slip_rows,
        period_start=period_start,
        period_end=period_end,
    )
    alerts = _build_alerts(leave_usage, overtime, turnover)

    return {
        "contract_type": "korea_hr_dashboard_v1",
        "company": company,
        "as_of_date": as_of_date.isoformat(),
        "headcount": headcount,
        "turnover": turnover,
        "tenure": tenure,
        "leave_usage": leave_usage,
        "overtime": overtime,
        "payroll_summary": payroll_summary,
        "alerts": alerts,
    }
