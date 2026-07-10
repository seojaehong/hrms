# -*- coding: utf-8 -*-
"""시급제 월 급여 자동계산 Frappe API.

근무 세션 목록(일별 출퇴근)을 받아 ①일별 가산수당(overtime_premium §56)
②월 집계+주휴수당(hourly_wage §55) ③statutory_payroll 호환 earnings 리스트로
반환한다. 코어는 전부 framework-free 모듈에 있고 이 파일은 파싱·조립만 한다.

fail-safe: 계산 전용(조회·저장 없음) — 반환값을 급여 마감 드래프트에 넣는 것은
호출부(승인 게이트 있는 플로우)의 몫이다.

테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import한다 (insurance_filing_api.py 컨벤션).
"""

from __future__ import annotations

import datetime as _dt
import importlib.util as _ilu
import json as _json
import pathlib as _pl
from typing import Any

try:
	import frappe as _frappe  # noqa: PLC0415

	_FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
	_frappe = None  # type: ignore[assignment]
	_FRAPPE_AVAILABLE = False


def _whitelist(fn):
	if _FRAPPE_AVAILABLE and _frappe is not None:
		return _frappe.whitelist()(fn)
	return fn


_MODULE_DIR = _pl.Path(__file__).resolve().parent


def _load_core(name: str):
	path = _MODULE_DIR / f"{name}.py"
	spec = _ilu.spec_from_file_location(f"_korea_{name}_core", path)
	module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
	spec.loader.exec_module(module)  # type: ignore[union-attr]
	return module


_premium = _load_core("overtime_premium")
_hourly = _load_core("hourly_wage")

_DATE_FMT = "%Y-%m-%d"
_TIME_FMTS = ("%H:%M", "%H:%M:%S")


def _parse_date(value: Any, field: str) -> _dt.date:
	try:
		return _dt.datetime.strptime(str(value).strip(), _DATE_FMT).date()
	except (ValueError, TypeError) as exc:
		raise ValueError(f"{field}는 YYYY-MM-DD 형식이어야 합니다: {value!r}") from exc


def _parse_time(value: Any, field: str) -> _dt.time:
	for fmt in _TIME_FMTS:
		try:
			return _dt.datetime.strptime(str(value).strip(), fmt).time()
		except (ValueError, TypeError):
			continue
	raise ValueError(f"{field}는 HH:MM 형식이어야 합니다: {value!r}")


def _coerce_bool(value: Any) -> bool:
	if isinstance(value, str):
		return value.strip().lower() in ("1", "true", "yes", "y")
	return bool(value)


def _parse_sessions(sessions: Any) -> list[Any]:
	"""JSON 문자열/리스트 → WorkSession 리스트. 검증 실패는 ValueError."""
	if isinstance(sessions, str):
		try:
			sessions = _json.loads(sessions)
		except _json.JSONDecodeError as exc:
			raise ValueError(f"sessions JSON 파싱 실패: {exc}") from exc
	if not isinstance(sessions, list):
		raise ValueError("sessions는 리스트여야 합니다")
	parsed = []
	for i, row in enumerate(sessions):
		if not isinstance(row, dict):
			raise ValueError(f"sessions[{i}]는 객체여야 합니다")
		missing = sorted({"work_date", "start_time", "end_time"} - set(row))
		if missing:
			raise ValueError(f"sessions[{i}] 필수 필드 누락: {', '.join(missing)}")
		try:
			break_minutes = int(row.get("break_minutes", 0) or 0)
		except (ValueError, TypeError) as exc:
			raise ValueError(f"sessions[{i}].break_minutes는 정수여야 합니다") from exc
		parsed.append(
			_premium.WorkSession(
				employee=str(row.get("employee", "")),
				work_date=_parse_date(row["work_date"], f"sessions[{i}].work_date"),
				start_time=_parse_time(row["start_time"], f"sessions[{i}].start_time"),
				end_time=_parse_time(row["end_time"], f"sessions[{i}].end_time"),
				break_minutes=break_minutes,
				is_holiday=_coerce_bool(row.get("is_holiday", False)),
				is_weekly_off=_coerce_bool(row.get("is_weekly_off", False)),
			)
		)
	return parsed


@_whitelist
def estimate_hourly_monthly_payroll(
	sessions: Any,
	hourly_rate: Any,
	contracted_weekly_hours: Any,
	perfect_attendance: Any = True,
	standard_daily_hours: Any = 8.0,
	minimum_wage: Any = None,
	extra_allowances: Any = None,
) -> dict[str, Any]:
	"""시급제 월 급여 자동계산 (계산 전용 — 저장 없음).

	Args:
		sessions: 일별 근무 세션 리스트(또는 JSON 문자열).
			각 {work_date, start_time, end_time, break_minutes?, is_holiday?, is_weekly_off?, employee?}
		hourly_rate: 통상시급(원).
		contracted_weekly_hours: 1주 소정근로시간 (주휴수당 산정 기준).
		perfect_attendance: 개근 여부 (False면 주휴수당 0).
		standard_daily_hours: 일 소정근로시간 (기본 8.0).
		minimum_wage: 해당 연도 최저시급(원, 선택) — 주면 위반 여부 플래그.
		extra_allowances: [{component, amount}] 추가 수당(선택, JSON 문자열 수용).

	Returns:
		{
			"earnings": [{component, amount}...],   # statutory_payroll 호환
			"gross_pay": int,
			"daily": [ {work_date, breakdown, pay} ... ],
			"weekly_aggregate": calculate_weekly_aggregate() 결과 (§53 한도 포함),
			"below_minimum_wage": bool | None,       # minimum_wage 미제공이면 None
		}
	"""
	rate = float(hourly_rate)
	if rate <= 0:
		raise ValueError("hourly_rate는 양수여야 합니다")

	work_sessions = _parse_sessions(sessions)
	if isinstance(extra_allowances, str) and extra_allowances.strip():
		extra_allowances = _json.loads(extra_allowances)

	daily_rows: list[dict[str, Any]] = []
	daily_pays: list[dict[str, Any]] = []
	for s in work_sessions:
		breakdown = _premium.calculate_daily_premium(s, standard_daily_hours=float(standard_daily_hours))
		pay = _premium.estimate_premium_amount(breakdown, hourly_rate=rate)
		daily_pays.append(pay)
		daily_rows.append({"work_date": s.work_date.isoformat(), "breakdown": breakdown, "pay": pay})

	monthly = _hourly.aggregate_monthly_gross(
		daily_pays=daily_pays,
		contracted_weekly_hours=contracted_weekly_hours,
		hourly_rate=rate,
		perfect_attendance=_coerce_bool(perfect_attendance),
		extra_allowances=extra_allowances or None,
	)

	below_min = None
	if minimum_wage not in (None, "", 0):
		below_min = _hourly.is_below_minimum_wage(rate, minimum_wage)

	return {
		"earnings": monthly["earnings"],
		"gross_pay": monthly["gross_pay"],
		"daily": daily_rows,
		"weekly_aggregate": _premium.calculate_weekly_aggregate(work_sessions),
		"below_minimum_wage": below_min,
	}


@_whitelist
def estimate_hourly_payroll_from_time_input(
	period: str,
	employee: str,
	hourly_rate: Any,
	contracted_weekly_hours: Any,
	perfect_attendance: Any = True,
	minimum_wage: Any = None,
	extra_allowances: Any = None,
) -> dict[str, Any]:
	"""저장된 근무시간 입력(Korea Payroll Time Input) → 시급제 월 gross 계산.

	time_input은 월 합계 시간 버킷(part_time/overtime/night/holiday hours)이므로
	gross_from_hour_buckets 경로를 쓴다(휴일 8h 초과 ×2.0 구분 불가 — 한계는 코어 docstring).
	계산 전용 — 어떤 저장도 하지 않는다.

	Returns: {"earnings", "gross_pay", "below_minimum_wage", "time_input": {버킷 원본}}
	"""
	if not (_FRAPPE_AVAILABLE and _frappe is not None):
		raise RuntimeError("frappe 환경에서만 호출 가능합니다 (time_input 조회 필요)")

	rows = _frappe.get_all(
		"Korea Payroll Time Input",
		filters={"period": str(period).strip(), "employee": employee},
		fields=["part_time_hours", "overtime_hours", "night_hours", "holiday_hours", "status"],
		limit=1,
	)
	if not rows:
		raise ValueError(f"근무시간 입력이 없습니다: employee={employee}, period={period}")
	row = dict(rows[0])

	if isinstance(extra_allowances, str) and extra_allowances.strip():
		extra_allowances = _json.loads(extra_allowances)

	monthly = _hourly.gross_from_hour_buckets(
		regular_hours=row.get("part_time_hours") or 0,
		overtime_hours=row.get("overtime_hours") or 0,
		night_hours=row.get("night_hours") or 0,
		holiday_hours=row.get("holiday_hours") or 0,
		hourly_rate=hourly_rate,
		contracted_weekly_hours=contracted_weekly_hours,
		perfect_attendance=_coerce_bool(perfect_attendance),
		extra_allowances=extra_allowances or None,
	)

	below_min = None
	if minimum_wage not in (None, "", 0):
		below_min = _hourly.is_below_minimum_wage(hourly_rate, minimum_wage)

	return {
		"earnings": monthly["earnings"],
		"gross_pay": monthly["gross_pay"],
		"below_minimum_wage": below_min,
		"time_input": row,
	}


@_whitelist
def list_hourly_payroll_proposals(
	period: str,
	company: str | None = None,
	minimum_wage: Any = None,
) -> dict[str, Any]:
	"""기간(period)의 시급제 직원 전원 gross 계산 제안 — 급여 마감 준비용 (계산 전용).

	Korea Employment Profile(wage_type=Hourly)의 base_wage(시급)·
	scheduled_work_hours_per_week(주 소정근로)와 해당 period의
	Korea Payroll Time Input(시간 버킷)을 결합해 직원별 earnings 제안을 만든다.

	어떤 저장도 하지 않는다 — 반환값을 마감 드래프트에 채우는 것은
	승인 게이트가 있는 호출부의 몫. 결측은 숨기지 않고 명단으로 노출한다
	(0원 제안이 조용히 마감에 섞이는 것을 막는다).

	Returns:
		{
			"period": str,
			"proposals": [ {employee, employee_name, hourly_rate, weekly_hours,
			                 gross_pay, earnings, below_minimum_wage, time_input} ... ],
			"missing_time_input": [employee...],   # Hourly 프로파일인데 근무시간 입력 없음
			"missing_rate": [employee...],         # base_wage(시급) 미입력
		}
	"""
	if not (_FRAPPE_AVAILABLE and _frappe is not None):
		raise RuntimeError("frappe 환경에서만 호출 가능합니다")
	period = str(period).strip()
	if not period:
		raise ValueError("period는 필수입니다")

	profile_filters: dict[str, Any] = {"wage_type": "Hourly"}
	if company:
		profile_filters["company"] = company
	profiles = _frappe.get_all(
		"Korea Employment Profile",
		filters=profile_filters,
		fields=["employee", "base_wage", "scheduled_work_hours_per_week"],
	)

	ti_filters: dict[str, Any] = {"period": period}
	if company:
		ti_filters["company"] = company
	time_inputs = {
		r["employee"]: dict(r)
		for r in _frappe.get_all(
			"Korea Payroll Time Input",
			filters=ti_filters,
			fields=["employee", "employee_name", "part_time_hours", "overtime_hours", "night_hours", "holiday_hours"],
		)
	}

	proposals: list[dict[str, Any]] = []
	missing_time_input: list[str] = []
	missing_rate: list[str] = []
	for prof in profiles:
		emp = prof.get("employee")
		rate = prof.get("base_wage") or 0
		weekly = prof.get("scheduled_work_hours_per_week") or 0
		if not rate or float(rate) <= 0:
			missing_rate.append(emp)
			continue
		row = time_inputs.get(emp)
		if row is None:
			missing_time_input.append(emp)
			continue
		monthly = _hourly.gross_from_hour_buckets(
			regular_hours=row.get("part_time_hours") or 0,
			overtime_hours=row.get("overtime_hours") or 0,
			night_hours=row.get("night_hours") or 0,
			holiday_hours=row.get("holiday_hours") or 0,
			hourly_rate=rate,
			contracted_weekly_hours=weekly,
		)
		below_min = None
		if minimum_wage not in (None, "", 0):
			below_min = _hourly.is_below_minimum_wage(rate, minimum_wage)
		proposals.append({
			"employee": emp,
			"employee_name": row.get("employee_name"),
			"hourly_rate": rate,
			"weekly_hours": weekly,
			"gross_pay": monthly["gross_pay"],
			"earnings": monthly["earnings"],
			"below_minimum_wage": below_min,
			"time_input": {k: row.get(k) for k in ("part_time_hours", "overtime_hours", "night_hours", "holiday_hours")},
		})

	return {
		"period": period,
		"proposals": proposals,
		"missing_time_input": missing_time_input,
		"missing_rate": missing_rate,
	}
