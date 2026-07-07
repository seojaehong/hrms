# Copyright (c) 2026, Frappe HRMS contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# framework-free 검증 함수 재사용 (테스트: hrms/tests/test_korea_service_request.py)
from hrms.regional.south_korea.service_request_api import (
	validate_category,
	validate_status_transition,
)


class KoreaServiceRequest(Document):
	def validate(self):
		self.validate_title()
		self.validate_category_value()
		if not self.status:
			self.status = "접수"
		self.validate_status_change()

	def validate_title(self):
		if not str(self.title or "").strip():
			frappe.throw(frappe._("제목(title)을 입력해 주세요."))

	def validate_category_value(self):
		try:
			self.category = validate_category(self.category)
		except ValueError as exc:
			frappe.throw(frappe._(str(exc)))

	def validate_status_change(self):
		"""상태 변경 시 전이 규칙 검증 — 완료는 종결 상태."""
		previous = self.get_doc_before_save()
		if previous is None:
			return
		old_status = str(previous.status or "접수")
		if old_status == self.status:
			return
		try:
			validate_status_transition(old_status, self.status)
		except ValueError as exc:
			frappe.throw(frappe._(str(exc)))
