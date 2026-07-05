"""Frappe 연동 API — 4대보험 신고서 3종 사이트 데이터로 생성.

이 모듈은 Frappe RPC 레이어에 노출되는 함수를 정의한다.
내부 로직(대상자 추출·xlsx 생성)은 insurance_filing.py / insurance_forms.py 코어에 위임한다.

테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import한다 (kakao_notification_api.py 컨벤션).

안전 불변식 (스킬 사고이력 2026-05-15):
  - human_approved != True 이면 어떤 frappe 조회·파일 생성도 하지 않고 즉시 blocked 반환 (fail-closed).
  - 주민번호(rrn)는 Employee 커스텀 필드가 있을 때만 채우고, 없으면 빈칸 + rrn_missing 명단에 기록.
"""

from __future__ import annotations

import calendar
import importlib.util as _ilu
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


# ---------------------------------------------------------------------------
# 코어 모듈 동적 로드 (importlib으로 frappe 패키지 경로 우회)
# ---------------------------------------------------------------------------
_MODULE_DIR = _pl.Path(__file__).resolve().parent


def _load_core(name: str):
	path = _MODULE_DIR / f"{name}.py"
	spec = _ilu.spec_from_file_location(f"_korea_{name}_core", path)
	module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
	spec.loader.exec_module(module)  # type: ignore[union-attr]
	return module


_filing = _load_core("insurance_filing")
_forms = _load_core("insurance_forms")

FILING_TYPES = ("acquisition", "loss", "daily")

# Employee 커스텀 필드(주민번호) 기본 필드명 — 사이트에 없으면 빈칸 처리
DEFAULT_RRN_FIELD = "custom_resident_registration_number"


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


@_whitelist
def generate_insurance_filing(
	filing_type: str,
	year: int | str,
	month: int | str,
	template_path: str,
	human_approved: bool | str = False,
	out_dir: str | None = None,
	company: str | None = None,
	rrn_field: str = DEFAULT_RRN_FIELD,
	workplace_info: dict | None = None,
) -> dict[str, Any]:
	"""사이트 데이터로 4대보험 신고서(취득/상실/일용직) xlsx 생성.

	Args:
		filing_type: "acquisition" | "loss" | "daily".
		year, month: 귀속월 (문자열도 수용).
		template_path: 신고서 템플릿 xlsx 경로(repo 밖 원본).
		human_approved: True 일 때만 파일 생성. 기본 False (fail-closed).
		out_dir: 산출물 디렉터리. 없으면 frappe 사이트 private/files 사용.
		company: Employee/Attendance 조회 필터(선택).
		rrn_field: Employee 주민번호 커스텀 필드명(없으면 빈칸 + rrn_missing).
		workplace_info: 생성기에 전달할 사업장 정보(선택).

	Returns:
		human_approved 아니면 {'status':'blocked', ...} (파일 미생성).
		생성되면 {'status':'created', 'file_path':..., 'rrn_missing':[...], ...}.
	"""
	# --- 인자 검증 (순수 — frappe/파일 I/O 없음) ---
	if filing_type not in FILING_TYPES:
		raise ValueError(f"filing_type must be one of {FILING_TYPES}: {filing_type!r}")
	year = int(year)
	month = int(month)
	if not (1 <= month <= 12):
		raise ValueError(f"invalid month: {month}")
	period = f"{year:04d}-{month:02d}"

	# --- fail-closed 게이트: 승인 전에는 어떤 조회·파일 생성도 하지 않는다 ---
	if not _coerce_bool(human_approved):
		return {
			"status": "blocked",
			"filing_type": filing_type,
			"period": period,
			"reason": "human_approved=True 없이는 신고서를 생성하지 않습니다 (fail-closed).",
			"requires_human_confirmation": True,
		}

	# --- 대상자 추출 (Employee 브로드 조회 후 코어가 귀속월 필터) ---
	employees = _get_employees(company, rrn_field)
	rrn_by_id = {emp.get("name"): emp.get(rrn_field) for emp in employees}

	out_path = _resolve_out_path(out_dir, period, filing_type)

	if filing_type == "acquisition":
		candidates = _filing.detect_acquisitions(employees, year, month)
		rrn_missing = _attach_rrn(candidates, rrn_by_id)
		_forms.generate_acquisition_report(template_path, candidates, out_path, workplace_info)
		count = len(candidates)
	elif filing_type == "loss":
		candidates = _filing.detect_losses(employees, year, month)
		rrn_missing = _attach_rrn(candidates, rrn_by_id)
		_forms.generate_loss_report(template_path, candidates, out_path, workplace_info)
		count = len(candidates)
	else:  # daily
		attendance = _get_attendance(company, year, month)
		workers = _filing.extract_daily_workers(employees, attendance, year, month)
		rrn_missing = _attach_rrn(workers, rrn_by_id)
		_forms.generate_daily_work_report(
			template_path, workers, year, month, out_path, workplace_info
		)
		count = len(workers)

	return {
		"status": "created",
		"filing_type": filing_type,
		"period": period,
		"file_path": out_path,
		"candidate_count": count,
		"rrn_missing": rrn_missing,
	}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _get_employees(company: str | None, rrn_field: str) -> list[dict]:
	"""사이트 Employee 조회 (귀속월 필터는 코어가 담당)."""
	fields = ["name", "employee_name", "date_of_joining", "relieving_date", "employment_type"]
	# 커스텀 주민번호 필드는 사이트에 실존할 때만 조회한다 (없으면 빈칸 + rrn_missing 처리).
	if rrn_field and rrn_field not in fields:
		try:
			has_field = bool(_frappe.get_meta("Employee").get_field(rrn_field))  # type: ignore[union-attr]
		except Exception:
			has_field = False
		if has_field:
			fields.append(rrn_field)
	filters: dict[str, Any] = {}
	if company:
		filters["company"] = company
	rows = _frappe.get_all("Employee", filters=filters, fields=fields)  # type: ignore[union-attr]
	return [dict(r) for r in rows]


def _get_attendance(company: str | None, year: int, month: int) -> list[dict]:
	"""귀속월 Attendance 조회(일용직 근무일 집계용)."""
	last_day = calendar.monthrange(year, month)[1]
	start = f"{year:04d}-{month:02d}-01"
	end = f"{year:04d}-{month:02d}-{last_day:02d}"
	filters: dict[str, Any] = {"attendance_date": ["between", [start, end]]}
	if company:
		filters["company"] = company
	rows = _frappe.get_all(  # type: ignore[union-attr]
		"Attendance",
		filters=filters,
		fields=["employee", "attendance_date", "status"],
	)
	return [dict(r) for r in rows]


def _attach_rrn(candidates: list[dict], rrn_by_id: dict) -> list[str]:
	"""후보에 rrn을 병합하고, 주민번호 없는 대상자 명단(rrn_missing)을 반환."""
	missing: list[str] = []
	for cand in candidates:
		rrn = rrn_by_id.get(cand.get("employee"))
		if rrn:
			cand["rrn"] = str(rrn)
		else:
			missing.append(cand.get("employee_name") or cand.get("employee") or "")
	return missing


def _resolve_out_path(out_dir: str | None, period: str, filing_type: str) -> str:
	"""산출물 파일 경로 확정. out_dir 없으면 frappe 사이트 private/files 사용."""
	if out_dir is None:
		if _FRAPPE_AVAILABLE and _frappe is not None:
			out_dir = _frappe.get_site_path("private", "files")
		else:
			raise ValueError("out_dir is required when frappe is unavailable")
	directory = _pl.Path(out_dir)
	directory.mkdir(parents=True, exist_ok=True)
	# gitignore 패턴(*_신고서_*.xlsx)과 일치하도록 네이밍
	return str(directory / f"{period}_{filing_type}_신고서_생성.xlsx")


def _coerce_bool(value: Any) -> bool:
	"""Frappe form dict에서 넘어오는 문자열 bool 처리."""
	if isinstance(value, bool):
		return value
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "y"}
	return bool(value)
