# Copyright (c) 2026, Frappe HRMS contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document


_BUSINESS_REGISTRATION_PATTERN = re.compile(r"^\d{3}-\d{2}-\d{5}$")
_WORKPLACE_MANAGEMENT_PATTERN = re.compile(r"^\d{11}$")


class KoreaWorkplaceProfile(Document):
    def validate(self):
        self.validate_registration_numbers()

    def validate_registration_numbers(self):
        business_registration_number = (getattr(self, "business_registration_number", None) or "").strip()
        if business_registration_number:
            if not _BUSINESS_REGISTRATION_PATTERN.fullmatch(business_registration_number):
                frappe.throw(
                    frappe._("Korea business registration number must use the 000-00-00000 format.")
                )
            self.business_registration_number = business_registration_number

        workplace_management_number = (getattr(self, "workplace_management_number", None) or "").strip()
        if workplace_management_number:
            if not _WORKPLACE_MANAGEMENT_PATTERN.fullmatch(workplace_management_number):
                frappe.throw(frappe._("Korea workplace management number must contain 11 digits."))
            self.workplace_management_number = workplace_management_number
