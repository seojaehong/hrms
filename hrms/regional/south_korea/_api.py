"""Frappe REST whitelist wrapper — Korea 모듈 통합 API.

이 파일만 frappe를 import합니다.
비즈니스 로직은 각 모듈 (ai_chat.py, global_search.py 등)에 집중합니다.

포함된 엔드포인트:
  - chat_query_api      : AI 챗봇 (5-A-1)
  - global_search_api   : 통합 검색 (5-A-2)
  - get_plan            : SaaS 플랜 조회 (5-B-1)
  - get_all_plans       : 전체 플랜 목록 (5-B-1)
  - calculate_monthly_invoice : 월 청구액 계산 (5-B-1)
  - list_invoices       : 청구 history (5-B-1)
  - initiate_subscription : 구독 시작 (5-B-1)
  - cancel_subscription : 구독 해지 (5-B-1)
  - upgrade_downgrade   : 플랜 변경 (5-B-1)
"""
from __future__ import annotations

import datetime as dt
import uuid

import frappe

# ---------------------------------------------------------------------------
# 5-A-1: AI 챗봇
# ---------------------------------------------------------------------------

from hrms.regional.south_korea.ai_chat import chat_query as _chat_query


@frappe.whitelist()
def chat_query_api(
    user_question: str,
    user_role: str = "employee",
    context_doctype: str | None = None,
    context_doc_name: str | None = None,
    session_id: str | None = None,
) -> dict:
    """한국 노무 AI 챗봇 REST endpoint.

    GET/POST /api/method/hrms.regional.south_korea._api.chat_query_api

    Parameters
    ----------
    user_question:
        사용자가 입력한 질문 텍스트.
    user_role:
        "employee" | "manager" | "admin" | "compliance".
        기본값: "employee".
    context_doctype:
        현재 열려 있는 Doctype (예: "Leave Application"). 선택.
    context_doc_name:
        현재 문서 name. 선택.
    session_id:
        대화 세션 ID. 미입력 시 자동 생성.

    Returns
    -------
    dict
        ai_chat.chat_query() 반환 구조와 동일.
        절대 mutation 없음 (assistant_only).
    """
    # session_id 자동 발급
    if not session_id:
        session_id = str(uuid.uuid4())

    # user_role 검증
    valid_roles = {"employee", "manager", "admin", "compliance"}
    if user_role not in valid_roles:
        user_role = "employee"

    return _chat_query(
        user_question=user_question,
        user_role=user_role,
        context_doctype=context_doctype,
        context_doc_name=context_doc_name,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# 5-A-2: 통합 검색
# ---------------------------------------------------------------------------

from hrms.regional.south_korea.global_search import (
    SEARCHABLE_DOCTYPES,
    global_search,
)


def _frappe_data_loader(
    doctype: str,
    query: str,
    search_fields: list[str],
    extra_filters: dict,
    limit: int,
) -> list[dict]:
    """frappe.get_all 기반 데이터 로더.

    - 각 search_field 에 LIKE %query% 필터를 OR 로 적용.
    - extra_filters 는 AND 조건 (company, owner_field 등).
    - doctype 미존재 시 빈 리스트 반환 (ForwardRef doctype 안전 처리).
    """
    try:
        query_lower = query.strip()
        if not query_lower:
            return []

        return_fields = list(
            dict.fromkeys(["name"] + list(search_fields) + list(extra_filters.keys()))
        )

        try:
            existing_cols = frappe.db.get_table_columns(doctype)
        except Exception:
            return []

        seen: set[str] = set()
        rows: list[dict] = []

        for field in search_fields:
            if field not in existing_cols:
                continue

            filters: list = [[field, "like", f"%{query_lower}%"]]
            for k, v in extra_filters.items():
                if k in existing_cols:
                    filters.append([k, "=", v])

            try:
                batch = frappe.get_list(
                    doctype,
                    filters=filters,
                    fields=return_fields,
                    page_length=limit,
                )
            except Exception:
                continue

            for row in batch:
                name = row.get("name")
                if name and name not in seen:
                    seen.add(name)
                    rows.append(row)
                if len(rows) >= limit:
                    break

            if len(rows) >= limit:
                break

        return rows[:limit]

    except Exception:
        frappe.log_error(frappe.get_traceback(), "korea_global_search._frappe_data_loader")
        return []


@frappe.whitelist()
def global_search_api(
    query: str,
    doctypes: str | None = None,
    company: str | None = None,
    limit_per_doctype: int = 10,
) -> dict:
    """통합 검색 API.

    클라이언트에서:
        frappe.call({
            method: 'hrms.regional.south_korea._api.global_search_api',
            args: { query: '김', doctypes: 'Employee,Salary Slip' },
        })

    Args:
        query: 검색어
        doctypes: 쉼표로 구분된 doctype 목록 (None이면 전체)
        company: 회사 필터
        limit_per_doctype: doctype 당 최대 결과 수 (1~50)
    """
    limit_per_doctype = max(1, min(int(limit_per_doctype), 50))

    user = frappe.session.user
    user_roles = frappe.get_roles(user)

    if "System Manager" in user_roles or "Administrator" in user_roles:
        user_role = "System Manager"
    elif "HR Manager" in user_roles:
        user_role = "HR Manager"
    elif "HR User" in user_roles:
        user_role = "HR User"
    else:
        user_role = "Employee"

    user_employee: str | None = frappe.db.get_value(
        "Employee", {"user_id": user}, "name"
    )

    doctype_list: list[str] | None = None
    if doctypes:
        doctype_list = [d.strip() for d in doctypes.split(",") if d.strip()]

    return global_search(
        query=query,
        user_role=user_role,
        user_employee=user_employee,
        company=company or None,
        doctypes=doctype_list,
        limit_per_doctype=limit_per_doctype,
        data_loader=_frappe_data_loader,
    )


# ---------------------------------------------------------------------------
# 5-B-1: SaaS 구독
# ---------------------------------------------------------------------------

from hrms.regional.south_korea.subscription import (
    PAYMENT_PROVIDERS,
    PLAN_TIERS,
    calculate_monthly_invoice as _calculate_monthly_invoice,
    cancel_subscription as _cancel_subscription,
    get_plan as _get_plan,
    initiate_subscription as _initiate_subscription,
    list_invoices as _list_invoices,
    upgrade_downgrade as _upgrade_downgrade,
)


@frappe.whitelist()
def get_plan(tier: str) -> dict:
    """플랜 정보 조회."""
    try:
        return _get_plan(tier)
    except ValueError as e:
        frappe.throw(str(e))


@frappe.whitelist()
def get_all_plans() -> dict:
    """전체 플랜 목록 + 결제 수단 반환 (UI 초기 로드용)."""
    return {
        "plans": PLAN_TIERS,
        "payment_providers": PAYMENT_PROVIDERS,
    }


@frappe.whitelist()
def calculate_monthly_invoice(
    tier: str,
    employee_count: int,
    period_start: str,
    period_end: str,
) -> dict:
    """월 청구액 계산.

    Args:
        tier:            플랜 키.
        employee_count:  현재 활성 직원 수 (int 또는 숫자 문자열).
        period_start:    청구 시작일 (YYYY-MM-DD).
        period_end:      청구 종료일 (YYYY-MM-DD).
    """
    try:
        return _calculate_monthly_invoice(
            tier=tier,
            employee_count=int(employee_count),
            period_start=dt.date.fromisoformat(period_start),
            period_end=dt.date.fromisoformat(period_end),
        )
    except (ValueError, TypeError) as e:
        frappe.throw(str(e))


@frappe.whitelist()
def list_invoices(company: str, limit: int = 12) -> list[dict]:
    """청구 history 조회."""
    return _list_invoices(company=company, limit=int(limit))


@frappe.whitelist()
def initiate_subscription(
    company: str,
    tier: str,
    payment_method: str,
    billing_email: str,
    dry_run: bool = True,
) -> dict:
    """구독 시작.

    human_approved는 서버 측에서 System Manager 역할 확인으로 대체.
    UI confirm 다이얼로그는 프론트엔드에서 처리.
    """
    _assert_system_manager()
    try:
        return _initiate_subscription(
            company=company,
            tier=tier,
            payment_method=payment_method,
            billing_email=billing_email,
            human_approved=True,
            dry_run=_coerce_bool(dry_run),
        )
    except (ValueError, PermissionError, NotImplementedError) as e:
        frappe.throw(str(e))


@frappe.whitelist()
def cancel_subscription(subscription_id: str) -> dict:
    """구독 해지."""
    _assert_system_manager()
    try:
        return _cancel_subscription(
            subscription_id=subscription_id,
            human_approved=True,
        )
    except (ValueError, PermissionError) as e:
        frappe.throw(str(e))


@frappe.whitelist()
def upgrade_downgrade(subscription_id: str, new_tier: str) -> dict:
    """플랜 변경."""
    _assert_system_manager()
    try:
        return _upgrade_downgrade(
            subscription_id=subscription_id,
            new_tier=new_tier,
            human_approved=True,
        )
    except (ValueError, PermissionError) as e:
        frappe.throw(str(e))


# ---------------------------------------------------------------------------
# 내부 헬퍼 (구독 모듈용)
# ---------------------------------------------------------------------------


def _assert_system_manager() -> None:
    """System Manager 역할이 없으면 PermissionError."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(
            "이 작업은 시스템 관리자(System Manager) 권한이 필요합니다.",
            frappe.PermissionError,
        )


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
