"""한국 노무 컴플라이언스 진단 (Korea Labor Compliance Diagnosis).

설계 원칙:
- read-only: 진단은 읽기 전용. DB mutation 절대 없음.
- AI 점수/확률 출력 없음: Pass / Warn / Fail 정성 status만.
- data_loader 추상화: Frappe 또는 mock 둘 다 작동.
- 외부 LLM API 사용 없음: 규칙 기반 판단만.

사용 예시::

    from hrms.regional.south_korea.compliance_diagnosis import run_full_compliance_diagnosis

    result = run_full_compliance_diagnosis(
        company="위너스",
        workplace="서울지사",
        as_of_date="2026-05-17",
        data_loader=FrappeDataLoader(company="위너스", workplace="서울지사"),
    )
"""

from __future__ import annotations

import importlib.util
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


def _load_mask_helpers():
    """kakao_notification.py에서 PII 마스킹 헬퍼를 지연 로드합니다.

    hrms/__init__.py가 frappe를 import하므로 file-path 직접 로드.
    Returns: (mask_korean_name, mask_phone_number) tuple.
    """
    _path = Path(__file__).resolve().with_name("kakao_notification.py")
    _spec = importlib.util.spec_from_file_location("_kakao_notification_helpers", _path)
    _mod = importlib.util.module_from_spec(_spec)
    assert _spec.loader is not None
    _spec.loader.exec_module(_mod)
    return _mod.mask_korean_name, _mod.mask_phone_number

# ---------------------------------------------------------------------------
# 규칙 정의 (Diagnosis Rule Definitions)
# ---------------------------------------------------------------------------

DIAGNOSIS_RULES: dict[str, dict[str, Any]] = {
    "social_insurance": {
        "name": "4대보험 가입",
        "law": "국민연금법 / 국민건강보험법 / 고용보험법 / 산업재해보상보험법",
        "severity": "high",
    },
    "wage_delay": {
        "name": "임금 정기 지급",
        "law": "근기법 43조",
        "severity": "high",
    },
    "overtime_limit": {
        "name": "주 12시간 연장근로 한도",
        "law": "근기법 53조",
        "severity": "medium",
    },
    "annual_leave_usage": {
        "name": "연차 사용 촉진",
        "law": "근기법 61조",
        "severity": "low",
    },
    "anti_bullying_policy": {
        "name": "직장 내 괴롭힘 예방 + 신고채널",
        "law": "근기법 76조의2 ~ 76조의3",
        "severity": "high",
    },
}

# 주 연장근로 한도 (시간) — 근기법 53조
WEEKLY_OVERTIME_LIMIT_HOURS: float = 12.0

# 연차 미사용 위험 임계값 (비율): 80% 이상 미사용 시 warn
ANNUAL_LEAVE_UNUSED_WARN_RATIO: float = 0.80

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# DataLoader Protocol — read-only 추상화
# ---------------------------------------------------------------------------


@runtime_checkable
class DataLoader(Protocol):
    """컴플라이언스 진단에 필요한 데이터 로더 프로토콜.

    모든 메서드는 read-only. 반환 타입은 dict/list — Frappe 문서 객체 불허.
    필드가 존재하지 않을 때 None을 반환하면 진단이 "data_unavailable" 처리함.
    """

    def get_workplace_profile(self, company: str, workplace: str) -> dict[str, Any] | None:
        """Korea Workplace Profile 조회.

        반환 예시::
            {
                "name": "서울지사",
                "company": "위너스",
                "scheduled_pay_day": 10,           # 정기 지급일 (1~31)
                "anti_bullying_policy_registered": True,  # 괴롭힘 예방 정책 등록 여부
                "grievance_channel_registered": True,     # 신고채널 등록 여부
            }
        """
        ...

    def get_employment_profiles(
        self, company: str, workplace: str
    ) -> list[dict[str, Any]]:
        """직원 고용 프로파일 목록 조회.

        반환 예시::
            [
                {
                    "employee": "EMP-0001",
                    "employee_name": "김철수",
                    "national_pension_enrolled": True,
                    "health_insurance_enrolled": True,
                    "employment_insurance_enrolled": True,
                    "industrial_accident_enrolled": True,
                },
                ...
            ]
        """
        ...

    def get_salary_slips(
        self,
        company: str,
        workplace: str,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        """급여 명세서 목록 조회 (read-only).

        반환 예시::
            [
                {
                    "name": "SAL-0001",
                    "employee": "EMP-0001",
                    "employee_name": "김철수",
                    "posting_date": "2026-04-30",  # 실제 지급일
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-30",
                    "status": "Submitted",
                },
                ...
            ]
        """
        ...

    def get_attendance_records(
        self,
        company: str,
        workplace: str,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        """근태 기록 목록 조회.

        반환 예시::
            [
                {
                    "employee": "EMP-0001",
                    "employee_name": "김철수",
                    "attendance_date": "2026-04-01",
                    "working_hours": 8.0,
                    "overtime_hours": 3.0,  # 연장근로 시간 (없으면 0)
                },
                ...
            ]
        """
        ...

    def get_leave_allocations(
        self, company: str, workplace: str, as_of_date: str
    ) -> list[dict[str, Any]]:
        """연차 할당 목록 조회.

        반환 예시::
            [
                {
                    "employee": "EMP-0001",
                    "employee_name": "김철수",
                    "leave_type": "연차",
                    "total_leaves_allocated": 15.0,
                    "from_date": "2026-01-01",
                    "to_date": "2026-12-31",
                },
                ...
            ]
        """
        ...

    def get_leave_applications(
        self, company: str, workplace: str, from_date: str, to_date: str
    ) -> list[dict[str, Any]]:
        """연차 사용 신청 목록 조회.

        반환 예시::
            [
                {
                    "employee": "EMP-0001",
                    "employee_name": "김철수",
                    "leave_type": "연차",
                    "total_leave_days": 3.0,
                    "status": "Approved",
                },
                ...
            ]
        """
        ...

    def get_policy_documents(
        self, company: str, workplace: str
    ) -> list[dict[str, Any]]:
        """정책 문서 목록 조회 (직장 내 괴롭힘 예방 정책 등).

        반환 예시::
            [
                {
                    "document_type": "anti_bullying_policy",
                    "title": "직장 내 괴롭힘 예방 및 처리 규정",
                    "registered_date": "2026-01-15",
                },
                ...
            ]
        """
        ...


# ---------------------------------------------------------------------------
# 개별 진단 함수 (Individual Diagnosis Functions)
# ---------------------------------------------------------------------------


def diagnose_social_insurance(
    *,
    workplace_profile: dict[str, Any] | None,
    employment_profiles: list[dict[str, Any]],
) -> dict[str, Any]:
    """4대보험 미가입자 발견 및 비율 진단.

    근거 법령: 국민연금법 / 국민건강보험법 / 고용보험법 / 산업재해보상보험법
    """
    rule = DIAGNOSIS_RULES["social_insurance"]

    if not employment_profiles:
        return _make_result(
            status="warn",
            findings=[
                _finding(
                    issue="고용 프로파일 데이터 없음 — 4대보험 가입 현황 확인 불가",
                    law=rule["law"],
                    data_unavailable=True,
                )
            ],
            recommendations=["Korea Employment Profile 데이터를 시스템에 등록하세요."],
        )

    findings = []
    for ep in employment_profiles:
        employee = ep.get("employee", "unknown")
        employee_name = ep.get("employee_name", employee)

        missing_insurances = []
        if ep.get("national_pension_enrolled") is False:
            missing_insurances.append("국민연금")
        if ep.get("health_insurance_enrolled") is False:
            missing_insurances.append("건강보험")
        if ep.get("employment_insurance_enrolled") is False:
            missing_insurances.append("고용보험")
        if ep.get("industrial_accident_enrolled") is False:
            missing_insurances.append("산재보험")

        # 필드 자체가 None인 경우 (데이터 미등록) — 개별 warn
        unavailable = []
        for field, label in [
            ("national_pension_enrolled", "국민연금"),
            ("health_insurance_enrolled", "건강보험"),
            ("employment_insurance_enrolled", "고용보험"),
            ("industrial_accident_enrolled", "산재보험"),
        ]:
            if ep.get(field) is None:
                unavailable.append(label)

        if missing_insurances:
            findings.append(
                _finding(
                    employee=employee,
                    employee_name=employee_name,
                    issue=f"4대보험 미가입: {', '.join(missing_insurances)}",
                    law=rule["law"],
                )
            )
        if unavailable:
            findings.append(
                _finding(
                    employee=employee,
                    employee_name=employee_name,
                    issue=f"4대보험 가입 정보 미등록 (확인 필요): {', '.join(unavailable)}",
                    law=rule["law"],
                    data_unavailable=True,
                )
            )

    # 상태 판정 — fail: 미가입자 1명 이상, warn: 데이터 미등록만, pass: 전원 가입
    fail_findings = [f for f in findings if not f.get("data_unavailable")]
    warn_findings = [f for f in findings if f.get("data_unavailable")]

    if fail_findings:
        status = "fail"
        recommendations = [
            "미가입 직원의 4대보험 즉시 취득 신고를 진행하세요 (근로 시작일 기준 소급 처리 필요).",
            "산재보험은 사업주 의무 가입으로 미가입 시 산업재해 발생 때 과태료 및 비용 부담이 발생합니다.",
        ]
    elif warn_findings:
        status = "warn"
        recommendations = [
            "4대보험 가입 현황을 Korea Employment Profile에 등록하여 관리하세요.",
        ]
    else:
        status = "pass"
        recommendations = []

    return _make_result(status=status, findings=findings, recommendations=recommendations)


def diagnose_wage_delay(
    *,
    salary_slips: list[dict[str, Any]],
    scheduled_pay_day: int | None,
) -> dict[str, Any]:
    """임금 정기 지급일 지연 발견 진단.

    근거 법령: 근기법 43조 (임금은 매월 1회 이상, 일정한 기일에 지급)

    Args:
        salary_slips: 급여 명세서 목록. posting_date 필드 기준 비교.
        scheduled_pay_day: 정기 지급일 (1~31). None이면 데이터 미등록.
    """
    rule = DIAGNOSIS_RULES["wage_delay"]

    if scheduled_pay_day is None:
        return _make_result(
            status="warn",
            findings=[
                _finding(
                    issue="정기 지급일이 Korea Workplace Profile에 등록되지 않음",
                    law=rule["law"],
                    data_unavailable=True,
                )
            ],
            recommendations=[
                "Korea Workplace Profile의 scheduled_pay_day 필드에 정기 지급일(1~31)을 등록하세요.",
            ],
        )

    if not salary_slips:
        return _make_result(
            status="warn",
            findings=[
                _finding(
                    issue="급여 명세서 데이터 없음 — 임금 지급 지연 이력 확인 불가",
                    law=rule["law"],
                    data_unavailable=True,
                )
            ],
            recommendations=["급여 명세서 처리 이력을 시스템에 등록하세요."],
        )

    findings = []
    for slip in salary_slips:
        posting_date_str = slip.get("posting_date")
        end_date_str = slip.get("end_date")
        if not posting_date_str or not end_date_str:
            continue

        posting_date = _parse_date(posting_date_str)
        end_date = _parse_date(end_date_str)
        if posting_date is None or end_date is None:
            continue

        # 해당 급여 월의 정기 지급일 산출
        # 급여 마감월 기준으로 scheduled_pay_day 적용
        # scheduled_pay_day가 말일 이후일 경우 말일로 클램핑
        pay_month = end_date.replace(day=1)
        expected_pay_date = _clamp_to_month_end(
            pay_month.year, pay_month.month, scheduled_pay_day
        )

        if posting_date > expected_pay_date:
            delay_days = (posting_date - expected_pay_date).days
            findings.append(
                _finding(
                    employee=slip.get("employee", ""),
                    employee_name=slip.get("employee_name", slip.get("employee", "")),
                    issue=(
                        f"임금 지급 지연: 정기 지급일 {expected_pay_date} 대비 "
                        f"{delay_days}일 초과 지급 (실제 지급일: {posting_date})"
                    ),
                    law=rule["law"],
                    detail={
                        "salary_slip": slip.get("name"),
                        "expected_pay_date": str(expected_pay_date),
                        "actual_pay_date": str(posting_date),
                        "delay_days": delay_days,
                    },
                )
            )

    if findings:
        status = "warn"
        recommendations = [
            "임금 정기 지급일을 준수하세요. 반복 지연은 근로기준법 43조 위반으로 과태료 대상입니다.",
            "부득이한 지연 사유는 근로자 동의서를 사전 확보하고 기록을 보관하세요.",
        ]
    else:
        status = "pass"
        recommendations = []

    return _make_result(status=status, findings=findings, recommendations=recommendations)


def diagnose_overtime_limit(
    *,
    attendance_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """주 12시간 연장근로 한도 초과 직원 진단.

    근거 법령: 근기법 53조 (연장근로는 주 12시간 한도)
    주 단위: 월~일 기준 (근로기준법 관행).

    Args:
        attendance_records: 근태 기록. attendance_date, employee, overtime_hours 필드 필수.
            날짜 범위 필터링은 호출자(run_full_compliance_diagnosis)가 수행함.
    """
    rule = DIAGNOSIS_RULES["overtime_limit"]

    if not attendance_records:
        return _make_result(
            status="warn",
            findings=[
                _finding(
                    issue="근태 기록 데이터 없음 — 연장근로 한도 초과 확인 불가",
                    law=rule["law"],
                    data_unavailable=True,
                )
            ],
            recommendations=["Attendance 기록을 시스템에 입력하고 연장근로 시간을 등록하세요."],
        )

    # (employee, week_start) → 연장근로 합계
    weekly_overtime: dict[tuple[str, date], float] = {}
    weekly_names: dict[tuple[str, date], str] = {}

    for rec in attendance_records:
        employee = rec.get("employee", "")
        employee_name = rec.get("employee_name", employee)
        att_date = _parse_date(str(rec.get("attendance_date", "")))
        if att_date is None or not employee:
            continue

        overtime = _as_float(rec.get("overtime_hours", 0))
        # 주 시작일: 해당 날의 월요일
        week_start = att_date - timedelta(days=att_date.weekday())
        key = (employee, week_start)
        weekly_overtime[key] = weekly_overtime.get(key, 0.0) + overtime
        weekly_names[key] = employee_name

    findings = []
    for (employee, week_start), total_ot in sorted(weekly_overtime.items()):
        if total_ot > WEEKLY_OVERTIME_LIMIT_HOURS:
            week_end = week_start + timedelta(days=6)
            findings.append(
                _finding(
                    employee=employee,
                    employee_name=weekly_names[(employee, week_start)],
                    issue=(
                        f"주 연장근로 한도 초과: {week_start} ~ {week_end} 주간 "
                        f"연장근로 {total_ot:.1f}h (한도 {WEEKLY_OVERTIME_LIMIT_HOURS}h)"
                    ),
                    law=rule["law"],
                    detail={
                        "week_start": str(week_start),
                        "week_end": str(week_end),
                        "overtime_hours": round(total_ot, 2),
                        "limit_hours": WEEKLY_OVERTIME_LIMIT_HOURS,
                    },
                )
            )

    if findings:
        status = "fail"
        recommendations = [
            "주 12시간 연장근로 한도를 초과한 직원에 대한 근로시간 조정이 필요합니다.",
            "연장근로 가산수당(통상임금의 50%)을 정확히 지급했는지 확인하세요.",
            "5인 이상 사업장에서 반복 위반 시 근로기준법 110조에 따라 2년 이하 징역 또는 2천만원 이하 벌금입니다.",
        ]
    else:
        status = "pass"
        recommendations = []

    return _make_result(status=status, findings=findings, recommendations=recommendations)


def diagnose_annual_leave_usage(
    *,
    leave_allocations: list[dict[str, Any]],
    leave_applications: list[dict[str, Any]],
) -> dict[str, Any]:
    """연차 미사용 및 소멸 위험 진단.

    근거 법령: 근기법 61조 (연차 사용 촉진 제도)
    기준: 총 연차 대비 사용한 연차 비율이 20% 미만(미사용 80% 초과)이면 warn.
    """
    rule = DIAGNOSIS_RULES["annual_leave_usage"]

    if not leave_allocations:
        return _make_result(
            status="warn",
            findings=[
                _finding(
                    issue="연차 할당 데이터 없음 — 연차 사용률 확인 불가",
                    law=rule["law"],
                    data_unavailable=True,
                )
            ],
            recommendations=["Leave Allocation 데이터를 시스템에 등록하세요."],
        )

    # 직원별 할당 합계
    allocated: dict[str, float] = {}
    allocated_names: dict[str, str] = {}
    for alloc in leave_allocations:
        employee = alloc.get("employee", "")
        if not employee:
            continue
        allocated_names[employee] = alloc.get("employee_name", employee)
        allocated[employee] = allocated.get(employee, 0.0) + _as_float(
            alloc.get("total_leaves_allocated", 0)
        )

    # 직원별 사용 합계 (Approved 상태만)
    used: dict[str, float] = {}
    for app in leave_applications:
        employee = app.get("employee", "")
        if not employee:
            continue
        if str(app.get("status", "")).lower() not in {"approved", "승인"}:
            continue
        used[employee] = used.get(employee, 0.0) + _as_float(
            app.get("total_leave_days", 0)
        )

    findings = []
    for employee, total_allocated in sorted(allocated.items()):
        if total_allocated <= 0:
            continue
        total_used = used.get(employee, 0.0)
        unused = total_allocated - total_used
        unused_ratio = unused / total_allocated

        if unused_ratio >= ANNUAL_LEAVE_UNUSED_WARN_RATIO:
            employee_name = allocated_names.get(employee, employee)
            findings.append(
                _finding(
                    employee=employee,
                    employee_name=employee_name,
                    issue=(
                        f"연차 미사용 비율 높음: 부여 {total_allocated:.0f}일 중 "
                        f"{unused:.0f}일 미사용 — 연도 말 소멸 위험"
                    ),
                    law=rule["law"],
                    detail={
                        "allocated_days": round(total_allocated, 1),
                        "used_days": round(total_used, 1),
                        "unused_days": round(unused, 1),
                    },
                )
            )

    if findings:
        status = "warn"
        recommendations = [
            "연차 사용 촉진 제도(근기법 61조)를 적용하여 사용 촉구 통보를 실시하세요.",
            "촉진 통보 미실시 시 미사용 연차에 대한 연차수당 지급 의무가 발생합니다.",
            "연도 말 소멸 전 직원에게 개별 통지하고 사용 계획서를 제출받으세요.",
        ]
    else:
        status = "pass"
        recommendations = []

    return _make_result(status=status, findings=findings, recommendations=recommendations)


def diagnose_anti_bullying(
    *,
    workplace_profile: dict[str, Any] | None,
    policy_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """직장 내 괴롭힘 예방 정책 및 신고채널 등록 여부 진단.

    근거 법령: 근기법 76조의2 ~ 76조의3
    5인 이상 사업장은 취업규칙에 직장 내 괴롭힘 예방·처리 규정 필수 포함 (2019.07.16 시행).
    """
    rule = DIAGNOSIS_RULES["anti_bullying_policy"]

    findings = []
    recommendations = []

    # 1. Workplace Profile 필드 확인
    if workplace_profile is None:
        findings.append(
            _finding(
                issue="Korea Workplace Profile 데이터 없음 — 괴롭힘 예방 정책 등록 확인 불가",
                law=rule["law"],
                data_unavailable=True,
            )
        )
    else:
        # 신고채널 등록 여부
        if not workplace_profile.get("grievance_channel_registered"):
            findings.append(
                _finding(
                    issue="직장 내 괴롭힘 신고채널이 Workplace Profile에 등록되지 않음",
                    law=rule["law"],
                )
            )
            recommendations.append(
                "근기법 76조의3에 따라 괴롭힘 신고를 처리할 채널(담당자, 절차)을 취업규칙에 명시하고 시스템에 등록하세요."
            )

        # 예방 정책 등록 여부
        if not workplace_profile.get("anti_bullying_policy_registered"):
            findings.append(
                _finding(
                    issue="직장 내 괴롭힘 예방 정책이 Workplace Profile에 등록되지 않음",
                    law=rule["law"],
                )
            )
            recommendations.append(
                "직장 내 괴롭힘 예방·대응 정책을 수립하고 취업규칙에 포함시켜 시스템에 등록하세요."
            )

    # 2. 정책 문서 확인
    policy_types = {
        doc.get("document_type", "")
        for doc in policy_documents
    }

    if "anti_bullying_policy" not in policy_types:
        findings.append(
            _finding(
                issue="직장 내 괴롭힘 예방 정책 문서가 시스템에 등록되지 않음",
                law=rule["law"],
            )
        )
        recommendations.append(
            "직장 내 괴롭힘 예방 정책 문서를 작성하여 시스템에 등록하세요 "
            "(취업규칙, 별도 규정 어느 형식이든 가능)."
        )

    # 상태 판정
    actual_fails = [f for f in findings if not f.get("data_unavailable")]
    data_missing = [f for f in findings if f.get("data_unavailable")]

    if actual_fails:
        status = "fail"
        if not recommendations:
            recommendations = [
                "직장 내 괴롭힘 예방 정책 및 신고채널을 시스템에 즉시 등록하세요.",
            ]
    elif data_missing:
        status = "warn"
        recommendations = recommendations or [
            "Korea Workplace Profile 및 Policy Document 데이터를 등록하여 진단이 가능하게 하세요.",
        ]
    else:
        status = "pass"
        recommendations = []

    return _make_result(status=status, findings=findings, recommendations=recommendations)


# ---------------------------------------------------------------------------
# 전체 진단 (Full Diagnosis Runner)
# ---------------------------------------------------------------------------


def run_full_compliance_diagnosis(
    *,
    company: str,
    workplace: str,
    as_of_date: str,
    data_loader: DataLoader,
    mask_pii: bool = True,
) -> dict[str, Any]:
    """전체 컴플라이언스 진단 실행.

    5개 카테고리를 순서대로 진단하고 종합 결과를 반환합니다.
    외부 LLM API 미사용, read-only, 점수/확률 출력 없음.

    Args:
        company: 회사명.
        workplace: 사업장명.
        as_of_date: 진단 기준일 (YYYY-MM-DD).
        data_loader: DataLoader 프로토콜 구현체 (Frappe 또는 mock).
        mask_pii: findings의 직원명(employee_name) 마스킹 여부 (기본 True).
            감사(audit) 목적으로 원본 확인이 필요한 경우 False로 명시적 해제.

    Returns:
        {
            "contract_type": "korea_compliance_diagnosis_v1",
            "as_of_date": str,
            "company": str,
            "workplace": str,
            "diagnoses": {
                "social_insurance": { "status": "pass"|"warn"|"fail", "findings": [...], "recommendations": [...] },
                "wage_delay": {...},
                "overtime_limit": {...},
                "annual_leave_usage": {...},
                "anti_bullying_policy": {...},
            },
            "overall_status": "good" | "needs_attention" | "high_risk",
            "high_severity_findings": int,
            "recommendation_summary": str,
            "pii_masked": bool,
        }

    주의:
        - 모든 권고(recommendations)는 human-review 대상입니다.
        - 진단 결과에 점수, 확률, 백분율 등 정량 지표는 포함하지 않습니다.
        - AI mutation 없음 — 데이터 수정/삽입/삭제 없음.
    """
    if not DATE_PATTERN.match(as_of_date):
        raise ValueError(f"as_of_date must be YYYY-MM-DD format, got: {as_of_date!r}")
    if not company:
        raise ValueError("company is required")

    # 데이터 수집 (read-only)
    workplace_profile = data_loader.get_workplace_profile(company, workplace)
    employment_profiles = data_loader.get_employment_profiles(company, workplace)

    # 임금체불 진단: 진단 기준일 기준 최근 12개월
    as_of = _parse_date(as_of_date) or date.today()
    wage_from_date = str(date(as_of.year - 1, as_of.month, 1))
    wage_to_date = as_of_date

    salary_slips = data_loader.get_salary_slips(
        company, workplace, wage_from_date, wage_to_date
    )

    scheduled_pay_day: int | None = None
    if workplace_profile:
        raw_pay_day = workplace_profile.get("scheduled_pay_day")
        if raw_pay_day is not None:
            try:
                scheduled_pay_day = int(raw_pay_day)
            except (TypeError, ValueError):
                scheduled_pay_day = None

    # 연장근로 진단: 최근 3개월 (연도 경계 처리)
    _ot_start_month = as_of.month - 3
    if _ot_start_month <= 0:
        _ot_start_year = as_of.year - 1
        _ot_start_month = _ot_start_month + 12
    else:
        _ot_start_year = as_of.year
    ot_from_date = str(date(_ot_start_year, _ot_start_month, 1))
    attendance_records = data_loader.get_attendance_records(
        company, workplace, ot_from_date, as_of_date
    )

    # 연차 진단: 현재 연도 연차 할당 및 사용
    leave_year_start = str(date(as_of.year, 1, 1))
    leave_allocations = data_loader.get_leave_allocations(
        company, workplace, as_of_date
    )
    leave_applications = data_loader.get_leave_applications(
        company, workplace, leave_year_start, as_of_date
    )

    # 정책 문서
    policy_documents = data_loader.get_policy_documents(company, workplace)

    # 개별 진단 실행
    diagnoses: dict[str, dict[str, Any]] = {
        "social_insurance": diagnose_social_insurance(
            workplace_profile=workplace_profile,
            employment_profiles=employment_profiles,
        ),
        "wage_delay": diagnose_wage_delay(
            salary_slips=salary_slips,
            scheduled_pay_day=scheduled_pay_day,
        ),
        "overtime_limit": diagnose_overtime_limit(
            attendance_records=attendance_records,
        ),
        "annual_leave_usage": diagnose_annual_leave_usage(
            leave_allocations=leave_allocations,
            leave_applications=leave_applications,
        ),
        "anti_bullying_policy": diagnose_anti_bullying(
            workplace_profile=workplace_profile,
            policy_documents=policy_documents,
        ),
    }

    # 종합 상태 산출
    high_severity_findings = _count_high_severity_findings(diagnoses)
    overall_status = _compute_overall_status(diagnoses)
    recommendation_summary = _build_recommendation_summary(diagnoses, overall_status)

    # PII 마스킹 — findings의 직원명 마스킹 (기본 ON, audit 시 명시적 해제)
    if mask_pii:
        _mask_findings_pii(diagnoses)

    return {
        "contract_type": "korea_compliance_diagnosis_v1",
        "as_of_date": as_of_date,
        "company": company,
        "workplace": workplace,
        "diagnoses": diagnoses,
        "overall_status": overall_status,
        "high_severity_findings": high_severity_findings,
        "recommendation_summary": recommendation_summary,
        "pii_masked": mask_pii,
    }


# ---------------------------------------------------------------------------
# 내부 헬퍼 (Internal Helpers)
# ---------------------------------------------------------------------------


def _mask_findings_pii(diagnoses: dict[str, dict[str, Any]]) -> None:
    """diagnoses 내 모든 finding의 employee_name을 in-place 마스킹합니다.

    mask_pii=True(기본값)일 때 run_full_compliance_diagnosis 종료 시점에 호출됩니다.
    kakao_notification의 mask_korean_name 헬퍼를 사용합니다.
    """
    try:
        mask_korean_name, _ = _load_mask_helpers()
    except Exception:
        # 마스킹 헬퍼 로드 실패 시 안전하게 건너뜀 (로그만 남기고 진단 결과는 반환)
        return

    for diagnosis in diagnoses.values():
        for finding in diagnosis.get("findings", []):
            if finding.get("employee_name"):
                finding["employee_name"] = mask_korean_name(finding["employee_name"])


def _make_result(
    *,
    status: str,
    findings: list[dict[str, Any]],
    recommendations: list[str],
) -> dict[str, Any]:
    """진단 결과 dict 생성."""
    assert status in {"pass", "warn", "fail"}, f"Invalid status: {status!r}"
    return {
        "status": status,
        "findings": findings,
        "recommendations": recommendations,
    }


def _finding(
    *,
    issue: str,
    law: str,
    employee: str = "",
    employee_name: str = "",
    detail: dict[str, Any] | None = None,
    data_unavailable: bool = False,
) -> dict[str, Any]:
    """발견 항목 dict 생성."""
    f: dict[str, Any] = {"issue": issue, "law": law}
    if employee:
        f["employee"] = employee
    if employee_name:
        f["employee_name"] = employee_name
    if detail:
        f["detail"] = detail
    if data_unavailable:
        f["data_unavailable"] = True
    return f


def _parse_date(value: Any) -> date | None:
    """문자열 또는 date 객체를 date로 변환."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _as_float(value: Any) -> float:
    """숫자 변환. 변환 실패 시 0.0 반환."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _clamp_to_month_end(year: int, month: int, day: int) -> date:
    """주어진 day가 해당 월의 말일을 초과하면 말일로 조정."""
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, max_day))


def _count_high_severity_findings(
    diagnoses: dict[str, dict[str, Any]]
) -> int:
    """high severity 규칙 중 fail/warn 상태인 항목 수 반환."""
    count = 0
    for rule_key, rule_meta in DIAGNOSIS_RULES.items():
        if rule_meta.get("severity") == "high":
            result = diagnoses.get(rule_key, {})
            if result.get("status") in {"fail", "warn"}:
                count += 1
    return count


def _compute_overall_status(
    diagnoses: dict[str, dict[str, Any]]
) -> str:
    """종합 상태 산출.

    - high_risk: high severity 규칙 중 fail 1개 이상
    - needs_attention: warn 있거나 medium severity fail
    - good: 모두 pass
    """
    # high severity fail 여부
    for rule_key, rule_meta in DIAGNOSIS_RULES.items():
        result = diagnoses.get(rule_key, {})
        if rule_meta.get("severity") == "high" and result.get("status") == "fail":
            return "high_risk"

    # 어떤 warn/fail이든
    for result in diagnoses.values():
        if result.get("status") in {"warn", "fail"}:
            return "needs_attention"

    return "good"


def _build_recommendation_summary(
    diagnoses: dict[str, dict[str, Any]],
    overall_status: str,
) -> str:
    """종합 권고 요약 문자열 생성."""
    status_labels = {
        "good": "컴플라이언스 양호",
        "needs_attention": "일부 항목 검토 필요",
        "high_risk": "즉시 조치 필요",
    }
    label = status_labels.get(overall_status, overall_status)

    fail_items = [
        DIAGNOSIS_RULES[k]["name"]
        for k, v in diagnoses.items()
        if v.get("status") == "fail"
    ]
    warn_items = [
        DIAGNOSIS_RULES[k]["name"]
        for k, v in diagnoses.items()
        if v.get("status") == "warn"
    ]

    parts = [f"[{label}]"]
    if fail_items:
        parts.append(f"위반 항목: {', '.join(fail_items)}")
    if warn_items:
        parts.append(f"검토 필요: {', '.join(warn_items)}")
    if not fail_items and not warn_items:
        parts.append("모든 항목 양호.")

    parts.append("이 보고서는 human-review 대상이며 최종 법적 판단은 담당자가 확인하세요.")
    return " | ".join(parts)
