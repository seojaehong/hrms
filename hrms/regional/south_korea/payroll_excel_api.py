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
# 내부 헬퍼
# ---------------------------------------------------------------------------


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
