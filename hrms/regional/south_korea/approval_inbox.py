"""
hrms/regional/south_korea/approval_inbox.py
결재 인박스 — 한국 HR 통합 결재 대기 항목 조회 및 처리.

본 모듈은 Frappe에 직접 의존하지만 방어적 패턴을 사용해
doctype이 없거나 DB가 없는 환경(테스트 등)에서도 안전하게 동작합니다.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import frappe

# ---------------------------------------------------------------------------
# 내부 상수
# ---------------------------------------------------------------------------

_DOCTYPE_LEAVE = "Leave Application"
_DOCTYPE_EXPENSE = "Expense Claim"
_DOCTYPE_PAYROLL = "Korea Payroll Closing Draft"
_DOCTYPE_CONTRACT = "Employment Contract"

_DOCTYPE_LABELS: dict[str, str] = {
    _DOCTYPE_LEAVE: "휴가신청",
    _DOCTYPE_EXPENSE: "경비청구",
    _DOCTYPE_PAYROLL: "페이롤마감",
    _DOCTYPE_CONTRACT: "계약승인",
}


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


def list_pending_approvals(*, approver: str, as_of_date: dt.date) -> list[dict]:
    """본인이 결재해야 할 항목 통합 목록.

    결재자(approver)의 user_id 기준으로 Leave Application, Expense Claim,
    Korea Payroll Closing Draft, Employment Contract의 결재 대기 항목을
    단일 리스트로 통합 반환합니다.

    Returns:
        [
            {
                "doctype": "Leave Application",
                "name": "HR-LA-2026-...",
                "title": "휴가신청 - 민지 김",
                "applicant_name": "민지 김",
                "requested_at": "2026-05-01T09:00:00",
                "details": {...},
                "url_app": "/app/leave-application/HR-LA-...",
                "url_pwa": "/hrms/leave-applications/HR-LA-...",
            },
            ...
        ]
    """
    if not approver:
        frappe.throw("approver는 필수입니다.")

    result: list[dict] = []

    # 각 소스별 수집 — doctype 없음 또는 DB 없음 시 graceful skip
    for collector in (
        _collect_leave_applications,
        _collect_expense_claims,
        _collect_payroll_closing_drafts,
        _collect_employment_contracts,
    ):
        try:
            result.extend(collector(approver=approver, as_of_date=as_of_date))
        except Exception:
            # 개별 소스 실패는 전체를 막지 않음
            if getattr(frappe, "log_error", None):
                frappe.log_error(f"approval_inbox: {collector.__name__} 수집 실패")

    # 최신 요청 순 정렬
    result.sort(key=lambda x: x.get("requested_at") or "", reverse=True)
    return result


def approve_item(
    *,
    doctype: str,
    name: str,
    approver: str,
    human_approved: bool,
    comment: str | None = None,
) -> dict:
    """결재 승인.

    human_approved가 True여야 실제 승인이 진행됩니다.
    actor와 타임스탬프를 Comment로 기록합니다.
    """
    if not human_approved:
        frappe.throw("human_approved=True 없이 승인할 수 없습니다.")
    _validate_actor(approver)

    handler = _get_mutation_handler(doctype)
    return handler(
        name=name,
        action="approve",
        actor=approver,
        comment=comment,
    )


def reject_item(
    *,
    doctype: str,
    name: str,
    approver: str,
    human_approved: bool,
    comment: str | None = None,
) -> dict:
    """결재 반려.

    human_approved가 True여야 실제 반려가 진행됩니다.
    """
    if not human_approved:
        frappe.throw("human_approved=True 없이 반려할 수 없습니다.")
    _validate_actor(approver)

    handler = _get_mutation_handler(doctype)
    return handler(
        name=name,
        action="reject",
        actor=approver,
        comment=comment,
    )


def count_pending_for_others(*, approver: str, as_of_date: dt.date) -> dict:
    """다른 결재자에게 배정된 결재 대기 건수 (read-only, mutation 없음).

    "마감 센터 확정 대기 1건 ↔ 내 결재함 0건" 혼란 UX 보조:
    내 결재함이 비어 있어도 조직 전체에 대기 건이 있으면 그 수를 알려준다.
    미배정(approver 빈 값) 항목은 카운트하지 않는다.
    """
    if not approver:
        frappe.throw("approver는 필수입니다.")

    # doctype → (대기 상태 filters, 결재자 필드)
    pending_specs = {
        _DOCTYPE_LEAVE: ({"status": "Open", "docstatus": 0}, "leave_approver"),
        _DOCTYPE_EXPENSE: ({"approval_status": "Draft", "docstatus": 0}, "expense_approver"),
        _DOCTYPE_PAYROLL: ({"status": "draft_pending_human_approval", "docstatus": 0}, "approver"),
        _DOCTYPE_CONTRACT: ({"status": "Approval Pending", "docstatus": 0}, "approver"),
    }

    by_doctype: dict[str, int] = {}
    total = 0
    for doctype, (filters, approver_field) in pending_specs.items():
        if not _doctype_exists(doctype):
            continue
        try:
            rows = frappe.get_list(
                doctype,
                filters=filters,
                fields=["name", approver_field],
                limit=1000,
            )
        except Exception:
            # 개별 소스 실패는 전체를 막지 않음 (list_pending_approvals와 동일 방침)
            if getattr(frappe, "log_error", None):
                frappe.log_error(f"approval_inbox: count_pending_for_others {doctype} 조회 실패")
            continue
        count = sum(
            1
            for row in rows
            if (row.get(approver_field) or "").strip() and row.get(approver_field) != approver
        )
        if count:
            by_doctype[doctype] = count
            total += count

    return {
        "contract_type": "korea_approval_inbox_pending_others_v1",
        "runtime_action": "runtime_read_only",
        "approver": approver,
        "total": total,
        "by_doctype": by_doctype,
    }


# ---------------------------------------------------------------------------
# 수집 함수
# ---------------------------------------------------------------------------


def _collect_leave_applications(
    *, approver: str, as_of_date: dt.date
) -> list[dict]:
    db = getattr(frappe, "db", None)
    if not db or not _doctype_exists(_DOCTYPE_LEAVE):
        return []

    rows = frappe.get_list(
        _DOCTYPE_LEAVE,
        filters={
            "status": "Open",
            "leave_approver": approver,
            "docstatus": 0,
        },
        fields=[
            "name",
            "employee_name",
            "leave_type",
            "from_date",
            "to_date",
            "total_leave_days",
            "description",
            "creation",
            "leave_approver",
        ],
        order_by="creation desc",
        limit=100,
    )

    items = []
    for row in rows:
        name = row.get("name", "")
        employee_name = row.get("employee_name", "")
        items.append(
            {
                "doctype": _DOCTYPE_LEAVE,
                "name": name,
                "title": f"{_DOCTYPE_LABELS[_DOCTYPE_LEAVE]} - {employee_name}",
                "applicant_name": employee_name,
                "requested_at": _fmt_datetime(row.get("creation")),
                "details": {
                    "leave_type": row.get("leave_type"),
                    "from_date": _fmt_date(row.get("from_date")),
                    "to_date": _fmt_date(row.get("to_date")),
                    "total_leave_days": row.get("total_leave_days"),
                    "description": row.get("description") or "",
                },
                "url_app": f"/app/leave-application/{name}",
                "url_pwa": f"/hrms/leave-applications/{name}",
            }
        )
    return items


def _collect_expense_claims(
    *, approver: str, as_of_date: dt.date
) -> list[dict]:
    db = getattr(frappe, "db", None)
    if not db or not _doctype_exists(_DOCTYPE_EXPENSE):
        return []

    rows = frappe.get_list(
        _DOCTYPE_EXPENSE,
        filters={
            "approval_status": "Draft",
            "expense_approver": approver,
            "docstatus": 0,
        },
        fields=[
            "name",
            "employee_name",
            "total_claimed_amount",
            "currency",
            "posting_date",
            "creation",
            "expense_approver",
            "company",
        ],
        order_by="creation desc",
        limit=100,
    )

    items = []
    for row in rows:
        name = row.get("name", "")
        employee_name = row.get("employee_name", "")
        amount = row.get("total_claimed_amount") or 0
        currency = row.get("currency") or "KRW"
        items.append(
            {
                "doctype": _DOCTYPE_EXPENSE,
                "name": name,
                "title": f"{_DOCTYPE_LABELS[_DOCTYPE_EXPENSE]} - {employee_name}",
                "applicant_name": employee_name,
                "requested_at": _fmt_datetime(row.get("creation")),
                "details": {
                    "total_claimed_amount": amount,
                    "currency": currency,
                    "posting_date": _fmt_date(row.get("posting_date")),
                    "company": row.get("company") or "",
                },
                "url_app": f"/app/expense-claim/{name}",
                "url_pwa": f"/hrms/expense-claims/{name}",
            }
        )
    return items


def _collect_payroll_closing_drafts(
    *, approver: str, as_of_date: dt.date
) -> list[dict]:
    db = getattr(frappe, "db", None)
    if not db or not _doctype_exists(_DOCTYPE_PAYROLL):
        return []

    # 주의: fields는 korea_payroll_closing_draft.json에 실재하는 필드만 사용.
    # (과거 employee_name/pay_year_month 등 미존재 필드 요청 → get_list 예외
    #  → 조용히 빈 리스트 반환 → "1 확정 대기 ↔ 인박스 0건" 버그)
    try:
        rows = frappe.get_list(
            _DOCTYPE_PAYROLL,
            filters={
                "status": "draft_pending_human_approval",
                "approver": approver,
                "docstatus": 0,
            },
            fields=[
                "name",
                "company",
                "workplace",
                "period_start",
                "period_end",
                "status",
                "creation",
            ],
            order_by="creation desc",
            limit=100,
        )
    except Exception:
        return []

    items = []
    for row in rows:
        name = row.get("name", "")
        workplace = row.get("workplace") or row.get("company") or name
        period = f"{_fmt_date(row.get('period_start')) or ''}~{_fmt_date(row.get('period_end')) or ''}"
        items.append(
            {
                "doctype": _DOCTYPE_PAYROLL,
                "name": name,
                "title": f"{_DOCTYPE_LABELS[_DOCTYPE_PAYROLL]} - {workplace} {period}",
                "applicant_name": workplace,
                "requested_at": _fmt_datetime(row.get("creation")),
                "details": {
                    "workplace": row.get("workplace") or "",
                    "company": row.get("company") or "",
                    "period_start": _fmt_date(row.get("period_start")),
                    "period_end": _fmt_date(row.get("period_end")),
                    "status": row.get("status") or "",
                },
                "url_app": f"/app/korea-payroll-closing-draft/{name}",
                # PWA에는 korea-payroll-closing-draft 상세 라우트가 없고
                # 세션 미리보기 라우트(/korea-payroll-closing-session/:name)가 있음
                "url_pwa": f"/hrms/korea-payroll-closing-session/{name}",
            }
        )
    return items


def _collect_employment_contracts(
    *, approver: str, as_of_date: dt.date
) -> list[dict]:
    db = getattr(frappe, "db", None)
    if not db or not _doctype_exists(_DOCTYPE_CONTRACT):
        return []

    try:
        rows = frappe.get_list(
            _DOCTYPE_CONTRACT,
            filters={
                "status": "Approval Pending",
                "approver": approver,
                "docstatus": 0,
            },
            fields=[
                "name",
                "employee_name",
                "contract_type",
                "start_date",
                "end_date",
                "creation",
            ],
            order_by="creation desc",
            limit=100,
        )
    except Exception:
        return []

    items = []
    for row in rows:
        name = row.get("name", "")
        employee_name = row.get("employee_name") or name
        items.append(
            {
                "doctype": _DOCTYPE_CONTRACT,
                "name": name,
                "title": f"{_DOCTYPE_LABELS[_DOCTYPE_CONTRACT]} - {employee_name}",
                "applicant_name": employee_name,
                "requested_at": _fmt_datetime(row.get("creation")),
                "details": {
                    "contract_type": row.get("contract_type") or "",
                    "start_date": _fmt_date(row.get("start_date")),
                    "end_date": _fmt_date(row.get("end_date")),
                },
                "url_app": f"/app/employment-contract/{name}",
                "url_pwa": f"/hrms/employment-contract/{name}",
            }
        )
    return items


# ---------------------------------------------------------------------------
# 뮤테이션 핸들러
# ---------------------------------------------------------------------------


def _get_mutation_handler(doctype: str):
    handlers = {
        _DOCTYPE_LEAVE: _mutate_leave_application,
        _DOCTYPE_EXPENSE: _mutate_expense_claim,
        _DOCTYPE_PAYROLL: _mutate_payroll_closing_draft,
        _DOCTYPE_CONTRACT: _mutate_employment_contract,
    }
    handler = handlers.get(doctype)
    if not handler:
        frappe.throw(f"지원하지 않는 doctype: {doctype}")
    return handler


def _mutate_leave_application(
    *, name: str, action: str, actor: str, comment: str | None
) -> dict:
    doc = frappe.get_doc(_DOCTYPE_LEAVE, name)
    new_status = "Approved" if action == "approve" else "Rejected"
    doc.status = new_status
    doc.save(ignore_permissions=True)
    _record_audit_comment(
        doctype=_DOCTYPE_LEAVE,
        name=name,
        action=action,
        actor=actor,
        comment=comment,
    )
    return {"doctype": _DOCTYPE_LEAVE, "name": name, "status": new_status, "actor": actor}


def _mutate_expense_claim(
    *, name: str, action: str, actor: str, comment: str | None
) -> dict:
    doc = frappe.get_doc(_DOCTYPE_EXPENSE, name)
    new_status = "Approved" if action == "approve" else "Rejected"
    doc.approval_status = new_status
    doc.save(ignore_permissions=True)
    _record_audit_comment(
        doctype=_DOCTYPE_EXPENSE,
        name=name,
        action=action,
        actor=actor,
        comment=comment,
    )
    return {"doctype": _DOCTYPE_EXPENSE, "name": name, "approval_status": new_status, "actor": actor}


def _mutate_payroll_closing_draft(
    *, name: str, action: str, actor: str, comment: str | None
) -> dict:
    """마감 draft 승인/반려 — draft 안전 불변식 준수.

    mutation_boundary=draft_only_no_submit_no_approve_no_send:
    여기서의 '승인'은 문서 제출(submit)이 아니라 draft에 승인 기록을
    남기는 수준이다. 판단 근거 — korea_payroll_closing_draft.json의
    status Select options에 draft_human_approved / draft_human_rejected가
    허용된 전이로 정의되어 있고(is_submittable=0, docstatus 0 유지),
    실제 확정·전송은 별도 담당자 플로우에서 수행된다.
    (과거 코드의 "approved"/"rejected"는 Select options에 없는 값이라
    저장 시 validation 실패를 유발했음.)
    """
    if not _doctype_exists(_DOCTYPE_PAYROLL):
        frappe.throw(f"{_DOCTYPE_PAYROLL} doctype이 설치되어 있지 않습니다.")
    doc = frappe.get_doc(_DOCTYPE_PAYROLL, name)
    new_status = "draft_human_approved" if action == "approve" else "draft_human_rejected"
    doc.status = new_status
    doc.save(ignore_permissions=True)
    _record_audit_comment(
        doctype=_DOCTYPE_PAYROLL,
        name=name,
        action=action,
        actor=actor,
        comment=comment,
    )
    return {"doctype": _DOCTYPE_PAYROLL, "name": name, "status": new_status, "actor": actor}


def _mutate_employment_contract(
    *, name: str, action: str, actor: str, comment: str | None
) -> dict:
    if not _doctype_exists(_DOCTYPE_CONTRACT):
        frappe.throw(f"{_DOCTYPE_CONTRACT} doctype이 설치되어 있지 않습니다.")
    doc = frappe.get_doc(_DOCTYPE_CONTRACT, name)
    new_status = "Approved" if action == "approve" else "Rejected"
    doc.status = new_status
    doc.save(ignore_permissions=True)
    _record_audit_comment(
        doctype=_DOCTYPE_CONTRACT,
        name=name,
        action=action,
        actor=actor,
        comment=comment,
    )
    return {"doctype": _DOCTYPE_CONTRACT, "name": name, "status": new_status, "actor": actor}


# ---------------------------------------------------------------------------
# 감사 로그 (Comment)
# ---------------------------------------------------------------------------


def _record_audit_comment(
    *,
    doctype: str,
    name: str,
    action: str,
    actor: str,
    comment: str | None,
) -> None:
    action_label = "승인" if action == "approve" else "반려"
    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content_parts = [
        f"[결재인박스] {action_label} — actor={actor}, human_approved=True, ts={now_str}"
    ]
    if comment:
        content_parts.append(f"사유: {comment}")
    content = "\n".join(content_parts)

    payload = {
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": doctype,
        "reference_name": name,
        "content": content,
    }
    try:
        frappe.get_doc(payload).insert(ignore_permissions=True)
    except Exception:
        if getattr(frappe, "log_error", None):
            frappe.log_error(f"approval_inbox: Comment 저장 실패 — {doctype}/{name}")


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _doctype_exists(doctype: str) -> bool:
    db = getattr(frappe, "db", None)
    if not db:
        return False
    try:
        exists_fn = getattr(db, "exists", None)
        if exists_fn:
            return bool(exists_fn("DocType", doctype))
        return False
    except Exception:
        return False


def _validate_actor(actor: str) -> None:
    if not actor:
        frappe.throw("approver(actor)가 필요합니다.")


def _fmt_date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _fmt_datetime(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.isoformat(sep="T")
    if isinstance(value, dt.date):
        return value.isoformat() + "T00:00:00"
    return str(value)
