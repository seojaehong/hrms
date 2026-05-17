"""Frappe API 레이어 — 한국 고용계약서 4종 preview + PDF 생성.

mutation 게이트: generate_korea_employment_contract_pdf 는 human_approved=True 이후에만 실행.
외부 LLM API 사용 없음.
"""

from __future__ import annotations

from typing import Any

import frappe

from hrms.regional.south_korea.employment_contract import (
	CONTRACT_TYPES,
	build_korea_employment_contract,
)

_PRINT_FORMAT_MAP = {
	"regular": "Korea Employment Contract Regular",
	"fixed_term": "Korea Employment Contract Fixed Term",
	"daily": "Korea Employment Contract Daily",
	"part_time": "Korea Employment Contract Part Time",
}


@frappe.whitelist()
def preview_korea_employment_contract(
	contract_type: str,
	company: dict[str, Any] | None = None,
	employee: dict[str, Any] | None = None,
	contract_terms: dict[str, Any] | None = None,
) -> dict[str, Any]:
	"""4종 고용계약서 preview — side-effect 없음.

	Parameters
	----------
	contract_type:
		"regular" | "fixed_term" | "daily" | "part_time"
	company:
		사업주 정보 dict
	employee:
		근로자 정보 dict
	contract_terms:
		계약 조건 dict

	Returns
	-------
	dict:
		build_korea_employment_contract 결과 + Frappe 메타 정보.
	"""
	company = _coerce_dict(company, "company")
	employee = _coerce_dict(employee, "employee")
	contract_terms = _coerce_dict(contract_terms, "contract_terms")

	if contract_type not in CONTRACT_TYPES:
		frappe.throw(
			f"contract_type must be one of: {', '.join(sorted(CONTRACT_TYPES))}. Got: {contract_type!r}"
		)

	try:
		result = build_korea_employment_contract(
			contract_type=contract_type,
			company=company,
			employee=employee,
			contract_terms=contract_terms,
		)
	except (TypeError, ValueError) as exc:
		frappe.throw(str(exc))

	return {
		**result,
		"runtime_action": "preview_only",
		"print_format_name": _PRINT_FORMAT_MAP.get(contract_type, ""),
	}


@frappe.whitelist()
def generate_korea_employment_contract_pdf(
	contract: dict[str, Any] | None = None,
	human_approved: bool = False,
) -> dict[str, Any]:
	"""PDF 생성 — human_approved=True 게이트 이후에만 실행.

	Parameters
	----------
	contract:
		preview_korea_employment_contract 의 반환 dict (또는 동일 구조)
	human_approved:
		True 여야만 PDF 생성 진행. False 이면 에러.

	Returns
	-------
	dict:
		{
			"status": "generated",
			"pdf_base64": str,          # base64 encoded PDF bytes
			"form_type": str,
			"form_title": str,
			"filename": str,
		}
	"""
	if not _coerce_bool(human_approved):
		frappe.throw("human_approved must be True to generate a PDF. Preview only until approved.")

	contract = _coerce_dict(contract, "contract")

	contract_type = contract.get("form_type") or ""
	if contract_type not in CONTRACT_TYPES:
		frappe.throw(
			f"contract.form_type must be one of: {', '.join(sorted(CONTRACT_TYPES))}. Got: {contract_type!r}"
		)

	html_content = contract.get("html_content")
	if not html_content:
		frappe.throw("contract.html_content is missing. Run preview_korea_employment_contract first.")

	# PDF 생성 (Frappe 내장 PDF 엔진 사용)
	try:
		from frappe.utils.pdf import get_pdf

		pdf_bytes = get_pdf(html_content)
	except Exception as exc:
		frappe.log_error(f"Korea employment contract PDF generation failed: {exc}")
		frappe.throw(f"PDF generation failed: {exc}")

	import base64

	pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

	employee_name = (contract.get("employee") or {}).get("employee_name", "근로자")
	form_title = contract.get("form_title", "근로계약서")
	filename = f"employment_contract_{contract_type}_{_safe_filename(employee_name)}.pdf"

	return {
		"status": "generated",
		"pdf_base64": pdf_base64,
		"form_type": contract_type,
		"form_title": form_title,
		"filename": filename,
		"mutation_boundary": "pdf_generated_no_db_write",
		"requires_human_approval": False,  # 이미 승인 완료
	}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _coerce_dict(value: Any, field: str) -> dict[str, Any]:
	"""dict 강제 변환. JSON 문자열 허용."""
	if value is None:
		return {}
	if isinstance(value, dict):
		return value
	if isinstance(value, str):
		import json

		try:
			parsed = json.loads(value)
			if isinstance(parsed, dict):
				return parsed
		except (json.JSONDecodeError, ValueError):
			pass
	frappe.throw(f"{field} must be a dict or JSON string")
	return {}  # unreachable, satisfies type checker


def _coerce_bool(value: Any) -> bool:
	if isinstance(value, bool):
		return value
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "y"}
	return bool(value)


def _safe_filename(name: str) -> str:
	"""파일명에 사용 가능한 문자만 남김."""
	import re

	safe = re.sub(r"[^\w\-가-힣]", "_", name)
	return safe[:40] if safe else "unknown"
