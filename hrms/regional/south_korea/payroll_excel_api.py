"""Frappe 연동 API — 급여 엑셀 업/다운로드 (F5).

내부 로직(파싱·무결성·워크북 빌드·diff·upsert)은 payroll_excel.py 코어에 위임한다.
테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import한다 (insurance_filing_api.py 컨벤션).

US-X1: 코어 승격 + 어댑터 뼈대. 실제 다운로드/검증/확정 엔드포인트는 US-X2~X4에서 추가.

안전 불변식:
  - 확정(apply) 경로는 human_approved != True 이면 어떤 저장도 하지 않고 blocked 반환 (fail-closed).
  - 개인 급여액은 로그에 남기지 않는다.
"""

from __future__ import annotations

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


_excel = _load_core("payroll_excel")

# 코어 함수 재노출 — US-X2~X4 어댑터가 이 심볼을 사용한다.
parse_payroll_workbook = _excel.parse_payroll_workbook
validate_payroll_rows = _excel.validate_payroll_rows
extract_payroll = _excel.extract_payroll
build_payroll_workbook = _excel.build_payroll_workbook
diff_payroll_rows = _excel.diff_payroll_rows
summarize_payroll_apply = _excel.summarize_payroll_apply

# 다운로드 조회 시 급여 관리자급만 (bench execute는 Administrator)
_PAYROLL_ROLES = ("System Manager", "HR Manager", "HR User")


# ---------------------------------------------------------------------------
# 공개 API — US-X2 급여 엑셀 다운로드
# ---------------------------------------------------------------------------


@_whitelist
def download_payroll_workbook(period: str, company: str | None = None) -> dict[str, Any]:
    """해당 월 Salary Slip 전건을 노호 급여대장 유사 xlsx(private File)로 생성해 file_url 반환.

    Args:
        period: 귀속월 'YYYY-MM'.
        company: 조회 회사(선택). 없으면 Global Defaults.default_company 폴백.

    Returns:
        {'status':'created', 'period', 'company', 'count', 'file_url', 'file_name'}.
    """
    start = _period_start(period)  # 순수 검증 — frappe 없이 형식 오류를 먼저 잡는다
    if not _FRAPPE_AVAILABLE or _frappe is None:
        raise RuntimeError("download_payroll_workbook는 frappe 런타임에서만 실행됩니다.")

    _frappe.only_for(_PAYROLL_ROLES)
    company = company or _frappe.db.get_single_value("Global Defaults", "default_company")
    if not company:
        raise ValueError("company를 특정할 수 없습니다 (Global Defaults.default_company 미설정).")

    slips = _collect_slips(company, start)
    workbook_bytes = build_payroll_workbook(slips, period)

    file_name = f"급여대장_{period}.xlsx"
    file_doc = _frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name,
            "content": workbook_bytes,
            "is_private": 1,
            "folder": "Home",
        }
    ).insert(ignore_permissions=True)

    return {
        "status": "created",
        "period": period,
        "company": company,
        "count": len(slips),
        "file_url": file_doc.file_url,
        "file_name": file_name,
    }


# ---------------------------------------------------------------------------
# 공개 API — US-X3 급여 엑셀 업로드 검증 (파싱→무결성→미리보기, 저장 없음)
# ---------------------------------------------------------------------------


@_whitelist
def validate_payroll_upload(file_url: str, period: str, sheet_type: str = "monthly") -> dict[str, Any]:
    """업로드된 급여대장 File 을 파싱·무결성 검사하고 기존 슬립과의 diff 를 반환 — 저장 없음.

    Args:
        file_url: 업로드된 File 의 file_url (frappe File doctype 경유).
        period: 귀속월 'YYYY-MM' — 기존 슬립 조회 대상.
        sheet_type: PROFILES 키 (기본 'monthly').

    Returns:
        성공: {'status':'ok', 'period', 'company', 'count', 'diff'}.
        파싱 실패: {'status':'parse_error', 'period', 'errors':[...]}.
        무결성 실패: {'status':'invalid', 'period', 'count', 'errors':[행번호 포함...]}.

    개인 급여액은 diff/응답에 담기지만 로그에는 남기지 않는다.
    """
    start = _period_start(period)  # 순수 형식 검증 — frappe 이전에 먼저 잡는다
    if not _FRAPPE_AVAILABLE or _frappe is None:
        raise RuntimeError("validate_payroll_upload는 frappe 런타임에서만 실행됩니다.")

    _frappe.only_for(_PAYROLL_ROLES)

    content = _read_file_bytes(file_url)
    try:
        rows = parse_payroll_workbook(content, sheet_type)
    except (ValueError, KeyError) as exc:
        return {"status": "parse_error", "period": period, "errors": [str(exc)]}

    errors = validate_payroll_rows(rows)
    if errors:
        return {"status": "invalid", "period": period, "count": len(rows), "errors": errors}

    company = _frappe.db.get_single_value("Global Defaults", "default_company")
    existing = _collect_slips(company, start) if company else []
    diff = diff_payroll_rows(existing, rows)
    return {
        "status": "ok",
        "period": period,
        "company": company,
        "count": len(rows),
        "diff": diff,
    }


# ---------------------------------------------------------------------------
# 공개 API — US-X4 급여 엑셀 업로드 확정 (human_approved 게이트 + 슬립 upsert)
# ---------------------------------------------------------------------------

# 확정(반영)은 HR Manager 전용 (bench execute 는 Administrator=System Manager)
_APPLY_ROLES = ("System Manager", "HR Manager")


@_whitelist
def apply_payroll_upload(
    file_url: str,
    period: str,
    human_approved: bool | str = False,
    sheet_type: str = "monthly",
) -> dict[str, Any]:
    """업로드된 급여대장 File 을 파싱·무결성 검사 후 Salary Slip 으로 upsert — human_approved 게이트.

    Args:
        file_url: 업로드된 File 의 file_url.
        period: 귀속월 'YYYY-MM'.
        human_approved: True 일 때만 반영. 기본 False (fail-closed) — 미승인 시 어떤 저장·조회도 없음.
        sheet_type: PROFILES 키 (기본 'monthly').

    Returns:
        미승인: {'status':'blocked', ...} (DB 무변경).
        승인+성공: {'status':'applied', 'period', 'company', 'created', 'updated', 'skipped',
                    'count', 'total_gross'}.
    무결성 실패 시 extract_payroll 가 ValueError. 개인 급여액은 로그에 남기지 않는다.

    한계(이번 이터레이션): 기존 슬립은 skipped 로 미변경한다 — 금액 갱신은 Salary Structure 개정이
    필요하므로 별도 story 로 분리. 신규 인원/신규 월 반영이 기본 사용 경로.
    """
    start = _period_start(period)  # 순수 형식 검증 — 게이트 이전에도 잘못된 period 는 막는다

    # --- fail-closed 게이트: 승인 전에는 frappe 조회·저장을 일절 하지 않는다 ---
    if not _coerce_bool(human_approved):
        return {
            "status": "blocked",
            "period": period,
            "reason": "human_approved=True 없이는 급여 슬립을 반영하지 않습니다 (fail-closed).",
            "requires_human_confirmation": True,
        }

    if not _FRAPPE_AVAILABLE or _frappe is None:
        raise RuntimeError("apply_payroll_upload는 frappe 런타임에서만 실행됩니다.")

    _frappe.only_for(_APPLY_ROLES)
    company = _frappe.db.get_single_value("Global Defaults", "default_company")
    if not company:
        raise ValueError("company를 특정할 수 없습니다 (Global Defaults.default_company 미설정).")

    content = _read_file_bytes(file_url)
    data = extract_payroll(content, period, sheet_type)  # 무결성 통과 강제 (실패 시 ValueError)
    employees = data["employees"]

    end = _period_end(period)
    results = _upsert_slips(company, start, end, employees, period)
    summary = summarize_payroll_apply(results)
    _record_apply_audit(company, period, summary)

    return {"status": "applied", "period": period, "company": company, **summary}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _read_file_bytes(file_url: str) -> bytes:
    """file_url 로 File 문서를 찾아 내용을 bytes 로 읽는다 (frappe File.get_content)."""
    file_doc = _frappe.get_doc("File", {"file_url": file_url})
    return file_doc.get_content()


def _period_start(period: str) -> str:
    """'YYYY-MM' → 'YYYY-MM-01'. 형식 오류는 ValueError."""
    parts = str(period).split("-")
    if len(parts) != 2:
        raise ValueError(f"period must be 'YYYY-MM': {period!r}")
    year, month = int(parts[0]), int(parts[1])
    if not (1 <= month <= 12):
        raise ValueError(f"invalid month: {month}")
    return f"{year:04d}-{month:02d}-01"


def _collect_slips(company: str, start: str) -> list[dict]:
    """해당 월(start_date=start) Salary Slip 전건을 빌더 입력 dict 목록으로 변환.

    earnings/deductions 자식 테이블은 슬립 문서에서 읽는다. 개인 금액은 로그 금지.
    """
    names = _frappe.get_all(
        "Salary Slip",
        filters={"company": company, "start_date": start, "docstatus": ("<", 2)},
        pluck="name",
    )
    slips: list[dict] = []
    for name in names:
        doc = _frappe.get_doc("Salary Slip", name)
        earnings: dict[str, int] = {}
        for row in getattr(doc, "earnings", None) or []:
            label = _row_get(row, "salary_component")
            if label:
                earnings[label] = earnings.get(label, 0) + _int(_row_get(row, "amount"))
        deductions: dict[str, int] = {}
        for row in getattr(doc, "deductions", None) or []:
            label = _row_get(row, "salary_component")
            if label:
                deductions[label] = deductions.get(label, 0) + _int(_row_get(row, "amount"))
        slips.append(
            {
                "name": _doc_get(doc, "employee_name") or _doc_get(doc, "employee"),
                "dept": _doc_get(doc, "department"),
                "join": _doc_get(doc, "posting_date"),
                "earnings": earnings,
                "deductions": deductions,
                "gross": _int(_doc_get(doc, "gross_pay")),
                "net": _int(_doc_get(doc, "net_pay")),
            }
        )
    return slips


def _row_get(row: Any, key: str) -> Any:
    return row.get(key) if isinstance(row, dict) else getattr(row, key, None)


def _doc_get(doc: Any, key: str) -> Any:
    return doc.get(key) if isinstance(doc, dict) else getattr(doc, key, None)


def _int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(round(float(value)))


def _coerce_bool(value: Any) -> bool:
    """Frappe form dict 에서 넘어오는 문자열 bool 처리 ('1'/'true'/'yes'/'y')."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _period_end(period: str) -> str:
    """'YYYY-MM' → 'YYYY-MM-DD' (해당 월 말일). 형식 검증은 _period_start 가 선행."""
    import calendar  # noqa: PLC0415 — 확정 경로에서만 필요

    year, month = (int(p) for p in str(period).split("-"))
    last = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-{last:02d}"


# ---------------------------------------------------------------------------
# 슬립 upsert 오케스트레이션 (seed_payroll_from_json.py 승격) — frappe 어댑터
# ---------------------------------------------------------------------------


def _upsert_slips(company: str, start: str, end: str, employees: list[dict], period: str) -> list[dict]:
    """급여대장 행을 Salary Slip 으로 upsert. seed 시퀀스(구성항목→직원→구조→배정→슬립)를 따른다.

    신규 인원은 슬립을 생성(docstatus 0 유지, submit 안 함)한다. 기존 슬립은 skipped —
    금액 갱신은 제출된 Salary Structure 개정이 필요하므로 이번 이터레이션에서 하지 않는다.
    반환 각 행: {name, action, gross}. 개인 금액은 로그 금지.
    """
    _ensure_salary_components(company, employees)
    results: list[dict] = []
    for e in employees:
        emp_id = _ensure_employee(company, e, start)
        ss_name = f"{period} {e['name']}"
        _ensure_salary_structure(company, ss_name, e)
        _ensure_structure_assignment(company, emp_id, ss_name, e, start)

        if _frappe.db.exists(
            "Salary Slip", {"employee": emp_id, "start_date": start, "docstatus": ("<", 2)}
        ):
            results.append({"name": e["name"], "action": "skipped", "gross": 0})
            continue

        _frappe.get_doc(
            {
                "doctype": "Salary Slip",
                "employee": emp_id,
                "start_date": start,
                "end_date": end,
                "company": company,
            }
        ).insert(ignore_permissions=True)
        results.append({"name": e["name"], "action": "created", "gross": _int(e.get("expected_gross"))})

    _frappe.db.commit()
    return results


def _ensure_salary_components(company: str, employees: list[dict]) -> None:
    seen: set[str] = set()
    for e in employees:
        for comp in e.get("earnings") or {}:
            _ensure_component(company, comp, "Earning", seen)
        for comp in e.get("deductions") or {}:
            _ensure_component(company, comp, "Deduction", seen)


def _ensure_component(company: str, comp: str, ctype: str, seen: set[str]) -> None:
    if comp in seen:
        return
    seen.add(comp)
    if _frappe.db.exists("Salary Component", comp):
        return
    payload: dict[str, Any] = {
        "doctype": "Salary Component",
        "salary_component": comp,
        "type": ctype,
        "company": company,
    }
    if "비과세" in comp:
        payload["is_tax_applicable"] = 0
    _frappe.get_doc(payload).insert(ignore_permissions=True)


def _ensure_employee(company: str, e: dict, start: str) -> str:
    emp_id = _frappe.db.get_value(
        "Employee", {"employee_name": e["name"], "company": company}, "name"
    )
    if emp_id:
        return emp_id
    doc = _frappe.get_doc(
        {
            "doctype": "Employee",
            "first_name": e["name"],
            "company": company,
            # 실입사일 그대로 (신고 데이터 소스 — 클램프 금지). 없으면 귀속월 1일.
            "date_of_joining": e.get("join") or start,
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "status": "Active",
            "personal_email": e.get("email") or None,
        }
    ).insert(ignore_permissions=True)
    return doc.name


def _ensure_salary_structure(company: str, ss_name: str, e: dict) -> None:
    if _frappe.db.exists("Salary Structure", ss_name):
        return
    ss = _frappe.get_doc(
        {
            "doctype": "Salary Structure",
            "__newname": ss_name,
            "company": company,
            "payroll_frequency": "Monthly",
            "earnings": [{"salary_component": c, "amount": a} for c, a in (e.get("earnings") or {}).items()],
            "deductions": [{"salary_component": c, "amount": a} for c, a in (e.get("deductions") or {}).items()],
        }
    )
    ss.insert(ignore_permissions=True)
    ss.submit()


def _ensure_structure_assignment(company: str, emp_id: str, ss_name: str, e: dict, start: str) -> None:
    if _frappe.db.exists(
        "Salary Structure Assignment", {"employee": emp_id, "salary_structure": ss_name}
    ):
        return
    ssa = _frappe.get_doc(
        {
            "doctype": "Salary Structure Assignment",
            "employee": emp_id,
            "salary_structure": ss_name,
            "from_date": start,
            "company": company,
            "base": (e.get("earnings") or {}).get("기본급", 0),
        }
    )
    ssa.insert(ignore_permissions=True)
    ssa.submit()


def _record_apply_audit(company: str, period: str, summary: dict) -> None:
    """확정 반영을 Comment 로 감사 기록 (집계 수치만 — 개인 급여액 금지). 실패는 무시(감사 부수효과)."""
    content = (
        f"[급여엑셀 반영] period={period}, company={company}, "
        f"created={summary['created']}, updated={summary['updated']}, "
        f"skipped={summary['skipped']}, total_gross={summary['total_gross']}, human_approved=True"
    )
    try:
        _frappe.get_doc(
            {"doctype": "Comment", "comment_type": "Info", "content": content}
        ).insert(ignore_permissions=True)
    except Exception:  # noqa: BLE001 — 감사 기록 실패가 반영을 되돌리지 않는다
        log_error = getattr(_frappe, "log_error", None)
        if log_error:
            log_error("payroll_excel_api: apply audit Comment 저장 실패")
