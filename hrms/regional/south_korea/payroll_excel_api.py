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
