"""한국 노무 컴플라이언스 감사 로그 Frappe API.

컴플라이언스 진단/액션 플랜/PDF 다운로드/발견 사항 처리 등의 이벤트를
구조화된 형태로 기록합니다.

엔드포인트:
    - log_compliance_event: 컴플라이언스 이벤트 기록

설계 원칙:
    - append-only: 기존 레코드 수정 없음.
    - AI 점수/확률 출력 없음.
    - actor는 Frappe 현재 로그인 사용자.
    - 외부 LLM API 사용 없음.

주의:
    현재 구현은 Frappe server log(frappe.logger) 기반입니다.
    별도 "Korea Compliance Audit Log" 독타입 생성 후 DB 저장으로 전환 가능.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
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

# 허용된 이벤트 유형
ALLOWED_EVENT_TYPES = frozenset(
    {
        "diagnosis_run",
        "pdf_download",
        "action_plan_generated",
        "finding_resolved",
        "finding_dismissed",
        "recommendation_checked",
    }
)

_SLUG_RE = re.compile(r"^[a-z_][a-z0-9_]{0,63}$")


def _whitelist(fn):
    """@_whitelist 데코레이터 — Frappe 없으면 no-op."""
    if _FRAPPE_AVAILABLE and frappe is not None:
        return frappe.whitelist()(fn)
    return fn


def _throw(msg: str) -> None:
    if _FRAPPE_AVAILABLE and frappe is not None:
        frappe.throw(msg)
    raise ValueError(msg)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _current_actor() -> str:
    if _FRAPPE_AVAILABLE and frappe is not None:
        try:
            return str(frappe.session.user) if frappe.session else "system"
        except Exception:
            return "system"
    return "system"


@_whitelist
def log_compliance_event(
    company: str,
    event_type: str,
    workplace: str = "",
    category_key: str = "",
    detail: str = "",
) -> dict[str, Any]:
    """컴플라이언스 이벤트 기록.

    Args:
        company: 회사명 (필수).
        event_type: 이벤트 유형 (허용 값: diagnosis_run, pdf_download,
            action_plan_generated, finding_resolved, finding_dismissed,
            recommendation_checked).
        workplace: 사업장명 (선택).
        category_key: 관련 카테고리 키 (선택, e.g. "wage_delay").
        detail: 부가 설명 JSON 문자열 또는 짧은 텍스트 (선택, 최대 500자).

    Returns:
        {
            "contract_type": "korea_compliance_audit_log_v1",
            "logged": true,
            "log_entry": {
                "timestamp": "YYYY-MM-DD HH:MM",
                "actor": "...",
                "company": "...",
                "workplace": "...",
                "event_type": "...",
                "event_label": "...",
                "category_key": "...",
                "detail": "...",
            }
        }

    주의:
        - read-only: DB mutation 없음 (logger 기록만).
        - actor는 Frappe 로그인 사용자에서 자동 추출.
        - 점수/확률 출력 없음.
    """
    if not company:
        _throw("company is required")

    if not event_type or event_type not in ALLOWED_EVENT_TYPES:
        _throw(
            f"event_type must be one of: {sorted(ALLOWED_EVENT_TYPES)}. "
            f"Got: {event_type!r}"
        )

    if category_key and not _SLUG_RE.match(category_key):
        _throw(
            f"category_key must match [a-z_][a-z0-9_]{{0,63}}. Got: {category_key!r}"
        )

    detail_str = str(detail or "")[:500]

    actor = _current_actor()
    timestamp = _now_iso()

    event_labels = {
        "diagnosis_run": "진단 실행",
        "pdf_download": "PDF 다운로드",
        "action_plan_generated": "액션 플랜 생성",
        "finding_resolved": "발견 사항 해결 표시",
        "finding_dismissed": "발견 사항 무시",
        "recommendation_checked": "권고 사항 체크",
    }
    event_label = event_labels.get(event_type, event_type)

    log_entry: dict[str, Any] = {
        "timestamp": timestamp,
        "actor": actor,
        "company": company,
        "workplace": workplace or "",
        "event_type": event_type,
        "event_label": event_label,
        "category_key": category_key or "",
        "detail": detail_str,
    }

    # Frappe logger 기록 (DB 대신 서버 로그)
    if _FRAPPE_AVAILABLE and frappe is not None:
        try:
            logger = frappe.logger("korea_compliance_audit", allow_site=True)
            logger.info(json.dumps(log_entry, ensure_ascii=False))
        except Exception:
            pass  # 로그 실패가 API 응답을 방해하지 않도록

    return {
        "contract_type": "korea_compliance_audit_log_v1",
        "logged": True,
        "log_entry": log_entry,
    }
