"""Framework-free Korea expense claim and cost settlement helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

_AMOUNT_PATTERN = re.compile(r"^[0-9]+$")


def build_cost_settlement(*, claims: list[dict[str, Any]]) -> dict[str, Any]:
	"""Aggregate expense claims by cost center and Korea tax category."""

	by_cost_center: dict[str, int] = {}
	by_tax_category: dict[str, int] = {}
	total = 0
	for claim in claims:
		amount = _amount(claim)
		cost_center = str(claim.get("cost_center") or "Unassigned")
		tax_category = str(claim.get("tax_category") or "Unclassified")
		by_cost_center[cost_center] = by_cost_center.get(cost_center, 0) + amount
		by_tax_category[tax_category] = by_tax_category.get(tax_category, 0) + amount
		total += amount
	return {
		"claim_count": len(claims),
		"total_amount": total,
		"by_cost_center": dict(sorted(by_cost_center.items())),
		"by_tax_category": dict(sorted(by_tax_category.items())),
	}


def build_reimbursement_batch(claims: list[dict[str, Any]]) -> list[dict[str, int | str]]:
	"""Aggregate payable reimbursement amounts by employee."""

	by_employee: dict[str, int] = {}
	for claim in claims:
		employee = str(claim.get("employee") or "").strip()
		if not employee:
			raise ValueError("employee is required")
		by_employee[employee] = by_employee.get(employee, 0) + _amount(claim)
	return [{"employee": employee, "amount": amount} for employee, amount in sorted(by_employee.items())]


def _amount(claim: dict[str, Any]) -> int:
	value = claim.get("amount", 0)
	if isinstance(value, bool):
		raise ValueError("claim amount must be an integer KRW amount")
	if isinstance(value, str):
		value = value.strip()
		if not _AMOUNT_PATTERN.fullmatch(value):
			raise ValueError("claim amount must be a plain integer KRW amount")
	try:
		amount = Decimal(str(value))
	except (InvalidOperation, ValueError) as exc:
		raise ValueError("claim amount must be a finite number") from exc
	if not amount.is_finite():
		raise ValueError("claim amount must be a finite number")
	if amount != amount.to_integral_value():
		raise ValueError("claim amount must be an integer KRW amount")
	amount_int = int(amount)
	if amount_int < 0:
		raise ValueError("claim amount cannot be negative")
	return amount_int


__all__ = ["build_cost_settlement", "build_reimbursement_batch"]
