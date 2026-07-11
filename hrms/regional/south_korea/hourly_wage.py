# -*- coding: utf-8 -*-
"""시급제(파트타임·시급 근로자) 급여 자동계산 — framework-free 코어.

`overtime_premium.estimate_premium_amount()`가 '근로한 시간 → 지급액'(기본급 포함 가산)을
계산하는 반면, 이 모듈은 **근로시간이 아닌 법정 수당인 주휴수당**과, 그 둘을 합쳐
statutory_payroll이 소비할 수 있는 **월 급여 earnings 리스트**로 조립한다.

법적 근거:
- 주휴수당: 근로기준법 §55(주휴일), 시행령 §30 — 1주 소정근로 15h 이상 + 개근 시,
  1일 소정근로시간분의 통상임금을 유급. 단시간근로자는 비례(§18, 시행령 별표2).
  주휴 유급시간 = min(1주 소정근로시간, 40) ÷ 40 × 8.
- 최저임금: 최저임금법 §6 — 시급이 최저임금 미만이면 위법(값은 정책 인자로 주입, 하드코딩 금지).
- 가산수당(연장·야간·휴일): 근로기준법 §56 — overtime_premium 모듈이 담당.

frappe 의존 없음 → `python3 hrms/tests/test_korea_hourly_wage.py` 직접 실행 검증 가능.
금액은 전부 정수 원(ROUND_HALF_UP).
"""
from __future__ import annotations

import pathlib
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# 법적 근거 인용 베이스 — published 온톨로지 노드가 없을 때의 폴백 (annual_leave 패턴)
LEGAL_BASIS_BASE_FALLBACK = "근로기준법 제55조"


def legal_basis_base(wiki_root: Any = None) -> str:
	"""주휴수당 근거 조항 인용 베이스 — published §55 노드 우선, 폴백 상수.

	wiki_root 미지정 시 레포 wiki/ontology. 로더 부재·노드 draft/부재 시 조용히 폴백.
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
			if getattr(node, "node_id", None) == "근로기준법_제55조":
				sources = getattr(node, "sources", None) or []
				if sources:
					return sources[0]
	except Exception:
		pass
	return LEGAL_BASIS_BASE_FALLBACK


# 근로기준법 상수 (법정)
FULL_TIME_WEEKLY_HOURS = Decimal("40")   # 법정 소정근로 상한 (§50)
WEEKLY_HOLIDAY_BASE_HOURS = Decimal("8")  # 통상근로자 1일 소정근로시간
MIN_WEEKLY_HOURS_FOR_HOLIDAY = Decimal("15")  # 주휴 발생 하한 (§18③)
# 월 평균 주 수 = 365 ÷ 12 ÷ 7
AVG_WEEKS_PER_MONTH = Decimal("365") / Decimal("12") / Decimal("7")
# 월 소정근로시간 209h = (주 40h + 유급주휴 8h) × 월평균 주수(≈4.345) 관행 확정값
# (통상시급 산정 분모 — 포괄임금 실무 규칙, 근로기준법 시행령 §6 취지)
MONTHLY_ORDINARY_HOURS = Decimal("209")


def ordinary_hourly_wage(monthly_base_salary: Any) -> Decimal:
	"""통상시급 = 기본급 ÷ 209 (포괄임금 실무 규칙 — 2026-07-11 스킬 브리지 이식).

	분모는 계약 시간이 아니라 월 소정 209h 고정. 반올림하지 않은 Decimal을 반환하며
	원 단위 확정은 호출자(수당 계산부)에서 한다.
	"""
	base = _dec(monthly_base_salary, "monthly_base_salary")
	if base < 0:
		raise ValueError("monthly_base_salary must be >= 0")
	return base / MONTHLY_ORDINARY_HOURS


def unused_leave_allowance(monthly_base_salary: Any, unused_days: Any) -> Decimal:
	"""미사용 연차수당 = 기본급 ÷ 209 × 8시간 × 미사용일수 (퇴직정산 실무 수식).

	Decimal 그대로 반환 — 원 단위 확정(절사/반올림)은 호출자 몫.
	"""
	days = _dec(unused_days, "unused_days")
	if days < 0:
		raise ValueError("unused_days must be >= 0")
	return ordinary_hourly_wage(monthly_base_salary) * Decimal("8") * days


def _dec(value: Any, name: str) -> Decimal:
	if isinstance(value, bool):
		raise ValueError(f"{name} must be a number, not bool")
	try:
		return Decimal(str(value))
	except Exception as exc:  # noqa: BLE001
		raise ValueError(f"{name} must be numeric: {value!r}") from exc


def _round_won(value: Decimal) -> int:
	return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def weekly_holiday_hours(contracted_weekly_hours: Any) -> Decimal:
	"""주휴 유급시간 = min(1주 소정근로시간, 40) ÷ 40 × 8 (시행령 §30).

	40시간 이상 근로자는 8시간으로 상한(연장근로는 소정근로에 미포함).
	단시간근로자는 비례 축소된다(예: 주 20h → 4h).
	"""
	weekly = _dec(contracted_weekly_hours, "contracted_weekly_hours")
	if weekly <= 0:
		return Decimal("0")
	capped = min(weekly, FULL_TIME_WEEKLY_HOURS)
	return (capped / FULL_TIME_WEEKLY_HOURS) * WEEKLY_HOLIDAY_BASE_HOURS


def weekly_holiday_allowance(
	*,
	contracted_weekly_hours: Any,
	hourly_rate: Any,
	perfect_attendance: bool = True,
) -> int:
	"""1주 주휴수당(원). 주 15시간 미만이거나 개근하지 않으면 0 (§55, §18③).

	주휴수당 = 주휴 유급시간 × 통상시급.
	"""
	weekly = _dec(contracted_weekly_hours, "contracted_weekly_hours")
	rate = _dec(hourly_rate, "hourly_rate")
	if rate < 0:
		raise ValueError("hourly_rate must be non-negative")
	if weekly < MIN_WEEKLY_HOURS_FOR_HOLIDAY or not perfect_attendance:
		return 0
	return _round_won(weekly_holiday_hours(weekly) * rate)


def monthly_weekly_holiday_allowance(
	*,
	contracted_weekly_hours: Any,
	hourly_rate: Any,
	perfect_attendance: bool = True,
	weeks_per_month: Any = AVG_WEEKS_PER_MONTH,
) -> int:
	"""월 환산 주휴수당(원) = 1주 주휴수당 × 월평균 주 수(기본 365/12/7 ≈ 4.345).

	월급 명세서에 주휴수당을 한 줄로 얹을 때 사용. 정수 원 반올림은 월 환산 후 1회.
	"""
	weekly = _dec(contracted_weekly_hours, "contracted_weekly_hours")
	rate = _dec(hourly_rate, "hourly_rate")
	weeks = _dec(weeks_per_month, "weeks_per_month")
	if weekly < MIN_WEEKLY_HOURS_FOR_HOLIDAY or not perfect_attendance:
		return 0
	weekly_pay = weekly_holiday_hours(weekly) * rate
	return _round_won(weekly_pay * weeks)


def is_below_minimum_wage(hourly_rate: Any, minimum_wage: Any) -> bool:
	"""시급이 최저임금 미만인지(최저임금법 §6). 최저임금 값은 반드시 인자로 주입."""
	return _dec(hourly_rate, "hourly_rate") < _dec(minimum_wage, "minimum_wage")


def compose_hourly_earnings(
	*,
	base_pay: Any,
	weekly_holiday_pay: Any = 0,
	overtime_pay: Any = 0,
	night_pay: Any = 0,
	holiday_pay: Any = 0,
	extra_allowances: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
	"""시급제 월 급여 earnings를 구성항목으로 조립.

	기본급/주휴수당/연장/야간/휴일 + 임의 수당을 하나의 earnings 리스트로 만들고
	gross 합계를 반환한다. 반환 형식은 statutory_payroll.build_statutory_payroll_snapshot의
	`earnings` 인자(각 {"component","amount"})와 호환.

	Returns: {"earnings": [ {component, amount}... ], "gross_pay": int}
	"""
	lines: list[dict[str, Any]] = []

	def _add(component: str, amount: Any) -> None:
		won = _round_won(_dec(amount, component))
		if won:
			lines.append({"component": component, "amount": won})

	_add("기본급", base_pay)
	_add("주휴수당", weekly_holiday_pay)
	_add("연장근로수당", overtime_pay)
	_add("야간근로수당", night_pay)
	_add("휴일근로수당", holiday_pay)
	for item in extra_allowances or []:
		_add(str(item.get("component", "기타수당")), item.get("amount", 0))

	gross = sum(line["amount"] for line in lines)
	return {"earnings": lines, "gross_pay": gross}


# §56 가산 배수 (overtime_premium과 동일 값 — DI 원칙상 상수 재정의)
MULTIPLIER_REGULAR = Decimal("1.0")
MULTIPLIER_OVERTIME = Decimal("1.5")   # 연장: 통상 + 50%
MULTIPLIER_NIGHT_ADDEND = Decimal("0.5")  # 야간: 추가분만(통상은 다른 버킷에 포함)
MULTIPLIER_HOLIDAY = Decimal("1.5")    # 휴일 8h 이내: 통상 + 50%


def gross_from_hour_buckets(
	*,
	regular_hours: Any,
	overtime_hours: Any = 0,
	night_hours: Any = 0,
	holiday_hours: Any = 0,
	hourly_rate: Any,
	contracted_weekly_hours: Any,
	perfect_attendance: bool = True,
	weeks_per_month: Any = AVG_WEEKS_PER_MONTH,
	extra_allowances: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
	"""월 시간 버킷(Korea Payroll Time Input 형태) → gross earnings.

	세션(출퇴근) 없이 월 합계 시간만 있을 때의 시급제 계산 경로.
	⚠️ 한계: 휴일 8h 초과(×2.0)는 버킷형으로 구분 불가 — holiday_hours 전체에
	×1.5를 적용한다. 8h 초과 휴일근로가 있는 사업장은 세션 기반
	estimate_hourly_monthly_payroll을 사용할 것.
	"""
	rate = _dec(hourly_rate, "hourly_rate")
	if rate < 0:
		raise ValueError("hourly_rate must be non-negative")

	base = _dec(regular_hours, "regular_hours") * rate * MULTIPLIER_REGULAR
	overtime = _dec(overtime_hours, "overtime_hours") * rate * MULTIPLIER_OVERTIME
	night = _dec(night_hours, "night_hours") * rate * MULTIPLIER_NIGHT_ADDEND
	holiday = _dec(holiday_hours, "holiday_hours") * rate * MULTIPLIER_HOLIDAY

	weekly_holiday = monthly_weekly_holiday_allowance(
		contracted_weekly_hours=contracted_weekly_hours,
		hourly_rate=hourly_rate,
		perfect_attendance=perfect_attendance,
		weeks_per_month=weeks_per_month,
	)

	return compose_hourly_earnings(
		base_pay=base,
		weekly_holiday_pay=weekly_holiday,
		overtime_pay=overtime,
		night_pay=night,
		holiday_pay=holiday,
		extra_allowances=extra_allowances,
	)


def aggregate_monthly_gross(
	*,
	daily_pays: list[dict[str, Any]],
	contracted_weekly_hours: Any,
	hourly_rate: Any,
	perfect_attendance: bool = True,
	weeks_per_month: Any = AVG_WEEKS_PER_MONTH,
	extra_allowances: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
	"""월 시급제 gross 자동계산 — 일별 지급액을 집계하고 주휴수당을 얹어 earnings로 조립.

	`daily_pays`는 overtime_premium.estimate_premium_amount()의 반환값 리스트(각 일자별)이다.
	이 모듈은 프레임워크 비의존을 위해 overtime_premium을 직접 import하지 않고
	**계산 결과를 인자로 주입**받는다(실 급여 플로우: 일별 세션 → estimate_premium_amount → 여기로).

	버킷 매핑:
		기본급   = Σ regular_pay          (근로한 통상시간 지급)
		연장수당 = Σ overtime_pay
		야간수당 = Σ night_pay            (야간 추가분)
		휴일수당 = Σ (holiday_pay + holiday_overtime_pay)
		주휴수당 = monthly_weekly_holiday_allowance(...)  (근로시간 아닌 법정수당)

	Returns: compose_hourly_earnings와 동일 형식 {"earnings": [...], "gross_pay": int}
	"""
	def _sum(key: str) -> Decimal:
		total = Decimal("0")
		for day in daily_pays:
			total += _dec(day.get(key, 0), key)
		return total

	base = _sum("regular_pay")
	overtime = _sum("overtime_pay")
	night = _sum("night_pay")
	holiday = _sum("holiday_pay") + _sum("holiday_overtime_pay")

	weekly_holiday = monthly_weekly_holiday_allowance(
		contracted_weekly_hours=contracted_weekly_hours,
		hourly_rate=hourly_rate,
		perfect_attendance=perfect_attendance,
		weeks_per_month=weeks_per_month,
	)

	return compose_hourly_earnings(
		base_pay=base,
		weekly_holiday_pay=weekly_holiday,
		overtime_pay=overtime,
		night_pay=night,
		holiday_pay=holiday,
		extra_allowances=extra_allowances,
	)
