# -*- coding: utf-8 -*-
"""MCP 계산 도구 순수 로직 — 시급제 급여·고지 대사 (framework-free).

server.py가 FastMCP로 등록하는 도구의 실제 계산을 여기 둔다(server.py는 mcp SDK를
import하므로 테스트 격리를 위해 순수 로직을 분리). 테넌트 데이터 조회 없음 —
전부 인자로 계산(calculate_annual_leave와 동일 성격의 MCP 계산 도구).
"""
from __future__ import annotations

import importlib.util as _ilu
import pathlib as _pl
from typing import Any

_CORE_DIR = _pl.Path(__file__).resolve().parents[1] / "hrms" / "regional" / "south_korea"


def _load_core(name: str):
	spec = _ilu.spec_from_file_location(f"korea_{name}", _CORE_DIR / f"{name}.py")
	module = _ilu.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


_hourly = _load_core("hourly_wage")
_recon = _load_core("insurance_reconciliation")


def estimate_hourly_pay(
	regular_hours: float,
	hourly_rate: float,
	contracted_weekly_hours: float,
	overtime_hours: float = 0,
	night_hours: float = 0,
	holiday_hours: float = 0,
	perfect_attendance: bool = True,
	minimum_wage: Any = None,
) -> dict:
	"""시급제 월 급여 계산 (근기법 §55 주휴·§56 가산). 월 시간 버킷+시급으로 gross earnings 산출.

	기본급=정상시간×시급, 연장×1.5, 야간 추가분×0.5, 휴일×1.5, 주휴수당(주15h+개근 시).
	minimum_wage 주면 최저임금 미달 플래그. 저장 없음.
	"""
	if float(hourly_rate) <= 0:
		raise ValueError("hourly_rate는 양수여야 합니다")
	result = _hourly.gross_from_hour_buckets(
		regular_hours=regular_hours,
		overtime_hours=overtime_hours,
		night_hours=night_hours,
		holiday_hours=holiday_hours,
		hourly_rate=hourly_rate,
		contracted_weekly_hours=contracted_weekly_hours,
		perfect_attendance=perfect_attendance,
	)
	below = None
	if minimum_wage not in (None, "", 0):
		below = _hourly.is_below_minimum_wage(hourly_rate, minimum_wage)
	return {
		"earnings": result["earnings"],
		"gross_pay": result["gross_pay"],
		"below_minimum_wage": below,
	}


def check_insurance_reconciliation(
	computed: list[dict],
	notified: list[dict],
	tolerance: int = 0,
) -> dict:
	"""4대보험 공제 대사 — 우리 계산(computed) vs 공단 고지(notified) 1원 단위 대조.

	각 행 {employee, national_pension?, health_insurance?, long_term_care_insurance?,
	employment_insurance?}. 차이·양방향 누락·한국어 요약 반환. 저장 없음.
	"""
	result = _recon.reconcile_contributions(computed, notified, tolerance=int(tolerance))
	result["summary_ko"] = _recon.summarize_reconciliation_ko(result)
	return result
