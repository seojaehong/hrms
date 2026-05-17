"""한국 노무 컴플라이언스 개선 액션 플랜 생성.

run_full_compliance_diagnosis 결과 → actionable action plan.

설계 원칙:
- read-only 변환: 진단 결과를 액션 플랜으로 변환. DB mutation 없음.
- AI 점수/확률 출력 없음.
- 외부 LLM API 사용 없음: 규칙 기반 변환만.
- human_approved 확인 필요: 액션 플랜은 admin + human confirm 후 활성화.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 카테고리별 기본 액션 템플릿
_ACTION_TEMPLATES: dict[str, dict[str, Any]] = {
    "social_insurance": {
        "category_label": "4대보험 가입",
        "assignee_role": "HR Manager",
        "estimated_effort_hours": 4,
        "default_action": "4대보험 취득 신고: 미가입 직원에 대해 즉시 공단 신고 진행 (국민건강보험공단 / 근로복지공단)",
    },
    "wage_delay": {
        "category_label": "임금 정기 지급",
        "assignee_role": "Payroll Manager",
        "estimated_effort_hours": 2,
        "default_action": "정기 지급일 준수 체계 점검: 급여 처리 일정을 재조정하고 부득이한 사유 발생 시 근로자 사전 동의서 확보",
    },
    "overtime_limit": {
        "category_label": "주 12h 연장근로 한도",
        "assignee_role": "Department Manager",
        "estimated_effort_hours": 3,
        "default_action": "연장근로 초과 직원 근무 일정 재조정: 업무 분산 또는 인력 추가 투입 검토 후 가산수당 지급 정확성 확인",
    },
    "annual_leave_usage": {
        "category_label": "연차 사용 촉진",
        "assignee_role": "HR Manager",
        "estimated_effort_hours": 2,
        "default_action": "연차 사용 촉진 통보 실시 (근기법 61조): 미사용 연차 비율이 높은 직원에게 서면 통보 및 사용 계획서 제출 요청",
    },
    "anti_bullying_policy": {
        "category_label": "직장 내 괴롭힘 예방",
        "assignee_role": "HR Manager",
        "estimated_effort_hours": 8,
        "default_action": "직장 내 괴롭힘 예방 정책 등록: 취업규칙 개정, 신고채널 지정, 정책 문서 시스템 등록 진행",
    },
}

_SEVERITY_DEADLINE_DAYS: dict[str, int] = {
    "high": 7,
    "medium": 14,
    "low": 30,
}


def generate_action_plan(
    *,
    diagnosis_result: dict[str, Any],
    company: str,
    deadline_days: int = 30,
) -> dict[str, Any]:
    """발견 사항 → actionable action plan.

    Args:
        diagnosis_result: run_full_compliance_diagnosis 반환값.
        company: 회사명.
        deadline_days: 기본 완료 기한 (일수). 심각도에 따라 개별 항목은 단축될 수 있음.

    Returns::
        {
            "contract_type": "korea_compliance_action_plan_v1",
            "company": str,
            "as_of_date": str,
            "deadline_date": str,
            "overall_status": str,
            "actions": [
                {
                    "category": str,
                    "category_label": str,
                    "severity": str,
                    "status": str,              # pass/warn/fail
                    "issue": str,
                    "recommended_action": str,
                    "assignee_role": str,
                    "estimated_effort_hours": int,
                    "deadline": str,
                    "law": str,
                },
                ...
            ],
            "summary": str,
            "requires_human_approval": True,
            "ai_role": "assistant_only",
        }

    주의:
        - read-only 변환. DB mutation 없음.
        - 점수/확률/백분율 출력 없음.
        - 모든 액션 플랜은 human-review + admin confirm 대상.
    """
    if not company:
        raise ValueError("company is required")

    as_of_date = diagnosis_result.get("as_of_date", str(date.today()))
    base_date = _parse_date(as_of_date) or date.today()
    deadline_date = base_date + timedelta(days=deadline_days)

    overall_status = diagnosis_result.get("overall_status", "needs_attention")
    diagnoses = diagnosis_result.get("diagnoses", {})

    actions: list[dict[str, Any]] = []

    # 규칙 정의 import (동적)
    try:
        from hrms.regional.south_korea.compliance_diagnosis import DIAGNOSIS_RULES
    except ImportError:
        DIAGNOSIS_RULES = {}  # type: ignore[assignment]

    for category_key, result in diagnoses.items():
        status = result.get("status", "warn")
        if status == "pass":
            continue  # pass 항목은 액션 불필요

        findings = result.get("findings", [])
        recommendations = result.get("recommendations", [])
        template = _ACTION_TEMPLATES.get(category_key, {})
        rule_meta = DIAGNOSIS_RULES.get(category_key, {}) if DIAGNOSIS_RULES else {}
        severity = rule_meta.get("severity", "medium")
        law = rule_meta.get("law", "")

        # 심각도 기반 개별 기한 계산
        item_deadline_days = _SEVERITY_DEADLINE_DAYS.get(severity, deadline_days)
        item_deadline = base_date + timedelta(days=item_deadline_days)

        # 발견 사항별 이슈 요약
        issue_texts = [f.get("issue", "") for f in findings if f.get("issue")]
        issue_summary = issue_texts[0] if issue_texts else f"{template.get('category_label', category_key)} 검토 필요"
        if len(issue_texts) > 1:
            issue_summary += f" 외 {len(issue_texts) - 1}건"

        # 권고 사항 → recommended_action
        if recommendations:
            recommended_action = recommendations[0]
        else:
            recommended_action = template.get("default_action", f"{category_key} 항목을 검토하고 시정하세요.")

        actions.append({
            "category": category_key,
            "category_label": template.get("category_label", category_key),
            "severity": severity,
            "status": status,
            "issue": issue_summary,
            "recommended_action": recommended_action,
            "all_recommendations": recommendations,
            "finding_count": len(findings),
            "assignee_role": template.get("assignee_role", "HR Manager"),
            "estimated_effort_hours": template.get("estimated_effort_hours", 2),
            "deadline": str(item_deadline),
            "law": law,
        })

    # severity 순 정렬: high → medium → low
    _severity_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: (_severity_order.get(a["severity"], 9), a["category"]))

    summary = _build_plan_summary(actions, overall_status)

    return {
        "contract_type": "korea_compliance_action_plan_v1",
        "company": company,
        "as_of_date": as_of_date,
        "deadline_date": str(deadline_date),
        "overall_status": overall_status,
        "actions": actions,
        "total_actions": len(actions),
        "summary": summary,
        "requires_human_approval": True,
        "ai_role": "assistant_only",
    }


def _build_plan_summary(actions: list[dict[str, Any]], overall_status: str) -> str:
    if not actions:
        return "모든 컴플라이언스 항목이 양호합니다. 별도 조치 불필요."

    high = [a for a in actions if a["severity"] == "high"]
    medium = [a for a in actions if a["severity"] == "medium"]
    low = [a for a in actions if a["severity"] == "low"]

    parts = []
    if high:
        parts.append(f"즉시 조치 필요 {len(high)}건")
    if medium:
        parts.append(f"14일 내 조치 {len(medium)}건")
    if low:
        parts.append(f"30일 내 조치 {len(low)}건")

    status_label = {
        "high_risk": "위험",
        "needs_attention": "주의",
        "good": "양호",
    }.get(overall_status, overall_status)

    return f"[{status_label}] " + " / ".join(parts) + ". 각 담당자에게 배정 후 human-review를 거쳐 조치하세요."


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None
