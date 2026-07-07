"""Frappe-facing API for Korea Payroll Time Input (F1 근무시간 제출).

고객사(노호)가 초과근무를 채팅으로 전달하다 108.5시간 통누락·63→13시간 오적용이
반복된 사고를 막기 위한 시스템 직접 입력 엔드포인트다.

- list_time_inputs: 해당 월 전 직원(Active) 그리드 — 입력 없던 직원도 0으로 포함
- save_time_inputs: draft 행 upsert (submitted 행은 수정 불가)
- submit_time_inputs: 해당 월 draft 전건 submitted 확정 (idempotent)

검증 로직(기간 포맷·0~400 시간 범위·행 정규화)은 framework-free로 분리되어
FakeFrappe 없이도 단위 테스트 가능하다.
"""

from __future__ import annotations

import json
import re
from typing import Any

try:  # pragma: no cover - exercised only inside a Frappe bench or test stub
	import frappe  # type: ignore
except ImportError:  # pragma: no cover
	frappe = None  # type: ignore

TIME_INPUT_DOCTYPE = "Korea Payroll Time Input"
EMPLOYEE_DOCTYPE = "Employee"
ALLOWED_ROLES = ["HR Manager", "HR User"]
HOUR_FIELDS = ("overtime_hours", "night_hours", "holiday_hours", "part_time_hours")
MAX_HOURS = 400.0
PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

LIST_CONTRACT_TYPE = "korea_payroll_time_input_list_v1"
SAVE_CONTRACT_TYPE = "korea_payroll_time_input_save_v1"
SUBMIT_CONTRACT_TYPE = "korea_payroll_time_input_submit_v1"


# ── framework-free 검증 코어 ────────────────────────────────────────


def validate_period_text(period: Any) -> str:
	"""period가 'YYYY-MM'(01~12월) 텍스트인지 검증하고 정규화한다."""

	if not isinstance(period, str) or not PERIOD_PATTERN.fullmatch(period.strip()):
		raise ValueError("period must be in YYYY-MM format")
	return period.strip()


def coerce_hours(value: Any, fieldname: str) -> float:
	"""시간 값을 0~400 범위의 float로 강제한다. 빈 값은 0."""

	if value is None or (isinstance(value, str) and not value.strip()):
		return 0.0
	if isinstance(value, bool):
		raise ValueError(f"{fieldname} must be a number")
	try:
		number = float(value)
	except (TypeError, ValueError):
		raise ValueError(f"{fieldname} must be a number") from None
	if number != number:  # NaN 거부
		raise ValueError(f"{fieldname} must be a number")
	if not (0 <= number <= MAX_HOURS):
		raise ValueError(f"{fieldname} must be between 0 and {MAX_HOURS:g}")
	return number


def normalize_time_input_rows(rows: Any) -> list[dict[str, Any]]:
	"""upsert 입력 행들을 정규화한다. 쓰기 전에 전 행을 먼저 검증한다."""

	if not isinstance(rows, list):
		raise ValueError("rows must be a list or JSON array")
	normalized: list[dict[str, Any]] = []
	seen_employees: set[str] = set()
	for row in rows:
		if not isinstance(row, dict):
			raise ValueError("each row must be a JSON object")
		employee = row.get("employee")
		if not isinstance(employee, str) or not employee.strip():
			raise ValueError("each row requires a non-empty employee")
		employee = employee.strip()
		if employee in seen_employees:
			raise ValueError(f"duplicate employee row: {employee}")
		seen_employees.add(employee)
		note = row.get("note") or ""
		if not isinstance(note, str):
			raise ValueError("note must be a string")
		normalized.append(
			{
				"employee": employee,
				**{fieldname: coerce_hours(row.get(fieldname), fieldname) for fieldname in HOUR_FIELDS},
				"note": note.strip(),
			}
		)
	return normalized


def merge_employee_time_inputs(
	employees: list[dict[str, Any]], inputs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
	"""전 직원 목록에 기존 입력을 join한 그리드 행을 만든다(미입력 직원은 0)."""

	inputs_by_employee = {row.get("employee"): row for row in inputs}
	grid: list[dict[str, Any]] = []
	for employee in employees:
		existing = inputs_by_employee.get(employee.get("name"), {})
		grid.append(
			{
				"employee": employee.get("name"),
				"employee_name": employee.get("employee_name"),
				**{fieldname: float(existing.get(fieldname) or 0) for fieldname in HOUR_FIELDS},
				"note": existing.get("note") or "",
				"status": existing.get("status") or "draft",
				"submitted_by": existing.get("submitted_by"),
				"submitted_at": existing.get("submitted_at"),
			}
		)
	return grid


# ── Frappe 런타임 경계 ──────────────────────────────────────────────


def _whitelist(fn):
	if frappe is None:
		return fn
	return frappe.whitelist()(fn)


@_whitelist
def list_time_inputs(period: Any, company: Any = None) -> dict[str, Any]:
	"""해당 월 전 직원(Active) 근무시간 입력 그리드를 반환한다."""

	_runtime_required()
	period_text = validate_period_text(period)
	company_text = _resolve_company(company)
	_require_access()
	employees = _active_employees(company_text)
	inputs = frappe.get_all(  # type: ignore[union-attr]
		TIME_INPUT_DOCTYPE,
		filters={"company": company_text, "period": period_text},
		fields=["name", "employee", "employee_name", *HOUR_FIELDS, "note", "status", "submitted_by", "submitted_at"],
	)
	rows = merge_employee_time_inputs(employees, inputs)
	submitted_count = sum(1 for row in inputs if row.get("status") == "submitted")
	return {
		"contract_type": LIST_CONTRACT_TYPE,
		"company": company_text,
		"period": period_text,
		"rows": rows,
		"total_employees": len(employees),
		"submitted_count": submitted_count,
		"all_submitted": bool(inputs) and submitted_count == len(inputs),
	}


@_whitelist
def save_time_inputs(period: Any, rows: Any, company: Any = None) -> dict[str, Any]:
	"""근무시간 입력 행들을 upsert한다. draft만 수정 가능, submitted면 거부."""

	_runtime_required()
	period_text = validate_period_text(period)
	company_text = _resolve_company(company)
	_require_access()
	normalized = normalize_time_input_rows(_coerce_json_if_needed(rows))

	employee_names = {employee["name"]: employee.get("employee_name") for employee in _active_employees(company_text)}
	plans: list[dict[str, Any]] = []
	for row in normalized:
		if row["employee"] not in employee_names:
			raise ValueError(f"unknown or inactive employee for {company_text}: {row['employee']}")
		existing = frappe.get_all(  # type: ignore[union-attr]
			TIME_INPUT_DOCTYPE,
			filters={"company": company_text, "period": period_text, "employee": row["employee"]},
			fields=["name", "status"],
		)
		if existing and existing[0].get("status") == "submitted":
			raise PermissionError(
				f"submitted time inputs cannot be modified: {row['employee']} ({period_text})"
			)
		plans.append({"row": row, "existing_name": existing[0]["name"] if existing else None})

	created = updated = 0
	for plan in plans:
		row = plan["row"]
		if plan["existing_name"]:
			doc = frappe.get_doc(TIME_INPUT_DOCTYPE, plan["existing_name"])  # type: ignore[union-attr]
			for fieldname in HOUR_FIELDS:
				setattr(doc, fieldname, row[fieldname])
			doc.note = row["note"]
			doc.save()
			updated += 1
		else:
			frappe.get_doc(  # type: ignore[union-attr]
				{
					"doctype": TIME_INPUT_DOCTYPE,
					"company": company_text,
					"period": period_text,
					"employee": row["employee"],
					"employee_name": employee_names[row["employee"]],
					**{fieldname: row[fieldname] for fieldname in HOUR_FIELDS},
					"note": row["note"],
					"status": "draft",
				}
			).insert()
			created += 1
	return {
		"contract_type": SAVE_CONTRACT_TYPE,
		"company": company_text,
		"period": period_text,
		"created": created,
		"updated": updated,
	}


@_whitelist
def submit_time_inputs(period: Any, company: Any = None) -> dict[str, Any]:
	"""해당 월 draft 전건을 submitted로 확정한다. 이미 제출된 경우 idempotent."""

	_runtime_required()
	period_text = validate_period_text(period)
	company_text = _resolve_company(company)
	_require_access()
	scope_filters = {"company": company_text, "period": period_text}
	draft_names = frappe.get_all(  # type: ignore[union-attr]
		TIME_INPUT_DOCTYPE, filters={**scope_filters, "status": "draft"}, pluck="name"
	)
	submitted_by = frappe.session.user  # type: ignore[union-attr]
	submitted_at = frappe.utils.now()  # type: ignore[union-attr]
	if not draft_names:
		already = frappe.get_all(  # type: ignore[union-attr]
			TIME_INPUT_DOCTYPE, filters={**scope_filters, "status": "submitted"}, pluck="name"
		)
		return {
			"contract_type": SUBMIT_CONTRACT_TYPE,
			"company": company_text,
			"period": period_text,
			"submitted_count": 0,
			"already_submitted": bool(already),
			"total_submitted": len(already),
		}
	for name in draft_names:
		doc = frappe.get_doc(TIME_INPUT_DOCTYPE, name)  # type: ignore[union-attr]
		doc.status = "submitted"
		doc.submitted_by = submitted_by
		doc.submitted_at = submitted_at
		doc.save()
	return {
		"contract_type": SUBMIT_CONTRACT_TYPE,
		"company": company_text,
		"period": period_text,
		"submitted_count": len(draft_names),
		"already_submitted": False,
		"submitted_by": submitted_by,
		"submitted_at": submitted_at,
	}


# ── 내부 헬퍼 ───────────────────────────────────────────────────────


def _active_employees(company: str) -> list[dict[str, Any]]:
	return frappe.get_all(  # type: ignore[union-attr]
		EMPLOYEE_DOCTYPE,
		filters={"company": company, "status": "Active"},
		fields=["name", "employee_name"],
	)


def _resolve_company(company: Any) -> str:
	if company is None:
		company = frappe.db.get_single_value("Global Defaults", "default_company")  # type: ignore[union-attr]
	if not isinstance(company, str) or not company.strip():
		raise ValueError("company must be a non-empty string")
	return company.strip()


def _require_access() -> None:
	if hasattr(frappe, "only_for"):
		frappe.only_for(ALLOWED_ROLES)  # type: ignore[union-attr]


def _runtime_required() -> None:
	if frappe is None:
		raise RuntimeError("Frappe runtime is required for Korea payroll time input operations")


def _coerce_json_if_needed(value: Any) -> Any:
	if isinstance(value, str):
		text = value.strip()
		if text.startswith("{") or text.startswith("["):
			try:
				return json.loads(text)
			except json.JSONDecodeError as exc:
				raise ValueError("JSON payload is invalid") from exc
	return value


__all__ = [
	"list_time_inputs",
	"save_time_inputs",
	"submit_time_inputs",
	"validate_period_text",
	"coerce_hours",
	"normalize_time_input_rows",
	"merge_employee_time_inputs",
]
