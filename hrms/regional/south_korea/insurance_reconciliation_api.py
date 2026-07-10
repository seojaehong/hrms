# -*- coding: utf-8 -*-
"""4대보험 고지 대사 Frappe API — 기간 슬립(우리 계산) vs 공단 고지 원커맨드 대사.

코어는 insurance_reconciliation.py(framework-free). 이 파일은 해당 월의 제출된
Salary Slip 공제를 모아 표준행으로 만들고, 주입된 고지내역과 대조한다.

- 계산·조회 전용 — 어떤 저장도 하지 않는다.
- 고지내역(notified)은 호출자가 주입: CODEF 조회 결과든 공단 xlsx를 파싱한 것이든
  표준행 [{employee, national_pension, ...}] 형태(JSON 문자열 수용).
- tolerance 기본 0 (1원 단위 규칙). 완화는 명시적으로만.
"""
from __future__ import annotations

import calendar
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


_recon = _load_core("insurance_reconciliation")


def _month_bounds(year: int, month: int) -> tuple[str, str]:
	last = calendar.monthrange(year, month)[1]
	return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}"


def _get_period_slips(year: int, month: int, company: str | None) -> list[dict[str, Any]]:
	"""해당 월(start_date 기준) 제출(docstatus=1)된 급여 슬립 + 공제 행."""
	start, end = _month_bounds(year, month)
	filters: dict[str, Any] = {
		"docstatus": 1,
		"start_date": ["between", [start, end]],
	}
	if company:
		filters["company"] = company
	slips = _frappe.get_all(  # type: ignore[union-attr]
		"Salary Slip",
		filters=filters,
		fields=["name", "employee", "employee_name"],
	)
	if not slips:
		return []
	names = [s["name"] for s in slips]
	detail_rows = _frappe.get_all(  # type: ignore[union-attr]
		"Salary Detail",
		filters={"parent": ["in", names], "parentfield": "deductions"},
		fields=["parent", "salary_component", "amount"],
	)
	by_parent: dict[str, list[dict[str, Any]]] = {}
	for row in detail_rows:
		by_parent.setdefault(row["parent"], []).append(
			{"salary_component": row.get("salary_component"), "amount": row.get("amount")}
		)
	return [
		{
			"employee": s["employee"],
			"employee_name": s.get("employee_name"),
			"deductions": by_parent.get(s["name"], []),
		}
		for s in slips
	]


@_whitelist
def reconcile_period_contributions(
	year: int | str,
	month: int | str,
	notified: Any,
	company: str | None = None,
	tolerance: int | str = 0,
) -> dict[str, Any]:
	"""해당 월 제출 슬립의 4대보험 공제 vs 공단 고지내역 대사 (조회·계산 전용).

	Args:
		year, month: 귀속월.
		notified: 공단 고지 표준행 리스트(또는 JSON 문자열)
			[{employee, national_pension?, health_insurance?, long_term_care_insurance?, employment_insurance?}]
		company: Salary Slip 필터(선택).
		tolerance: 허용 오차(원, 기본 0 — 1원 단위 규칙).

	Returns:
		{"period", "employee_count", "reconciliation": reconcile_contributions() 결과,
		 "summary_ko": 1줄 요약, "unmapped_deductions": 비4대 공제 목록(정보)}
	"""
	if not (_FRAPPE_AVAILABLE and _frappe is not None):
		raise RuntimeError("frappe 환경에서만 호출 가능합니다 (Salary Slip 조회 필요)")
	year = int(year)
	month = int(month)
	if not (1 <= month <= 12):
		raise ValueError(f"invalid month: {month}")
	if isinstance(notified, str):
		notified = _json.loads(notified)
	if not isinstance(notified, list):
		raise ValueError("notified는 표준행 리스트여야 합니다")

	slips = _get_period_slips(year, month, company)
	extracted = _recon.contribution_rows_from_slips(slips)
	result = _recon.reconcile_contributions(
		extracted["rows"], notified, tolerance=int(tolerance)
	)
	return {
		"period": f"{year:04d}-{month:02d}",
		"employee_count": len(slips),
		"reconciliation": result,
		"summary_ko": _recon.summarize_reconciliation_ko(result),
		"unmapped_deductions": extracted["unmapped"],
	}
