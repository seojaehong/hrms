"""Frappe 연동 API — 퇴직정산 통합 (퇴직금·미사용연차수당·퇴직소득세·건보정산).

코어(severance_settlement.settle_retirement)에 위임하는 whitelisted 래퍼.
웹 RPC 입력(ISO 날짜 문자열, JSON 문자열 리스트)을 코어 타입으로 변환하고
JSON-safe 결과(Decimal 없음)를 반환한다.

테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import한다 (insurance_filing_api.py 컨벤션).
"""

from __future__ import annotations

import datetime
import importlib.util as _ilu
import json
import pathlib as _pl
from decimal import Decimal
from typing import Any

# ---------------------------------------------------------------------------
# Frappe 조건부 import — framework-free 테스트 환경에서 안전하게 로드
# ---------------------------------------------------------------------------
try:
	import frappe as _frappe  # noqa: PLC0415

	_FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
	_frappe = None  # type: ignore[assignment]
	_FRAPPE_AVAILABLE = False


def _whitelist(fn):
	"""@frappe.whitelist() 데코레이터 — Frappe 없으면 no-op."""
	if _FRAPPE_AVAILABLE and _frappe is not None:
		return _frappe.whitelist()(fn)
	return fn


# ---------------------------------------------------------------------------
# 코어 모듈 동적 로드 (importlib으로 frappe 패키지 경로 우회)
# ---------------------------------------------------------------------------
_MODULE_DIR = _pl.Path(__file__).resolve().parent


def _load_core(name: str):
	path = _MODULE_DIR / (name + ".py")
	spec = _ilu.spec_from_file_location(f"_korea_{name}_core", path)
	module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
	spec.loader.exec_module(module)  # type: ignore[union-attr]
	return module


_core = _load_core("severance_settlement")


def _parse_date(value: Any, name: str) -> datetime.date:
	"""ISO 문자열 또는 date 객체 → date. 그 외는 즉시 거부."""
	if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
		return value
	if isinstance(value, datetime.datetime):
		return value.date()
	if isinstance(value, str):
		try:
			return datetime.date.fromisoformat(value)
		except ValueError as exc:
			raise ValueError(f"{name}은 YYYY-MM-DD 형식이어야 합니다: {value!r}") from exc
	raise ValueError(f"{name}은 날짜여야 합니다: {value!r}")


def _parse_list(value: Any, name: str) -> list | None:
	"""리스트 또는 JSON 문자열 리스트 → list. None/빈값은 None."""
	if value is None or value == "" or value == []:
		return None
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except json.JSONDecodeError as exc:
			raise ValueError(f"{name}은 JSON 배열이어야 합니다: {value!r}") from exc
	if not isinstance(value, list):
		raise ValueError(f"{name}은 리스트여야 합니다: {value!r}")
	return value


def _json_safe(obj: Any) -> Any:
	"""Decimal → int/float 재귀 변환 (Frappe RPC 직렬화)."""
	if isinstance(obj, Decimal):
		return int(obj) if obj == obj.to_integral_value() else float(obj)
	if isinstance(obj, dict):
		return {k: _json_safe(v) for k, v in obj.items()}
	if isinstance(obj, (list, tuple)):
		return [_json_safe(v) for v in obj]
	return obj


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


@_whitelist
def settle_retirement_api(
	hire_date: Any,
	severance_date: Any,
	average_wage_per_day: Any,
	monthly_base_salary: Any,
	ordinary_wage_per_day: Any = None,
	unused_leave_days: Any = 0,
	monthly_remuneration_for_health: Any = None,
	paid_health_total: Any = 0,
	paid_longterm_care_total: Any = 0,
	mid_month_hire: Any = False,
) -> dict[str, Any]:
	"""퇴직정산 통합: 퇴직금 + 미사용연차수당 + 퇴직소득세 + 건보정산 (코어 위임).

	Returns:
		코어 결과 그대로(JSON-safe 변환) — severance_pay / unused_leave_allowance /
		severance_income_tax / health_insurance_reconciliation / payout_summary.
	"""
	result = _core.settle_retirement(
		hire_date=_parse_date(hire_date, "hire_date"),
		severance_date=_parse_date(severance_date, "severance_date"),
		average_wage_per_day=average_wage_per_day,
		monthly_base_salary=monthly_base_salary,
		ordinary_wage_per_day=ordinary_wage_per_day if ordinary_wage_per_day not in (None, "") else None,
		unused_leave_days=unused_leave_days or 0,
		monthly_remuneration_for_health=_parse_list(
			monthly_remuneration_for_health, "monthly_remuneration_for_health"
		),
		paid_health_total=paid_health_total or 0,
		paid_longterm_care_total=paid_longterm_care_total or 0,
		mid_month_hire=bool(mid_month_hire) and mid_month_hire not in ("false", "0", 0),
	)
	return _json_safe(result)
