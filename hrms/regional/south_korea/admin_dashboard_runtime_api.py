"""Frappe-facing read-only runtime API for Korea admin dashboard cards.

This endpoint queries narrow persisted runtime rows for the operator Admin Home and
then delegates card construction to the framework-free dashboard contract. It does
not save, submit, approve, send notifications, call providers, or create payroll
or audit documents.
"""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only inside a Frappe bench or test stub
	import frappe  # type: ignore
except ImportError:  # pragma: no cover - direct-run import without Frappe is unsupported for runtime reads
	frappe = None  # type: ignore

DRAFT_DOCTYPE = "Korea Payroll Closing Draft"
AUDIT_LOG_DOCTYPE = "Korea Payroll Closing Review Audit Log"
EMPLOYEE_DOCTYPE = "Employee"
SALARY_SLIP_DOCTYPE = "Salary Slip"
ATTENDANCE_DOCTYPE = "Attendance"
PENDING_DRAFT_STATUS = "draft_pending_human_approval"
RUNTIME_READ_DOCTYPES = (DRAFT_DOCTYPE, AUDIT_LOG_DOCTYPE, EMPLOYEE_DOCTYPE, SALARY_SLIP_DOCTYPE, ATTENDANCE_DOCTYPE)


def _whitelist(fn):
	if frappe is None:
		return fn
	return frappe.whitelist()(fn)


@_whitelist
def get_korea_admin_dashboard_runtime(*, company: Any, workplaces: Any | None = None) -> dict[str, Any]:
	"""Return read-only operator dashboard cards from persisted Korea runtime rows."""

	_runtime_required()
	company_text = _require_text(company, "company")
	workplace_payloads = None if workplaces is None else _coerce_workplaces(workplaces)
	_require_runtime_read_access()
	metrics = _build_runtime_metrics(company=company_text, workplaces=workplace_payloads)
	admin_dashboard = _load_sibling_module("admin_dashboard.py", "korea_admin_dashboard_runtime_core")
	dashboard = admin_dashboard.build_admin_dashboard(metrics=metrics)
	return {
		"contract_type": "korea_admin_dashboard_runtime_api_v1",
		"runtime_action": "runtime_read_only",
		"requires_runtime_apply": False,
		"company": company_text,
		"workplaces": list(workplace_payloads) if workplace_payloads is not None else [],
		"metrics": deepcopy(metrics),
		"dashboard": deepcopy(dashboard),
	}


def _build_runtime_metrics(*, company: str, workplaces: list[str] | None) -> dict[str, int]:
	filters = _scope_filters(company=company, workplaces=workplaces)
	draft_filters = {**filters, "status": PENDING_DRAFT_STATUS, "docstatus": 0}
	audit_filters = {**filters, "docstatus": 0}
	operational_filters = _operational_doctype_filters(company=company, workplaces=workplaces)
	return {
		"blocked_payroll_closings": _count_doctype(DRAFT_DOCTYPE, draft_filters),
		"payroll_review_audit_logs": _count_doctype(AUDIT_LOG_DOCTYPE, audit_filters),
		"pending_payslips": _count_doctype(SALARY_SLIP_DOCTYPE, {**operational_filters, "docstatus": 0}),
		"unclosed_attendance": _count_doctype(ATTENDANCE_DOCTYPE, {**operational_filters, "docstatus": 0}),
	}


def _scope_filters(*, company: str, workplaces: list[str] | None) -> dict[str, Any]:
	filters: dict[str, Any] = {"company": company}
	if workplaces is not None:
		filters["workplace"] = ("in", list(workplaces))
	return filters


def _operational_doctype_filters(*, company: str, workplaces: list[str] | None) -> dict[str, Any]:
	filters: dict[str, Any] = {"company": company}
	if workplaces is not None:
		employees = frappe.get_all(  # type: ignore[union-attr]
			EMPLOYEE_DOCTYPE,
			filters={"company": company, "work_location_name": ("in", list(workplaces))},
			pluck="name",
		)
		filters["employee"] = ("in", list(employees))
	return filters


def _count_doctype(doctype: str, filters: dict[str, Any]) -> int:
	count = frappe.db.count(doctype, filters=filters)  # type: ignore[union-attr]
	if type(count) is not int or count < 0:
		raise ValueError(f"{doctype} count must be a non-negative integer")
	return count


def _runtime_required() -> None:
	if frappe is None:
		raise RuntimeError("Frappe runtime is required for Korea admin dashboard runtime reads")
	if not hasattr(frappe, "db") or not hasattr(frappe.db, "count"):
		raise RuntimeError("Frappe database count API is required for Korea admin dashboard runtime reads")
	if not hasattr(frappe, "get_all"):
		raise RuntimeError("Frappe get_all API is required for Korea admin dashboard runtime reads")


def _require_runtime_read_access() -> None:
	if hasattr(frappe, "only_for"):
		frappe.only_for(["HR Manager"])  # type: ignore[union-attr]
	if hasattr(frappe, "has_permission"):
		for doctype in RUNTIME_READ_DOCTYPES:
			if not frappe.has_permission(doctype, ptype="read"):  # type: ignore[union-attr]
				raise PermissionError(f"read permission is required for {doctype}")


def _coerce_workplaces(value: Any) -> list[str]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, list):
		raise ValueError("workplaces must be a list or JSON array")
	normalized: list[str] = []
	for workplace in coerced:
		if not isinstance(workplace, str) or not workplace.strip():
			raise ValueError("workplaces must contain non-empty strings")
		text = workplace.strip()
		if text not in normalized:
			normalized.append(text)
	return normalized


def _coerce_json_if_needed(value: Any) -> Any:
	if isinstance(value, str):
		text = value.strip()
		if text.startswith("{") or text.startswith("["):
			try:
				return json.loads(text)
			except json.JSONDecodeError as exc:
				raise ValueError("JSON payload is invalid") from exc
	return value


def _require_text(value: Any, fieldname: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{fieldname} must be a non-empty string")
	return value.strip()


def _load_sibling_module(filename: str, module_name: str):
	path = Path(__file__).with_name(filename)
	spec = importlib.util.spec_from_file_location(module_name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = ["get_korea_admin_dashboard_runtime"]
