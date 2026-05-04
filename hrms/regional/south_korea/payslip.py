"""Framework-free Korea payslip MVP helpers."""

from __future__ import annotations

import hashlib
import json
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


def _normalize_line(line: dict[str, Any]) -> dict[str, Any]:
	label = str(line.get("label") or "").strip()
	if not label:
		raise ValueError("line label is required")
	amount = int(line.get("amount", 0))
	if amount < 0:
		raise ValueError("line amount cannot be negative")
	return {"label": label, "amount": amount}


def _mask_employee(employee: str) -> str:
	if len(employee) <= 4:
		return "*" * len(employee)
	return f"{employee[:4]}****{employee[-2:]}"


def _checksum(payload: dict[str, Any]) -> str:
	canonical = json.dumps({k: v for k, v in payload.items() if k != "checksum"}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
	return hashlib.sha256(canonical.encode()).hexdigest()


__all__ = ["build_payslip_snapshot", "build_employee_payslip_view"]
