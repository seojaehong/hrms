"""Frappe API 래퍼 — 산재 발생 신고 workflow.

이 모듈은 Frappe 의존성을 가지는 얇은 API 레이어입니다.
순수 로직은 hrms/regional/south_korea/industrial_accident.py에 위치합니다.

제공 엔드포인트:
- create_accident_report_api: 산재 보고서 생성 (Frappe 컨텍스트 포함)
- generate_pdf_payload_api: PDF payload 생성
- submit_to_workers_compensation_corp_api: 근로복지공단 제출 (human_approved 게이트)
- list_pending_reports_api: 미제출 산재 보고 목록 (DB 조회 포함)
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import frappe

from hrms.regional.south_korea.industrial_accident import (
    CONTRACT_TYPE,
    create_accident_report,
    generate_accident_report_pdf_payload,
    list_pending_reports,
    submit_to_workers_compensation_corp,
)

# PII 차단 필드 — 산재 신고서 API에서 입력 거부
_BLOCKED_PII_FIELDS = {
    "resident_registration_number",
    "foreigner_registration_number",
    "bank_account_number",
}


@frappe.whitelist()
def create_accident_report_api(payload: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
    """산재 발생 보고서 생성 API.

    Frappe whitelist 엔드포인트. 입력 검증 후 industrial_accident.create_accident_report() 호출.

    Args (payload 또는 kwargs로 전달):
        employee (str): 재해 근로자 이름 또는 사번
        incident_datetime (str): 재해 발생 일시 (ISO format: YYYY-MM-DD HH:MM:SS)
        incident_location (str): 재해 발생 장소
        incident_description (str): 재해 발생 경위
        injury_type (str): 상해 종류
        affected_body_part (str): 상해 부위
        expected_treatment_days (int): 요양 예상 일수
        witnesses (list[str]): 목격자 목록 (선택)
        initial_treatment (str): 초기 치료 내용
        workplace (str): 사업장 이름
        human_approved (bool): 담당자 확인 여부 (기본값: False)

    Returns:
        create_accident_report() 반환값 + Frappe 컨텍스트 필드
    """
    payload = _coerce_payload(payload, kwargs)
    _ensure_no_pii(payload)

    _require_keys(
        payload,
        {
            "employee",
            "incident_datetime",
            "incident_location",
            "incident_description",
            "injury_type",
            "affected_body_part",
            "expected_treatment_days",
            "initial_treatment",
            "workplace",
        },
        "payload",
    )
    _reject_unknown_keys(
        payload,
        {
            "employee",
            "incident_datetime",
            "incident_location",
            "incident_description",
            "injury_type",
            "affected_body_part",
            "expected_treatment_days",
            "witnesses",
            "initial_treatment",
            "workplace",
            "human_approved",
        },
        "payload",
    )

    incident_datetime = _parse_datetime(payload["incident_datetime"])
    expected_treatment_days = _as_int(payload["expected_treatment_days"], "expected_treatment_days")
    witnesses = _coerce_list(payload.get("witnesses"))
    human_approved = _coerce_bool(payload.get("human_approved", False))

    report = create_accident_report(
        employee=payload["employee"],
        incident_datetime=incident_datetime,
        incident_location=payload["incident_location"],
        incident_description=payload["incident_description"],
        injury_type=payload["injury_type"],
        affected_body_part=payload["affected_body_part"],
        expected_treatment_days=expected_treatment_days,
        witnesses=witnesses,
        initial_treatment=payload["initial_treatment"],
        workplace=payload["workplace"],
        human_approved=human_approved,
    )

    # Frappe 감사 로그 (PII 미포함)
    _log_accident_report_created(report)

    return report


@frappe.whitelist()
def generate_pdf_payload_api(payload: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
    """산재발생신고서 PDF payload 생성 API.

    Args (payload 또는 kwargs):
        report (dict): create_accident_report() 또는 create_accident_report_api() 반환값

    Returns:
        generate_accident_report_pdf_payload() 반환값
    """
    payload = _coerce_payload(payload, kwargs)
    report = payload.get("report")
    if not isinstance(report, dict):
        frappe.throw("report 필드가 필요합니다 (create_accident_report_api 반환값).")

    try:
        return generate_accident_report_pdf_payload(report)
    except ValueError as e:
        frappe.throw(str(e))


@frappe.whitelist()
def submit_to_workers_compensation_corp_api(
    payload: dict[str, Any] | None = None, **kwargs
) -> dict[str, Any]:
    """근로복지공단 산재 신고서 제출 API.

    mutation 게이트: human_approved=True 필수.
    v1에서는 dry_run=True(기본값)만 실제 동작 지원.

    Args (payload 또는 kwargs):
        report (dict): create_accident_report_api() 반환값
        human_approved (bool): 담당자 최종 승인 (True 필수)
        dry_run (bool): 실제 공단 API 미호출 여부 (기본값: True)

    Returns:
        submit_to_workers_compensation_corp() 반환값
    """
    payload = _coerce_payload(payload, kwargs)
    _reject_unknown_keys(payload, {"report", "human_approved", "dry_run"}, "payload")

    report = payload.get("report")
    if not isinstance(report, dict):
        frappe.throw("report 필드가 필요합니다.")

    human_approved = _coerce_bool(payload.get("human_approved", False))
    dry_run = _coerce_bool(payload.get("dry_run", True))

    try:
        result = submit_to_workers_compensation_corp(
            report=report,
            human_approved=human_approved,
            dry_run=dry_run,
        )
    except PermissionError as e:
        frappe.throw(str(e))
    except ValueError as e:
        frappe.throw(str(e))
    except NotImplementedError as e:
        frappe.throw(str(e))

    # 제출 성공 시 Comment 기록
    if result.get("status") in ("submitted", "dry_run") and human_approved:
        _log_submission_attempt(report, result)

    return result


@frappe.whitelist()
def list_pending_reports_api(
    payload: dict[str, Any] | None = None, **kwargs
) -> list[dict[str, Any]]:
    """신고 마감일 임박 또는 미제출 산재 보고 목록 API.

    DB에서 보고서 목록을 읽어 오거나, 직접 보고서 리스트를 제공할 수 있습니다.

    Args (payload 또는 kwargs):
        workplace (str): 사업장 이름
        as_of_date (str): 기준일 (YYYY-MM-DD, 기본값: 오늘)
        reports (list[dict]): 필터링할 보고서 목록 (제공 시 DB 조회 생략)

    Returns:
        list_pending_reports() 반환값 (days_until_deadline 포함)
    """
    payload = _coerce_payload(payload, kwargs)
    _require_keys(payload, {"workplace"}, "payload")
    _reject_unknown_keys(payload, {"workplace", "as_of_date", "reports"}, "payload")

    workplace = payload["workplace"]
    as_of_str = payload.get("as_of_date")
    if as_of_str:
        try:
            as_of_date = dt.date.fromisoformat(str(as_of_str))
        except ValueError:
            frappe.throw("as_of_date는 YYYY-MM-DD 형식이어야 합니다.")
    else:
        as_of_date = dt.date.today()

    reports = payload.get("reports") or []
    if not isinstance(reports, list):
        frappe.throw("reports는 리스트여야 합니다.")

    return list_pending_reports(
        workplace=workplace,
        as_of_date=as_of_date,
        reports=reports,
    )


# ── 내부 헬퍼 ──────────────────────────────────────────────────────────────────

def _coerce_payload(payload: dict[str, Any] | None, kwargs: dict[str, Any]) -> dict[str, Any]:
    """payload 또는 kwargs를 dict로 정규화."""
    if payload is not None:
        return payload
    if kwargs:
        return kwargs
    if getattr(frappe, "local", None) and getattr(frappe.local, "form_dict", None):
        form_dict = dict(frappe.local.form_dict)
        if len(form_dict) == 1 and "payload" in form_dict and isinstance(form_dict["payload"], str):
            return json.loads(form_dict["payload"])
        return form_dict
    return {}


def _ensure_no_pii(payload: Any) -> None:
    """PII 차단 필드 포함 여부 검사."""
    if isinstance(payload, dict):
        blocked = set(payload) & _BLOCKED_PII_FIELDS
        if blocked:
            frappe.throw(f"PII 필드는 허용되지 않습니다: {', '.join(sorted(blocked))}")
        for value in payload.values():
            _ensure_no_pii(value)
    elif isinstance(payload, list):
        for item in payload:
            _ensure_no_pii(item)


def _require_keys(payload: Any, required_keys: set[str], label: str) -> None:
    """필수 키 존재 여부 검사."""
    if not isinstance(payload, dict):
        frappe.throw(f"{label}는 object여야 합니다.")
    missing = [k for k in sorted(required_keys) if k not in payload or payload.get(k) in (None, "")]
    if missing:
        frappe.throw(f"{label}에 필수 필드가 없습니다: {', '.join(missing)}")


def _reject_unknown_keys(payload: Any, allowed_keys: set[str], label: str) -> None:
    """허용되지 않은 키 포함 여부 검사."""
    if not isinstance(payload, dict):
        frappe.throw(f"{label}는 object여야 합니다.")
    unknown = sorted(set(payload) - allowed_keys)
    if unknown:
        frappe.throw(f"{label}에 지원되지 않는 필드가 있습니다: {', '.join(unknown)}")


def _parse_datetime(value: Any) -> dt.datetime:
    """문자열 또는 datetime을 datetime으로 변환."""
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return dt.datetime.strptime(value, fmt)
            except ValueError:
                continue
    frappe.throw(f"incident_datetime 형식 오류: {value!r} — YYYY-MM-DD HH:MM:SS 형식 필요")
    raise RuntimeError("frappe.throw가 예기치 않게 반환됨")


def _as_int(value: Any, label: str) -> int:
    """정수로 변환."""
    try:
        result = int(value)
        if result < 0:
            raise ValueError
        return result
    except (TypeError, ValueError):
        frappe.throw(f"{label}는 0 이상의 정수여야 합니다: {value!r}")
        raise RuntimeError("frappe.throw가 예기치 않게 반환됨")


def _coerce_bool(value: Any) -> bool:
    """bool로 변환."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _coerce_list(value: Any) -> list[str]:
    """리스트 또는 JSON 문자열을 list[str]로 변환."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                return [str(item) for item in parsed] if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                pass
        # 쉼표 구분 문자열로 처리
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return []


def _log_accident_report_created(report: dict[str, Any]) -> None:
    """산재 보고서 생성 감사 로그 (Frappe Comment — PII 미포함)."""
    if not getattr(frappe, "log_error", None):
        return
    try:
        payload = report.get("report_payload") or {}
        content = (
            f"[산재신고] 보고서 생성: "
            f"workplace={payload.get('workplace')}, "
            f"report_type={report.get('report_type')}, "
            f"applies_obligation={report.get('applies_report_obligation')}, "
            f"deadline={report.get('report_deadline')}"
        )
        # Frappe 감사 로그가 있을 경우 사용; 없으면 무시
        if hasattr(frappe, "get_doc"):
            comment = {
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Employee",
                "reference_name": payload.get("employee", "unknown"),
                "content": content,
            }
            frappe.get_doc(comment).insert(ignore_permissions=True)
    except Exception:
        if getattr(frappe, "log_error", None):
            frappe.log_error("산재 보고서 생성 감사 로그 기록 실패")


def _log_submission_attempt(report: dict[str, Any], result: dict[str, Any]) -> None:
    """공단 제출 시도 감사 로그 (Frappe Comment — PII 미포함)."""
    try:
        payload = report.get("report_payload") or {}
        content = (
            f"[산재신고] 제출 시도: "
            f"status={result.get('status')}, "
            f"workplace={payload.get('workplace')}, "
            f"report_type={report.get('report_type')}"
        )
        if hasattr(frappe, "get_doc"):
            comment = {
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Employee",
                "reference_name": payload.get("employee", "unknown"),
                "content": content,
            }
            frappe.get_doc(comment).insert(ignore_permissions=True)
    except Exception:
        if getattr(frappe, "log_error", None):
            frappe.log_error("산재 제출 감사 로그 기록 실패")
