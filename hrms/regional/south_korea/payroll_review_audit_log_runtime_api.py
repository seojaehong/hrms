"""Frappe-facing read-only runtime API for Korea payroll review audit logs.

These endpoints query persisted ``Korea Payroll Closing Review Audit Log`` rows and
reuse the framework-free route-only list/detail contracts. They do not save,
submit, approve, send notifications, call providers, or create payroll documents.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only inside a Frappe bench or test stub
	import frappe  # type: ignore
except ImportError:  # pragma: no cover - direct-run import without Frappe is unsupported for runtime reads
	frappe = None  # type: ignore

DOCTYPE = "Korea Payroll Closing Review Audit Log"
RUNTIME_INSERT_CONTRACT_TYPE = "korea_payroll_closing_review_audit_log_runtime_insert_v1"
RUNTIME_INSERT_ACTION = "runtime_review_audit_log_created"
MUTATION_BOUNDARY = "audit_log_only_no_submit_no_send_no_provider_call"
AUDIT_LOG_CONTRACT_TYPE = "korea_payroll_closing_draft_review_audit_log_v1"
AI_ROLE = "assistant_only"
DEFAULT_LIMIT = 50
MAX_LIMIT = 200

ROW_FIELDS = [
	"name",
	"company",
	"workplace",
	"period_start",
	"period_end",
	"status",
	"action",
	"draft_name",
	"source_payroll_entry",
	"previous_status",
	"review_actor",
	"audit_actor",
	"source_audit_log_contract_type",
	"mutation_boundary",
	"requires_human_approval",
	"ai_role",
	"audit_event",
	"source_runtime_apply",
	"docstatus",
	"creation",
]


def _whitelist(fn):
	if frappe is None:
		return fn
	return frappe.whitelist()(fn)


@_whitelist
def list_korea_payroll_review_audit_logs_runtime(
	*,
	company: str,
	workplaces: Any | None = None,
	limit: Any = DEFAULT_LIMIT,
) -> dict[str, Any]:
	"""Return a scoped operator list from persisted review audit-log rows."""

	_runtime_required()
	company_text = _require_text(company, "company")
	workplace_payloads = None if workplaces is None else deepcopy(_coerce_list(workplaces, "workplaces"))
	limit_value = _coerce_limit(limit)
	filters: dict[str, Any] = {"company": company_text}
	if workplace_payloads is not None:
		filters["workplace"] = ("in", workplace_payloads)
	rows = frappe.get_all(  # type: ignore[union-attr]
		DOCTYPE,
		filters=filters,
		fields=ROW_FIELDS,
		order_by="creation desc",
		limit_page_length=limit_value,
	)
	row_payloads = [_runtime_row_from_doc(row) for row in rows]
	core = _load_sibling_module("payroll_review_audit_log_list.py", "korea_payroll_review_audit_log_list_runtime_core")
	result = deepcopy(
		core.build_korea_payroll_review_audit_log_list(
			row_payloads,
			company=company_text,
			workplaces=workplace_payloads,
			strict_scope=True,
		)
	)
	list_contract_type = result.get("contract_type")
	result.update(
		{
			"contract_type": "korea_payroll_review_audit_log_runtime_list_api_v1",
			"audit_log_list_contract_type": list_contract_type,
			"runtime_action": "runtime_read_only",
			"requires_runtime_apply": False,
			"requires_human_approval": True,
			"ai_role": AI_ROLE,
		}
	)
	return result


@_whitelist
def get_korea_payroll_review_audit_log_detail_runtime(
	*,
	company: str,
	name: Any,
	workplaces: Any | None = None,
) -> dict[str, Any]:
	"""Return one scoped route-only audit-log detail from a persisted row."""

	_runtime_required()
	company_text = _require_text(company, "company")
	name_text = _require_text(name, "name")
	workplace_payloads = None if workplaces is None else deepcopy(_coerce_list(workplaces, "workplaces"))
	filters: dict[str, Any] = {"name": name_text, "company": company_text}
	if workplace_payloads is not None:
		filters["workplace"] = ("in", workplace_payloads)
	rows = frappe.get_all(  # type: ignore[union-attr]
		DOCTYPE,
		filters=filters,
		fields=ROW_FIELDS,
		order_by="creation desc",
		limit_page_length=1,
	)
	if not rows:
		raise ValueError("audit row was not found in the requested company/workplace scope")
	row = _runtime_row_from_doc(rows[0])
	core = _load_sibling_module("payroll_review_audit_log_list.py", "korea_payroll_review_audit_log_detail_runtime_core")
	result = deepcopy(
		core.build_korea_payroll_review_audit_log_detail(
			row,
			company=company_text,
			workplaces=workplace_payloads,
		)
	)
	detail_contract_type = result.get("contract_type")
	result.update(
		{
			"contract_type": "korea_payroll_review_audit_log_runtime_detail_api_v1",
			"audit_log_detail_contract_type": detail_contract_type,
			"runtime_action": "runtime_read_only",
			"requires_runtime_apply": False,
			"requires_human_approval": True,
			"ai_role": AI_ROLE,
		}
	)
	return result


def _runtime_required() -> None:
	if frappe is None:
		raise RuntimeError("Frappe runtime is required for payroll review audit-log runtime reads")


def _runtime_row_from_doc(value: Any) -> dict[str, Any]:
	if not isinstance(value, dict):
		value = {field: getattr(value, field, None) for field in ROW_FIELDS}
	row = deepcopy(value)
	creation = row.pop("creation", None)
	created_at = _normalize_optional_created_at(row.get("created_at") or creation)
	period_start = _normalize_iso_date(row.get("period_start"), "period_start")
	period_end = _normalize_iso_date(row.get("period_end"), "period_end")
	row.update(
		{
			"contract_type": RUNTIME_INSERT_CONTRACT_TYPE,
			"runtime_action": RUNTIME_INSERT_ACTION,
			"requires_runtime_apply": False,
			"mutation_boundary": row.get("mutation_boundary"),
			"doctype": DOCTYPE,
			"source_audit_log_contract_type": row.get("source_audit_log_contract_type"),
			"requires_human_approval": _coerce_stored_bool(row.get("requires_human_approval"), "requires_human_approval"),
			"ai_role": row.get("ai_role"),
			"docstatus": row.get("docstatus", 0),
			"created_at": created_at,
			"period_start": period_start,
			"period_end": period_end,
		}
	)
	row["audit_event"] = _coerce_json_object(row.get("audit_event"), "audit_event")
	row["source_runtime_apply"] = _coerce_json_object(row.get("source_runtime_apply"), "source_runtime_apply")
	return row


def _coerce_stored_bool(value: Any, fieldname: str) -> bool:
	if value is True or value == 1:
		return True
	if value is False or value == 0:
		return False
	raise ValueError(f"{fieldname} must be stored as a boolean check value")


def _normalize_optional_created_at(value: Any) -> str | None:
	"""Return only timezone-aware timestamps accepted by the route-only core."""

	if value is None:
		return None
	if isinstance(value, dt.datetime):
		if value.tzinfo is None or value.utcoffset() is None:
			return None
		return value.isoformat()
	if isinstance(value, str):
		text = value.strip()
		if not text:
			return None
		try:
			parsed = dt.datetime.fromisoformat(text)
		except ValueError:
			return None
		if parsed.tzinfo is None or parsed.utcoffset() is None:
			return None
		return parsed.isoformat()
	return None


def _normalize_iso_date(value: Any, fieldname: str) -> str:
	if type(value) is dt.date:
		return value.isoformat()
	if isinstance(value, str):
		text = value.strip()
		try:
			return dt.date.fromisoformat(text).isoformat()
		except ValueError as exc:
			raise ValueError(f"{fieldname} must be an ISO date") from exc
	raise ValueError(f"{fieldname} must be an ISO date")


def _coerce_json_object(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a JSON object")
	return coerced


def _coerce_list(value: Any, fieldname: str) -> list[Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, list):
		raise ValueError(f"{fieldname} must be a list or JSON array")
	for item in coerced:
		if not isinstance(item, str) or not item.strip():
			raise ValueError(f"{fieldname} must contain non-empty strings")
	return [item.strip() for item in coerced]


def _coerce_json_if_needed(value: Any) -> Any:
	if isinstance(value, str):
		text = value.strip()
		if text.startswith("{") or text.startswith("["):
			try:
				return json.loads(text)
			except json.JSONDecodeError as exc:
				raise ValueError("JSON payload is invalid") from exc
	return value


def _coerce_limit(value: Any) -> int:
	if value is None:
		return DEFAULT_LIMIT
	if type(value) is int:
		limit = value
	elif isinstance(value, str) and value.strip().isdigit():
		limit = int(value.strip())
	else:
		raise ValueError("limit must be an integer")
	if limit < 1 or limit > MAX_LIMIT:
		raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
	return limit


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


__all__ = [
	"list_korea_payroll_review_audit_logs_runtime",
	"get_korea_payroll_review_audit_log_detail_runtime",
]
