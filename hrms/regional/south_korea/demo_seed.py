"""Korea HRMS demo seed — Wave 4 extended.

Idempotent: safe to run multiple times.  All mutations go through
``ensure_doc`` which skips existing records.

Entry point (bench execute):
    bench --site hrms.localhost execute \
        hrms.regional.south_korea.demo_seed.seed_korea_demo

Legacy entry point (kept for backward compatibility):
    bench --site hrms.localhost execute \
        hrms.regional.south_korea.demo_seed.main
"""
from __future__ import annotations

import json
import os
import random
import secrets
from datetime import date, timedelta

import frappe
from frappe.utils import getdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_doc(doctype, name=None, filters=None, values=None, ignore_links=False, update_existing=True):
    values = values or {}
    if filters:
        if frappe.db.exists(doctype, filters):
            doc = frappe.get_doc(doctype, filters)
        else:
            doc = None
    elif name and frappe.db.exists(doctype, name):
        doc = frappe.get_doc(doctype, name)
    else:
        doc = None

    if doc is None:
        payload = {"doctype": doctype, **values}
        if name:
            payload["name"] = name
            payload["__newname"] = name
        doc = frappe.get_doc(payload).insert(ignore_permissions=True, ignore_links=ignore_links)
        return doc, True

    if not update_existing:
        return doc, False

    changed = False
    for key, value in values.items():
        if doc.get(key) != value:
            doc.set(key, value)
            changed = True
    if changed:
        if ignore_links:
            doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)
    return doc, False


def _employee_name(employee):
    name = getattr(employee, "name", None)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("employee.name must be a non-empty string")
    return name.strip()


def _employee_workplace(employee):
    workplace = getattr(employee, "work_location_name", None) or getattr(employee, "branch", None) or "서울 본사"
    if not isinstance(workplace, str) or not workplace.strip():
        raise ValueError("employee.work_location_name must be a non-empty string when provided")
    return workplace.strip()


def _require_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _document_value(doc, fieldname, default):
    getter = getattr(doc, "get", None)
    if callable(getter):
        value = getter(fieldname)
        if value is not None:
            return value
    return getattr(doc, fieldname, default)


# ---------------------------------------------------------------------------
# Masters — unchanged from baseline
# ---------------------------------------------------------------------------

def ensure_warehouse_type(name):
    return ensure_doc("Warehouse Type", name=name, values={"description": f"Auto-created for demo company bootstrap: {name}"})


def ensure_company():
    values = {
        "company_name": "노란봉투법 데모",
        "abbr": "NBG",
        "default_currency": "KRW",
        "country": "Korea, Republic of",
        "valuation_method": "FIFO",
        "default_holiday_list": "KR Public Holidays 2026 Demo",
        "business_registration_number": "123-45-67890",
        "workplace_management_number": "KR-WORKSITE-001",
        "default_work_location": "서울 본사",
        "korea_rules_reference": ".hermes/KOREA_LEGAL_RULES_INPUT.yaml",
    }
    return ensure_doc("Company", name="노란봉투법 데모", values=values)


def ensure_department(company, name):
    values = {
        "department_name": name,
        "company": company,
        "is_group": 0,
    }
    return ensure_doc("Department", name=f"{name} - NBG", values=values)


def ensure_designation(name):
    return ensure_doc("Designation", name=name, values={"designation_name": name})


def ensure_employment_type(name):
    return ensure_doc("Employment Type", name=name, values={"employee_type_name": name})


def ensure_gender(name):
    return ensure_doc("Gender", name=name, values={"gender": name})


def ensure_branch(name):
    return ensure_doc("Branch", name=name, values={"branch": name})


def ensure_holiday_list():
    data = {
        "holiday_list_name": "KR Public Holidays 2026 Demo",
        "country": "Korea, Republic of",
        "from_date": "2026-01-01",
        "to_date": "2026-12-31",
        "sample_holidays": [
            {"description": "신정", "holiday_date": "2026-01-01"},
            {"description": "설날 전날", "holiday_date": "2026-02-16"},
            {"description": "설날", "holiday_date": "2026-02-17"},
            {"description": "설날 다음날", "holiday_date": "2026-02-18"},
            {"description": "삼일절", "holiday_date": "2026-03-01"},
            {"description": "삼일절 대체공휴일", "holiday_date": "2026-03-02"},
            {"description": "어린이날", "holiday_date": "2026-05-05"},
            {"description": "부처님오신날", "holiday_date": "2026-05-24"},
            {"description": "부처님오신날 대체공휴일", "holiday_date": "2026-05-25"},
            {"description": "현충일", "holiday_date": "2026-06-06"},
            {"description": "광복절", "holiday_date": "2026-08-15"},
            {"description": "광복절 대체공휴일", "holiday_date": "2026-08-17"},
            {"description": "추석 전날(검증 필요)", "holiday_date": "2026-09-23"},
            {"description": "추석(검증 필요)", "holiday_date": "2026-09-24"},
            {"description": "추석 다음날(검증 필요)", "holiday_date": "2026-09-25"},
            {"description": "개천절", "holiday_date": "2026-10-03"},
            {"description": "개천절 대체공휴일", "holiday_date": "2026-10-05"},
            {"description": "한글날", "holiday_date": "2026-10-09"},
            {"description": "성탄절", "holiday_date": "2026-12-25"},
        ],
    }

    values = {
        "holiday_list_name": data["holiday_list_name"],
        "from_date": data["from_date"],
        "to_date": data["to_date"],
        "country": data["country"],
    }
    holiday_list, created = ensure_doc("Holiday List", name=data["holiday_list_name"], values=values)
    existing = {
        row.holiday_date.strftime("%Y-%m-%d") if hasattr(row.holiday_date, "strftime") else str(row.holiday_date)
        for row in holiday_list.holidays
    }
    changed = False
    for item in data["sample_holidays"]:
        if item["holiday_date"] not in existing:
            holiday_list.append("holidays", {
                "holiday_date": item["holiday_date"],
                "description": item["description"],
            })
            changed = True
    if changed:
        holiday_list.save(ignore_permissions=True)
    return holiday_list, created or changed


def ensure_holiday_list_assignment(company, holiday_list_name):
    """Create a submitted Holiday List Assignment for the company.

    Required for Salary Slip validate (HRMS override uses tabHoliday List Assignment,
    not Company.default_holiday_list).
    """
    filters = {
        "applicable_for": "Company",
        "assigned_to": company,
        "holiday_list": holiday_list_name,
        "docstatus": ("<", 2),
    }
    if frappe.db.exists("Holiday List Assignment", filters):
        doc = frappe.get_doc("Holiday List Assignment", frappe.db.get_value("Holiday List Assignment", filters, "name"))
        if doc.docstatus == 0:
            doc.submit()
        return doc, False
    doc = frappe.new_doc("Holiday List Assignment")
    doc.applicable_for = "Company"
    doc.assigned_to = company
    doc.employee_company = company
    doc.holiday_list = holiday_list_name
    doc.from_date = "2026-01-01"
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc, True


def ensure_shift_type(holiday_list_name):
    values = {
        "start_time": "09:00:00",
        "end_time": "18:00:00",
        "holiday_list": holiday_list_name,
        "enable_auto_attendance": 0,
        "working_hours_calculation_based_on": "First Check-in and Last Check-out",
    }
    return ensure_doc("Shift Type", name="KR Standard Day Shift 09-18", values=values)


def ensure_leave_type(name, **extra):
    values = {"leave_type_name": name, **extra}
    return ensure_doc("Leave Type", name=name, values=values)


def build_demo_user_password() -> str:
    return os.environ.get("HRMS_DEMO_USER_PASSWORD") or secrets.token_urlsafe(18)


def ensure_user(email, first_name, last_name, role_profile=None):
    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
        created = False
    else:
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "enabled": 1,
            "send_welcome_email": 0,
            "user_type": "System User",
            "new_password": build_demo_user_password(),
        }).insert(ignore_permissions=True)
        created = True
    wanted_roles = {"HR Manager", "HR User", "Employee"}
    existing_roles = {r.role for r in user.roles}
    for role in wanted_roles - existing_roles:
        user.append("roles", {"role": role})
    user.save(ignore_permissions=True)
    return user, created


def ensure_employee(company, department, designation, user_email, first_name, last_name, gender, dob, doj, branch, custom):
    employee_name = f"{first_name} {last_name}"
    values = {
        "naming_series": "HR-EMP-",
        "first_name": first_name,
        "last_name": last_name,
        "gender": gender,
        "date_of_birth": dob,
        "date_of_joining": doj,
        "status": "Active",
        "company": company,
        "department": department,
        "designation": designation,
        "employment_type": "Full-time",
        "employment_type_kr": custom.get("employment_type_kr", "Regular"),
        "branch": branch,
        "prefered_email": user_email,
        "company_email": user_email,
        "user_id": user_email,
        "create_user_automatically": 0,
        "work_location_name": custom.get("work_location_name", "서울 본사"),
        "bank_name": custom.get("bank_name", "국민은행"),
        "bank_ac_no": custom.get("bank_ac_no", "110-0000-0000"),
        "bank_account_holder_name": custom.get("bank_account_holder_name", employee_name),
        "resident_zip_code": custom.get("resident_zip_code", "04524"),
        "road_address": custom.get("road_address", "서울특별시 중구 세종대로 110"),
        "rrn_masked": custom.get("rrn_masked", "900101-1******"),
        "cell_number": custom.get("cell_number", "010-0000-0000"),
    }
    filters = {"employee_name": employee_name, "company": company}
    doc, created = ensure_doc("Employee", filters=filters, values=values)
    return doc, created


def ensure_salary_components():
    component_map = {
        "Basic Pay": {"type": "Earning", "description": "기본급", "korea_component_category": "Ordinary Wage", "is_tax_applicable": 1},
        "Meal Allowance": {"type": "Earning", "description": "식대", "korea_component_category": "Allowance", "is_tax_applicable": 1},
        "Position Allowance": {"type": "Earning", "description": "직책수당", "korea_component_category": "Allowance", "is_tax_applicable": 1},
        "Overtime Allowance": {"type": "Earning", "description": "연장근로수당", "korea_component_category": "Allowance", "is_tax_applicable": 1},
        "Night Work Allowance": {"type": "Earning", "description": "야간근로수당", "korea_component_category": "Allowance", "is_tax_applicable": 1},
        "Holiday Work Allowance": {"type": "Earning", "description": "휴일근로수당", "korea_component_category": "Allowance", "is_tax_applicable": 1},
        "Unused Leave Payout": {"type": "Earning", "description": "미사용 연차수당", "korea_component_category": "Allowance", "is_tax_applicable": 1},
        "National Pension": {"type": "Deduction", "description": "국민연금", "korea_component_category": "Statutory Deduction", "exempted_from_income_tax": 1},
        "Health Insurance": {"type": "Deduction", "description": "건강보험", "korea_component_category": "Statutory Deduction", "exempted_from_income_tax": 1},
        "Long-term Care Insurance": {"type": "Deduction", "description": "장기요양보험", "korea_component_category": "Statutory Deduction", "exempted_from_income_tax": 1},
        "Employment Insurance": {"type": "Deduction", "description": "고용보험", "korea_component_category": "Statutory Deduction", "exempted_from_income_tax": 1},
        "Industrial Accident Insurance": {
            "type": "Deduction",
            "description": "산재보험(사업주 부담)",
            "korea_component_category": "Employer Statutory Contribution",
            "exempted_from_income_tax": 1,
            "is_company_contribution_only": 1,
        },
        "Income Tax": {"type": "Deduction", "description": "원천세", "korea_component_category": "Statutory Deduction", "exempted_from_income_tax": 0},
    }

    touched = []
    for name, values in component_map.items():
        payload = {
            "salary_component": name,
            **values,
        }
        doc, _ = ensure_doc("Salary Component", name=name, values=payload)
        touched.append(doc.name)
    return touched


def ensure_salary_structure(company):
    name = "KR Demo Salary Structure"
    earnings = [
        ("Basic Pay", 2800000),
        ("Meal Allowance", 200000),
        ("Position Allowance", 300000),
        ("Overtime Allowance", 150000),
    ]
    deductions = [
        ("National Pension", 126000),
        ("Health Insurance", 99260),
        ("Long-term Care Insurance", 9114),
        ("Employment Insurance", 25200),
        ("Income Tax", 45210),
    ]

    if frappe.db.exists("Salary Structure", name):
        doc = frappe.get_doc("Salary Structure", name)
        created = False
    else:
        doc = frappe.new_doc("Salary Structure")
        doc.name = name
        doc.company = company
        doc.is_active = "Yes"
        doc.currency = "KRW"
        doc.payroll_frequency = "Monthly"
        created = True

    doc.company = company
    doc.is_active = "Yes"
    doc.currency = "KRW"
    doc.payroll_frequency = "Monthly"
    doc.set("earnings", [])
    doc.set("deductions", [])

    for component, amount in earnings:
        doc.append("earnings", {"salary_component": component, "amount": amount})
    for component, amount in deductions:
        doc.append("deductions", {"salary_component": component, "amount": amount})

    if created:
        doc.insert(ignore_permissions=True)
        doc.submit()
    else:
        if doc.docstatus == 0:
            doc.submit()
    return doc, created


def ensure_salary_structure_assignment(employee, company, salary_structure, base=3450000, from_date="2026-01-01"):
    values = {
        "employee": employee,
        "salary_structure": salary_structure,
        "from_date": from_date,
        "company": company,
        "currency": "KRW",
        "base": base,
    }
    doc, created = ensure_doc(
        "Salary Structure Assignment",
        filters={"employee": employee, "salary_structure": salary_structure, "docstatus": ("<", 2)},
        values=values,
    )
    # SSA must be submitted for Salary Slip lookup to work
    if doc.docstatus == 0:
        doc.submit()
    return doc, created


def ensure_demo_payroll_closing_draft(company):
    """Seed a positive draft row that the read-only payroll closing worklist can see.

    This is demo/runtime seed data only. It creates a draft ``Korea Payroll
    Closing Draft`` row so Gate 10 can prove the existing read-only worklist path
    with positive scoped rows. It does not submit, approve, send, call providers,
    or create payroll documents.
    """

    company_name = _require_text(company, "company")
    workplace = "서울 본사"
    period_start = "2026-05-01"
    period_end = "2026-05-31"
    session_name = "KPCS-DEMO-2026-05-SEOUL-HQ"
    draft_name = "KPCD-DEMO-2026-05-SEOUL-HQ"
    source_payroll_entry = "KR-DEMO-PAYROLL-ENTRY-2026-05"
    audit_preview = {
        "runtime_action": "preview_only",
        "requires_runtime_apply": False,
        "company": company_name,
        "workplace": workplace,
        "period_start": period_start,
        "period_end": period_end,
        "blocker_codes": ["attendance_not_ready", "expense_settlement_not_ready"],
    }
    session = {
        "contract_type": "korea_payroll_closing_session_v1",
        "name": session_name,
        "company": company_name,
        "workplace": workplace,
        "period_start": period_start,
        "period_end": period_end,
        "status": "blocked",
        "blockers": [
            {
                "code": "attendance_not_ready",
                "severity": "blocking",
                "message": "Demo attendance remains open for payroll-close review.",
            },
            {
                "code": "expense_settlement_not_ready",
                "severity": "blocking",
                "message": "Demo expense claim remains unsettled for payroll-close review.",
            },
        ],
        "next_actions": [
            {
                "action": "review_demo_blockers",
                "label": "Review demo payroll closing blockers",
                "requires_runtime_apply": False,
            }
        ],
        "readiness_cards": [
            {
                "key": "attendance",
                "label": "Attendance",
                "state": "blocked",
                "summary": "Demo attendance blocker requires human review.",
            },
            {
                "key": "expense_settlement",
                "label": "Expense Settlement",
                "state": "blocked",
                "summary": "Demo expense settlement blocker requires human review.",
            },
        ],
        "payroll_artifacts": {
            "payroll_entry": source_payroll_entry,
            "salary_slip_count": 2,
        },
        "audit_preview": audit_preview,
        "requires_human_approval": True,
        "ai_role": "assistant_only",
    }
    values = {
        "company": company_name,
        "workplace": workplace,
        "period_start": period_start,
        "period_end": period_end,
        "status": "draft_pending_human_approval",
        "source_payroll_entry": source_payroll_entry,
        "approver": "demo.hr.manager@node.pe.kr",
        "source_session_contract_type": "korea_payroll_closing_session_v1",
        "mutation_boundary": "draft_only_no_submit_no_approve_no_send",
        "requires_human_approval": True,
        "ai_role": "assistant_only",
        "docstatus": 0,
        "payload": json.dumps({"session": session}, ensure_ascii=False, sort_keys=True),
        "audit_preview": json.dumps(audit_preview, ensure_ascii=False, sort_keys=True),
    }
    doc, _created = ensure_doc(
        "Korea Payroll Closing Draft",
        name=draft_name,
        filters={
            "company": company_name,
            "workplace": workplace,
            "period_start": period_start,
            "period_end": period_end,
            "status": "draft_pending_human_approval",
            "docstatus": 0,
        },
        values=values,
        ignore_links=True,
        update_existing=False,
    )
    return {
        "contract_type": "korea_demo_payroll_closing_draft_seed_v1",
        "runtime_action": "demo_seed_only",
        "requires_runtime_apply": False,
        "mutation_boundary": "demo_seed_idempotent_draft_only_no_submit_no_approve_no_send_no_provider_call",
        "requires_human_approval": True,
        "ai_role": "assistant_only",
        "company": company_name,
        "draft_rows": [
            {
                "doctype": "Korea Payroll Closing Draft",
                "name": doc.name,
                "company": company_name,
                "workplace": _document_value(doc, "workplace", workplace),
                "period_start": str(_document_value(doc, "period_start", period_start)),
                "period_end": str(_document_value(doc, "period_end", period_end)),
                "status": _document_value(doc, "status", "draft_pending_human_approval"),
                "docstatus": _document_value(doc, "docstatus", 0),
                "runtime_visible_via": "payroll_closing_worklist_runtime_api",
            }
        ],
    }


def ensure_demo_blocker_transactions(company, employees):
    """Seed realistic blocker-generating rows for the Korea payroll closing demo.

    These rows are intentionally unsubmitted/draft operational data. They make the
    operator worklist visibly blocked without submitting payroll, approving
    expenses, sending messages, or calling external providers.
    """
    if not isinstance(company, str) or not company.strip():
        raise ValueError("company must be a non-empty string")
    employee_list = list(employees or [])
    if len(employee_list) < 2:
        raise ValueError("at least two demo employees are required for blocker seed scenarios")

    hq_employee = employee_list[0]
    store_employee = employee_list[1]
    hq_name = _employee_name(hq_employee)
    store_name = _employee_name(store_employee)
    hq_workplace = _employee_workplace(hq_employee)
    store_workplace = _employee_workplace(store_employee)
    company_name = company.strip()

    overtime_type_name = "KR Demo Overtime Review"
    expense_type_name = "KR Demo Meal Transport"
    ensure_doc(
        "Overtime Type",
        name=overtime_type_name,
        values={
            "overtime_salary_component": "Overtime Allowance",
            "maximum_overtime_hours_allowed": 4,
            "overtime_calculation_method": "Fixed Hourly Rate",
            "hourly_rate": 70000,
            "standard_multiplier": 1.5,
            "applicable_for_weekend": 0,
            "applicable_for_public_holiday": 0,
        },
    )
    ensure_doc(
        "Expense Claim Type",
        name=expense_type_name,
        values={
            "expense_type": expense_type_name,
            "description": "Demo meal and transport expense used to show unsettled payroll closing blockers.",
            "accounts": [
                {
                    "company": company_name,
                    "default_account": "Administrative Expenses - NBG",
                }
            ],
        },
    )

    scenarios = [
        {
            "doctype": "Attendance",
            "name": "KR-DEMO-ATT-ABSENT-2026-05-15",
            "workplace": hq_workplace,
            "blocker_code": "attendance_not_ready",
            "description": "Absent attendance remains unsubmitted before payroll close.",
            "filters": {
                "company": company_name,
                "employee": hq_name,
                "attendance_date": "2026-05-15",
                "docstatus": 0,
            },
            "values": {
                "naming_series": "HR-ATT-.YYYY.-",
                "employee": hq_name,
                "company": company_name,
                "attendance_date": "2026-05-15",
                "status": "Absent",
                "working_hours": 0,
                "docstatus": 0,
            },
        },
        {
            "doctype": "Overtime Slip",
            "name": "KR-DEMO-OT-PENDING-2026-05",
            "workplace": store_workplace,
            "blocker_code": "overtime_pending_review",
            "description": "Overtime slip remains draft for operator review before payroll close.",
            "filters": {
                "company": company_name,
                "employee": store_name,
                "posting_date": "2026-05-31",
                "start_date": "2026-05-01",
                "end_date": "2026-05-31",
                "docstatus": 0,
            },
            "values": {
                "employee": store_name,
                "company": company_name,
                "posting_date": "2026-05-31",
                "start_date": "2026-05-01",
                "end_date": "2026-05-31",
                "total_overtime_duration": 2.5,
                "docstatus": 0,
                "overtime_details": [
                    {
                        "date": "2026-05-22",
                        "overtime_type": overtime_type_name,
                        "overtime_duration": 2.5,
                        "standard_working_hours": 8,
                    }
                ],
            },
        },
        {
            "doctype": "Expense Claim",
            "name": "KR-DEMO-EXP-UNSETTLED-2026-05",
            "workplace": store_workplace,
            "blocker_code": "expense_settlement_not_ready",
            "description": "Expense claim remains draft/unsettled before payroll close.",
            "filters": {
                "company": company_name,
                "employee": store_name,
                "posting_date": "2026-05-28",
                "approval_status": "Draft",
                "docstatus": 0,
            },
            "values": {
                "naming_series": "HR-EXP-.YYYY.-",
                "employee": store_name,
                "company": company_name,
                "posting_date": "2026-05-28",
                "approval_status": "Draft",
                "currency": "KRW",
                "exchange_rate": 1,
                "total_claimed_amount": 86000,
                "total_sanctioned_amount": 0,
                "is_paid": 0,
                "docstatus": 0,
                "expenses": [
                    {
                        "expense_date": "2026-05-27",
                        "expense_type": expense_type_name,
                        "description": "Payroll-close demo unsettled meal and transport claim",
                        "amount": 86000,
                        "sanctioned_amount": 0,
                    }
                ],
            },
        },
    ]

    blocker_rows = []
    for scenario in scenarios:
        values = dict(scenario["values"])
        doc, _created = ensure_doc(
            scenario["doctype"],
            name=scenario["name"],
            filters=scenario.get("filters"),
            values=values,
        )
        blocker_rows.append(
            {
                "doctype": scenario["doctype"],
                "name": doc.name,
                "company": company_name,
                "workplace": scenario["workplace"],
                "employee": values["employee"],
                "docstatus": values["docstatus"],
                "blocker_code": scenario["blocker_code"],
                "description": scenario["description"],
            }
        )

    return {
        "contract_type": "korea_demo_blocker_seed_v1",
        "runtime_action": "demo_seed_only",
        "requires_runtime_apply": False,
        "mutation_boundary": "demo_seed_idempotent_no_submit_no_approve_no_send_no_provider_call",
        "requires_human_approval": True,
        "ai_role": "assistant_only",
        "company": company_name,
        "blocker_rows": blocker_rows,
    }


# ---------------------------------------------------------------------------
# Wave 4 — Extended employee roster (8 new employees)
# ---------------------------------------------------------------------------

#: Deterministic list of 8 additional employees (총 10명 포함 기존 2명)
#: 가나다순 정렬 (last_name + first_name 기준)
EXTENDED_EMPLOYEE_SPECS = [
    # ── 서울 본사 / 본부지원 / 인사 ───────────────────────────────────
    {
        "user": "jisoo.kang@nodebot.kr",
        "first_name": "지수",
        "last_name": "강",
        "gender": "Female",
        "dob": "1990-05-20",
        "doj": "2016-03-01",   # 10년차 → 연차 19일
        "department": "인사 - NBG",
        "designation": "HR Specialist",
        "branch": "서울 본사",
        "base": 4200000,
        "custom": {
            "employment_type_kr": "Regular",
            "work_location_name": "서울 본사",
            "bank_name": "우리은행",
            "bank_ac_no": "1002-000-111111",
            "bank_account_holder_name": "강지수",
            "resident_zip_code": "04524",
            "road_address": "서울특별시 중구 세종대로 110",
            "rrn_masked": "900520-2******",
            "cell_number": "010-3001-3001",
        },
        # 연차 시뮬레이션: 10년차 → 15+4 = 19일
        "annual_leave_days": 19,
        "attendance_rate": 0.95,  # 정상 출근
    },
    {
        "user": "minjun.kim@nodebot.kr",
        "first_name": "민준",
        "last_name": "김",
        "gender": "Male",
        "dob": "1998-11-10",
        "doj": "2025-11-01",   # 1년 미만 → 월차 적용
        "department": "본부지원 - NBG",
        "designation": "Staff",
        "branch": "서울 본사",
        "base": 2700000,
        "custom": {
            "employment_type_kr": "Regular",
            "work_location_name": "서울 본사",
            "bank_name": "카카오뱅크",
            "bank_ac_no": "3333-00-2222222",
            "bank_account_holder_name": "김민준",
            "resident_zip_code": "04524",
            "road_address": "서울특별시 중구 세종대로 110",
            "rrn_masked": "981110-1******",
            "cell_number": "010-3002-3002",
        },
        # 1년 미만 → 월차 (입사 후 매월 1일 발생, 최대 11일)
        "annual_leave_days": 6,   # 6개월치 월차
        "attendance_rate": 0.88,  # 출근률 88%
    },
    {
        "user": "sooyeon.kim@nodebot.kr",
        "first_name": "수연",
        "last_name": "김",
        "gender": "Female",
        "dob": "1993-08-22",
        "doj": "2021-04-01",   # 5년차 → 연차 17일
        "department": "본부지원 - NBG",
        "designation": "Senior Staff",
        "branch": "서울 본사",
        "base": 3800000,
        "custom": {
            "employment_type_kr": "Regular",
            "work_location_name": "서울 본사",
            "bank_name": "국민은행",
            "bank_ac_no": "110-0003-3333",
            "bank_account_holder_name": "김수연",
            "resident_zip_code": "04524",
            "road_address": "서울특별시 중구 세종대로 110",
            "rrn_masked": "930822-2******",
            "cell_number": "010-3003-3003",
        },
        # 5년차 → 15+2 = 17일
        "annual_leave_days": 17,
        "attendance_rate": 0.95,
    },
    # ── 강남 매장 / 매장운영 ─────────────────────────────────────────
    {
        "user": "dongwoo.lim@nodebot.kr",
        "first_name": "동우",
        "last_name": "임",
        "gender": "Male",
        "dob": "2000-03-05",
        "doj": "2026-02-01",   # 1년 미만 신입
        "department": "매장운영 - NBG",
        "designation": "Crew",
        "branch": "강남 매장",
        "base": 2500000,
        "custom": {
            "employment_type_kr": "Part-time",
            "work_location_name": "강남 매장",
            "bank_name": "신한은행",
            "bank_ac_no": "110-0444-4444",
            "bank_account_holder_name": "임동우",
            "resident_zip_code": "06134",
            "road_address": "서울특별시 강남구 테헤란로 152",
            "rrn_masked": "000305-1******",
            "cell_number": "010-3004-3004",
        },
        "annual_leave_days": 3,   # 3개월치 월차
        "attendance_rate": 0.75,  # 75% — 80% 룰 트리거 케이스
    },
    {
        "user": "hyunah.jung@nodebot.kr",
        "first_name": "현아",
        "last_name": "정",
        "gender": "Female",
        "dob": "1995-12-30",
        "doj": "2022-09-01",
        "department": "매장운영 - NBG",
        "designation": "Store Supervisor",
        "branch": "강남 매장",
        "base": 3200000,
        "custom": {
            "employment_type_kr": "Regular",
            "work_location_name": "강남 매장",
            "bank_name": "하나은행",
            "bank_ac_no": "200-0555-5555",
            "bank_account_holder_name": "정현아",
            "resident_zip_code": "06134",
            "road_address": "서울특별시 강남구 테헤란로 152",
            "rrn_masked": "951230-2******",
            "cell_number": "010-3005-3005",
        },
        "annual_leave_days": 15,
        "attendance_rate": 0.95,
    },
    # ── 부산 지사 / 영업 / 관리 ─────────────────────────────────────
    {
        "user": "seojun.choi@nodebot.kr",
        "first_name": "서준",
        "last_name": "최",
        "gender": "Male",
        "dob": "1988-06-15",
        "doj": "2015-07-01",   # 10년차 → 19일
        "department": "영업 - NBG",
        "designation": "Sales Manager",
        "branch": "부산 지사",
        "base": 4500000,
        "custom": {
            "employment_type_kr": "Regular",
            "work_location_name": "부산 지사",
            "bank_name": "부산은행",
            "bank_ac_no": "201-0666-6666",
            "bank_account_holder_name": "최서준",
            "resident_zip_code": "47011",
            "road_address": "부산광역시 동구 중앙대로 206",
            "rrn_masked": "880615-1******",
            "cell_number": "010-3006-3006",
        },
        "annual_leave_days": 19,
        "attendance_rate": 0.95,
    },
    {
        "user": "yujin.han@nodebot.kr",
        "first_name": "유진",
        "last_name": "한",
        "gender": "Female",
        "dob": "1997-04-18",
        "doj": "2026-03-01",   # 1년 미만 신입
        "department": "영업 - NBG",
        "designation": "Sales Staff",
        "branch": "부산 지사",
        "base": 2600000,
        "custom": {
            "employment_type_kr": "Regular",
            "work_location_name": "부산 지사",
            "bank_name": "국민은행",
            "bank_ac_no": "110-0777-7777",
            "bank_account_holder_name": "한유진",
            "resident_zip_code": "47011",
            "road_address": "부산광역시 동구 중앙대로 206",
            "rrn_masked": "970418-2******",
            "cell_number": "010-3007-3007",
        },
        "annual_leave_days": 2,   # 2개월치 월차
        "attendance_rate": 0.88,
    },
    {
        "user": "juho.oh@nodebot.kr",
        "first_name": "주호",
        "last_name": "오",
        "gender": "Male",
        "dob": "1991-09-27",
        "doj": "2021-01-04",   # 5년차 → 17일
        "department": "관리 - NBG",
        "designation": "Admin Manager",
        "branch": "부산 지사",
        "base": 3600000,
        "custom": {
            "employment_type_kr": "Regular",
            "work_location_name": "부산 지사",
            "bank_name": "신한은행",
            "bank_ac_no": "140-0888-8888",
            "bank_account_holder_name": "오주호",
            "resident_zip_code": "47011",
            "road_address": "부산광역시 동구 중앙대로 206",
            "rrn_masked": "910927-1******",
            "cell_number": "010-3008-3008",
        },
        "annual_leave_days": 17,
        "attendance_rate": 0.95,
    },
]

# Wave 4 departments (5 new)
WAVE4_DEPARTMENTS = ["매장운영", "본부지원", "영업", "관리", "인사"]

# Wave 4 branches (1 new, total 3)
WAVE4_BRANCHES = ["부산 지사"]

# Wave 4 designations
WAVE4_DESIGNATIONS = [
    "HR Specialist", "Senior Staff", "Staff", "Crew",
    "Sales Manager", "Sales Staff", "Admin Manager",
]


# ---------------------------------------------------------------------------
# Wave 4 — Attendance seeding (3 months: 2026-03 ~ 2026-05)
# ---------------------------------------------------------------------------

_PUBLIC_HOLIDAYS_2026 = {
    "2026-03-01",  # 삼일절
    "2026-03-02",  # 삼일절 대체공휴일
    "2026-05-05",  # 어린이날
}

# Attendance status weights per attendance_rate bucket
_STATUS_WEIGHTS = {
    # (status, probability_weight)
    0.95: [("Present", 85), ("Half Day", 5), ("Work From Home", 5), ("On Leave", 5)],
    0.88: [("Present", 75), ("Half Day", 5), ("Work From Home", 3), ("On Leave", 12), ("Absent", 5)],
    0.75: [("Present", 60), ("Half Day", 5), ("Work From Home", 2), ("On Leave", 10), ("Absent", 23)],
}


def _get_status_weights(rate: float) -> list:
    """Return the closest pre-defined status weight bucket."""
    thresholds = sorted(_STATUS_WEIGHTS.keys())
    chosen = thresholds[0]
    for t in thresholds:
        if rate >= t - 0.05:
            chosen = t
    return _STATUS_WEIGHTS[chosen]


def _is_working_day(d: date) -> bool:
    """Return True if date is a weekday and not a public holiday."""
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    if d.strftime("%Y-%m-%d") in _PUBLIC_HOLIDAYS_2026:
        return False
    return True


def _iter_month_working_days(year: int, month: int):
    """Yield all working dates in the given month."""
    first = date(year, month, 1)
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    d = first
    while d <= last:
        if _is_working_day(d):
            yield d
        d += timedelta(days=1)


def _weighted_choice(weights: list, rng: random.Random) -> str:
    """Choose a status string using weighted random."""
    population = []
    for status, weight in weights:
        population.extend([status] * weight)
    return rng.choice(population)


def _att_name(employee_name: str, att_date: date) -> str:
    """Build a deterministic Attendance record name for idempotency."""
    safe = employee_name.replace(" ", "-")
    return f"KR-ATT-{safe}-{att_date.strftime('%Y%m%d')}"


def ensure_attendance_for_employee(employee_doc, company: str, months: list[tuple[int, int]]):
    """Seed Attendance records for one employee across given months.

    Args:
        employee_doc: Frappe Employee document
        company: company name string
        months: list of (year, month) tuples, e.g. [(2026,3),(2026,4),(2026,5)]

    Returns:
        dict with count of created/skipped records
    """
    emp_name = _employee_name(employee_doc)
    rate = getattr(employee_doc, "_demo_attendance_rate", 0.95)
    rng = random.Random(f"att-{emp_name}")  # deterministic per employee
    weights = _get_status_weights(rate)

    doj_str = getattr(employee_doc, "date_of_joining", None)
    doj = getdate(doj_str) if doj_str else date(2020, 1, 1)

    created = 0
    skipped = 0

    for year, month in months:
        for d in _iter_month_working_days(year, month):
            if d < doj:
                continue  # employee hadn't joined yet
            record_name = _att_name(emp_name, d)
            if frappe.db.exists("Attendance", record_name):
                skipped += 1
                continue

            status = _weighted_choice(weights, rng)
            working_hours = 8.0 if status in ("Present", "Work From Home") else (4.0 if status == "Half Day" else 0.0)

            att = frappe.get_doc({
                "doctype": "Attendance",
                "name": record_name,
                "__newname": record_name,
                "naming_series": "HR-ATT-.YYYY.-",
                "employee": emp_name,
                "company": company,
                "attendance_date": d.strftime("%Y-%m-%d"),
                "status": status,
                "working_hours": working_hours,
                # NOTE: docstatus is NOT set here; frappe.insert() ignores it.
                # We call .submit() separately below to reach docstatus=1.
            })
            try:
                att.insert(ignore_permissions=True)
                att.submit()  # promotes to docstatus=1 so payroll closing can read it
                created += 1
            except Exception:
                skipped += 1

    return {"created": created, "skipped": skipped}


# ---------------------------------------------------------------------------
# Wave 4 — Leave allocation seeding
# ---------------------------------------------------------------------------

def ensure_leave_allocation(employee_name: str, company: str, leave_type: str, leave_days: int, year: int = 2026):
    """Seed an Annual Leave allocation for the given employee/year.

    Idempotent: if an allocation already exists with docstatus < 2, skip.
    """
    from_date = f"{year}-01-01"
    to_date = f"{year}-12-31"
    filters = {
        "employee": employee_name,
        "leave_type": leave_type,
        "from_date": from_date,
        "to_date": to_date,
        "docstatus": ("<", 2),
    }
    if frappe.db.exists("Leave Allocation", filters):
        return None, False

    alloc = frappe.get_doc({
        "doctype": "Leave Allocation",
        "employee": employee_name,
        "leave_type": leave_type,
        "from_date": from_date,
        "to_date": to_date,
        "new_leaves_allocated": leave_days,
        "company": company,
        # NOTE: docstatus is NOT set here; frappe.insert() ignores it.
        # We call .submit() separately below to reach docstatus=1.
    })
    try:
        alloc.insert(ignore_permissions=True)
        alloc.submit()  # promotes to docstatus=1 so leave balance is active
        return alloc, True
    except Exception:
        return None, False


# ---------------------------------------------------------------------------
# Wave 4 — Payroll Entry Draft seeding (3 months × 3 worksites)
# ---------------------------------------------------------------------------

#: (period_year_month, branch, draft_name_suffix)
WAVE4_PAYROLL_DRAFTS = [
    ("2026-03", "서울 본사",  "KPCD-DEMO-2026-03-SEOUL-HQ"),
    ("2026-04", "강남 매장", "KPCD-DEMO-2026-04-GANGNAM"),
    ("2026-05", "부산 지사",  "KPCD-DEMO-2026-05-BUSAN"),
]


def ensure_wave4_payroll_closing_drafts(company: str):
    """Seed 3 monthly payroll-close drafts across 3 branches.

    Each draft is a Korea Payroll Closing Draft in 'draft_pending_human_approval'
    state — visible on the closing worklist but NOT submitted/approved.
    """
    company_name = _require_text(company, "company")
    seeded = []

    for ym, branch, draft_name in WAVE4_PAYROLL_DRAFTS:
        year, month = ym.split("-")
        import calendar as _cal
        last_day = _cal.monthrange(int(year), int(month))[1]
        period_start = f"{ym}-01"
        period_end = f"{ym}-{last_day:02d}"

        audit_preview = {
            "runtime_action": "preview_only",
            "requires_runtime_apply": False,
            "company": company_name,
            "workplace": branch,
            "period_start": period_start,
            "period_end": period_end,
        }
        values = {
            "company": company_name,
            "workplace": branch,
            "period_start": period_start,
            "period_end": period_end,
            "status": "draft_pending_human_approval",
            "source_payroll_entry": f"KR-DEMO-PE-{ym}-{branch[:2]}",
            "approver": "demo.hr.manager@node.pe.kr",
            "source_session_contract_type": "korea_payroll_closing_session_v1",
            "mutation_boundary": "draft_only_no_submit_no_approve_no_send",
            "requires_human_approval": True,
            "ai_role": "assistant_only",
            "docstatus": 0,
            "payload": json.dumps({"session": {
                "contract_type": "korea_payroll_closing_session_v1",
                "name": draft_name,
                "company": company_name,
                "workplace": branch,
                "period_start": period_start,
                "period_end": period_end,
                "status": "draft",
            }}, ensure_ascii=False),
            "audit_preview": json.dumps(audit_preview, ensure_ascii=False),
        }
        doc, _created = ensure_doc(
            "Korea Payroll Closing Draft",
            name=draft_name,
            filters={
                "company": company_name,
                "workplace": branch,
                "period_start": period_start,
                "period_end": period_end,
                "docstatus": 0,
            },
            values=values,
            ignore_links=True,
            update_existing=False,
        )
        seeded.append({
            "name": doc.name,
            "period": ym,
            "branch": branch,
        })

    return seeded


# ---------------------------------------------------------------------------
# Wave 4 — main extension runner
# ---------------------------------------------------------------------------

def seed_korea_demo_wave4(company_name: str, holiday_list_name: str, salary_structure_name: str):
    """Seed Wave 4 additions: 8 employees, 3 branches/5 departments, attendance, leave, payroll drafts.

    All mutations are idempotent.  Call this AFTER the baseline seed (main/seed_korea_demo).

    Returns:
        dict summary of what was created/updated
    """
    log: dict = {
        "branches": [],
        "departments": [],
        "designations": [],
        "employees": [],
        "leave_allocations": [],
        "attendance": {},
        "payroll_drafts": [],
    }

    # 1. New branch
    for branch_name in WAVE4_BRANCHES:
        doc, created = ensure_branch(branch_name)
        log["branches"].append({"name": branch_name, "created": created})

    # 2. New departments
    for dept_name in WAVE4_DEPARTMENTS:
        doc, created = ensure_department(company_name, dept_name)
        log["departments"].append({"name": f"{dept_name} - NBG", "created": created})

    # 3. New designations
    for desg_name in WAVE4_DESIGNATIONS:
        doc, created = ensure_designation(desg_name)
        log["designations"].append({"name": desg_name, "created": created})

    # 4. New employees + leave types
    for spec in EXTENDED_EMPLOYEE_SPECS:
        user_email = spec["user"]
        ensure_user(user_email, spec["first_name"], spec["last_name"])

        emp_doc, emp_created = ensure_employee(
            company=company_name,
            department=spec["department"],
            designation=spec["designation"],
            user_email=user_email,
            first_name=spec["first_name"],
            last_name=spec["last_name"],
            gender=spec["gender"],
            dob=spec["dob"],
            doj=spec["doj"],
            branch=spec["branch"],
            custom=spec["custom"],
        )
        # Attach demo metadata needed by attendance seed
        emp_doc._demo_attendance_rate = spec.get("attendance_rate", 0.95)

        log["employees"].append({
            "name": emp_doc.name,
            "email": user_email,
            "created": emp_created,
            "attendance_rate": spec.get("attendance_rate", 0.95),
            "annual_leave_days": spec.get("annual_leave_days", 15),
        })

        # Salary structure assignment — use date_of_joining as from_date
        _emp_doj = str(emp_doc.date_of_joining) if emp_doc.date_of_joining else "2026-01-01"
        ensure_salary_structure_assignment(
            emp_doc.name,
            company_name,
            salary_structure_name,
            base=spec.get("base", 3000000),
            from_date=_emp_doj,
        )

        # Leave allocation (Annual Leave)
        alloc_doc, alloc_created = ensure_leave_allocation(
            emp_doc.name,
            company_name,
            "Annual Leave",
            spec.get("annual_leave_days", 15),
        )
        log["leave_allocations"].append({
            "employee": emp_doc.name,
            "days": spec.get("annual_leave_days", 15),
            "created": alloc_created,
        })

        # Attendance: 2026-03, 2026-04, 2026-05
        att_result = ensure_attendance_for_employee(
            emp_doc,
            company_name,
            [(2026, 3), (2026, 4), (2026, 5)],
        )
        log["attendance"][emp_doc.name] = att_result

    # 5. Wave 4 payroll closing drafts (3 months × 3 branches)
    payroll_drafts = ensure_wave4_payroll_closing_drafts(company_name)
    log["payroll_drafts"] = payroll_drafts

    return log


# ---------------------------------------------------------------------------
# Unified entry point (Wave 4)
# ---------------------------------------------------------------------------

def seed_korea_demo():
    """Full idempotent seed: baseline (Wave 1-3) + Wave 4 extensions.

    Run via:
        bench --site hrms.localhost execute \
            hrms.regional.south_korea.demo_seed.seed_korea_demo
    """
    created_list: list = []
    updated_list: list = []

    # ── Baseline (originally in main()) ─────────────────────────────────
    holiday_list, changed = ensure_holiday_list()
    (updated_list if changed else created_list).append(f"Holiday List::{holiday_list.name}")

    warehouse_type, warehouse_created = ensure_warehouse_type("Transit")
    (created_list if warehouse_created else updated_list).append(f"Warehouse Type::{warehouse_type.name}")

    company, company_created = ensure_company()
    (created_list if company_created else updated_list).append(f"Company::{company.name}")

    # Holiday List Assignment must be submitted so Salary Slip validation can find it
    hla, hla_created = ensure_holiday_list_assignment(company.name, holiday_list.name)
    (created_list if hla_created else updated_list).append(f"Holiday List Assignment::{hla.name}")

    for name in ["운영", "매장운영"]:
        doc, was_created = ensure_department(company.name, name)
        (created_list if was_created else updated_list).append(f"Department::{doc.name}")

    for name in ["HR Manager", "Store Supervisor"]:
        doc, was_created = ensure_designation(name)
        (created_list if was_created else updated_list).append(f"Designation::{doc.name}")

    for name in ["Full-time", "Part-time"]:
        doc, was_created = ensure_employment_type(name)
        (created_list if was_created else updated_list).append(f"Employment Type::{doc.name}")

    for name in ["Male", "Female"]:
        doc, was_created = ensure_gender(name)
        (created_list if was_created else updated_list).append(f"Gender::{doc.name}")

    for name in ["서울 본사", "강남 매장"]:
        doc, was_created = ensure_branch(name)
        (created_list if was_created else updated_list).append(f"Branch::{doc.name}")

    shift, shift_created = ensure_shift_type(holiday_list.name)
    (created_list if shift_created else updated_list).append(f"Shift Type::{shift.name}")

    for component_name in ensure_salary_components():
        updated_list.append(f"Salary Component::{component_name}")

    leave_configs = [
        ("Annual Leave", {"is_earned_leave": 1, "earned_leave_frequency": "Monthly", "is_carry_forward": 1, "maximum_carry_forwarded_leaves": 25}),
        ("Sick Leave", {"is_lwp": 0, "is_carry_forward": 0}),
        ("Family Event Leave", {"is_lwp": 0, "is_carry_forward": 0}),
    ]
    for leave_name, options in leave_configs:
        doc, was_created = ensure_leave_type(leave_name, **options)
        (created_list if was_created else updated_list).append(f"Leave Type::{doc.name}")

    ensure_user("demo.hr.manager@node.pe.kr", "Demo", "Manager")
    ensure_user("demo.store@node.pe.kr", "Demo", "Store")

    baseline_employees = [
        {
            "user": "demo.hr.manager@node.pe.kr",
            "first_name": "민지",
            "last_name": "김",
            "gender": "Female",
            "dob": "1992-03-15",
            "doj": "2024-03-01",
            "department": "운영 - NBG",
            "designation": "HR Manager",
            "branch": "서울 본사",
            "custom": {
                "employment_type_kr": "Regular",
                "work_location_name": "서울 본사",
                "bank_name": "국민은행",
                "bank_ac_no": "110-1234-5678",
                "bank_account_holder_name": "김민지",
                "resident_zip_code": "04524",
                "road_address": "서울특별시 중구 세종대로 110",
                "rrn_masked": "920315-2******",
                "cell_number": "010-1000-1000",
            },
        },
        {
            "user": "demo.store@node.pe.kr",
            "first_name": "현우",
            "last_name": "박",
            "gender": "Male",
            "dob": "1996-07-02",
            "doj": "2025-06-01",
            "department": "매장운영 - NBG",
            "designation": "Store Supervisor",
            "branch": "강남 매장",
            "custom": {
                "employment_type_kr": "Regular",
                "work_location_name": "강남 매장",
                "bank_name": "신한은행",
                "bank_ac_no": "140-2222-3333",
                "bank_account_holder_name": "박현우",
                "resident_zip_code": "06134",
                "road_address": "서울특별시 강남구 테헤란로 152",
                "rrn_masked": "960702-1******",
                "cell_number": "010-2000-2000",
            },
        },
    ]

    employee_docs = []
    employee_names = []
    for payload in baseline_employees:
        doc, was_created = ensure_employee(
            company=company.name,
            department=payload["department"],
            designation=payload["designation"],
            user_email=payload["user"],
            first_name=payload["first_name"],
            last_name=payload["last_name"],
            gender=payload["gender"],
            dob=payload["dob"],
            doj=payload["doj"],
            branch=payload["branch"],
            custom=payload["custom"],
        )
        employee_docs.append(doc)
        employee_names.append(doc.name)
        (created_list if was_created else updated_list).append(f"Employee::{doc.name}")

    blocker_seed = ensure_demo_blocker_transactions(company=company.name, employees=employee_docs)
    for row in blocker_seed["blocker_rows"]:
        updated_list.append(f"{row['doctype']}::{row['name']}")

    draft_seed = ensure_demo_payroll_closing_draft(company=company.name)
    for row in draft_seed["draft_rows"]:
        updated_list.append(f"{row['doctype']}::{row['name']}")

    structure, was_created = ensure_salary_structure(company.name)
    (created_list if was_created else updated_list).append(f"Salary Structure::{structure.name}")

    for employee in employee_names:
        # Use the employee's date_of_joining as from_date to avoid validation error
        emp_doc = frappe.get_doc("Employee", employee)
        doj = str(emp_doc.date_of_joining) if emp_doc.date_of_joining else "2026-01-01"
        doc, created_assignment = ensure_salary_structure_assignment(employee, company.name, structure.name, from_date=doj)
        (created_list if created_assignment else updated_list).append(f"Salary Structure Assignment::{doc.name}")

    # ── Wave 4 extension ─────────────────────────────────────────────────
    wave4_log = seed_korea_demo_wave4(
        company_name=company.name,
        holiday_list_name=holiday_list.name,
        salary_structure_name=structure.name,
    )

    frappe.db.commit()

    summary = {
        "wave": "4",
        "created_or_updated": created_list + updated_list,
        "company": company.name,
        "holiday_list": holiday_list.name,
        "shift_type": shift.name,
        "salary_structure": structure.name,
        "baseline_employees": employee_names,
        "wave4": wave4_log,
        "employee_count": len(employee_names) + len(wave4_log["employees"]),
        "branch_count": 3,
        "department_count": 7,
        "demo_blocker_seed": blocker_seed,
        "demo_payroll_closing_draft_seed": draft_seed,
        "demo_login": {
            "url": "http://hrms.localhost:8000/app",
            "username": "demo.hr.manager@node.pe.kr",
            "password": "DemoHRMS!2026",
        },
    }
    print(json.dumps(summary, ensure_ascii=False, default=str, indent=2))
    return summary


# ---------------------------------------------------------------------------
# Phase 2-A Demo Employee Roster (framework-free)
# ---------------------------------------------------------------------------

_DEMO_EMPLOYEE_ROSTER = [
    {
        "user": "demo.hr.manager@node.pe.kr",
        "first_name": "민지",
        "last_name": "김",
        "gender": "Female",
        "dob": "1992-03-15",
        "doj": "2024-03-01",
        "department": "운영",
        "designation": "HR Manager",
        "custom": {
            "employment_type_kr": "Regular",
            "work_location_name": "서울 본사",
            "cell_number": "010-1000-1000",
        },
    },
    {
        "user": "demo.store@node.pe.kr",
        "first_name": "현우",
        "last_name": "박",
        "gender": "Male",
        "dob": "1996-07-02",
        "doj": "2025-06-01",
        "department": "매장운영",
        "designation": "Store Supervisor",
        "custom": {
            "employment_type_kr": "Regular",
            "work_location_name": "강남 매장",
            "cell_number": "010-2000-2000",
        },
    },
    {
        "user": "demo.accounting@node.pe.kr",
        "first_name": "서연",
        "last_name": "이",
        "gender": "Female",
        "dob": "1990-11-28",
        "doj": "2023-01-02",
        "department": "경리",
        "designation": "Accountant",
        "custom": {
            "employment_type_kr": "Regular",
            "work_location_name": "서울 본사",
            "cell_number": "010-3000-3000",
        },
    },
    {
        "user": "demo.ops1@node.pe.kr",
        "first_name": "준혁",
        "last_name": "최",
        "gender": "Male",
        "dob": "1994-05-10",
        "doj": "2024-07-01",
        "department": "물류",
        "designation": "Operations Staff",
        "custom": {
            "employment_type_kr": "Fixed-term",
            "work_location_name": "부산 지사",
            "cell_number": "010-4000-4000",
        },
    },
    {
        "user": "demo.ops2@node.pe.kr",
        "first_name": "지수",
        "last_name": "한",
        "gender": "Female",
        "dob": "1998-02-14",
        "doj": "2025-03-01",
        "department": "물류",
        "designation": "Operations Staff",
        "custom": {
            "employment_type_kr": "Fixed-term",
            "work_location_name": "부산 지사",
            "cell_number": "010-5000-5000",
        },
    },
    {
        "user": "demo.parttime1@node.pe.kr",
        "first_name": "유진",
        "last_name": "오",
        "gender": "Female",
        "dob": "2000-08-20",
        "doj": "2026-01-15",
        "department": "매장운영",
        "designation": "Part-time Staff",
        "custom": {
            "employment_type_kr": "Part-time",
            "work_location_name": "강남 매장",
            "cell_number": "010-6000-6000",
        },
    },
    {
        "user": "demo.parttime2@node.pe.kr",
        "first_name": "도현",
        "last_name": "윤",
        "gender": "Male",
        "dob": "2001-04-05",
        "doj": "2026-02-01",
        "department": "매장운영",
        "designation": "Part-time Staff",
        "custom": {
            "employment_type_kr": "Part-time",
            "work_location_name": "강남 매장",
            "cell_number": "010-7000-7000",
        },
    },
    {
        "user": "demo.busan1@node.pe.kr",
        "first_name": "수빈",
        "last_name": "장",
        "gender": "Female",
        "dob": "1993-12-03",
        "doj": "2023-09-01",
        "department": "영업",
        "designation": "Sales Staff",
        "custom": {
            "employment_type_kr": "Regular",
            "work_location_name": "부산 지사",
            "cell_number": "010-8000-8000",
        },
    },
    {
        "user": "demo.busan2@node.pe.kr",
        "first_name": "태양",
        "last_name": "정",
        "gender": "Male",
        "dob": "1997-06-22",
        "doj": "2024-11-01",
        "department": "영업",
        "designation": "Sales Staff",
        "custom": {
            "employment_type_kr": "Fixed-term",
            "work_location_name": "부산 지사",
            "cell_number": "010-9000-9000",
        },
    },
    {
        "user": "demo.admin@node.pe.kr",
        "first_name": "하은",
        "last_name": "강",
        "gender": "Female",
        "dob": "1991-09-17",
        "doj": "2022-04-01",
        "department": "경영지원",
        "designation": "Admin Manager",
        "custom": {
            "employment_type_kr": "Regular",
            "work_location_name": "서울 본사",
            "cell_number": "010-1001-0001",
        },
    },
]


def build_demo_employee_roster() -> list[dict]:
    """데모 직원 명단 반환 — framework-free, 실제 DB mutation 없음.

    반환 목록:
    - 10명 이상의 한국 중소기업 페르소나
    - 3개 이상의 근무지
    - Regular / Fixed-term / Part-time 고용 형태 포함
    - 비밀번호 / 점수 / 위험도 등 민감 정보 미포함
    """
    import copy as _copy
    return [_copy.deepcopy(row) for row in _DEMO_EMPLOYEE_ROSTER]


# ---------------------------------------------------------------------------
# Phase 2-A Demo Browser Credential Handoff + Runtime Apply
# ---------------------------------------------------------------------------

_DEMO_BROWSER_USERNAME = "demo.hr.manager@node.pe.kr"
_DEMO_ALLOWED_USERNAMES = {_DEMO_BROWSER_USERNAME}


def build_demo_browser_credential_handoff() -> dict:
    """데모 브라우저 자격증명 핸드오프 dict 반환 — framework-free, 실제 mutation 없음.

    비밀번호나 점수 등 민감 정보를 포함하지 않습니다.
    """
    return {
        "contract_type": "korea_demo_browser_credential_handoff_v1",
        "runtime_action": "demo_credential_handoff_only",
        "requires_runtime_apply": False,
        "requires_human_approval": True,
        "ai_role": "assistant_only",
        "username": _DEMO_BROWSER_USERNAME,
        "employee_link_required": True,
        "password_env_var": "FRAPPE_BROWSER_PASSWORD",
        "mutation_boundary": "credential_handoff_only_no_payroll_submit_approve_send_provider_call",
        "note": "Call ensure_demo_browser_credential with human_approved=True to apply.",
    }


def ensure_demo_browser_credential(
    *,
    password: str,
    human_approved: bool = False,
    username: str = _DEMO_BROWSER_USERNAME,
) -> dict:
    """데모 브라우저 자격증명 적용 — human_approved=True 게이트 이후에만 실행.

    frappe.db.exists()로 사용자 및 활성 직원 연결 여부를 검사합니다.
    """
    if not human_approved:
        raise ValueError("human_approved must be True before credential runtime apply")

    if username not in _DEMO_ALLOWED_USERNAMES:
        raise ValueError(
            f"username must be the approved demo browser user: {_DEMO_BROWSER_USERNAME!r}"
        )

    # Verify Frappe user exists
    if not frappe.db.exists("User", username):
        raise ValueError(f"Frappe user {username!r} does not exist")

    # Verify active employee linked to this user
    if not frappe.db.exists("Employee", {"user_id": username, "status": "Active"}):
        raise ValueError(f"active employee linked to {username} is required")

    # Apply credential
    update_password(username, password)

    return {
        "contract_type": "korea_demo_browser_credential_runtime_apply_v1",
        "runtime_action": "demo_credential_runtime_apply",
        "requires_runtime_apply": True,
        "requires_human_approval": True,
        "human_approval_verified": True,
        "ai_role": "assistant_only",
        "username": username,
        "employee_link_verified": True,
        "credential_ready_for_browser_verifier": True,
        "password_env_var": "FRAPPE_BROWSER_PASSWORD",
        "mutation_boundary": "credential_only_no_payroll_submit_approve_send_provider_call",
    }


# update_password reference — overrideable in tests
try:
    from frappe.utils.password import update_password
except Exception:
    def update_password(username: str, password: str) -> None:  # type: ignore[misc]
        """Stub for non-Frappe environments."""
        pass


# ---------------------------------------------------------------------------
# Backward-compatible entry point
# ---------------------------------------------------------------------------

def main():
    """Legacy entry point.  Delegates to seed_korea_demo()."""
    seed_korea_demo()


if __name__ == "__main__":
    main()
