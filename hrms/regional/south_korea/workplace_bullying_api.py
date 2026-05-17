"""직장 내 괴롭힘 워크플로우 — Frappe whitelist API 레이어.

이 파일은 Frappe 환경에서만 실행됩니다.
비즈니스 로직은 workplace_bullying.py (framework-free)에 있습니다.

사용법 (Frappe whitelist API):
    POST /api/method/hrms.regional.south_korea._api.create_bullying_report
    POST /api/method/hrms.regional.south_korea._api.assign_investigator_api
    POST /api/method/hrms.regional.south_korea._api.submit_investigation_finding_api
    POST /api/method/hrms.regional.south_korea._api.apply_protective_action_api
    GET  /api/method/hrms.regional.south_korea._api.get_bullying_dashboard_api
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import frappe

from hrms.regional.south_korea.workplace_bullying import (
    ACTION_TYPES,
    REPORT_STATUS,
    apply_protective_action,
    assign_investigator,
    create_bullying_report,
    get_bullying_dashboard,
    redact_report_for_viewer,
    submit_investigation_finding,
)

# ---------------------------------------------------------------------------
# 스토리지 헬퍼 — Frappe Document를 활용한 저장/로드
# ---------------------------------------------------------------------------
# 실제 Frappe 설치에서는 "Workplace Bullying Report" DocType이 존재해야 합니다.
# 이 레이어는 인터페이스 계약만 정의하며, DocType 정의는 별도 설치 과정에서 생성됩니다.
_REPORT_DOCTYPE = "Workplace Bullying Report"


def _load_report(report_id: str) -> dict[str, Any]:
    """Frappe DB에서 보고서를 로드."""
    if not frappe.db.exists(_REPORT_DOCTYPE, report_id):
        frappe.throw(f"신고 건을 찾을 수 없습니다: {report_id}", frappe.DoesNotExistError)
    doc = frappe.get_doc(_REPORT_DOCTYPE, report_id)
    try:
        return json.loads(doc.report_payload)
    except (AttributeError, ValueError, TypeError):
        frappe.throw(f"신고 데이터 파싱 오류: {report_id}")


def _save_report(report: dict[str, Any]) -> None:
    """Frappe DB에 보고서를 저장/업데이트."""
    report_id = report["report_id"]
    payload_str = json.dumps(report, ensure_ascii=False)

    if frappe.db.exists(_REPORT_DOCTYPE, report_id):
        doc = frappe.get_doc(_REPORT_DOCTYPE, report_id)
        doc.report_payload = payload_str
        doc.status = report.get("status")
        doc.workplace = report.get("workplace")
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.new_doc(_REPORT_DOCTYPE)
        doc.name = report_id
        doc.report_payload = payload_str
        doc.status = report.get("status")
        doc.workplace = report.get("workplace")
        doc.insert(ignore_permissions=True)


def _viewer_context() -> tuple[str, str | None]:
    """현재 로그인 사용자의 역할과 ID를 반환."""
    user = frappe.session.user or "Guest"
    if "System Manager" in frappe.get_roles(user) or "HR Manager" in frappe.get_roles(user):
        return "hr_admin", user
    return "staff", user


# ---------------------------------------------------------------------------
# Frappe whitelist endpoints
# ---------------------------------------------------------------------------


@frappe.whitelist()
def create_bullying_report_api(
    reporter_anonymous: bool | str = False,
    reporter_name: str | None = None,
    reporter_contact: str | None = None,
    incident_date: str = "",
    incident_location: str = "",
    incident_description: str = "",
    alleged_perpetrator: str | None = None,
    witnesses: list[str] | str | None = None,
    evidence_attachments: list[str] | str | None = None,
    workplace: str = "",
) -> dict[str, Any]:
    """신고 접수 API. human_approved 불필요 (즉시 처리 — 피해자 보호 원칙)."""
    try:
        anonymous = _coerce_bool(reporter_anonymous)
        parsed_date = _parse_date(incident_date, "incident_date")
        witnesses_list = _coerce_list(witnesses)
        attachments_list = _coerce_list(evidence_attachments)

        report = create_bullying_report(
            reporter_anonymous=anonymous,
            reporter_name=reporter_name if not anonymous else None,
            reporter_contact=reporter_contact if not anonymous else None,
            incident_date=parsed_date,
            incident_location=incident_location,
            incident_description=incident_description,
            alleged_perpetrator=alleged_perpetrator,
            witnesses=witnesses_list,
            evidence_attachments=attachments_list,
            workplace=workplace,
            human_approved=False,
        )

        _save_report(report)

        # 반환 시 현재 사용자 권한에 따라 PII 마스킹
        viewer_role, viewer_id = _viewer_context()
        return {
            "status": "ok",
            "report": redact_report_for_viewer(report, viewer_role, viewer_id),
        }
    except ValueError as exc:
        frappe.throw(str(exc))


@frappe.whitelist()
def assign_investigator_api(
    report_id: str = "",
    investigator: str = "",
    decided_by: str = "",
    human_approved: bool | str = False,
) -> dict[str, Any]:
    """조사관 지정 API. human_approved=True 필수."""
    try:
        _require_human_approved_param(human_approved, "assign_investigator")
        report = _load_report(report_id)
        updated = assign_investigator(
            report=report,
            investigator=investigator,
            decided_by=decided_by,
            human_approved=True,
        )
        _save_report(updated)
        viewer_role, viewer_id = _viewer_context()
        return {
            "status": "ok",
            "report": redact_report_for_viewer(updated, viewer_role, viewer_id),
        }
    except ValueError as exc:
        frappe.throw(str(exc))


@frappe.whitelist()
def submit_investigation_finding_api(
    report_id: str = "",
    investigator: str = "",
    finding: str = "",
    investigation_notes: str = "",
    recommended_actions: list[str] | str | None = None,
    decided_by: str = "",
    human_approved: bool | str = False,
) -> dict[str, Any]:
    """조사 결과 제출 API. human_approved=True 필수."""
    try:
        _require_human_approved_param(human_approved, "submit_investigation_finding")
        report = _load_report(report_id)
        actions_list = _coerce_list(recommended_actions)
        updated = submit_investigation_finding(
            report=report,
            investigator=investigator,
            finding=finding,
            investigation_notes=investigation_notes,
            recommended_actions=actions_list,
            decided_by=decided_by,
            human_approved=True,
        )
        _save_report(updated)
        viewer_role, viewer_id = _viewer_context()
        return {
            "status": "ok",
            "report": redact_report_for_viewer(updated, viewer_role, viewer_id),
        }
    except ValueError as exc:
        frappe.throw(str(exc))


@frappe.whitelist()
def apply_protective_action_api(
    report_id: str = "",
    action_type: str = "",
    target_employee: str = "",
    action_description: str = "",
    decided_by: str = "",
    human_approved: bool | str = False,
) -> dict[str, Any]:
    """조치 적용 API (피해자 보호/가해자 징계). human_approved=True 필수."""
    try:
        _require_human_approved_param(human_approved, "apply_protective_action")
        report = _load_report(report_id)
        updated = apply_protective_action(
            report=report,
            action_type=action_type,
            target_employee=target_employee,
            action_description=action_description,
            decided_by=decided_by,
            human_approved=True,
        )
        _save_report(updated)
        viewer_role, viewer_id = _viewer_context()
        return {
            "status": "ok",
            "report": redact_report_for_viewer(updated, viewer_role, viewer_id),
        }
    except ValueError as exc:
        frappe.throw(str(exc))


@frappe.whitelist()
def get_bullying_dashboard_api(
    workplace: str = "",
    period_start: str = "",
    period_end: str = "",
) -> dict[str, Any]:
    """관리자 대시보드 API. 집계 데이터만 반환 (PII 없음)."""
    try:
        start = _parse_date(period_start, "period_start")
        end = _parse_date(period_end, "period_end")

        # DB에서 해당 workplace의 보고서 로드
        raw_docs = frappe.get_all(
            _REPORT_DOCTYPE,
            filters={"workplace": workplace},
            fields=["report_payload"],
        )
        reports = []
        for row in raw_docs:
            try:
                reports.append(json.loads(row.get("report_payload") or "{}"))
            except (ValueError, TypeError):
                continue

        return get_bullying_dashboard(
            reports=reports,
            workplace=workplace,
            period_start=start,
            period_end=end,
        )
    except ValueError as exc:
        frappe.throw(str(exc))


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _require_human_approved_param(value: Any, fn_name: str) -> None:
    if not _coerce_bool(value):
        frappe.throw(
            f"{fn_name}은(는) human_approved=true 파라미터가 필요합니다. "
            f"담당자가 명시적으로 승인한 경우에만 호출하세요."
        )


def _parse_date(value: str, field: str) -> dt.date:
    if not value:
        frappe.throw(f"{field}은(는) 필수 항목입니다 (YYYY-MM-DD 형식)")
    try:
        return dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        frappe.throw(f"{field}은(는) YYYY-MM-DD 형식이어야 합니다, 입력값: {value!r}")


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, TypeError):
            pass
        return [value] if value.strip() else []
    return []
