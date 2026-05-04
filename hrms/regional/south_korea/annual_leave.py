# Copyright (c) 2026, Frappe HRMS contributors
# For license information, please see license.txt

"""South Korea annual leave reference calculations.

This module intentionally stays framework-free so the calculation surface can be
validated without a running Frappe bench. Downstream PRs can wire this reference
engine into Leave Allocation and Korea Employment Profile records.
"""

from __future__ import annotations

import datetime as dt
from calendar import monthrange

SUPPORTED_BASES = {"Hire Date", "Fiscal Year"}


def calculate_annual_leave_entitlement(
	hire_date: dt.date,
	as_of_date: dt.date,
	basis: str = "Hire Date",
	fiscal_year_start_month: int = 1,
	fiscal_year_start_day: int = 1,
	employment_end_date: dt.date | None = None,
) -> dict:
	"""Return Korean annual leave entitlement reference values.

	Rules covered in v1:
	- first service year: one day for each completed month, capped at 11;
	- from first anniversary: 15 days;
	- long service: add one day every two years after the first year, capped at 25;
	- fiscal-year basis: keep monthly accrual and add a first-year prorated annual
	  entitlement for the fiscal period.
	"""

	_validate_inputs(
		hire_date,
		as_of_date,
		basis,
		fiscal_year_start_month,
		fiscal_year_start_day,
		employment_end_date,
	)
	effective_as_of_date = min(as_of_date, employment_end_date) if employment_end_date else as_of_date

	service_years = completed_years(hire_date, effective_as_of_date)
	if basis == "Fiscal Year":
		period_start, period_end = fiscal_period_for(
			effective_as_of_date, fiscal_year_start_month, fiscal_year_start_day
		)
		monthly_accrual = first_year_monthly_accrual(hire_date, effective_as_of_date)
		annual_entitlement = fiscal_year_annual_entitlement(
			hire_date=hire_date,
			as_of_date=effective_as_of_date,
			period_start=period_start,
			period_end=period_end,
			employment_end_date=employment_end_date,
		)
	else:
		period_start = add_years(hire_date, service_years)
		period_end = add_years(period_start, 1) - dt.timedelta(days=1)
		monthly_accrual = first_year_monthly_accrual(hire_date, effective_as_of_date)
		annual_entitlement = anniversary_annual_entitlement(service_years)

	total = round(monthly_accrual + annual_entitlement, 2)
	return {
		"basis": basis,
		"hire_date": hire_date,
		"as_of_date": as_of_date,
		"employment_end_date": employment_end_date,
		"period_start": period_start,
		"period_end": period_end,
		"service_years": service_years,
		"monthly_accrual_days": monthly_accrual,
		"annual_entitlement_days": annual_entitlement,
		"total_entitlement_days": total,
	}


def first_year_monthly_accrual(hire_date: dt.date, as_of_date: dt.date) -> int:
	"""One day per completed month before the first anniversary, capped at 11."""

	if as_of_date < hire_date:
		raise ValueError("as_of_date cannot be before hire_date")
	if completed_years(hire_date, as_of_date) >= 1:
		return 0
	return min(11, completed_months(hire_date, as_of_date))


def anniversary_annual_entitlement(service_years: int) -> int:
	"""Annual leave days from anniversary-based service years."""

	if service_years < 1:
		return 0
	additional_days = max(0, (service_years - 1) // 2)
	return min(25, 15 + additional_days)


def fiscal_year_annual_entitlement(
	hire_date: dt.date,
	as_of_date: dt.date,
	period_start: dt.date,
	period_end: dt.date,
	employment_end_date: dt.date | None = None,
) -> float:
	"""Return fiscal-year annual entitlement for the current fiscal period.

	For employees in their first service year, Korean HR operations commonly need
	a prorated reference amount when converting to fiscal-year administration. For
	employees past the first anniversary, use the anniversary entitlement measured
	at the fiscal period end.
	"""

	if completed_years(hire_date, as_of_date) < 1:
		employment_start = max(hire_date, period_start)
		employment_finish = min(period_end, employment_end_date) if employment_end_date else period_end
		if employment_start > employment_finish:
			return 0
		employed_days = (employment_finish - employment_start).days + 1
		period_days = (period_end - period_start).days + 1
		return round(15 * employed_days / period_days, 2)
	anniversary_reference_date = min(period_end, employment_end_date) if employment_end_date else period_end
	return anniversary_annual_entitlement(completed_years(hire_date, anniversary_reference_date))


def completed_years(start: dt.date, end: dt.date) -> int:
	"""Whole anniversaries completed between two dates."""

	years = end.year - start.year
	if add_years(start, years) > end:
		years -= 1
	return max(0, years)


def completed_months(start: dt.date, end: dt.date) -> int:
	"""Whole monthly anniversaries completed between two dates."""

	months = (end.year - start.year) * 12 + end.month - start.month
	if add_months(start, months) > end:
		months -= 1
	return max(0, months)


def fiscal_period_for(
	as_of_date: dt.date, fiscal_year_start_month: int = 1, fiscal_year_start_day: int = 1
) -> tuple[dt.date, dt.date]:
	"""Return fiscal period start/end containing as_of_date."""

	start = _clamped_date(as_of_date.year, fiscal_year_start_month, fiscal_year_start_day)
	if as_of_date < start:
		start = _clamped_date(as_of_date.year - 1, fiscal_year_start_month, fiscal_year_start_day)
	end = add_years(start, 1) - dt.timedelta(days=1)
	return start, end


def add_years(value: dt.date, years: int) -> dt.date:
	"""Add whole years, clamping leap-day to the last valid day of the month."""

	target_year = value.year + years
	return _clamped_date(target_year, value.month, value.day)


def add_months(value: dt.date, months: int) -> dt.date:
	"""Add whole months, clamping end-of-month hires to valid anniversaries."""

	total_month = value.month - 1 + months
	target_year = value.year + total_month // 12
	target_month = total_month % 12 + 1
	return _clamped_date(target_year, target_month, value.day)


def _clamped_date(year: int, month: int, day: int) -> dt.date:
	last_day = monthrange(year, month)[1]
	return dt.date(year, month, min(day, last_day))


def _validate_inputs(
	hire_date: dt.date,
	as_of_date: dt.date,
	basis: str,
	fiscal_year_start_month: int,
	fiscal_year_start_day: int,
	employment_end_date: dt.date | None,
) -> None:
	if not isinstance(hire_date, dt.date) or not isinstance(as_of_date, dt.date):
		raise TypeError("hire_date and as_of_date must be datetime.date values")
	if employment_end_date is not None and not isinstance(employment_end_date, dt.date):
		raise TypeError("employment_end_date must be a datetime.date value")
	if as_of_date < hire_date:
		raise ValueError("as_of_date cannot be before hire_date")
	if employment_end_date is not None and employment_end_date < hire_date:
		raise ValueError("employment_end_date cannot be before hire_date")
	if basis not in SUPPORTED_BASES:
		raise ValueError(f"basis must be one of {sorted(SUPPORTED_BASES)}")
	if not 1 <= fiscal_year_start_month <= 12:
		raise ValueError("fiscal_year_start_month must be between 1 and 12")
	last_day = monthrange(2024, fiscal_year_start_month)[1]
	if not 1 <= fiscal_year_start_day <= last_day:
		raise ValueError("fiscal_year_start_day is not valid for fiscal_year_start_month")


__all__ = [
	"calculate_annual_leave_entitlement",
	"first_year_monthly_accrual",
	"anniversary_annual_entitlement",
	"fiscal_year_annual_entitlement",
	"completed_years",
	"completed_months",
	"fiscal_period_for",
]
