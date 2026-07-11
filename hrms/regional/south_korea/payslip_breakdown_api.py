"""Frappe 연동 API — 임금명세서 산정내역 분해 (근로기준법 §48②).

코어(payslip_breakdown)에 위임하는 whitelisted 래퍼. 웹 RPC 입력(JSON 문자열
리스트/딕셔너리)을 코어 타입으로 변환하고 JSON-safe 결과를 반환한다.

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


_core = _load_core("payslip_breakdown")


def _json_safe(obj: Any) -> Any:
	"""date → ISO 문자열, Decimal → int/float 재귀 변환 (Frappe RPC 직렬화)."""
	if isinstance(obj, datetime.date):
		return obj.isoformat()
	if isinstance(obj, Decimal):
		return int(obj) if obj == obj.to_integral_value() else float(obj)
	if isinstance(obj, dict):
		return {k: _json_safe(v) for k, v in obj.items()}
	if isinstance(obj, (list, tuple)):
		return [_json_safe(v) for v in obj]
	return obj


def _parse_list(value: Any, name: str) -> list | None:
	"""Frappe RPC의 리스트 인자는 JSON 문자열로 올 수 있음 — 문자열이면 파싱."""
	if value is None:
		return None
	if isinstance(value, str):
		try:
			parsed = json.loads(value)
		except json.JSONDecodeError as exc:
			raise ValueError(f"{name}은 JSON 리스트 문자열이어야 합니다: {value!r}") from exc
		if not isinstance(parsed, list):
			raise ValueError(f"{name}은 리스트여야 합니다: {value!r}")
		return parsed
	if isinstance(value, list):
		return value
	raise ValueError(f"{name}은 리스트여야 합니다: {value!r}")


def _parse_dict(value: Any, name: str) -> dict:
	if isinstance(value, str):
		try:
			parsed = json.loads(value)
		except json.JSONDecodeError as exc:
			raise ValueError(f"{name}은 JSON 딕셔너리 문자열이어야 합니다: {value!r}") from exc
		if not isinstance(parsed, dict):
			raise ValueError(f"{name}은 딕셔너리여야 합니다: {value!r}")
		return parsed
	if isinstance(value, dict):
		return value
	raise ValueError(f"{name}은 딕셔너리여야 합니다: {value!r}")


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


@_whitelist
def build_payslip_breakdown_api(
	*,
	employee: Any,
	period: Any,
	payment_date: Any,
	wage_type: Any,
	base_salary: Any = None,
	hourly_rate: Any = None,
	regular_hours: Any = 0,
	contracted_weekly_hours: Any = None,
	perfect_attendance: Any = True,
	weeks_per_month: Any = None,
	overtime_hours: Any = 0,
	night_hours: Any = 0,
	holiday_work_hours: Any = 0,
	annual_leave_hours: Any = 0,
	extra_earnings: Any = None,
	monthly_taxable_income: Any = None,
	insurance_base: Any = None,
	company_size: Any = "small",
	industry_rate: Any = 0.0143,
	dependents: Any = 1,
	children_under_8: Any = 0,
) -> dict[str, Any]:
	"""임금명세서 산정내역(earnings) + 공제(deductions) payload (코어 위임).

	extra_earnings는 dict 리스트 또는 JSON 문자열 리스트를 모두 허용한다.
	perfect_attendance는 Frappe RPC 문자열 불리언('false'/'0')도 허용한다.
	"""
	result = _core.build_payslip_breakdown(
		employee=employee,
		period=period,
		payment_date=payment_date,
		wage_type=wage_type,
		base_salary=base_salary,
		hourly_rate=hourly_rate,
		regular_hours=regular_hours,
		contracted_weekly_hours=contracted_weekly_hours,
		perfect_attendance=_parse_bool(perfect_attendance),
		weeks_per_month=weeks_per_month,
		overtime_hours=overtime_hours,
		night_hours=night_hours,
		holiday_work_hours=holiday_work_hours,
		annual_leave_hours=annual_leave_hours,
		extra_earnings=_parse_list(extra_earnings, "extra_earnings"),
		monthly_taxable_income=monthly_taxable_income,
		insurance_base=insurance_base,
		company_size=company_size,
		industry_rate=industry_rate,
		dependents=int(dependents),
		children_under_8=int(children_under_8),
	)
	return _json_safe(result)


@_whitelist
def render_payslip_markdown_api(breakdown: Any) -> str:
	"""build_payslip_breakdown_api() 결과 → 교부용 마크다운 (코어 위임).

	breakdown은 dict 또는 JSON 문자열 dict를 모두 허용한다.
	"""
	breakdown = _parse_dict(breakdown, "breakdown")
	return _core.render_payslip_markdown(breakdown)


def _parse_bool(value: Any) -> bool:
	"""Frappe RPC 불리언 — 'false'/'0'/0/'' 은 False."""
	return bool(value) and value not in ("false", "False", "0", 0)
