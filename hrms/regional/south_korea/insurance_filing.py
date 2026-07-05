"""4대보험 신고 자동화 코어 — framework-free.

로컬 /4대보험신고 스킬의 검증된 규칙을 제품 기능으로 이식:
  - 취득 신고: 해당 월 입사자 (date_of_joining ∈ 귀속월)
  - 상실 신고: 해당 월 퇴사자 (relieving_date ∈ 귀속월, 상실일 = 마지막근무일 + 1)
  - 근로내용확인(일용직) 역산: 개별 근무일이 없으면 마지막근무일에서 근무일수만큼 연속 역순 마킹

안전 불변식 (스킬 사고이력 2026-05-15 반영):
  - 대상자 자동 추출 결과는 **사람 확인 전 제출물이 아니다** — 반환 컨트랙트에
    requires_human_confirmation=True 를 항상 포함하고, 명단 확인 후에만 신고서를 만든다.
  - 주민번호는 이 모듈에 들어오지 않는다(입력 스키마에 없음) — 신고서 파일 생성 단계(2단계)에서만 취급.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

LOSS_REASON_CODES = {
    "자진퇴사": "11",
    "권고사직": "23",
    "계약만료": "32",
    "정년": "31",
    "기타": "26",
}


def _to_date(value: Any, fieldname: str) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError as error:
        raise ValueError(f"{fieldname} must be an ISO date: {value!r}") from error


def _in_month(day: dt.date | None, year: int, month: int) -> bool:
    return bool(day and day.year == year and day.month == month)


def detect_acquisitions(employees: list[dict], year: int, month: int) -> list[dict]:
    """귀속월 입사자(취득 신고 대상) 추출. employees: [{name, employee_name, date_of_joining, ...}]"""
    out = []
    for emp in employees:
        join = _to_date(emp.get("date_of_joining"), "date_of_joining")
        if _in_month(join, year, month):
            out.append(
                {
                    "employee": emp.get("name", ""),
                    "employee_name": emp.get("employee_name") or emp.get("first_name", ""),
                    "acquisition_date": join.isoformat(),
                    "monthly_wage": int(emp.get("monthly_wage") or 0),
                }
            )
    return sorted(out, key=lambda r: (r["acquisition_date"], r["employee_name"]))


def detect_losses(employees: list[dict], year: int, month: int) -> list[dict]:
    """귀속월 퇴사자(상실 신고 대상) 추출. 상실일 = 마지막근무일(relieving_date) + 1."""
    out = []
    for emp in employees:
        leave = _to_date(emp.get("relieving_date"), "relieving_date")
        if _in_month(leave, year, month):
            reason = str(emp.get("loss_reason") or "자진퇴사")
            out.append(
                {
                    "employee": emp.get("name", ""),
                    "employee_name": emp.get("employee_name") or emp.get("first_name", ""),
                    "last_working_date": leave.isoformat(),
                    "loss_date": (leave + dt.timedelta(days=1)).isoformat(),
                    "loss_reason": reason,
                    "loss_reason_code": LOSS_REASON_CODES.get(reason, LOSS_REASON_CODES["기타"]),
                }
            )
    return sorted(out, key=lambda r: (r["loss_date"], r["employee_name"]))


def mark_daily_work_days(work_day_count: int, last_work_day: int, days_in_month: int) -> list[int]:
    """근로내용확인(일용직) 역산: 마지막근무일에서 근무일수만큼 연속 역순 마킹.

    예: 근무일수 4, 마지막 5일 → [2, 3, 4, 5]
    """
    if not (1 <= last_work_day <= days_in_month):
        raise ValueError(f"last_work_day out of range: {last_work_day}")
    if not (1 <= work_day_count <= last_work_day):
        raise ValueError(
            f"work_day_count({work_day_count}) must be between 1 and last_work_day({last_work_day})"
        )
    return list(range(last_work_day - work_day_count + 1, last_work_day + 1))


DAILY_EMPLOYMENT_TYPES = ("일용직", "일용근로자")
WORKED_ATTENDANCE_STATUS = ("Present", "Half Day")


def _is_daily_default(emp: dict) -> bool:
	return str(emp.get("employment_type") or "") in DAILY_EMPLOYMENT_TYPES


def extract_daily_workers(
	employees: list[dict],
	attendance_rows: list[dict],
	year: int,
	month: int,
	is_daily=None,
) -> list[dict]:
	"""일용직 직원의 해당 월 근태를 근로내용확인신고 workers 입력 형태로 집계.

	- 대상: is_daily(emp) True (기본: employment_type ∈ DAILY_EMPLOYMENT_TYPES).
	- 근무일: attendance_rows 중 해당 직원·귀속월·status ∈ WORKED_ATTENDANCE_STATUS 의 '일(day)'.
	- 반환: [{employee, employee_name, work_days:[int...], daily_wage, total_wage}]
	    (generate_daily_work_report 의 workers 입력으로 그대로 투입 가능)

    순수 함수 — frappe 미의존. attendance_rows: [{employee, attendance_date, status}].
	"""
	if not (1 <= month <= 12):
		raise ValueError(f"invalid month: {month}")
	decide = is_daily or _is_daily_default

	# 직원별 근무일 집계 (귀속월·근무 status 만)
	days_by_employee: dict[str, set] = {}
	for row in attendance_rows:
		if str(row.get("status") or "") not in WORKED_ATTENDANCE_STATUS:
			continue
		day = _to_date(row.get("attendance_date"), "attendance_date")
		if not _in_month(day, year, month):
			continue
		emp_id = row.get("employee", "")
		days_by_employee.setdefault(emp_id, set()).add(day.day)

	out = []
	for emp in employees:
		if not decide(emp):
			continue
		emp_id = emp.get("name", "")
		work_days = sorted(days_by_employee.get(emp_id, set()))
		if not work_days:
			continue
		daily_wage = int(emp.get("daily_wage") or 0)
		total_wage = int(emp.get("total_wage") or daily_wage * len(work_days))
		out.append(
			{
				"employee": emp_id,
				"employee_name": emp.get("employee_name") or emp.get("first_name", ""),
				"work_days": work_days,
				"daily_wage": daily_wage,
				"total_wage": total_wage,
			}
		)
	return sorted(out, key=lambda r: r["employee_name"])


def build_filing_contract(
    *,
    filing_type: str,
    year: int,
    month: int,
    employees: list[dict],
) -> dict:
    """신고 준비 컨트랙트. AI/화면은 이 결과의 명단을 사람에게 확인받은 뒤에만 신고서를 생성한다."""
    if filing_type not in ("acquisition", "loss"):
        raise ValueError("filing_type must be 'acquisition' or 'loss'")
    if not (1 <= month <= 12):
        raise ValueError(f"invalid month: {month}")
    rows = (
        detect_acquisitions(employees, year, month)
        if filing_type == "acquisition"
        else detect_losses(employees, year, month)
    )
    return {
        "contract_type": "korea_insurance_filing_preparation_v1",
        "filing_type": filing_type,
        "period": f"{year}-{month:02d}",
        "candidates": rows,
        "candidate_count": len(rows),
        "requires_human_confirmation": True,
        "note": "대상자 명단을 담당자가 확인·확정한 후에만 신고서를 생성한다 (자동 제출 금지).",
    }
