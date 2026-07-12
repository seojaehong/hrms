"""Frappe 연동 API — 포괄임금 설계·역산 감사.

코어(inclusive_wage.py)에 위임하는 whitelisted 래퍼. 최저시급은 인자로 받지 않고
서버에서 published 온톨로지(wiki/ontology/법정수치/최저임금_<연도>.md)로 조회해
주입한다 — 임의 값 주입 사고 방지(statutory_ontology 신뢰 규칙).

테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import한다 (insurance_filing_api.py 컨벤션).
"""

from __future__ import annotations

import datetime
import importlib.util as _ilu
import pathlib as _pl
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


def _load_core(name: str, sub: str = ""):
	path = _MODULE_DIR / (sub + name + ".py") if sub else _MODULE_DIR / (name + ".py")
	spec = _ilu.spec_from_file_location(f"_korea_{name}_core", path)
	module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
	spec.loader.exec_module(module)  # type: ignore[union-attr]
	return module


_core = _load_core("inclusive_wage")
_stat = _load_core("statutory_ontology", "ontology/")
_ntg = _load_core("net_to_gross")


def _as_bool(value: Any, default: bool = True) -> bool:
	"""Frappe RPC 문자열('0'/'false'/'true')·불리언 혼용 입력을 안전 해석."""
	if value is None or value == "":
		return default
	if isinstance(value, bool):
		return value
	if isinstance(value, (int, float)):
		return bool(value)
	return str(value).strip().lower() not in ("0", "false", "no", "off")

# wiki 루트 = repo (hrms/regional/south_korea → parents[3])
_WIKI_ROOT = _pl.Path(__file__).resolve().parents[3] / "wiki" / "ontology"


def _resolve_minimum_hourly_wage() -> int:
	"""올해 최저시급을 published 온톨로지에서 조회. 확정값 없으면 즉시 거부(fail-closed)."""
	year = datetime.date.today().year
	value = _stat.get_minimum_hourly_wage(_WIKI_ROOT, year)
	if value is None:
		raise ValueError(
			f"{year}년 최저임금 published 확정값이 온톨로지에 없습니다 — "
			"wiki/ontology/법정수치 노드 승인 후 사용하세요."
		)
	return value


def _json_safe(result: dict[str, Any], minimum_hourly_wage: int) -> dict[str, Any]:
	"""Decimal → float 변환(Frappe RPC 직렬화) + 주입된 최저시급 노출."""
	out = dict(result)
	out["ordinary_hourly_wage"] = float(result["ordinary_hourly_wage"])
	out["minimum_hourly_wage"] = minimum_hourly_wage
	return out


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


@_whitelist
def design_inclusive_wage_api(
	total_monthly: Any,
	fixed_ot_hours: Any,
	fixed_night_hours: Any = 0,
	fixed_holiday_hours: Any = 0,
) -> dict[str, Any]:
	"""포괄임금 설계: 총액 → 통상시급 기준 구성항목 분해 (코어 위임).

	Returns:
		코어 결과 + minimum_hourly_wage(서버 주입값), ordinary_hourly_wage는 float.
	"""
	min_wage = _resolve_minimum_hourly_wage()
	result = _core.design_inclusive_wage(
		total_monthly,
		fixed_ot_hours,
		fixed_night_hours,
		fixed_holiday_hours,
		minimum_hourly_wage=min_wage,
	)
	return _json_safe(result, min_wage)


@_whitelist
def audit_inclusive_wage_api(
	base_pay: Any,
	fixed_ot_pay: Any = 0,
	fixed_ot_hours: Any = 0,
	fixed_night_pay: Any = 0,
	fixed_night_hours: Any = 0,
	fixed_holiday_pay: Any = 0,
	fixed_holiday_hours: Any = 0,
) -> dict[str, Any]:
	"""포괄임금 역산 감사: 계약 기재액의 적법 최소 지급액 충족 검증 (코어 위임).

	Returns:
		코어 결과 + minimum_hourly_wage(서버 주입값), ordinary_hourly_wage는 float.
	"""
	min_wage = _resolve_minimum_hourly_wage()
	result = _core.audit_inclusive_wage(
		base_pay=base_pay,
		fixed_ot_pay=fixed_ot_pay,
		fixed_ot_hours=fixed_ot_hours,
		fixed_night_pay=fixed_night_pay,
		fixed_night_hours=fixed_night_hours,
		fixed_holiday_pay=fixed_holiday_pay,
		fixed_holiday_hours=fixed_holiday_hours,
		minimum_hourly_wage=min_wage,
	)
	return _json_safe(result, min_wage)


@_whitelist
def reverse_net_api(
	target_net: Any,
	non_taxable: Any = 0,
	dependents: Any = 1,
	children_under_8: Any = 0,
	include_pension: Any = True,
	include_health: Any = True,
	include_longterm_care: Any = True,
	include_employment: Any = True,
	pension_override: Any = None,
) -> dict[str, Any]:
	"""NET(실수령액) → GROSS(세전 총액) 역산 (코어 net_to_gross 위임).

	계산 전용 — 저장 없음. 공제 규칙은 statutory_2026 엔진 단일 소스.

	Returns:
		net_to_gross.reverse_net_to_gross 결과 그대로
		(gross, achieved_net, diff, exact, deductions{...}).
	"""
	return _ntg.reverse_net_to_gross(
		target_net,
		non_taxable=non_taxable,
		dependents=dependents,
		children_under_8=children_under_8,
		include_pension=_as_bool(include_pension),
		include_health=_as_bool(include_health),
		include_longterm_care=_as_bool(include_longterm_care),
		include_employment=_as_bool(include_employment),
		pension_override=pension_override,
	)
