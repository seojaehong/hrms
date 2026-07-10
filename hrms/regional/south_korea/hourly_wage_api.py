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
