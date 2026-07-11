# -*- coding: utf-8 -*-
"""포괄임금 설계·역산 감사 — framework-free 코어.

노무사 실무의 두 가지 상반된 작업을 다룬다:
  1) 설계(design): 총액(연봉/월급)을 주고 "이 총액을 통상시급 기준으로 쪼개면
     기본급·고정연장·고정야간·고정휴일수당이 얼마여야 하는가"를 역산한다.
  2) 역산 감사(audit): 이미 체결된 계약(기본급 + 각 고정수당 기재액)이 적법한
     최소 지급액을 충족하는지 검증한다(부족분 검출).

법적 근거:
- 통상시급 산정 분모 209h: 포괄임금 실무 확정값 (hourly_wage.py:MONTHLY_ORDINARY_HOURS와 동일 —
  DI 원칙상 상수 재정의, 서로 import하지 않음).
- 연장수당: 근로기준법 §56①(통상임금의 50% 가산).
- 야간수당: 근로기준법 §56③(22시~06시 근로에 대한 가산분만 — 기본분은 소정/연장에 포함).
- 휴일수당: 근로기준법 §56②1(8시간 이내 휴일근로는 50% 가산. 8시간 초과분은 100% 가산이나
  이 모듈은 고정 휴일근로가 8시간 이내라고 가정하는 실무 케이스만 다룬다).
- 최저임금: 최저임금법 §6 — 값은 반드시 인자로 주입(하드코딩 금지). 2026년 10,320원은
  `ontology/statutory_ontology.get_minimum_hourly_wage(wiki_root, 2026)`에서 조회해 호출자가
  주입한다.
- 연장근로 한도: 근로기준법 §53① — 1주 12시간 한도. 월 환산 시
  12h × (365÷12÷7주) ≈ 52.14h를 넘는 고정연장은 경고 대상(설계 단계에서부터 위법 소지).

경고는 raise가 아니라 warnings 리스트로 반환한다 — 판단(계약 유지/재설계)은 노무사 몫이다.

frappe 의존 없음 → `python3 hrms/tests/test_korea_inclusive_wage.py` 직접 실행 검증 가능.
금액은 전부 정수 원(ROUND_HALF_UP), 통상시급 자체는 미반올림 Decimal로 반환한다.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# 월 소정근로시간 209h = (주 40h + 유급주휴 8h) × 월평균 주수(≈4.345) 관행 확정값
# (hourly_wage.py:MONTHLY_ORDINARY_HOURS와 동일값 — DI 원칙상 재정의, cross-import 금지)
MONTHLY_ORDINARY_HOURS = Decimal("209")

# §56 가산 배수 (hourly_wage.py와 동일값 — DI 원칙상 상수 재정의)
MULTIPLIER_OVERTIME = Decimal("1.5")      # 연장: 통상 + 50%
MULTIPLIER_NIGHT_ADDEND = Decimal("0.5")  # 야간: 가산분만(통상은 다른 버킷에 포함)
MULTIPLIER_HOLIDAY = Decimal("1.5")       # 휴일 8h 이내: 통상 + 50%

# 월평균 주 수 = 365 ÷ 12 ÷ 7 (hourly_wage.py:AVG_WEEKS_PER_MONTH와 동일값 — 재정의)
AVG_WEEKS_PER_MONTH = Decimal("365") / Decimal("12") / Decimal("7")
# 연장근로 주 12시간 한도(§53①)의 월 환산 상한 ≈ 52.14h
MONTHLY_FIXED_OT_HOUR_LIMIT = Decimal("12") * AVG_WEEKS_PER_MONTH


def _dec(value: Any, name: str) -> Decimal:
	if isinstance(value, bool):
		raise ValueError(f"{name} must be a number, not bool")
	try:
		return Decimal(str(value))
	except Exception as exc:  # noqa: BLE001
		raise ValueError(f"{name} must be numeric: {value!r}") from exc


def _round_won(value: Decimal) -> int:
	return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def design_inclusive_wage(
	total_monthly: Any,
	fixed_ot_hours: Any,
	fixed_night_hours: Any = 0,
	fixed_holiday_hours: Any = 0,
	*,
	minimum_hourly_wage: Any,
) -> dict[str, Any]:
	"""총액 → 통상시급 기준 구성항목 분해(포괄임금 설계).

	t = total ÷ (209 + 1.5×H_ot + 0.5×H_night + 1.5×H_hol)

	각 고정수당은 t 기준으로 원 단위 반올림해 확정하고, 기본급은
	`총액 − 확정된 수당 합`으로 역산한다(끝수를 기본급이 흡수 — 검산 항등 `total`
	필드가 입력 총액과 항상 같도록 보장하기 위한 명시적 규칙).

	Returns:
		{ordinary_hourly_wage, base_pay, fixed_ot_pay, night_pay, holiday_pay,
		 total, legal_floor_ok, warnings}
	"""
	total = _dec(total_monthly, "total_monthly")
	ot_h = _dec(fixed_ot_hours, "fixed_ot_hours")
	night_h = _dec(fixed_night_hours, "fixed_night_hours")
	hol_h = _dec(fixed_holiday_hours, "fixed_holiday_hours")
	min_wage = _dec(minimum_hourly_wage, "minimum_hourly_wage")

	if total < 0:
		raise ValueError("total_monthly must be >= 0")
	# 총액은 원 단위(정수)여야 한다 — 절사해서 조용히 흘려보내지 않고 거부한다.
	if total != total.to_integral_value():
		raise ValueError(f"total_monthly must be a whole-won amount (no fractional won): {total_monthly!r}")
	for name, h in (("fixed_ot_hours", ot_h), ("fixed_night_hours", night_h), ("fixed_holiday_hours", hol_h)):
		if h < 0:
			raise ValueError(f"{name} must be >= 0")

	denominator = (
		MONTHLY_ORDINARY_HOURS
		+ MULTIPLIER_OVERTIME * ot_h
		+ MULTIPLIER_NIGHT_ADDEND * night_h
		+ MULTIPLIER_HOLIDAY * hol_h
	)
	t = total / denominator

	ot_pay = _round_won(t * MULTIPLIER_OVERTIME * ot_h) if ot_h > 0 else 0
	night_pay = _round_won(t * MULTIPLIER_NIGHT_ADDEND * night_h) if night_h > 0 else 0
	holiday_pay = _round_won(t * MULTIPLIER_HOLIDAY * hol_h) if hol_h > 0 else 0

	# 끝수 조정: 기본급이 나머지를 흡수해 base+ot+night+holiday == 입력 총액을 보장.
	base_pay = int(total) - ot_pay - night_pay - holiday_pay

	warnings: list[str] = []
	legal_floor_ok = t >= min_wage
	if not legal_floor_ok:
		warnings.append(f"통상시급 {t:.2f}원이 최저임금 {min_wage}원 미만입니다 (최저임금법 §6).")
	if ot_h > MONTHLY_FIXED_OT_HOUR_LIMIT:
		warnings.append(
			f"고정연장 {ot_h}h가 주 12시간 한도의 월 환산 약 {MONTHLY_FIXED_OT_HOUR_LIMIT:.2f}h"
			"를 초과합니다 (근로기준법 §53①)."
		)

	return {
		"ordinary_hourly_wage": t,
		"base_pay": base_pay,
		"fixed_ot_pay": ot_pay,
		"night_pay": night_pay,
		"holiday_pay": holiday_pay,
		"total": base_pay + ot_pay + night_pay + holiday_pay,
		"legal_floor_ok": legal_floor_ok,
		"warnings": warnings,
	}


def audit_inclusive_wage(
	*,
	base_pay: Any,
	fixed_ot_pay: Any = 0,
	fixed_ot_hours: Any = 0,
	fixed_night_pay: Any = 0,
	fixed_night_hours: Any = 0,
	fixed_holiday_pay: Any = 0,
	fixed_holiday_hours: Any = 0,
	minimum_hourly_wage: Any,
) -> dict[str, Any]:
	"""기존 계약(기본급 + 고정수당 기재액)의 역산 감사.

	통상시급 = base_pay ÷ 209 로 산정한 뒤, 각 고정수당의 "적정액"(t 기준 재계산)과
	계약 기재액을 비교해 부족분을 검출한다. 최저임금 미달·주 12시간 한도 초과도
	함께 경고한다(raise 아님 — 판단은 노무사).

	Returns:
		{ordinary_hourly_wage, expected_ot_pay/night_pay/holiday_pay,
		 ot_shortfall/night_shortfall/holiday_shortfall, legal_floor_ok,
		 overtime_limit_ok, warnings}
	"""
	base = _dec(base_pay, "base_pay")
	ot_pay = _dec(fixed_ot_pay, "fixed_ot_pay")
	ot_h = _dec(fixed_ot_hours, "fixed_ot_hours")
	night_pay = _dec(fixed_night_pay, "fixed_night_pay")
	night_h = _dec(fixed_night_hours, "fixed_night_hours")
	holiday_pay = _dec(fixed_holiday_pay, "fixed_holiday_pay")
	holiday_h = _dec(fixed_holiday_hours, "fixed_holiday_hours")
	min_wage = _dec(minimum_hourly_wage, "minimum_hourly_wage")

	if base < 0:
		raise ValueError("base_pay must be >= 0")
	for name, value in (
		("fixed_ot_pay", ot_pay),
		("fixed_ot_hours", ot_h),
		("fixed_night_pay", night_pay),
		("fixed_night_hours", night_h),
		("fixed_holiday_pay", holiday_pay),
		("fixed_holiday_hours", holiday_h),
	):
		if value < 0:
			raise ValueError(f"{name} must be >= 0")

	t = base / MONTHLY_ORDINARY_HOURS

	expected_ot = _round_won(t * MULTIPLIER_OVERTIME * ot_h) if ot_h > 0 else 0
	expected_night = _round_won(t * MULTIPLIER_NIGHT_ADDEND * night_h) if night_h > 0 else 0
	expected_holiday = _round_won(t * MULTIPLIER_HOLIDAY * holiday_h) if holiday_h > 0 else 0

	ot_shortfall = max(expected_ot - int(ot_pay), 0)
	night_shortfall = max(expected_night - int(night_pay), 0)
	holiday_shortfall = max(expected_holiday - int(holiday_pay), 0)

	warnings: list[str] = []
	if ot_shortfall > 0:
		warnings.append(
			f"연장수당 부족: 계약 {int(ot_pay)}원 < 적정 {expected_ot}원 (근로기준법 §56①)."
		)
	if night_shortfall > 0:
		warnings.append(
			f"야간수당 부족: 계약 {int(night_pay)}원 < 적정 {expected_night}원 (근로기준법 §56③)."
		)
	if holiday_shortfall > 0:
		warnings.append(
			f"휴일수당 부족: 계약 {int(holiday_pay)}원 < 적정 {expected_holiday}원 (근로기준법 §56②1)."
		)

	legal_floor_ok = t >= min_wage
	if not legal_floor_ok:
		warnings.append(f"통상시급 {t:.2f}원이 최저임금 {min_wage}원 미만입니다 (최저임금법 §6).")

	overtime_limit_ok = ot_h <= MONTHLY_FIXED_OT_HOUR_LIMIT
	if not overtime_limit_ok:
		warnings.append(
			f"고정연장 {ot_h}h가 주 12시간 한도의 월 환산 약 {MONTHLY_FIXED_OT_HOUR_LIMIT:.2f}h"
			"를 초과합니다 (근로기준법 §53①)."
		)

	return {
		"ordinary_hourly_wage": t,
		"expected_ot_pay": expected_ot,
		"expected_night_pay": expected_night,
		"expected_holiday_pay": expected_holiday,
		"ot_shortfall": ot_shortfall,
		"night_shortfall": night_shortfall,
		"holiday_shortfall": holiday_shortfall,
		"legal_floor_ok": legal_floor_ok,
		"overtime_limit_ok": overtime_limit_ok,
		"warnings": warnings,
	}
