"""Framework-free Korea payroll verification provider contract.

This module intentionally does not depend on public/government payroll APIs.
It prepares internal statutory payroll snapshots for later verification through
realistic provider routes: paid vendors, partner APIs, delegated/RPA connectors,
owned connector services, or manual review.
"""

from __future__ import annotations

import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

_ALLOWED_PROVIDER_TYPES = {
	"paid_vendor_api",
	"partner_api",
	"delegated_rpa_connector",
	"owned_connector_service",
	"manual_review",
}

_ALLOWED_RESULT_STATUSES = {"verified", "needs_review", "rejected"}

_BASIS_FIELDS = (
	"gross_earnings",
	"taxable_earnings",
	"non_taxable_earnings",
	"employee_deductions",
	"employer_contributions",
	"total_employee_deductions",
	"total_employer_contributions",
	"net_reference_pay",
	"contribution_bases",
	"policy_reference",
)


def build_payroll_verification_request(
	*,
	snapshot: dict[str, Any],
	period: dict[str, Any],
	workplace: dict[str, Any],
	provider: dict[str, Any] | None = None,
	consent_reference: str | None = None,
) -> dict[str, Any]:
	"""Build a vendor-ready payroll verification request payload.

	The request is a pure contract object for future adapters. It keeps the
	internal policy-based payroll snapshot as the source of truth and lets an
	external provider supply verification evidence later.
	"""

	_validate_dict(snapshot, "snapshot")
	_validate_dict(period, "period")
	_validate_dict(workplace, "workplace")
	provider_payload = _normalize_provider(provider)
	basis = _extract_basis(snapshot)

	return {
		"request_type": "korea_payroll_verification_v1",
		"status": "pending_external_verification",
		"period": deepcopy(period),
		"workplace": deepcopy(workplace),
		"provider": provider_payload,
		"consent_reference": consent_reference,
		"basis": basis,
		"expected_evidence": [
			"provider_reference",
			"amount_delta_summary",
			"reviewable_evidence",
			"human_approval_decision",
		],
	}


def normalize_payroll_verification_result(*, request: dict[str, Any], provider_result: dict[str, Any]) -> dict[str, Any]:
	"""Normalize a provider response without auto-approving payroll output."""

	_validate_dict(request, "request")
	_validate_dict(provider_result, "provider_result")
	status = provider_result.get("status")
	if status not in _ALLOWED_RESULT_STATUSES:
		raise ValueError(f"status must be one of {sorted(_ALLOWED_RESULT_STATUSES)}")

	amount_deltas = _normalize_amount_deltas(provider_result.get("amount_deltas", {}))
	evidence = provider_result.get("evidence", [])
	if not isinstance(evidence, list):
		raise ValueError("evidence must be a list")

	provider_payload = _normalize_provider(request.get("provider"))
	return {
		"result_type": "korea_payroll_verification_result_v1",
		"status": status,
		"provider": provider_payload,
		"external_reference": provider_result.get("external_reference"),
		"amount_deltas": amount_deltas,
		"evidence": deepcopy(evidence),
		"review_notes": provider_result.get("review_notes"),
		"requires_human_approval": True,
	}


def _normalize_provider(provider: dict[str, Any] | None) -> dict[str, Any]:
	provider = {"type": "manual_review", "name": "manual payroll verification"} if provider is None else deepcopy(provider)
	_validate_dict(provider, "provider")
	provider_type = provider.get("type")
	if provider_type == "public_government_api":
		raise ValueError("public_government_api is not an allowed payroll verification provider")
	if provider_type not in _ALLOWED_PROVIDER_TYPES:
		raise ValueError(f"provider.type must be one of {sorted(_ALLOWED_PROVIDER_TYPES)}")
	if not str(provider.get("name") or "").strip():
		raise ValueError("provider.name is required")
	for fieldname in ("provider_key", "endpoint_key"):
		if fieldname in provider and provider[fieldname] is not None:
			value = str(provider[fieldname]).strip()
			if not value:
				raise ValueError(f"provider.{fieldname} is required when provided")
			if _contains_korean_mobile_number(value):
				raise ValueError(f"provider.{fieldname} must not contain phone numbers")
			provider[fieldname] = value
	return provider


def _extract_basis(snapshot: dict[str, Any]) -> dict[str, Any]:
	basis: dict[str, Any] = {}
	for field in _BASIS_FIELDS:
		if field in snapshot:
			basis[field] = deepcopy(snapshot[field])
	for field in (
		"gross_earnings",
		"taxable_earnings",
		"non_taxable_earnings",
		"total_employee_deductions",
		"total_employer_contributions",
		"net_reference_pay",
	):
		if field not in basis:
			raise ValueError(f"snapshot.{field} is required")
		basis[field] = _to_integer_won(basis[field], f"snapshot.{field}")
	for map_field in ("employee_deductions", "employer_contributions"):
		if map_field in basis:
			basis[map_field] = _normalize_amount_deltas(basis[map_field], prefix=f"snapshot.{map_field}")
	if "contribution_bases" in basis:
		basis["contribution_bases"] = _normalize_contribution_bases(basis["contribution_bases"])
	return basis


def _normalize_contribution_bases(value: Any) -> dict[str, dict[str, int]]:
	_validate_dict(value, "snapshot.contribution_bases")
	normalized: dict[str, dict[str, int]] = {}
	for component, split in value.items():
		component_name = str(component).strip()
		if not component_name:
			raise ValueError("snapshot.contribution_bases component name is required")
		_validate_dict(split, f"snapshot.contribution_bases.{component_name}")
		normalized[component_name] = {
			"employee": _to_integer_won(split.get("employee"), f"snapshot.contribution_bases.{component_name}.employee"),
			"employer": _to_integer_won(split.get("employer"), f"snapshot.contribution_bases.{component_name}.employer"),
		}
	return normalized


def _normalize_amount_deltas(amount_deltas: Any, *, prefix: str = "amount_deltas") -> dict[str, int]:
	_validate_dict(amount_deltas, prefix)
	normalized = {}
	for component, amount in amount_deltas.items():
		name = str(component).strip()
		if not name:
			raise ValueError(f"{prefix} component name is required")
		normalized[name] = _to_integer_won(amount, f"{prefix}.{name}")
	return normalized


def _validate_dict(value: Any, name: str) -> None:
	if not isinstance(value, dict):
		raise ValueError(f"{name} must be a dict")


def _contains_korean_mobile_number(value: str) -> bool:
	pattern = (
		r"(?<!\d)(?:01\d[-\s]?\d{3,4}[-\s]?\d{4}"
		r"|\+?82[-\s]?1\d[-\s]?\d{3,4}[-\s]?\d{4})(?!\d)"
	)
	return re.search(pattern, value) is not None


def _to_integer_won(value: Any, name: str) -> int:
	if isinstance(value, bool):
		raise ValueError(f"{name} must be a finite number")
	try:
		amount = Decimal(str(value))
	except (InvalidOperation, ValueError) as exc:
		raise ValueError(f"{name} must be a finite number") from exc
	if not amount.is_finite():
		raise ValueError(f"{name} must be a finite number")
	if amount != amount.to_integral_value():
		raise ValueError(f"{name} must be an integer KRW amount")
	return int(amount)


__all__ = ["build_payroll_verification_request", "normalize_payroll_verification_result"]
