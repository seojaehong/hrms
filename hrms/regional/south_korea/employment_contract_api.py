"""Frappe API 레이어 — 한국 고용계약서 4종 preview + PDF 생성.

mutation 게이트: generate_korea_employment_contract_pdf 는 human_approved=True 이후에만 실행.
외부 LLM API 사용 없음.
"""

from __future__ import annotations

import copy
import importlib.util as _ilu
import json
import pathlib as _pl
from typing import Any

# ---------------------------------------------------------------------------
# Frappe 조건부 import — framework-free 테스트 환경에서 안전하게 로드
# ---------------------------------------------------------------------------
try:
	import frappe as _frappe  # noqa: PLC0415

	_FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
	_frappe = None  # type: ignore[assignment]
	_FRAPPE_AVAILABLE = False


def _whitelist(fn):
	"""@frappe.whitelist() 데코레이터 — Frappe 없으면 no-op."""
	if _FRAPPE_AVAILABLE and _frappe is not None:
		return _frappe.whitelist()(fn)
	return fn


def _throw(msg: str) -> None:
	"""Frappe.throw 또는 ValueError."""
	if _FRAPPE_AVAILABLE and _frappe is not None:
		_frappe.throw(msg)
	raise ValueError(msg)


# ---------------------------------------------------------------------------
# employment_contract 모듈 동적 로드 (frappe 패키지 경로 우회)
# ---------------------------------------------------------------------------
_MODULE_DIR = _pl.Path(__file__).resolve().parent
_CONTRACT_CORE = _MODULE_DIR / "employment_contract.py"

_spec = _ilu.spec_from_file_location("_employment_contract_core", _CONTRACT_CORE)
_core = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_core)  # type: ignore[union-attr]

CONTRACT_TYPES = _core.CONTRACT_TYPES
build_korea_employment_contract = _core.build_korea_employment_contract
build_contract_snapshot = _core.build_contract_snapshot
contract_signature_hash = _core.contract_signature_hash

_PRINT_FORMAT_MAP = {
	"regular": "Korea Employment Contract Regular",
	"fixed_term": "Korea Employment Contract Fixed Term",
	"daily": "Korea Employment Contract Daily",
	"part_time": "Korea Employment Contract Part Time",
}


@_whitelist
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
		_throw(
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
		_throw(str(exc))

	return {
		**result,
		"runtime_action": "preview_only",
		"print_format_name": _PRINT_FORMAT_MAP.get(contract_type, ""),
	}


@_whitelist
def preview_korea_employment_contract_snapshot(
	*,
	employment_profile: dict[str, Any] | str,
) -> dict[str, Any]:
	"""고용계약 스냅샷 미리보기 — framework-free, 실제 mutation 없음.

	employment_profile 은 dict 또는 JSON 문자열로 전달 가능.
	문자열 필드(start_date, monthly_wage 등)는 자동 변환합니다.
	"""
	import datetime as _dt
	import re as _re

	# Coerce employment_profile from JSON string
	if isinstance(employment_profile, str):
		try:
			employment_profile = json.loads(employment_profile)
		except (json.JSONDecodeError, TypeError) as exc:
			raise ValueError("JSON payload is invalid") from exc
	if not isinstance(employment_profile, dict):
		raise ValueError("employment_profile must be a dict or JSON object")

	profile = copy.deepcopy(employment_profile)

	# --- Coerce and validate date fields ---
	for date_field in ("start_date", "end_date"):
		raw = profile.get(date_field)
		if raw is None:
			continue
		# Reject datetime objects
		if isinstance(raw, _dt.datetime):
			raise ValueError(f"{date_field} must be an ISO date string (YYYY-MM-DD)")
		if isinstance(raw, _dt.date):
			# Accept date objects as-is
			continue
		if not isinstance(raw, str):
			raise ValueError(f"{date_field} must be an ISO date string (YYYY-MM-DD)")
		# Validate ISO date format strictly: YYYY-MM-DD only
		if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
			raise ValueError(f"{date_field} must be an ISO date string (YYYY-MM-DD)")
		try:
			profile[date_field] = _dt.date.fromisoformat(raw)
		except ValueError as exc:
			raise ValueError(f"{date_field} must be an ISO date string (YYYY-MM-DD)") from exc

	# --- Strict integer coercion for numeric fields ---
	def _coerce_strict_int(val: Any, fieldname: str) -> int:
		"""Coerce to strict int. Reject bool, float, int subclasses, non-numeric strings."""
		if isinstance(val, bool):
			raise ValueError(f"{fieldname} must be an integer")
		if isinstance(val, str):
			try:
				parsed = int(val)
				if str(parsed) != val.strip():
					raise ValueError(f"{fieldname} must be an integer")
				return parsed
			except ValueError:
				raise ValueError(f"{fieldname} must be an integer")
		if type(val) is not int:  # noqa: E721
			raise ValueError(f"{fieldname} must be an integer")
		return val

	for int_field in ("monthly_wage", "pay_day", "probation_months"):
		raw = profile.get(int_field)
		if raw is None:
			continue
		profile[int_field] = _coerce_strict_int(raw, int_field)

	# --- Coerce working_hours_per_week: reject bool, accept int/float/string ---
	raw_hours = profile.get("working_hours_per_week")
	if raw_hours is not None:
		if isinstance(raw_hours, bool):
			raise ValueError("working_hours_per_week must be numeric")
		if isinstance(raw_hours, str):
			try:
				profile["working_hours_per_week"] = float(raw_hours)
			except ValueError:
				raise ValueError("working_hours_per_week must be numeric")

	# --- Strip employee string ---
	if isinstance(profile.get("employee"), str):
		profile["employee"] = profile["employee"].strip()

	# --- Call core build_contract_snapshot ---
	snapshot = build_contract_snapshot(**{k: v for k, v in profile.items()
	                                       if k in (
	                                           "employee", "company", "workplace", "start_date",
	                                           "job_title", "employment_type", "working_hours_per_week",
	                                           "monthly_wage", "pay_day", "end_date", "probation_months",
	                                           "job_description",
	                                       )})

	return {
		"contract_type": "korea_employment_contract_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"contract_snapshot": copy.deepcopy(snapshot),
	}


@_whitelist
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
		_throw("human_approved must be True to generate a PDF. Preview only until approved.")

	contract = _coerce_dict(contract, "contract")

	contract_type = contract.get("form_type") or ""
	if contract_type not in CONTRACT_TYPES:
		_throw(
			f"contract.form_type must be one of: {', '.join(sorted(CONTRACT_TYPES))}. Got: {contract_type!r}"
		)

	html_content = contract.get("html_content")
	if not html_content:
		_throw("contract.html_content is missing. Run preview_korea_employment_contract first.")

	# PDF 생성 (Frappe 내장 PDF 엔진 사용)
	try:
		from frappe.utils.pdf import get_pdf  # noqa: PLC0415

		pdf_bytes = get_pdf(html_content)
	except Exception as exc:
		if _FRAPPE_AVAILABLE and _frappe is not None:
			_frappe.log_error(f"Korea employment contract PDF generation failed: {exc}")
		_throw(f"PDF generation failed: {exc}")

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
	_throw(f"{field} must be a dict or JSON string")
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
