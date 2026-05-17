"""Framework-free Korea payslip MVP helpers."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any


def build_payslip_snapshot(
	*,
	employee: str,
	period: str,
	earnings: list[dict[str, Any]],
	deductions: list[dict[str, Any]],
) -> dict[str, Any]:
	"""Build a deterministic payslip payload for employee self-service."""

	if not employee:
		raise ValueError("employee is required")
	if not period:
		raise ValueError("period is required")
	earning_lines = [_normalize_line(line) for line in earnings]
	deduction_lines = [_normalize_line(line) for line in deductions]
	gross_pay = sum(line["amount"] for line in earning_lines)
	total_deductions = sum(line["amount"] for line in deduction_lines)
	payload = {
		"employee": employee,
		"period": period,
		"sections": [
			{"title": "Earnings", "lines": earning_lines, "total": gross_pay},
			{"title": "Deductions", "lines": deduction_lines, "total": total_deductions},
		],
		"gross_pay": gross_pay,
		"total_deductions": total_deductions,
		"net_pay": gross_pay - total_deductions,
	}
	payload["checksum"] = _checksum(payload)
	return payload


def build_employee_payslip_view(payslip: dict[str, Any]) -> dict[str, Any]:
	"""Return employee-facing payslip view without internal checksum."""

	view = {key: value for key, value in payslip.items() if key != "checksum"}
	view["employee"] = _mask_employee(str(payslip.get("employee", "")))
	return view


def build_korea_wage_statement_preview(*, salary_slip: dict[str, Any], actor: str) -> dict[str, Any]:
	"""Build a print/PDF-friendly Korea wage statement preview.

	This helper is intentionally framework-free and side-effect-free. It mirrors
	the Korean wage statement sections operators need to review before any later
	download, notification, or payroll mutation path exists.
	"""

	if not isinstance(salary_slip, dict):
		raise ValueError("salary_slip must be a dict")
	actor = _require_text(actor, "actor")
	source_name = _require_text(salary_slip.get("name"), "salary_slip.name")
	employee = _require_text(salary_slip.get("employee"), "salary_slip.employee")
	company = _require_text(salary_slip.get("company"), "salary_slip.company")
	period_start = _require_text(salary_slip.get("period_start"), "salary_slip.period_start")
	period_end = _require_text(salary_slip.get("period_end"), "salary_slip.period_end")
	if period_start > period_end:
		raise ValueError("salary_slip.period_start cannot be after salary_slip.period_end")

	earnings = _normalize_wage_statement_lines(salary_slip.get("earnings"), "earnings")
	deductions = _normalize_wage_statement_lines(salary_slip.get("deductions", []), "deductions")
	gross_pay = sum(line["amount"] for line in earnings)
	total_deductions = sum(line["amount"] for line in deductions)
	calculation_basis = [
		{"section": "지급", "label": line["label"], "basis": line["basis"], "amount": line["amount"]}
		for line in earnings
	] + [
		{"section": "공제", "label": line["label"], "basis": line["basis"], "amount": line["amount"]}
		for line in deductions
	]

	return {
		"contract_type": "korea_wage_statement_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"source_salary_slip": source_name,
		"employee": employee,
		"employee_name": salary_slip.get("employee_name") or employee,
		"company": company,
		"period_start": period_start,
		"period_end": period_end,
		"sections": [
			{"title": "지급", "lines": earnings, "total": gross_pay},
			{"title": "공제", "lines": deductions, "total": total_deductions},
			{"title": "산출근거", "lines": calculation_basis},
		],
		"gross_pay": gross_pay,
		"total_deductions": total_deductions,
		"net_pay": gross_pay - total_deductions,
		"print_labels": {
			"earnings": "지급",
			"deductions": "공제",
			"calculation_basis": "산출근거",
			"net_pay": "실지급액",
		},
		"prepared_by": actor,
		"mutation_boundary": "preview_only_no_submit_approve_send_provider_call",
		"requires_human_approval": True,
		"ai_role": "assistant_only",
	}


def _normalize_line(line: dict[str, Any]) -> dict[str, Any]:
	label = str(line.get("label") or "").strip()
	if not label:
		raise ValueError("line label is required")
	amount = int(line.get("amount", 0))
	if amount < 0:
		raise ValueError("line amount cannot be negative")
	return {"label": label, "amount": amount}


def _normalize_wage_statement_lines(lines: Any, field: str) -> list[dict[str, Any]]:
	if not isinstance(lines, list):
		raise ValueError(f"salary_slip.{field} must be a list")
	if field == "earnings" and not lines:
		raise ValueError("salary_slip.earnings must not be empty")
	return [_normalize_wage_statement_line(line, f"salary_slip.{field}[{index}]") for index, line in enumerate(lines)]


def _normalize_wage_statement_line(line: Any, field: str) -> dict[str, Any]:
	if not isinstance(line, dict):
		raise ValueError(f"{field} must be a dict")
	label = _require_text(line.get("label"), f"{field}.label")
	basis = _require_text(line.get("basis"), f"{field}.basis")
	amount = _coerce_integer_krw(line.get("amount"), f"{field}.amount")
	if amount < 0:
		raise ValueError(f"{field}.amount cannot be negative")
	return {"label": label, "amount": amount, "basis": basis}


def _require_text(value: Any, field: str) -> str:
	if not isinstance(value, str):
		raise ValueError(f"{field} must be a string")
	value = value.strip()
	if not value:
		raise ValueError(f"{field} is required")
	return value


def _coerce_integer_krw(value: Any, field: str) -> int:
	if isinstance(value, bool):
		raise ValueError(f"{field} must be integer KRW")
	if isinstance(value, int):
		return value
	if isinstance(value, str):
		text = value.strip()
		if not text:
			raise ValueError(f"{field} must be integer KRW")
		if "e" in text.lower() or "." in text:
			raise ValueError(f"{field} must be integer KRW")
		try:
			amount = Decimal(text)
		except InvalidOperation as exc:
			raise ValueError(f"{field} must be integer KRW") from exc
		if not amount.is_finite() or amount != amount.to_integral_value():
			raise ValueError(f"{field} must be integer KRW")
		return int(amount)
	raise ValueError(f"{field} must be integer KRW")


def _mask_employee(employee: str) -> str:
	if len(employee) <= 4:
		return "*" * len(employee)
	return f"{employee[:4]}****{employee[-2:]}"


def _checksum(payload: dict[str, Any]) -> str:
	canonical = json.dumps({k: v for k, v in payload.items() if k != "checksum"}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
	return hashlib.sha256(canonical.encode()).hexdigest()


__all__ = ["build_payslip_snapshot", "build_employee_payslip_view", "build_korea_wage_statement_preview"]
