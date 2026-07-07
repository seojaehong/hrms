# Copyright (c) 2026, Frappe HRMS contributors
# For license information, please see license.txt

"""Korea Payroll Time Input — 월별 직원 근무시간 제출 레코드.

고객사가 초과·야간·휴일·파트 시간을 채팅으로 전달하다 누락/오적용되는 사고를
막기 위해 시스템에 직접 입력하는 단순 draft/submitted 레코드다.
is_submittable=0: 상태는 status 필드로만 관리한다(마감 draft 패턴과 동일 철학).
"""

from __future__ import annotations

import re

import frappe
from frappe.model.document import Document

PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
HOUR_FIELDS = ("overtime_hours", "night_hours", "holiday_hours", "part_time_hours")
MAX_HOURS = 400.0
ALLOWED_STATUSES = {"draft", "submitted"}


class KoreaPayrollTimeInput(Document):
	def validate(self):
		self._normalize_required_text()
		self._validate_period_format()
		self._validate_hours_range()
		self._validate_status()
		self._validate_no_duplicate()

	def _normalize_required_text(self):
		for fieldname, label in (("company", "Company"), ("period", "Period"), ("employee", "Employee")):
			value = (getattr(self, fieldname, None) or "").strip()
			if not value:
				frappe.throw(frappe._(f"{label} is required."))
			setattr(self, fieldname, value)

	def _validate_period_format(self):
		if not PERIOD_PATTERN.fullmatch(self.period):
			frappe.throw(frappe._("period must be in YYYY-MM format."))

	def _validate_hours_range(self):
		for fieldname in HOUR_FIELDS:
			value = getattr(self, fieldname, None) or 0
			try:
				number = float(value)
			except (TypeError, ValueError):
				frappe.throw(frappe._(f"{fieldname} must be a number."))
			if number != number or not (0 <= number <= MAX_HOURS):
				frappe.throw(frappe._(f"{fieldname} must be between 0 and {MAX_HOURS:g}."))
			setattr(self, fieldname, number)

	def _validate_status(self):
		if getattr(self, "status", None) not in ALLOWED_STATUSES:
			frappe.throw(frappe._("status must be draft or submitted."))

	def _validate_no_duplicate(self):
		filters = {
			"company": self.company,
			"period": self.period,
			"employee": self.employee,
		}
		name = getattr(self, "name", None)
		if name:
			filters["name"] = ["!=", name]
		existing = frappe.db.exists("Korea Payroll Time Input", filters)
		if existing:
			frappe.throw(
				frappe._("Korea Payroll Time Input already exists for this company/period/employee.")
			)
