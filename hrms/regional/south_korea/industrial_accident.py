"""산재 발생 신고 workflow.

법적 근거:
- 산업재해보상보험법 제53조의2 (산재 발생 보고)
- 산업안전보건법 제57조 (중대재해 보고)

보고 기준:
- 요양 4일 이상 사고: 1개월 내 산재 발생 보고서 제출 필수
- 요양 3일 미만 사고: 자체 처리 허용 (신고 의무 없음)
- 사망 사고: 즉시 중대재해보고서 제출 (산안법 §57 준용)

NOTE (v1 scope): 산안법 §57의 '중대재해' 정의는 사망 외에도
3개월 이상 요양이 필요한 부상자 2인 이상 동시 발생,
10인 이상 동시 부상 등을 포함하나, v1에서는 injury_type='사망'만을
즉시 신고 트리거로 처리한다. 향후 v2에서 복수 피해자 기준을 추가할 것.

이 모듈은 프레임워크 독립(framework-free)으로 작성됩니다.
import frappe 금지 — 순수 Python만 사용.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

# ── 상수 ──────────────────────────────────────────────────────────────────────

CONTRACT_TYPE = "korea_industrial_accident_report_v1"

REPORT_TYPES = ["minor", "serious", "fatal"]  # 경상 / 중상 / 사망

# 신고서 양식 종류
FORM_TYPE_ACCIDENT = "산재발생신고서"         # 산안법 §73 서식 (4일 이상 요양)
FORM_TYPE_CRITICAL = "중대재해보고서"         # 산안법 §57 서식 (사망)

# 사망 injury_type 판별 집합 (소문자 정규화)
_FATAL_TYPES: frozenset[str] = frozenset({"사망"})

# PDF 필드 키 목록 (고용노동부 표준 서식)
_PDF_FIELDS = (
    "사업장명",
    "사업장소재지",
    "사업자등록번호",
    "재해자성명",
    "재해발생일시",
    "재해발생장소",
    "재해발생경위",
    "상해종류",
    "상해부위",
    "요양예상일수",
    "목격자",
    "초기치료내용",
    "보고서유형",
    "신고의무여부",
    "신고기한",
)


# ── 공개 함수 ──────────────────────────────────────────────────────────────────

def create_accident_report(
    *,
    employee: str,
    incident_datetime: dt.datetime,
    incident_location: str,
    incident_description: str,
    injury_type: str,        # 자상/낙상/감전/화상/추락/사망 등
    affected_body_part: str,
    expected_treatment_days: int,
    witnesses: list[str] | None,
    initial_treatment: str,
    workplace: str,
    human_approved: bool = False,
) -> dict[str, Any]:
    """산재 발생 보고 생성.

    자동 분류 기준:
    - injury_type == '사망'           → fatal  → 즉시 신고 (중대재해보고서)
    - expected_treatment_days >= 4   → serious → 1개월 내 신고 (산재발생신고서)
    - expected_treatment_days < 4    → minor   → 자체 처리 OK (신고 의무 없음)

    human_approved=True 없이도 보고서 생성은 가능하나,
    실제 제출 (submit_to_workers_compensation_corp)은 human_approved 필수.

    Args:
        employee: 재해 근로자 이름 또는 사번
        incident_datetime: 재해 발생 일시 (datetime, 시각 포함)
        incident_location: 재해 발생 장소
        incident_description: 재해 발생 경위 (상세 기술)
        injury_type: 상해 종류 (자상/낙상/감전/화상/추락/사망 등)
        affected_body_part: 상해 부위 (손/발/머리/척추 등)
        expected_treatment_days: 요양 예상 일수 (0 이상 정수)
        witnesses: 목격자 성명 목록 (없으면 None 또는 빈 리스트)
        initial_treatment: 초기 치료 내용
        workplace: 사업장 이름
        human_approved: 담당자 확인 여부 (제출 게이트)

    Returns:
        {
            "contract_type": "korea_industrial_accident_report_v1",
            "report_type": "minor" | "serious" | "fatal",
            "applies_report_obligation": bool,
            "report_deadline": str | None,  # ISO date (YYYY-MM-DD) 또는 None
            "report_form_type": "산재발생신고서" | "중대재해보고서" | None,
            "report_payload": dict,         # 신고서 양식 필드 채워진 dict
            "human_approved": bool,
        }

    Raises:
        ValueError: 필수 입력값 누락 또는 타입 오류
    """
    _validate_create_inputs(
        employee=employee,
        incident_datetime=incident_datetime,
        incident_location=incident_location,
        incident_description=incident_description,
        injury_type=injury_type,
        affected_body_part=affected_body_part,
        expected_treatment_days=expected_treatment_days,
        initial_treatment=initial_treatment,
        workplace=workplace,
    )

    report_type, applies_obligation, form_type, deadline = _classify(
        injury_type=injury_type,
        expected_treatment_days=expected_treatment_days,
        incident_date=incident_datetime.date(),
    )

    payload = _build_report_payload(
        employee=employee,
        incident_datetime=incident_datetime,
        incident_location=incident_location,
        incident_description=incident_description,
        injury_type=injury_type,
        affected_body_part=affected_body_part,
        expected_treatment_days=expected_treatment_days,
        witnesses=witnesses or [],
        initial_treatment=initial_treatment,
        workplace=workplace,
        form_type=form_type,
        applies_obligation=applies_obligation,
        deadline=deadline,
    )

    return {
        "contract_type": CONTRACT_TYPE,
        "report_type": report_type,
        "applies_report_obligation": applies_obligation,
        "report_deadline": deadline,
        "report_form_type": form_type,
        "report_payload": payload,
        "human_approved": human_approved,
    }


def generate_accident_report_pdf_payload(report: dict[str, Any]) -> dict[str, Any]:
    """산재발생신고서 양식 (고용노동부 표준) PDF용 payload 생성.

    입력: create_accident_report() 반환값
    반환: PDF 렌더링 엔진이 소비하는 flat dict (고용노동부 서식 필드 기준)

    Args:
        report: create_accident_report() 반환 dict

    Returns:
        {
            "pdf_template": "korea_industrial_accident_report",
            "form_type": str,
            "fields": { <고용노동부 서식 필드명>: <값>, ... },
        }

    Raises:
        ValueError: report 구조가 올바르지 않은 경우
    """
    if not isinstance(report, dict):
        raise ValueError("report는 dict여야 합니다.")
    if report.get("contract_type") != CONTRACT_TYPE:
        raise ValueError(f"contract_type이 {CONTRACT_TYPE}이 아닙니다: {report.get('contract_type')}")

    payload = report.get("report_payload")
    if not isinstance(payload, dict):
        raise ValueError("report_payload가 없거나 dict가 아닙니다.")

    form_type = report.get("report_form_type") or FORM_TYPE_ACCIDENT

    fields: dict[str, Any] = {
        "사업장명": payload.get("workplace", ""),
        "사업장소재지": payload.get("incident_location", ""),
        "사업자등록번호": "",            # Frappe _api.py 레이어에서 채움
        "재해자성명": payload.get("employee", ""),
        "재해발생일시": payload.get("incident_datetime", ""),
        "재해발생장소": payload.get("incident_location", ""),
        "재해발생경위": payload.get("incident_description", ""),
        "상해종류": payload.get("injury_type", ""),
        "상해부위": payload.get("affected_body_part", ""),
        "요양예상일수": str(payload.get("expected_treatment_days", 0)),
        "목격자": "없음" if not payload.get("witnesses") else ", ".join(payload["witnesses"]),
        "초기치료내용": payload.get("initial_treatment", ""),
        "보고서유형": form_type,
        "신고의무여부": "예" if report.get("applies_report_obligation") else "아니오",
        "신고기한": report.get("report_deadline") or "해당없음",
    }

    return {
        "pdf_template": "korea_industrial_accident_report",
        "form_type": form_type,
        "fields": fields,
    }


def submit_to_workers_compensation_corp(
    *,
    report: dict[str, Any],
    human_approved: bool,
    dry_run: bool = True,
) -> dict[str, Any]:
    """근로복지공단 산재 신고서 제출.

    v1은 dry_run 모드만 지원. 실제 공단 API 연동은 v2 예정.
    실제 API endpoint 미구현 — v1은 dry_run=True 기준으로 보고서 생성 및
    제출 준비 상태 확인만 수행.

    human_approved=False이면 dry_run 여부와 관계없이 거부됩니다.
    제출 자체가 돌이킬 수 없는 변경(mutation)이기 때문입니다.

    Args:
        report: create_accident_report() 반환 dict
        human_approved: 담당자 최종 승인 여부 (False면 즉시 거부)
        dry_run: True(기본값)이면 실제 공단 API 미호출 (시뮬레이션)

    Returns:
        {
            "status": "dry_run" | "submitted" | "refused",
            "reason": str,
            "report_id": str | None,
            "submitted_at": str | None,   # ISO datetime
            "payload_sent": dict | None,
        }

    Raises:
        ValueError: report 구조가 올바르지 않은 경우
        PermissionError: human_approved=False
    """
    if not human_approved:
        raise PermissionError(
            "산재 신고는 담당자 승인(human_approved=True)이 필요합니다. "
            "보고서를 검토하고 human_approved=True로 재호출하세요."
        )

    if not isinstance(report, dict):
        raise ValueError("report는 dict여야 합니다.")
    if report.get("contract_type") != CONTRACT_TYPE:
        raise ValueError(f"contract_type이 {CONTRACT_TYPE}이 아닙니다.")

    if not report.get("applies_report_obligation"):
        return {
            "status": "refused",
            "reason": "신고 의무 없음 (요양 3일 미만). 자체 처리 가능합니다.",
            "report_id": None,
            "submitted_at": None,
            "payload_sent": None,
        }

    pdf_payload = generate_accident_report_pdf_payload(report)

    if dry_run:
        return {
            "status": "dry_run",
            "reason": "dry_run=True: 실제 공단 API 미호출. v2에서 실제 제출 구현 예정.",
            "report_id": None,
            "submitted_at": None,
            "payload_sent": pdf_payload,
        }

    # v1: 실제 공단 API 미구현
    # v2 구현 시 여기에 근로복지공단 REST API 호출 코드 삽입
    raise NotImplementedError(
        "근로복지공단 API 실제 연결은 v2에서 구현 예정입니다. "
        "현재는 dry_run=True만 지원합니다."
    )


def list_pending_reports(
    *,
    workplace: str,
    as_of_date: dt.date,
    reports: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """신고 마감일 임박 또는 미제출 산재 보고 목록 반환.

    프레임워크 독립 버전 — DB 조회 없이 입력 리스트를 필터링합니다.
    Frappe DB 연동이 필요한 경우 _api.py 의 list_pending_reports_api()를 사용하세요.

    Args:
        workplace: 사업장 이름 필터
        as_of_date: 기준일 (마감일 임박 판단 기준)
        reports: create_accident_report() 반환값의 리스트

    Returns:
        마감일이 as_of_date 이후이거나 미제출인 보고서 목록.
        각 항목에 'days_until_deadline' 키를 추가하여 반환.
    """
    result = []
    for r in reports:
        if not isinstance(r, dict):
            continue
        r_payload = r.get("report_payload") or {}
        if r_payload.get("workplace") != workplace:
            continue
        if not r.get("applies_report_obligation"):
            continue

        deadline_str = r.get("report_deadline")
        if not deadline_str:
            continue

        try:
            deadline = dt.date.fromisoformat(deadline_str)
        except (ValueError, TypeError):
            continue

        days_until = (deadline - as_of_date).days
        entry = dict(r)
        entry["days_until_deadline"] = days_until
        entry["overdue"] = days_until < 0
        result.append(entry)

    # 마감일 임박순 정렬
    result.sort(key=lambda x: x.get("report_deadline", ""))
    return result


# ── 내부 함수 ──────────────────────────────────────────────────────────────────

def _classify(
    *,
    injury_type: str,
    expected_treatment_days: int,
    incident_date: dt.date,
) -> tuple[str, bool, str | None, str | None]:
    """보고 유형, 신고 의무 여부, 양식 유형, 마감일 결정.

    Returns:
        (report_type, applies_obligation, form_type, deadline_iso)
    """
    normalized_injury = injury_type.strip()

    # 사망 → 즉시 신고 (중대재해보고서)
    if normalized_injury in _FATAL_TYPES:
        deadline = incident_date.isoformat()
        return "fatal", True, FORM_TYPE_CRITICAL, deadline

    # 4일 이상 요양 → 1개월 내 신고 (산재발생신고서)
    if expected_treatment_days >= 4:
        # 1개월 후 = 익월 동일 일자 (월말 경계는 달력 기준)
        deadline = _add_one_month(incident_date)
        return "serious", True, FORM_TYPE_ACCIDENT, deadline.isoformat()

    # 3일 미만 → 자체 처리 OK
    return "minor", False, None, None


def _add_one_month(base: dt.date) -> dt.date:
    """기준일로부터 1개월 후 날짜 계산.

    월말 경계 처리: 1월 31일 + 1개월 = 2월 28일(29일).
    """
    month = base.month + 1
    year = base.year
    if month > 12:
        month = 1
        year += 1
    # 해당 월의 마지막 날 초과 방지
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    day = min(base.day, last_day)
    return dt.date(year, month, day)


def _build_report_payload(
    *,
    employee: str,
    incident_datetime: dt.datetime,
    incident_location: str,
    incident_description: str,
    injury_type: str,
    affected_body_part: str,
    expected_treatment_days: int,
    witnesses: list[str],
    initial_treatment: str,
    workplace: str,
    form_type: str | None,
    applies_obligation: bool,
    deadline: str | None,
) -> dict[str, Any]:
    """신고서 payload dict 구성."""
    return {
        "employee": employee,
        "incident_datetime": incident_datetime.isoformat(sep=" "),
        "incident_location": incident_location,
        "incident_description": incident_description,
        "injury_type": injury_type,
        "affected_body_part": affected_body_part,
        "expected_treatment_days": expected_treatment_days,
        "witnesses": witnesses,
        "initial_treatment": initial_treatment,
        "workplace": workplace,
        "form_type": form_type,
        "applies_report_obligation": applies_obligation,
        "report_deadline": deadline,
    }


def _validate_create_inputs(
    *,
    employee: str,
    incident_datetime: dt.datetime,
    incident_location: str,
    incident_description: str,
    injury_type: str,
    affected_body_part: str,
    expected_treatment_days: int,
    initial_treatment: str,
    workplace: str,
) -> None:
    """필수 입력값 검증."""
    if not isinstance(employee, str) or not employee.strip():
        raise ValueError("employee는 비어있지 않은 문자열이어야 합니다.")
    if not isinstance(incident_datetime, dt.datetime):
        raise ValueError("incident_datetime은 datetime.datetime 타입이어야 합니다.")
    if not isinstance(incident_location, str) or not incident_location.strip():
        raise ValueError("incident_location은 비어있지 않은 문자열이어야 합니다.")
    if not isinstance(incident_description, str) or not incident_description.strip():
        raise ValueError("incident_description은 비어있지 않은 문자열이어야 합니다.")
    if not isinstance(injury_type, str) or not injury_type.strip():
        raise ValueError("injury_type은 비어있지 않은 문자열이어야 합니다.")
    if not isinstance(affected_body_part, str) or not affected_body_part.strip():
        raise ValueError("affected_body_part는 비어있지 않은 문자열이어야 합니다.")
    if not isinstance(expected_treatment_days, int) or expected_treatment_days < 0:
        raise ValueError("expected_treatment_days는 0 이상의 정수여야 합니다.")
    if not isinstance(initial_treatment, str) or not initial_treatment.strip():
        raise ValueError("initial_treatment는 비어있지 않은 문자열이어야 합니다.")
    if not isinstance(workplace, str) or not workplace.strip():
        raise ValueError("workplace는 비어있지 않은 문자열이어야 합니다.")
