# Copyright (c) 2026, Frappe HRMS contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# framework-free 검증/마스킹 함수 재사용 (테스트: hrms/tests/test_korea_onboarding_request.py)
from hrms.regional.south_korea.onboarding_request_api import mask_rrn, validate_rrn


class KoreaEmployeeOnboardingRequest(Document):
	def validate(self):
		self.validate_and_mask_rrn()
		if not self.status:
			self.status = "requested"

	def validate_and_mask_rrn(self):
		"""rrn 형식 검증(13자리·성별코드 1-8·생년월일 정합) 후 정규화 저장 + 마스킹 필드 갱신.

		PII 불변식: 오류 메시지에 입력 rrn을 절대 포함하지 않는다 (validate_rrn 보장).
		"""
		raw = str(self.rrn or "")
		candidate = raw.replace("-", "").replace(" ", "").strip()
		if not candidate or not candidate.isdigit():
			# 빈 값(reqd가 차단) 또는 이미 암호화된 기존 값(변경 없음) — 재검증 대상 아님
			return
		try:
			normalized = validate_rrn(candidate)
		except ValueError as exc:
			frappe.throw(frappe._(str(exc)))
			return
		self.rrn = normalized
		self.masked_rrn = mask_rrn(normalized)
