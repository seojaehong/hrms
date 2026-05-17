"""한국 노무 컴플라이언스 개선 액션 플랜 Frappe API.

compliance_action_plan.py 의 generate_action_plan을 Frappe whitelist endpoint로 래핑.

엔드포인트:
    - generate_action_plan: 진단 실행 후 액션 플랜 생성

설계 원칙:
    - read-only: DB mutation 없음.
    - AI 점수/확률 출력 없음.
    - 모든 액션 플랜은 human-review + admin confirm 대상.
    - 외부 LLM API 사용 없음.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Frappe 조건부 import
# ---------------------------------------------------------------------------
try:
    import frappe  # noqa: PLC0415

    _FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
    frappe = None  # type: ignore[assignment]
    _FRAPPE_AVAILABLE = False

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _whitelist(fn):
    """@_whitelist 데코레이터 — Frappe 없으면 no-op."""
    if _FRAPPE_AVAILABLE and frappe is not None:
        return frappe.whitelist()(fn)
    return fn


def _throw(msg: str) -> None:
    if _FRAPPE_AVAILABLE and frappe is not None:
        frappe.throw(msg)
    raise ValueError(msg)


@_whitelist
def generate_action_plan(
    company: str,
    workplace: str = "",
    as_of_date: str | None = None,
    deadline_days: int = 30,
) -> dict[str, Any]:
    """한국 노무 컴플라이언스 개선 액션 플랜 생성.

    내부적으로 run_compliance_diagnosis를 호출하여 진단 결과를 얻은 후
    compliance_action_plan.generate_action_plan으로 액션 플랜을 생성합니다.

    Args:
        company: 회사명 (필수).
        workplace: 사업장명 (선택).
        as_of_date: 진단 기준일 YYYY-MM-DD (선택, 기본값: 오늘).
        deadline_days: 기본 완료 기한 일수 (기본값: 30일).

    Returns:
        generate_action_plan 반환 구조와 동일.

    주의:
        - read-only. DB mutation 없음.
        - 점수/확률 출력 없음.
        - 결과는 human-review + admin confirm 대상.
    """
    if not company:
        _throw("company is required")

    if not as_of_date:
        as_of_date = str(frappe.utils.today()) if _FRAPPE_AVAILABLE else "2026-01-01"

    if not DATE_PATTERN.match(as_of_date):
        _throw(f"as_of_date must be YYYY-MM-DD format, got: {as_of_date!r}")

    try:
        deadline_days = int(deadline_days)
        if deadline_days < 1:
            deadline_days = 30
    except (TypeError, ValueError):
        deadline_days = 30

    # 1단계: 진단 실행
    from hrms.regional.south_korea.compliance_diagnosis_api import (
        FrappeDataLoader,
        run_full_compliance_diagnosis,
    )

    loader = FrappeDataLoader(company=company, workplace=workplace or "")

    try:
        diagnosis_result = run_full_compliance_diagnosis(
            company=company,
            workplace=workplace or "",
            as_of_date=as_of_date,
            data_loader=loader,
        )
    except ValueError as exc:
        _throw(str(exc))
        return {}  # unreachable

    # 2단계: 액션 플랜 생성
    from hrms.regional.south_korea.compliance_action_plan import generate_action_plan as _gen_plan

    try:
        return _gen_plan(
            diagnosis_result=diagnosis_result,
            company=company,
            deadline_days=deadline_days,
        )
    except ValueError as exc:
        _throw(str(exc))
        return {}  # unreachable
