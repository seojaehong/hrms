"""Framework-free South Korea employment contract helpers."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

REQUIRED_TERMS = (
	"employee",
	"company",
	"workplace",
	"start_date",
	"job_title",
	"employment_type",
	"working_hours_per_week",
	"monthly_wage",
	"pay_day",
)


def build_contract_snapshot(
	*,
	employee: str,
	company: str,
	workplace: str,
	start_date: dt.date,
	job_title: str,
	employment_type: str,
	working_hours_per_week: float,
	monthly_wage: int,
	pay_day: int,
	end_date: dt.date | None = None,
	probation_months: int = 0,
	work_location: str | None = None,
	work_duties: str | None = None,
) -> dict[str, Any]:
	"""Return a deterministic MVP employment contract payload.

	The helper avoids Frappe imports so contract policy can be tested before DocType
	or print-format integration. It records required-term completeness instead of
	throwing on blank business fields, while rejecting invalid dates and numbers.
	"""

	_validate_date("start_date", start_date)
	if end_date is not None:
		_validate_date("end_date", end_date)
		if end_date < start_date:
			raise ValueError("end_date cannot be before start_date")
	_validate_positive_finite("working_hours_per_week", working_hours_per_week)
	monthly_wage = _require_plain_int("monthly_wage", monthly_wage)
	pay_day = _require_plain_int("pay_day", pay_day)
	probation_months = _require_plain_int("probation_months", probation_months)
	if monthly_wage < 0:
		raise ValueError("monthly_wage cannot be negative")
	if not 1 <= pay_day <= 31:
		raise ValueError("pay_day must be between 1 and 31")
	if probation_months < 0:
		raise ValueError("probation_months cannot be negative")

	payload: dict[str, Any] = {
		"employee": str(employee or "").strip(),
		"company": str(company or "").strip(),
		"workplace": str(workplace or "").strip(),
		"start_date": start_date.isoformat(),
		"end_date": end_date.isoformat() if end_date else None,
		"contract_type": "Fixed Term" if end_date else "Indefinite",
		"job_title": str(job_title or "").strip(),
		"employment_type": str(employment_type or "").strip(),
		"working_hours_per_week": round(float(working_hours_per_week), 2),
		"monthly_wage": int(monthly_wage),
		"pay_day": int(pay_day),
		"probation_months": int(probation_months),
		"work_location": str(work_location or workplace or "").strip(),
		"work_duties": str(work_duties or job_title or "").strip(),
	}
	missing_terms = [field for field in REQUIRED_TERMS if _is_missing(payload.get(field))]
	payload["required_terms_complete"] = not missing_terms
	payload["missing_terms"] = missing_terms
	payload["signature_hash"] = contract_signature_hash(payload)
	return payload


def contract_signature_hash(payload: dict[str, Any]) -> str:
	"""Return deterministic hash for a reviewed contract payload."""

	normalized = {
		key: value
		for key, value in payload.items()
		if key not in {"signature_hash"}
	}
	canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
	return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_missing(value: Any) -> bool:
	return value is None or (isinstance(value, str) and not value.strip())


def _validate_date(fieldname: str, value: dt.date) -> None:
	if type(value) is not dt.date:
		raise TypeError(f"{fieldname} must be a datetime.date")


def _validate_positive_finite(fieldname: str, value: float) -> None:
	if isinstance(value, bool):
		raise ValueError(f"{fieldname} must be numeric")
	try:
		number = float(value)
	except (TypeError, ValueError) as exc:
		raise ValueError(f"{fieldname} must be numeric") from exc
	if number <= 0 or number in {float("inf"), float("-inf")} or number != number:
		raise ValueError(f"{fieldname} must be a positive finite number")


def _require_plain_int(fieldname: str, value: int) -> int:
	if type(value) is not int:
		raise ValueError(f"{fieldname} must be an integer")
	return value


__all__ = ["REQUIRED_TERMS", "build_contract_snapshot", "contract_signature_hash"]
