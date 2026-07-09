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

# Employee 커스텀 필드(주민번호) 기본 필드명 — 사이트에 없으면 빈칸 처리.
# 표준: resident_registration_number (setup.py, Password=암호화 저장 → 복호화 경로로 읽음).
# 레거시: custom_resident_registration_number (구 사이트 호환 폴백).
DEFAULT_RRN_FIELD = "resident_registration_number"
LEGACY_RRN_FIELDS = ("custom_resident_registration_number",)


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
	management_number: str | None = None,
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
		management_number: 사업장 관리번호 필터(선택) — 한 법인에 관리번호가 여러 개
			(본점/지점·상용/일용 분리성립)일 때 해당 관리번호 소속 직원만으로 신고서를 생성.
			직원 소속은 Employee.workplace_management_number(비면 미소속으로 간주, 필터 시 제외).
			신고서는 관리번호 단위로 나가야 하므로 관리번호별로 이 함수를 각각 호출한다.

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

	# --- 권한: 사이트 실행 시 HR 관리자급만 (bench execute는 Administrator) ---
	if _FRAPPE_AVAILABLE and _frappe is not None and hasattr(_frappe, "only_for"):
		_frappe.only_for(("System Manager", "HR Manager", "HR User"))

	# --- 대상자 추출 (Employee 브로드 조회 후 코어가 귀속월 필터) ---
	employees = _get_employees(company, rrn_field)
	if management_number:
		employees = _filter_by_management_number(employees, management_number)
		workplace_info = dict(workplace_info or {})
		workplace_info.setdefault("management_number", str(management_number))
	_attach_wages(employees)
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
		candidates = workers
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
		# 보수 0원 대상자는 담당자 확인 필수 (임금 소스: Salary Structure Assignment.base)
		"wage_missing": [
			c.get("employee_name", "")
			for c in candidates
			if not (c.get("monthly_wage") or c.get("total_wage"))
		],
	}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _resolve_rrn_field(rrn_field: str) -> tuple[str | None, bool]:
	"""사이트에 실존하는 주민번호 필드를 해석한다.

	요청 필드가 없으면 레거시 필드명(LEGACY_RRN_FIELDS)으로 폴백.
	Returns: (실존 필드명 또는 None, Password(암호화) 타입 여부).
	"""
	for candidate in (rrn_field, *LEGACY_RRN_FIELDS):
		if not candidate:
			continue
		try:
			meta_field = _frappe.get_meta("Employee").get_field(candidate)  # type: ignore[union-attr]
		except Exception:
			meta_field = None
		if meta_field:
			is_password = getattr(meta_field, "fieldtype", None) == "Password"
			return candidate, is_password
	return None, False


def _decrypt_rrn(employee_name: str, fieldname: str) -> str | None:
	"""Password(암호화) 필드에서 주민번호 복호화. 실패 시 None(빈칸 + rrn_missing 처리)."""
	try:
		from frappe.utils.password import get_decrypted_password  # noqa: PLC0415

		return get_decrypted_password("Employee", employee_name, fieldname, raise_exception=False)
	except Exception:
		return None


MGMT_NO_FIELD = "workplace_management_number"


def _filter_by_management_number(employees: list[dict], management_number: str) -> list[dict]:
	"""관리번호 소속 직원만 남긴다 (Employee.workplace_management_number 정확 일치).

	공백/미입력 직원은 필터 시 제외된다 — 잘못된 관리번호로 신고서에 섞여 나가는 것보다
	명단에서 빠져 보이는 쪽이 안전하다(누락은 검수에서 드러나고, 오소속 신고는 정정신고 비용).
	"""
	target = str(management_number).strip()
	return [
		emp for emp in employees
		if str(emp.get(MGMT_NO_FIELD) or "").strip() == target
	]


def _get_employees(company: str | None, rrn_field: str) -> list[dict]:
	"""사이트 Employee 조회 (귀속월 필터는 코어가 담당)."""
	fields = [
		"name", "employee_name", "date_of_joining", "relieving_date",
		"employment_type", "reason_for_leaving",
	]
	# 관리번호 필드는 사이트에 실존할 때만 조회 (구 사이트 호환)
	try:
		if _frappe.get_meta("Employee").get_field(MGMT_NO_FIELD):  # type: ignore[union-attr]
			fields.append(MGMT_NO_FIELD)
	except Exception:
		pass
	# 커스텀 주민번호 필드는 사이트에 실존할 때만 조회한다 (없으면 빈칸 + rrn_missing 처리).
	resolved_field, rrn_encrypted = _resolve_rrn_field(rrn_field)
	if resolved_field and not rrn_encrypted and resolved_field not in fields:
		fields.append(resolved_field)  # 평문(Data) 필드만 get_all로 직접 조회
	filters: dict[str, Any] = {}
	if company:
		filters["company"] = company
	rows = _frappe.get_all("Employee", filters=filters, fields=fields)  # type: ignore[union-attr]
	employees = [dict(r) for r in rows]
	for emp in employees:
		# detect_losses의 상실사유 키로 매핑 (없으면 코어가 기본값+코드로 처리, 명단 확인 게이트에서 검증)
		if emp.get("reason_for_leaving"):
			emp["loss_reason"] = str(emp["reason_for_leaving"])
		# 암호화(Password) 필드는 직원별 복호화로 읽는다 (get_all은 암호문/공백만 반환).
		if resolved_field and rrn_encrypted:
			emp[rrn_field] = _decrypt_rrn(emp.get("name"), resolved_field)
		elif resolved_field and resolved_field != rrn_field:
			emp[rrn_field] = emp.get(resolved_field)  # 레거시 필드값을 요청 키로 노출
	return employees


def _attach_wages(employees: list[dict]) -> None:
	"""보수월액 소스: 제출된 Salary Structure Assignment 중 최신 base.

	이 값이 없으면 monthly_wage=0으로 남고 결과의 wage_missing에 표시된다 —
	0원 보수 신고서가 조용히 나가는 것을 막기 위해 호출부가 명단을 노출한다.
	일용직 daily_wage도 base를 일급으로 사용한다(일용직 SSA는 일급 기준 운영 전제).
	"""
	try:
		rows = _frappe.get_all(  # type: ignore[union-attr]
			"Salary Structure Assignment",
			filters={"docstatus": 1},
			fields=["employee", "base", "from_date"],
			order_by="from_date desc",
		)
	except Exception:
		rows = []
	base_by_employee: dict = {}
	for row in rows:
		emp_id = row.get("employee")
		if emp_id and emp_id not in base_by_employee:
			base_by_employee[emp_id] = int(round(float(row.get("base") or 0)))
	for emp in employees:
		base = base_by_employee.get(emp.get("name"), 0)
		emp.setdefault("monthly_wage", base)
		emp.setdefault("daily_wage", base if _is_daily(emp) else 0)


def _is_daily(emp: dict) -> bool:
	return str(emp.get("employment_type") or "") in ("일용직", "일용근로자")


def _get_attendance(company: str | None, year: int, month: int) -> list[dict]:
	"""귀속월 Attendance 조회(일용직 근무일 집계용)."""
	last_day = calendar.monthrange(year, month)[1]
	start = f"{year:04d}-{month:02d}-01"
	end = f"{year:04d}-{month:02d}-{last_day:02d}"
	filters: dict[str, Any] = {
		"attendance_date": ["between", [start, end]],
		"docstatus": 1,  # 취소(2)·임시저장(0) 근태는 근로일로 집계하지 않는다
	}
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
