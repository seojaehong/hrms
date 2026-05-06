"""Framework-free Korea HR profile validation contracts."""

from __future__ import annotations

import datetime as dt
import re
from copy import deepcopy
from typing import Any

BUSINESS_REGISTRATION_RE = re.compile(r"^\d{3}-\d{2}-\d{5}$")
WORKPLACE_MANAGEMENT_RE = re.compile(r"^\d{11}$")
MASKED_RRN_RE = re.compile(r"^\d{6}-[1-8]\*{6}$")


def validate_workplace_profile(profile: dict[str, Any]) -> dict[str, Any]:
	"""Validate a Korea Workplace Profile-shaped payload without mutation."""

	if not isinstance(profile, dict):
		raise TypeError("profile must be a dict")
	normalized = deepcopy(profile)
	business_registration_number = str(normalized.get("business_registration_number") or "").strip()
	workplace_management_number = str(normalized.get("workplace_management_number") or "").strip()

	if business_registration_number:
		if not BUSINESS_REGISTRATION_RE.match(business_registration_number):
			raise ValueError("business_registration_number must use 000-00-00000 format")
		normalized["business_registration_number"] = business_registration_number
	if workplace_management_number:
		if not WORKPLACE_MANAGEMENT_RE.match(workplace_management_number):
			raise ValueError("workplace_management_number must be 11 digits")
		normalized["workplace_management_number"] = workplace_management_number
	return _valid_result(normalized)


def validate_employment_profile(
	profile: dict[str, Any],
	*,
	employee_company: str | None = None,
	workplace_company: str | None = None,
) -> dict[str, Any]:
	"""Validate a Korea Employment Profile-shaped payload without mutation."""

	if not isinstance(profile, dict):
		raise TypeError("profile must be a dict")
	normalized = deepcopy(profile)
	company = _blank_to_none(normalized.get("company"))
	if company is not None:
		normalized["company"] = company
	rrn_masked = str(normalized.get("rrn_masked") or "").strip()
	if rrn_masked:
		if not MASKED_RRN_RE.match(rrn_masked):
			raise ValueError("rrn_masked must be masked, for example 900101-1******")
		normalized["rrn_masked"] = rrn_masked

	start_date = _coerce_optional_iso_date(normalized.get("contract_start_date"), "contract_start_date")
	end_date = _coerce_optional_iso_date(normalized.get("contract_end_date"), "contract_end_date")
	if start_date is not None:
		normalized["contract_start_date"] = start_date.isoformat()
	if end_date is not None:
		normalized["contract_end_date"] = end_date.isoformat()
	if start_date is not None and end_date is not None and end_date < start_date:
		raise ValueError("contract_end_date must be on or after contract_start_date")

	if company and employee_company and str(employee_company).strip() != company:
		raise ValueError("employee_company must match employment profile company")
	if company and workplace_company and str(workplace_company).strip() != company:
		raise ValueError("workplace_company must match employment profile company")

	return _valid_result(normalized)


def _valid_result(normalized: dict[str, Any]) -> dict[str, Any]:
	return {
		"valid": True,
		"normalized": deepcopy(normalized),
		"errors": [],
		"warnings": [],
	}


def _blank_to_none(value: Any) -> str | None:
	text = str(value or "").strip()
	return text or None


def _coerce_optional_iso_date(value: Any, fieldname: str) -> dt.date | None:
	if value in (None, ""):
		return None
	if isinstance(value, dt.datetime):
		return value.date()
	if isinstance(value, dt.date):
		return value
	if isinstance(value, str):
		try:
			return dt.date.fromisoformat(value.strip())
		except ValueError as exc:
			raise ValueError(f"{fieldname} must be an ISO date string") from exc
	raise ValueError(f"{fieldname} must be a date or ISO date string")


__all__ = [
	"validate_workplace_profile",
	"validate_employment_profile",
]
