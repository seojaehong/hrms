"""한국 노무 컴플라이언스 진단 Frappe API.

이 모듈은 Frappe whitelist API 엔드포인트를 제공합니다.
핵심 진단 로직은 compliance_diagnosis.py에 분리되어 있습니다.

엔드포인트:
    - run_compliance_diagnosis: 전체 진단 실행
    - get_diagnosis_rules: 진단 규칙 목록 반환 (참고용)

설계 원칙:
    - read-only: DB mutation 없음
    - AI 점수/확률 출력 없음
    - 모든 권고는 human-review 대상
"""

from __future__ import annotations

import re
from typing import Any

import frappe

from hrms.regional.south_korea.compliance_diagnosis import (
    DIAGNOSIS_RULES,
    DataLoader,
    run_full_compliance_diagnosis,
)

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 연차 대상 Leave Type 한국어/영문 목록
ANNUAL_LEAVE_TYPES = {"연차", "연차휴가", "Annual Leave", "annual_leave"}


# ---------------------------------------------------------------------------
# Frappe DataLoader 구현
# ---------------------------------------------------------------------------


class FrappeDataLoader:
    """Frappe frappe.get_all / frappe.db.get_value 기반 DataLoader 구현.

    모든 메서드는 read-only. 쓰기 작업 없음.
    """

    def __init__(self, company: str, workplace: str) -> None:
        self.company = company
        self.workplace = workplace

    def get_workplace_profile(
        self, company: str, workplace: str
    ) -> dict[str, Any] | None:
        """Korea Workplace Profile 조회 (custom field fallback 포함)."""
        # Korea Workplace Profile 독립 Doctype이 있는 경우 우선 조회
        if frappe.db.exists("Korea Workplace Profile", {"company": company, "workplace": workplace}):
            doc = frappe.db.get_value(
                "Korea Workplace Profile",
                {"company": company, "workplace": workplace},
                [
                    "name",
                    "company",
                    "scheduled_pay_day",
                    "anti_bullying_policy_registered",
                    "grievance_channel_registered",
                ],
                as_dict=True,
            )
            if doc:
                return dict(doc)

        # Branch doctype의 custom 필드 fallback
        if frappe.db.exists("Branch", workplace):
            branch_fields = _get_available_branch_fields()
            if branch_fields:
                doc = frappe.db.get_value("Branch", workplace, branch_fields, as_dict=True)
                if doc:
                    return _normalize_branch_profile(dict(doc), workplace, company)

        return None

    def get_employment_profiles(
        self, company: str, workplace: str
    ) -> list[dict[str, Any]]:
        """Korea Employment Profile 조회."""
        # Korea Employment Profile 독립 Doctype 우선
        if frappe.db.table_exists("Korea Employment Profile"):
            rows = frappe.get_all(
                "Korea Employment Profile",
                filters={"company": company, "workplace": workplace},
                fields=[
                    "employee",
                    "employee_name",
                    "national_pension_enrolled",
                    "health_insurance_enrolled",
                    "employment_insurance_enrolled",
                    "industrial_accident_enrolled",
                ],
            )
            return [dict(r) for r in rows]

        # Employee doctype custom 필드 fallback
        employee_filters: dict[str, Any] = {"company": company, "status": "Active"}
        if workplace and frappe.db.exists("Branch", workplace):
            employee_filters["branch"] = workplace

        available_fields = _get_available_employee_insurance_fields()
        base_fields = ["name", "employee_name"]
        fields = base_fields + available_fields

        rows = frappe.get_all("Employee", filters=employee_filters, fields=fields)
        return [_normalize_employee_insurance_row(dict(r)) for r in rows]

    def get_salary_slips(
        self,
        company: str,
        workplace: str,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        """급여 명세서 조회 (read-only)."""
        filters: dict[str, Any] = {
            "company": company,
            "docstatus": 1,
            "posting_date": ["between", [from_date, to_date]],
        }
        if workplace:
            # branch 필터는 Salary Slip에 branch 필드가 있을 때만
            if "branch" in (frappe.db.get_table_columns("Salary Slip") or []):
                filters["branch"] = workplace

        rows = frappe.get_all(
            "Salary Slip",
            filters=filters,
            fields=[
                "name",
                "employee",
                "employee_name",
                "posting_date",
                "start_date",
                "end_date",
                "status",
            ],
            order_by="posting_date asc",
        )
        return [dict(r) for r in rows]

    def get_attendance_records(
        self,
        company: str,
        workplace: str,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        """근태 기록 조회."""
        filters: dict[str, Any] = {
            "company": company,
            "docstatus": 1,
            "attendance_date": ["between", [from_date, to_date]],
        }

        available_ot_fields = _get_available_overtime_fields()
        fields = [
            "employee",
            "employee_name",
            "attendance_date",
            "working_hours",
        ] + available_ot_fields

        if workplace:
            employee_names = _get_employee_names_for_workplace(company, workplace)
            if employee_names is not None:
                if not employee_names:
                    return []
                filters["employee"] = ["in", list(employee_names)]

        rows = frappe.get_all(
            "Attendance",
            filters=filters,
            fields=fields,
            order_by="employee asc, attendance_date asc",
        )
        return [_normalize_attendance_row(dict(r)) for r in rows]

    def get_leave_allocations(
        self, company: str, workplace: str, as_of_date: str
    ) -> list[dict[str, Any]]:
        """연차 할당 조회."""
        filters: dict[str, Any] = {
            "company": company,
            "docstatus": 1,
            "leave_type": ["in", list(ANNUAL_LEAVE_TYPES)],
            "from_date": ["<=", as_of_date],
            "to_date": [">=", as_of_date],
        }

        employee_names = _get_employee_names_for_workplace(company, workplace)
        if employee_names is not None:
            if not employee_names:
                return []
            filters["employee"] = ["in", list(employee_names)]

        rows = frappe.get_all(
            "Leave Allocation",
            filters=filters,
            fields=[
                "employee",
                "employee_name",
                "leave_type",
                "total_leaves_allocated",
                "from_date",
                "to_date",
            ],
        )
        return [dict(r) for r in rows]

    def get_leave_applications(
        self, company: str, workplace: str, from_date: str, to_date: str
    ) -> list[dict[str, Any]]:
        """연차 사용 신청 조회."""
        filters: dict[str, Any] = {
            "company": company,
            "docstatus": 1,
            "status": "Approved",
            "leave_type": ["in", list(ANNUAL_LEAVE_TYPES)],
            "from_date": ["between", [from_date, to_date]],
        }

        employee_names = _get_employee_names_for_workplace(company, workplace)
        if employee_names is not None:
            if not employee_names:
                return []
            filters["employee"] = ["in", list(employee_names)]

        rows = frappe.get_all(
            "Leave Application",
            filters=filters,
            fields=[
                "employee",
                "employee_name",
                "leave_type",
                "total_leave_days",
                "from_date",
                "to_date",
                "status",
            ],
        )
        return [dict(r) for r in rows]

    def get_policy_documents(
        self, company: str, workplace: str
    ) -> list[dict[str, Any]]:
        """정책 문서 조회 (Korea Policy Document doctype 있는 경우)."""
        if not frappe.db.table_exists("Korea Policy Document"):
            return []

        rows = frappe.get_all(
            "Korea Policy Document",
            filters={"company": company, "workplace": workplace},
            fields=["name", "document_type", "title", "registered_date"],
        )
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Frappe Whitelist API
# ---------------------------------------------------------------------------


@frappe.whitelist()
def run_compliance_diagnosis(
    company: str,
    workplace: str = "",
    as_of_date: str | None = None,
) -> dict[str, Any]:
    """한국 노무 컴플라이언스 전체 진단 실행.

    Args:
        company: 회사명 (필수).
        workplace: 사업장명 (선택). 빈 문자열이면 전사 진단.
        as_of_date: 진단 기준일 YYYY-MM-DD (선택, 기본값: 오늘).

    Returns:
        run_full_compliance_diagnosis 반환 구조와 동일.

    주의:
        - read-only 진단. DB 수정 없음.
        - 점수/확률 출력 없음. 정성 status(pass/warn/fail) + 발견 + 권고만.
        - 모든 권고는 human-review 대상.
    """
    if not company:
        frappe.throw("company is required")

    if not as_of_date:
        as_of_date = str(frappe.utils.today())

    if not DATE_PATTERN.match(as_of_date):
        frappe.throw(f"as_of_date must be YYYY-MM-DD format, got: {as_of_date!r}")

    loader = FrappeDataLoader(company=company, workplace=workplace or "")

    try:
        return run_full_compliance_diagnosis(
            company=company,
            workplace=workplace or "",
            as_of_date=as_of_date,
            data_loader=loader,
        )
    except ValueError as exc:
        frappe.throw(str(exc))


@frappe.whitelist()
def get_diagnosis_rules() -> dict[str, Any]:
    """진단 규칙 목록 반환 (참고용, read-only).

    Returns:
        { "rules": [ { "key": str, "name": str, "law": str, "severity": str } ] }
    """
    rules = [
        {
            "key": key,
            "name": meta["name"],
            "law": meta["law"],
            "severity": meta["severity"],
        }
        for key, meta in DIAGNOSIS_RULES.items()
    ]
    return {"rules": rules}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _get_employee_names_for_workplace(
    company: str, workplace: str
) -> set[str] | None:
    """사업장(Branch) 소속 직원 name 집합 반환. workplace 미지정 시 None 반환."""
    if not workplace:
        return None
    names = frappe.get_all(
        "Employee",
        filters={"company": company, "branch": workplace, "status": "Active"},
        pluck="name",
    )
    return set(names)


def _get_available_overtime_fields() -> list[str]:
    """Attendance doctype에 존재하는 연장근로 필드 목록."""
    candidates = [
        "actual_overtime_duration",
        "overtime_hours",
        "custom_overtime_hours",
    ]
    columns = set(frappe.db.get_table_columns("Attendance") or [])
    return [f for f in candidates if f in columns]


def _get_available_employee_insurance_fields() -> list[str]:
    """Employee doctype에 존재하는 4대보험 custom 필드 목록."""
    candidates = [
        "national_pension_enrolled",
        "custom_national_pension_enrolled",
        "health_insurance_enrolled",
        "custom_health_insurance_enrolled",
        "employment_insurance_enrolled",
        "custom_employment_insurance_enrolled",
        "industrial_accident_enrolled",
        "custom_industrial_accident_enrolled",
    ]
    columns = set(frappe.db.get_table_columns("Employee") or [])
    return [f for f in candidates if f in columns]


def _get_available_branch_fields() -> list[str]:
    """Branch doctype에서 Workplace Profile 관련 필드 목록."""
    candidates = [
        "scheduled_pay_day",
        "custom_scheduled_pay_day",
        "anti_bullying_policy_registered",
        "custom_anti_bullying_policy_registered",
        "grievance_channel_registered",
        "custom_grievance_channel_registered",
    ]
    columns = set(frappe.db.get_table_columns("Branch") or [])
    return [f for f in candidates if f in columns]


def _normalize_branch_profile(
    doc: dict[str, Any], workplace: str, company: str
) -> dict[str, Any]:
    """Branch 필드를 Workplace Profile 스키마로 정규화."""
    return {
        "name": workplace,
        "company": company,
        "scheduled_pay_day": (
            doc.get("scheduled_pay_day") or doc.get("custom_scheduled_pay_day")
        ),
        "anti_bullying_policy_registered": bool(
            doc.get("anti_bullying_policy_registered")
            or doc.get("custom_anti_bullying_policy_registered")
        ),
        "grievance_channel_registered": bool(
            doc.get("grievance_channel_registered")
            or doc.get("custom_grievance_channel_registered")
        ),
    }


def _normalize_employee_insurance_row(row: dict[str, Any]) -> dict[str, Any]:
    """Employee 행을 Employment Profile 스키마로 정규화."""

    def _enrolled(field: str, custom_field: str) -> bool | None:
        val = row.get(field)
        if val is None:
            val = row.get(custom_field)
        if val is None:
            return None
        return bool(val)

    return {
        "employee": row.get("name", ""),
        "employee_name": row.get("employee_name", ""),
        "national_pension_enrolled": _enrolled(
            "national_pension_enrolled", "custom_national_pension_enrolled"
        ),
        "health_insurance_enrolled": _enrolled(
            "health_insurance_enrolled", "custom_health_insurance_enrolled"
        ),
        "employment_insurance_enrolled": _enrolled(
            "employment_insurance_enrolled", "custom_employment_insurance_enrolled"
        ),
        "industrial_accident_enrolled": _enrolled(
            "industrial_accident_enrolled", "custom_industrial_accident_enrolled"
        ),
    }


def _normalize_attendance_row(row: dict[str, Any]) -> dict[str, Any]:
    """Attendance 행 정규화 — overtime_hours 필드 통합."""
    # actual_overtime_duration > overtime_hours > custom_overtime_hours 순서 우선
    overtime = (
        _as_float(row.get("actual_overtime_duration"))
        or _as_float(row.get("overtime_hours"))
        or _as_float(row.get("custom_overtime_hours"))
    )
    return {
        "employee": row.get("employee", ""),
        "employee_name": row.get("employee_name", ""),
        "attendance_date": str(row.get("attendance_date", "")),
        "working_hours": _as_float(row.get("working_hours", 0)),
        "overtime_hours": overtime,
    }


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
