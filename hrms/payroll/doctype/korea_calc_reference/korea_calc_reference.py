# Copyright (c) 2026, contributors
# For license information, please see license.txt

from frappe.model.document import Document


class KoreaCalcReference(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		applied_pay_year_month: DF.Data | None
		employee_id: DF.Data
		engine_version: DF.Data | None
		import_type: DF.Select
		linked_salary_slip: DF.Link | None
		ruleset_version: DF.Data | None
		run_id: DF.Data
		pay_year_month: DF.Data | None
		retirement_date: DF.Date | None
		settlement_kind: DF.Select | None
		settlement_year: DF.Int | None
		source_payload: DF.Code | None
	# end: auto-generated types

	pass
