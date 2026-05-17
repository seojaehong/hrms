"""Frappe whitelist API wrappers for 5인 미만 사업장 룰 엔진.

모든 비즈니스 로직은 small_workplace_rules 에 위임한다.
이 모듈은 Frappe 컨텍스트에서만 실행된다 (import frappe).

엔드포인트:
    POST /api/method/hrms.regional.south_korea._api.evaluate_provision
    POST /api/method/hrms.regional.south_korea._api.filter_payroll
    POST /api/method/hrms.regional.south_korea._api.filter_leave_allocations
    POST /api/method/hrms.regional.south_korea._api.get_law_summary
"""

from __future__ import annotations

import json
from typing import Any

import frappe

from hrms.regional.south_korea import small_workplace_rules as rules

# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _coerce_payload(payload: Any, kwargs: dict) -> dict:
    """payload 인자를 dict 로 정규화한다.

    1. payload 가 dict 이면 그대로 사용.
    2. payload 가 str 이면 JSON 파싱.
    3. payload 가 None 이면 form_dict 에서 'payload' 키를 JSON 파싱 시도.
    4. kwargs 병합 (form_dict 방식 호환).
    """
    if isinstance(payload, str):
        payload = json.loads(payload)
    if payload is None:
        raw = getattr(frappe.local, "form_dict", {}).get("payload")
        if raw:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        else:
            payload = {}
    if not isinstance(payload, dict):
        frappe.throw("payload 는 JSON 객체여야 합니다.")
    return payload


def _require_keys(d: dict, keys: set[str], label: str) -> None:
    missing = keys - d.keys()
    if missing:
        frappe.throw(f"{label} 에 필수 필드가 없습니다: {sorted(missing)}")


# ---------------------------------------------------------------------------
# Frappe Whitelisted API
# ---------------------------------------------------------------------------

@frappe.whitelist()
def evaluate_provision(payload: dict | None = None, **kwargs) -> dict[str, Any]:
    """특정 조항의 5인 미만 적용 여부를 반환한다.

    Request payload:
        {
            "workplace_profile": { "headcount": int, ... },
            "provision_key": str
        }

    Response:
        {
            "provision_key": str,
            "law": str,
            "applies": bool,
            "reason": str
        }
    """
    payload = _coerce_payload(payload, kwargs)
    _require_keys(payload, {"workplace_profile", "provision_key"}, "payload")

    workplace_profile = payload["workplace_profile"]
    provision_key = payload["provision_key"]

    if not isinstance(workplace_profile, dict):
        frappe.throw("workplace_profile 은 JSON 객체여야 합니다.")
    if not isinstance(provision_key, str):
        frappe.throw("provision_key 는 문자열이어야 합니다.")

    try:
        return rules.evaluate_provision(
            workplace_profile=workplace_profile,
            provision_key=provision_key,
        )
    except ValueError as exc:
        frappe.throw(str(exc))


@frappe.whitelist()
def filter_payroll(payload: dict | None = None, **kwargs) -> dict[str, Any]:
    """페이롤 항목에서 5인 미만 적용 제외 가산수당 컴포넌트를 필터링한다.

    Request payload:
        {
            "workplace_profile": { "headcount": int, ... },
            "payroll_components": [
                { "code": "overtime_premium", "label": "연장수당", "amount": 50000 },
                ...
            ]
        }

    Response:
        {
            "applied_components": [...],
            "excluded_components": [...],
            "reason": str
        }
    """
    payload = _coerce_payload(payload, kwargs)
    _require_keys(payload, {"workplace_profile", "payroll_components"}, "payload")

    workplace_profile = payload["workplace_profile"]
    payroll_components = payload["payroll_components"]

    if not isinstance(workplace_profile, dict):
        frappe.throw("workplace_profile 은 JSON 객체여야 합니다.")
    if not isinstance(payroll_components, list):
        frappe.throw("payroll_components 는 JSON 배열이어야 합니다.")

    try:
        return rules.filter_payroll_for_small_workplace(
            workplace_profile=workplace_profile,
            payroll_components=payroll_components,
        )
    except ValueError as exc:
        frappe.throw(str(exc))


@frappe.whitelist()
def filter_leave_allocations(payload: dict | None = None, **kwargs) -> dict[str, Any]:
    """휴가 배정에서 5인 미만 적용 제외 휴가를 필터링한다.

    Request payload:
        {
            "workplace_profile": { "headcount": int, ... },
            "leave_allocations": [
                { "leave_type_key": "annual_paid_leave", "days": 15 },
                ...
            ]
        }

    Response:
        {
            "applied_allocations": [...],
            "excluded_allocations": [...],
            "reason": str
        }
    """
    payload = _coerce_payload(payload, kwargs)
    _require_keys(payload, {"workplace_profile", "leave_allocations"}, "payload")

    workplace_profile = payload["workplace_profile"]
    leave_allocations = payload["leave_allocations"]

    if not isinstance(workplace_profile, dict):
        frappe.throw("workplace_profile 은 JSON 객체여야 합니다.")
    if not isinstance(leave_allocations, list):
        frappe.throw("leave_allocations 는 JSON 배열이어야 합니다.")

    try:
        return rules.filter_leave_allocations_for_small_workplace(
            workplace_profile=workplace_profile,
            leave_allocations=leave_allocations,
        )
    except ValueError as exc:
        frappe.throw(str(exc))


@frappe.whitelist()
def get_law_summary(payload: dict | None = None, **kwargs) -> dict[str, Any]:
    """사업장 적용 법령 요약을 반환한다.

    Request payload:
        {
            "workplace_profile": { "headcount": int, ... }
        }

    Response:
        {
            "is_small_workplace": bool,
            "headcount": int,
            "exempt_provisions": [...],
            "always_applicable": [...],
            "legal_summary": str
        }
    """
    payload = _coerce_payload(payload, kwargs)
    _require_keys(payload, {"workplace_profile"}, "payload")

    workplace_profile = payload["workplace_profile"]

    if not isinstance(workplace_profile, dict):
        frappe.throw("workplace_profile 은 JSON 객체여야 합니다.")

    try:
        return rules.get_applicable_law_summary(workplace_profile=workplace_profile)
    except ValueError as exc:
        frappe.throw(str(exc))
