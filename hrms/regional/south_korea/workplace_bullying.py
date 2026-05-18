"""직장 내 괴롭힘 신고/조사/조치 워크플로우 코어.

법적 근거:
- 근로기준법 76조의2: 직장 내 괴롭힘 정의
- 근로기준법 76조의3: 사용자 조치 의무 (조사/피해자보호/가해자징계/비밀유지)
- 산업안전보건법 41조의2: 고객 폭언 등에 대한 조치

이 모듈은 framework-free 코어입니다. frappe를 import하지 않습니다.
외부 의존성 없음 — 단위 테스트는 별도 setup 없이 실행 가능합니다.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from typing import Any

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

REPORT_STATUS = ["received", "investigating", "concluded", "closed"]

# 상태 전이 규칙: {current_status: allowed_next_statuses}
_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "received": {"investigating"},
    "investigating": {"concluded"},
    "concluded": {"closed"},
    "closed": set(),
}

ACTION_TYPES = [
    "isolation",     # 분리 조치
    "warning",       # 경고
    "reprimand",     # 견책
    "suspension",    # 정직
    "dismissal",     # 해고
    "no_action",     # 조치 없음
]

FINDING_TYPES = {"confirmed", "unconfirmed", "not_workplace_bullying"}

# 조사관 역할 — 이 역할만 신원 정보 접근 가능 (76조의3 4항)
_PRIVILEGED_ROLES = {"investigator_assigned", "hr_admin"}

# PII 필드: 보고서에서 일반 조회자에게 노출하면 안 되는 필드
_REPORT_PII_FIELDS = {"reporter_name", "reporter_contact", "reporter_hash"}


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


def create_bullying_report(
    *,
    reporter_anonymous: bool,
    reporter_name: str | None,
    reporter_contact: str | None,
    incident_date: dt.date,
    incident_location: str,
    incident_description: str,
    alleged_perpetrator: str | None = None,
    witnesses: list[str] | None = None,
    evidence_attachments: list[str] | None = None,
    workplace: str,
    human_approved: bool = False,  # 신고 접수는 immediate — 피해자 보호 원칙
) -> dict[str, Any]:
    """신고 접수 (근기법 76조의3 1항).

    - reporter_anonymous=True이면 reporter_name/contact를 해시로만 저장.
    - 비밀유지 원칙 (76조의3 4항) — 식별 정보는 최소화.
    - 신고 접수 자체는 human_approved 없이 즉시 처리 (피해자 보호 우선).
    - 반환: 생성된 report dict (report_id 포함).
    """
    _require_str(incident_location, "incident_location")
    _require_str(incident_description, "incident_description")
    _require_str(workplace, "workplace")
    if not isinstance(incident_date, dt.date):
        raise ValueError("incident_date must be a datetime.date instance")

    report_id = _new_report_id()
    now = _now_iso()

    if reporter_anonymous:
        reporter_hash = _hash_identity(reporter_name, reporter_contact)
        stored_name = None
        stored_contact = None
    else:
        reporter_hash = None
        stored_name = reporter_name
        stored_contact = reporter_contact

    report: dict[str, Any] = {
        "report_id": report_id,
        "status": "received",
        "workplace": workplace,
        # 신고자 정보 (비밀유지)
        "reporter_anonymous": reporter_anonymous,
        "reporter_name": stored_name,
        "reporter_contact": stored_contact,
        "reporter_hash": reporter_hash,
        # 사건 정보
        "incident_date": incident_date.isoformat(),
        "incident_location": incident_location,
        "incident_description": incident_description,
        "alleged_perpetrator": alleged_perpetrator,
        "witnesses": list(witnesses) if witnesses else [],
        "evidence_attachments": list(evidence_attachments) if evidence_attachments else [],
        # 조사/조치 정보 (초기값)
        "investigator": None,
        "investigator_assigned_at": None,
        "finding": None,
        "investigation_notes": None,
        "recommended_actions": [],
        "finding_submitted_at": None,
        "protective_actions": [],
        # 감사 로그 (76조의3 2항, 4항)
        "audit_log": [
            _audit_entry(
                action="report_received",
                actor="system",
                timestamp=now,
                details={
                    "anonymous": reporter_anonymous,
                    "workplace": workplace,
                    "incident_date": incident_date.isoformat(),
                },
            )
        ],
        "created_at": now,
        "updated_at": now,
    }
    return report


def assign_investigator(
    *,
    report: dict[str, Any],
    investigator: str,
    decided_by: str,
    human_approved: bool,
) -> dict[str, Any]:
    """조사관 지정 (근기법 76조의3 3항).

    - human_approved=True 필수.
    - status: "received" → "investigating".
    - 반환: 업데이트된 report dict (원본 변경 X — 복사본 반환).
    """
    _require_human_approved(human_approved, "assign_investigator")
    _require_str(investigator, "investigator")
    _require_str(decided_by, "decided_by")
    _validate_report(report)
    _assert_status(report, "received", "assign_investigator")

    now = _now_iso()
    updated = _copy_report(report)
    updated["investigator"] = investigator
    updated["investigator_assigned_at"] = now
    updated["status"] = "investigating"
    updated["updated_at"] = now
    updated["audit_log"].append(
        _audit_entry(
            action="investigator_assigned",
            actor=decided_by,
            timestamp=now,
            details={"investigator": investigator},
        )
    )
    return updated


def submit_investigation_finding(
    *,
    report: dict[str, Any],
    investigator: str,
    finding: str,
    investigation_notes: str,
    recommended_actions: list[str],
    decided_by: str,
    human_approved: bool,
) -> dict[str, Any]:
    """조사 결과 제출 (근기법 76조의3 2항).

    - human_approved=True 필수.
    - status: "investigating" → "concluded".
    - finding: "confirmed" | "unconfirmed" | "not_workplace_bullying".
    - 반환: 업데이트된 report dict.
    """
    _require_human_approved(human_approved, "submit_investigation_finding")
    _require_str(investigator, "investigator")
    _require_str(investigation_notes, "investigation_notes")
    _validate_report(report)
    _assert_status(report, "investigating", "submit_investigation_finding")

    if finding not in FINDING_TYPES:
        raise ValueError(
            f"finding must be one of {sorted(FINDING_TYPES)}, got: {finding!r}"
        )
    if not isinstance(recommended_actions, list):
        raise ValueError("recommended_actions must be a list")

    # 담당 조사관 일치 여부 확인 (비밀유지 + 조사 무결성)
    _assert_is_assigned_investigator(report, investigator)

    now = _now_iso()
    updated = _copy_report(report)
    updated["finding"] = finding
    updated["investigation_notes"] = investigation_notes
    updated["recommended_actions"] = list(recommended_actions)
    updated["finding_submitted_at"] = now
    updated["status"] = "concluded"
    updated["updated_at"] = now
    updated["audit_log"].append(
        _audit_entry(
            action="finding_submitted",
            actor=decided_by,
            timestamp=now,
            details={
                "investigator": investigator,
                "finding": finding,
                "recommended_actions": list(recommended_actions),
            },
        )
    )
    return updated


def apply_protective_action(
    *,
    report: dict[str, Any],
    action_type: str,
    target_employee: str,
    action_description: str,
    decided_by: str,
    human_approved: bool,
) -> dict[str, Any]:
    """조치 적용 (근기법 76조의3 1항 피해자 보호 / 2항 가해자 조치).

    - human_approved=True 필수.
    - status: "concluded" 또는 "investigating"에서 가능.
    - "confirmed" 이외의 finding인 경우 가해자 대상 징계·해고 불가.
    - audit log에 기록.
    - 반환: 업데이트된 report dict.
    """
    _require_human_approved(human_approved, "apply_protective_action")
    _require_str(target_employee, "target_employee")
    _require_str(action_description, "action_description")
    _require_str(decided_by, "decided_by")
    _validate_report(report)

    status = report.get("status")
    if status not in {"investigating", "concluded"}:
        raise ValueError(
            f"apply_protective_action requires status 'investigating' or 'concluded', "
            f"current status: {status!r}"
        )

    if action_type not in ACTION_TYPES:
        raise ValueError(
            f"action_type must be one of {ACTION_TYPES}, got: {action_type!r}"
        )

    # 가해자 대상 징계/해고는 "confirmed" 판정 이후에만 가능 (근기법 76조의3 2항)
    _assert_perpetrator_action_allowed(report, action_type, target_employee)

    now = _now_iso()
    action_record: dict[str, Any] = {
        "action_type": action_type,
        "target_employee": target_employee,
        "action_description": action_description,
        "decided_by": decided_by,
        "applied_at": now,
    }

    updated = _copy_report(report)
    updated["protective_actions"].append(action_record)
    updated["updated_at"] = now
    updated["audit_log"].append(
        _audit_entry(
            action="protective_action_applied",
            actor=decided_by,
            timestamp=now,
            details=action_record,
        )
    )
    return updated


def get_bullying_dashboard(
    *,
    reports: list[dict[str, Any]],
    workplace: str,
    period_start: dt.date,
    period_end: dt.date,
) -> dict[str, Any]:
    """관리자 대시보드 집계 데이터.

    - 개인 식별 정보 없음 — 집계만 반환.
    - 신고 건수 / status별 분포 / 평균 처리 기간 / 조치 유형 통계.
    - 근기법 76조의3 4항 비밀유지: report_id / 신원 정보 미포함.
    """
    if not isinstance(period_start, dt.date) or not isinstance(period_end, dt.date):
        raise ValueError("period_start and period_end must be datetime.date instances")
    if period_start > period_end:
        raise ValueError("period_start must be <= period_end")
    _require_str(workplace, "workplace")

    filtered = [
        r for r in reports
        if r.get("workplace") == workplace
        and _date_in_range(r.get("created_at", ""), period_start, period_end)
    ]

    total = len(filtered)
    status_counts: dict[str, int] = {s: 0 for s in REPORT_STATUS}
    finding_counts: dict[str, int] = {}
    action_type_counts: dict[str, int] = {}
    resolution_days: list[float] = []

    for r in filtered:
        status = r.get("status", "received")
        status_counts[status] = status_counts.get(status, 0) + 1

        finding = r.get("finding")
        if finding:
            finding_counts[finding] = finding_counts.get(finding, 0) + 1

        for action in r.get("protective_actions", []):
            at = action.get("action_type", "unknown")
            action_type_counts[at] = action_type_counts.get(at, 0) + 1

        # 평균 처리 기간: created_at → finding_submitted_at (결론 날짜)
        if r.get("finding_submitted_at") and r.get("created_at"):
            try:
                created = dt.datetime.fromisoformat(r["created_at"])
                concluded = dt.datetime.fromisoformat(r["finding_submitted_at"])
                days = (concluded - created).total_seconds() / 86400
                resolution_days.append(days)
            except (ValueError, TypeError):
                pass

    avg_resolution_days = (
        round(sum(resolution_days) / len(resolution_days), 1)
        if resolution_days
        else None
    )

    return {
        "workplace": workplace,
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
        },
        "total_reports": total,
        "status_distribution": status_counts,
        "finding_distribution": finding_counts,
        "action_type_distribution": action_type_counts,
        "avg_resolution_days": avg_resolution_days,
    }


def redact_report_for_viewer(
    report: dict[str, Any],
    viewer_role: str,
    viewer_id: str | None = None,
) -> dict[str, Any]:
    """비밀유지 원칙에 따른 PII 마스킹 (근기법 76조의3 4항).

    조사관(investigator_assigned)이고 viewer_id가 지정 조사관과 일치하는 경우,
    또는 hr_admin인 경우에만 reporter_name / reporter_contact 접근 허용.
    그 외에는 PII 필드를 마스킹.
    """
    _validate_report(report)

    is_privileged = viewer_role in _PRIVILEGED_ROLES
    if viewer_role == "investigator_assigned":
        # 지정된 조사관과 viewer_id가 일치하는지 추가 확인
        assigned = report.get("investigator")
        is_privileged = bool(assigned and viewer_id and assigned == viewer_id)

    redacted = _copy_report(report)
    if not is_privileged:
        for field in _REPORT_PII_FIELDS:
            if field in redacted:
                redacted[field] = "[REDACTED]"

    return redacted


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _require_human_approved(human_approved: bool, fn_name: str) -> None:
    if not human_approved:
        raise ValueError(
            f"{fn_name} requires human_approved=True "
            f"(근기법 76조의3 — 사용자 조치 의무는 담당자 승인 필요)"
        )


def _require_str(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _validate_report(report: Any) -> None:
    if not isinstance(report, dict):
        raise ValueError("report must be a dict")
    if "report_id" not in report:
        raise ValueError("report must contain 'report_id'")
    if "status" not in report:
        raise ValueError("report must contain 'status'")


def _assert_status(report: dict[str, Any], expected: str, fn_name: str) -> None:
    current = report.get("status")
    if current != expected:
        raise ValueError(
            f"{fn_name} requires status={expected!r}, current status={current!r}"
        )


def _assert_is_assigned_investigator(report: dict[str, Any], investigator: str) -> None:
    """조사 결과 제출 시 지정된 조사관인지 확인 (조사 무결성 + 비밀유지)."""
    assigned = report.get("investigator")
    if assigned and assigned != investigator:
        raise ValueError(
            f"비밀유지 위반: investigator {investigator!r}는 이 신고의 지정 조사관이 아닙니다 "
            f"(지정: {assigned!r}). 근기법 76조의3 4항."
        )


def _assert_perpetrator_action_allowed(
    report: dict[str, Any],
    action_type: str,
    target_employee: str,
) -> None:
    """가해자 대상 징계성 조치는 'confirmed' finding 이후에만 허용 (근기법 76조의3 2항).

    단, no_action / isolation / warning은 조사 중이라도 피해자 보호 목적으로 가능.
    징계 강도가 높은 조치(suspension, dismissal, reprimand)는 confirmed 이후에만.
    """
    punitive_actions = {"suspension", "dismissal", "reprimand"}
    if action_type not in punitive_actions:
        return

    finding = report.get("finding")
    if finding != "confirmed":
        raise ValueError(
            f"징계성 조치({action_type})는 조사 결과 'confirmed' 판정 이후에만 가능합니다. "
            f"현재 finding: {finding!r}. 근기법 76조의3 2항."
        )


def _hash_identity(name: str | None, contact: str | None) -> str:
    """익명 신고자 식별을 위한 SHA-256 해시 (추후 신고 중복 탐지용).

    원본 데이터는 저장하지 않습니다 (76조의3 4항 비밀유지).
    """
    raw = f"{name or ''}|{contact or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_report_id() -> str:
    return "BR-" + uuid.uuid4().hex[:12].upper()


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _audit_entry(
    *,
    action: str,
    actor: str,
    timestamp: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "action": action,
        "actor": actor,
        "timestamp": timestamp,
        "details": details,
    }


def _copy_report(report: dict[str, Any]) -> dict[str, Any]:
    """보고서 딕셔너리의 얕은 복사 (리스트 필드는 새 리스트로)."""
    copied = dict(report)
    copied["audit_log"] = list(report.get("audit_log", []))
    copied["witnesses"] = list(report.get("witnesses", []))
    copied["evidence_attachments"] = list(report.get("evidence_attachments", []))
    copied["recommended_actions"] = list(report.get("recommended_actions", []))
    copied["protective_actions"] = list(report.get("protective_actions", []))
    return copied


def _date_in_range(iso_ts: str, start: dt.date, end: dt.date) -> bool:
    """ISO timestamp 문자열이 [start, end] 기간 안에 있는지 확인."""
    try:
        parsed = dt.datetime.fromisoformat(iso_ts).date()
        return start <= parsed <= end
    except (ValueError, TypeError):
        return False
