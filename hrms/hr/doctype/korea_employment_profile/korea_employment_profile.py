# Copyright (c) 2026, Frappe HRMS contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document


_MASKED_RRN_PATTERN = re.compile(r"^\d{6}-[1-8]\*{6}$")


class KoreaEmploymentProfile(Document):
    def validate(self):
        self.validate_masked_rrn()
        self.validate_link_consistency()

    def validate_masked_rrn(self):
        rrn_masked = (getattr(self, "rrn_masked", None) or "").strip()
        if rrn_masked:
            if not _MASKED_RRN_PATTERN.fullmatch(rrn_masked):
                frappe.throw(frappe._("Korea masked RRN must use the 000000-1****** format."))
            self.rrn_masked = rrn_masked

    def validate_link_consistency(self):
        company = getattr(self, "company", None)
        if not company:
            return

        employee = getattr(self, "employee", None)
        if employee:
            employee_company = frappe.db.get_value("Employee", employee, "company")
            if employee_company and employee_company != company:
                frappe.throw(frappe._("Employee company must match Korea Employment Profile company."))

        workplace_profile = getattr(self, "workplace_profile", None)
        if workplace_profile:
            workplace_company = frappe.db.get_value(
                "Korea Workplace Profile", workplace_profile, "company"
            )
            if workplace_company and workplace_company != company:
                frappe.throw(
                    frappe._("Workplace Profile company must match Korea Employment Profile company.")
                )
