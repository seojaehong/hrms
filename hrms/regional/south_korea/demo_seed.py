import json
import os
import secrets
from pathlib import Path

import frappe
from frappe.utils import getdate
try:
    from frappe.utils.password import update_password
except ImportError:  # no-bench direct tests provide a minimal frappe stub
    update_password = None


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
    existing = {row.holiday_date.strftime('%Y-%m-%d') if hasattr(row.holiday_date, 'strftime') else str(row.holiday_date) for row in holiday_list.holidays}
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


DEMO_BROWSER_USERNAME = "demo.hr.manager@node.pe.kr"
DEMO_BROWSER_PASSWORD_ENV_VAR = "FRAPPE_BROWSER_PASSWORD"


def build_demo_user_password() -> str:
    return os.environ.get("HRMS_DEMO_USER_PASSWORD") or secrets.token_urlsafe(18)


def build_demo_browser_credential_handoff(username=DEMO_BROWSER_USERNAME, password_env_var=DEMO_BROWSER_PASSWORD_ENV_VAR):
    username = _require_text(username, "username")
    password_env_var = _require_text(password_env_var, "password_env_var")
    return {
        "contract_type": "korea_demo_browser_credential_handoff_v1",
        "runtime_action": "demo_credential_handoff_only",
        "requires_runtime_apply": False,
        "username": username,
        "employee_link_required": True,
        "password_env_var": password_env_var,
        "browser_verifier_command": "FRAPPE_BROWSER_USERNAME=<username> FRAPPE_BROWSER_PASSWORD=<secret> node scripts/verify_korea_payroll_closing_browser_runtime.mjs --base-url http://hrms.localhost:8000 --company <company>",
        "mutation_boundary": "credential_handoff_only_no_payroll_submit_approve_send_provider_call",
        "requires_human_approval": True,
        "ai_role": "assistant_only",
    }


def ensure_demo_browser_credential(username=DEMO_BROWSER_USERNAME, password=None, human_approved=False):
    """Set the employee-linked demo user's browser password without reporting it.

    This is a narrow demo-credential runtime apply helper for authenticated browser
    verification. It does not submit payroll, approve drafts, send messages, call
    providers, or create payroll documents. The credential side effect requires
    explicit human approval before the password update boundary.
    """

    username = _require_text(username, "username")
    if username != DEMO_BROWSER_USERNAME:
        raise ValueError("username must be the approved demo browser user")
    if human_approved is not True:
        raise ValueError("human_approved must be True before credential runtime apply")
    password = password if password is not None else os.environ.get(DEMO_BROWSER_PASSWORD_ENV_VAR)
    password = _require_text(password, "password")
    if not frappe.db.exists("User", username):
        raise ValueError(f"demo browser user {username} is required")
    employee_filters = {"user_id": username, "status": "Active"}
    if not frappe.db.exists("Employee", employee_filters):
        raise ValueError(f"active employee linked to {username} is required")
    if update_password is None:
        raise RuntimeError("frappe.utils.password.update_password is unavailable in this runtime")
    update_password(username, password)
    return {
        "contract_type": "korea_demo_browser_credential_runtime_apply_v1",
        "runtime_action": "demo_credential_runtime_apply",
        "requires_runtime_apply": False,
        "username": username,
        "employee_link_verified": True,
        "credential_ready_for_browser_verifier": True,
        "password_env_var": DEMO_BROWSER_PASSWORD_ENV_VAR,
        "human_approval_verified": True,
        "mutation_boundary": "credential_only_no_payroll_submit_approve_send_provider_call",
        "requires_human_approval": True,
        "ai_role": "assistant_only",
    }


def ensure_user(email, first_name, last_name, roles=None):
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
    wanted_roles = set(roles or {"Employee"})
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
        "employment_type": custom.get("employment_type", "Full-time"),
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
    else:
        doc.save(ignore_permissions=True)
    return doc, created


def ensure_salary_structure_assignment(employee, company, salary_structure):
    name = f"{employee} - {salary_structure}"
    values = {
        "employee": employee,
        "salary_structure": salary_structure,
        "from_date": "2026-01-01",
        "company": company,
        "currency": "KRW",
        "base": 3450000,
    }
    return ensure_doc("Salary Structure Assignment", filters={"employee": employee, "salary_structure": salary_structure, "docstatus": ("<", 2)}, values=values)


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


def build_demo_employee_roster():
    """Return Korea SME/franchise demo employee personas for runtime seeding.

    This fixture is intentionally static and secret-free. It enriches the demo
    tenant with mixed employment types and workplaces without adding payroll
    submission, approval, messaging, provider, or AI scoring behavior.
    """

    return [
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
                "employment_type": "Full-time",
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
                "employment_type": "Full-time",
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
        {
            "user": "demo.ops.lead@node.pe.kr",
            "first_name": "서연",
            "last_name": "이",
            "gender": "Female",
            "dob": "1988-11-20",
            "doj": "2023-01-16",
            "department": "운영 - NBG",
            "designation": "Operations Lead",
            "branch": "서울 본사",
            "custom": {
                "employment_type": "Full-time",
                "employment_type_kr": "Regular",
                "work_location_name": "서울 본사",
                "bank_name": "우리은행",
                "bank_ac_no": "100-3000-3000",
                "bank_account_holder_name": "이서연",
                "resident_zip_code": "04524",
                "road_address": "서울특별시 중구 세종대로 110",
                "rrn_masked": "881120-2******",
                "cell_number": "010-3000-3000",
            },
        },
        {
            "user": "demo.payroll@node.pe.kr",
            "first_name": "준호",
            "last_name": "최",
            "gender": "Male",
            "dob": "1990-05-08",
            "doj": "2024-09-02",
            "department": "운영 - NBG",
            "designation": "Payroll Specialist",
            "branch": "서울 본사",
            "custom": {
                "employment_type": "Full-time",
                "employment_type_kr": "Fixed-term",
                "work_location_name": "서울 본사",
                "bank_name": "하나은행",
                "bank_ac_no": "160-4000-4000",
                "bank_account_holder_name": "최준호",
                "resident_zip_code": "04524",
                "road_address": "서울특별시 중구 세종대로 110",
                "rrn_masked": "900508-1******",
                "cell_number": "010-4000-4000",
            },
        },
        {
            "user": "demo.gangnam.ft@node.pe.kr",
            "first_name": "하은",
            "last_name": "정",
            "gender": "Female",
            "dob": "1998-02-11",
            "doj": "2025-02-03",
            "department": "매장운영 - NBG",
            "designation": "Store Staff",
            "branch": "강남 매장",
            "custom": {
                "employment_type": "Full-time",
                "employment_type_kr": "Regular",
                "work_location_name": "강남 매장",
                "bank_name": "카카오뱅크",
                "bank_ac_no": "3333-5000-5000",
                "bank_account_holder_name": "정하은",
                "resident_zip_code": "06134",
                "road_address": "서울특별시 강남구 테헤란로 152",
                "rrn_masked": "980211-2******",
                "cell_number": "010-5000-5000",
            },
        },
        {
            "user": "demo.gangnam.pt@node.pe.kr",
            "first_name": "도윤",
            "last_name": "한",
            "gender": "Male",
            "dob": "2001-09-19",
            "doj": "2026-01-05",
            "department": "매장운영 - NBG",
            "designation": "Part-time Crew",
            "branch": "강남 매장",
            "custom": {
                "employment_type": "Part-time",
                "employment_type_kr": "Part-time",
                "work_location_name": "강남 매장",
                "bank_name": "토스뱅크",
                "bank_ac_no": "190-6000-6000",
                "bank_account_holder_name": "한도윤",
                "resident_zip_code": "06134",
                "road_address": "서울특별시 강남구 테헤란로 152",
                "rrn_masked": "010919-3******",
                "cell_number": "010-6000-6000",
            },
        },
        {
            "user": "demo.hongdae.lead@node.pe.kr",
            "first_name": "지아",
            "last_name": "윤",
            "gender": "Female",
            "dob": "1994-12-03",
            "doj": "2024-11-01",
            "department": "매장운영 - NBG",
            "designation": "Store Supervisor",
            "branch": "홍대 매장",
            "custom": {
                "employment_type": "Full-time",
                "employment_type_kr": "Regular",
                "work_location_name": "홍대 매장",
                "bank_name": "국민은행",
                "bank_ac_no": "110-7000-7000",
                "bank_account_holder_name": "윤지아",
                "resident_zip_code": "04050",
                "road_address": "서울특별시 마포구 양화로 160",
                "rrn_masked": "941203-2******",
                "cell_number": "010-7000-7000",
            },
        },
        {
            "user": "demo.hongdae.pt@node.pe.kr",
            "first_name": "서준",
            "last_name": "강",
            "gender": "Male",
            "dob": "2000-04-24",
            "doj": "2026-03-02",
            "department": "매장운영 - NBG",
            "designation": "Part-time Crew",
            "branch": "홍대 매장",
            "custom": {
                "employment_type": "Part-time",
                "employment_type_kr": "Part-time",
                "work_location_name": "홍대 매장",
                "bank_name": "신한은행",
                "bank_ac_no": "140-8000-8000",
                "bank_account_holder_name": "강서준",
                "resident_zip_code": "04050",
                "road_address": "서울특별시 마포구 양화로 160",
                "rrn_masked": "000424-3******",
                "cell_number": "010-8000-8000",
            },
        },
        {
            "user": "demo.busan.manager@node.pe.kr",
            "first_name": "수빈",
            "last_name": "오",
            "gender": "Female",
            "dob": "1991-08-14",
            "doj": "2023-10-10",
            "department": "매장운영 - NBG",
            "designation": "Store Supervisor",
            "branch": "부산 매장",
            "custom": {
                "employment_type": "Full-time",
                "employment_type_kr": "Fixed-term",
                "work_location_name": "부산 매장",
                "bank_name": "부산은행",
                "bank_ac_no": "101-9000-9000",
                "bank_account_holder_name": "오수빈",
                "resident_zip_code": "48058",
                "road_address": "부산광역시 해운대구 센텀중앙로 97",
                "rrn_masked": "910814-2******",
                "cell_number": "010-9000-9000",
            },
        },
        {
            "user": "demo.busan.pt@node.pe.kr",
            "first_name": "민재",
            "last_name": "장",
            "gender": "Male",
            "dob": "2002-06-30",
            "doj": "2026-04-01",
            "department": "매장운영 - NBG",
            "designation": "Part-time Crew",
            "branch": "부산 매장",
            "custom": {
                "employment_type": "Part-time",
                "employment_type_kr": "Part-time",
                "work_location_name": "부산 매장",
                "bank_name": "농협은행",
                "bank_ac_no": "301-1010-1010",
                "bank_account_holder_name": "장민재",
                "resident_zip_code": "48058",
                "road_address": "부산광역시 해운대구 센텀중앙로 97",
                "rrn_masked": "020630-3******",
                "cell_number": "010-1010-1010",
            },
        },
    ]


def main():
    created = []
    updated = []

    holiday_list, changed = ensure_holiday_list()
    (updated if changed else created).append(f"Holiday List::{holiday_list.name}")

    warehouse_type, warehouse_created = ensure_warehouse_type("Transit")
    (created if warehouse_created else updated).append(f"Warehouse Type::{warehouse_type.name}")

    company, company_created = ensure_company()
    (created if company_created else updated).append(f"Company::{company.name}")

    for name in ["운영", "매장운영"]:
        doc, was_created = ensure_department(company.name, name)
        (created if was_created else updated).append(f"Department::{doc.name}")

    for name in ["HR Manager", "Store Supervisor", "Operations Lead", "Payroll Specialist", "Store Staff", "Part-time Crew"]:
        doc, was_created = ensure_designation(name)
        (created if was_created else updated).append(f"Designation::{doc.name}")

    for name in ["Full-time", "Part-time"]:
        doc, was_created = ensure_employment_type(name)
        (created if was_created else updated).append(f"Employment Type::{doc.name}")

    for name in ["Male", "Female"]:
        doc, was_created = ensure_gender(name)
        (created if was_created else updated).append(f"Gender::{doc.name}")

    for name in ["서울 본사", "강남 매장", "홍대 매장", "부산 매장"]:
        doc, was_created = ensure_branch(name)
        (created if was_created else updated).append(f"Branch::{doc.name}")

    shift, shift_created = ensure_shift_type(holiday_list.name)
    (created if shift_created else updated).append(f"Shift Type::{shift.name}")

    for component_name in ensure_salary_components():
        updated.append(f"Salary Component::{component_name}")

    leave_configs = [
        ("Annual Leave", {"is_earned_leave": 1, "earned_leave_frequency": "Monthly", "is_carry_forward": 1, "maximum_carry_forwarded_leaves": 25}),
        ("Sick Leave", {"is_lwp": 0, "is_carry_forward": 0}),
        ("Family Event Leave", {"is_lwp": 0, "is_carry_forward": 0}),
    ]
    for leave_name, options in leave_configs:
        doc, was_created = ensure_leave_type(leave_name, **options)
        (created if was_created else updated).append(f"Leave Type::{doc.name}")

    employees = build_demo_employee_roster()
    for payload in employees:
        roles = {"Employee"}
        if payload["user"] in {"demo.hr.manager@node.pe.kr", "demo.store@node.pe.kr"}:
            roles = {"HR Manager", "HR User", "Employee"}
        user_doc, user_created = ensure_user(payload["user"], payload["first_name"], payload["last_name"], roles=roles)
        (created if user_created else updated).append(f"User::{user_doc.name}")

    employee_docs = []
    employee_names = []
    for payload in employees:
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
        (created if was_created else updated).append(f"Employee::{doc.name}")

    blocker_seed = ensure_demo_blocker_transactions(company=company.name, employees=employee_docs)
    for row in blocker_seed["blocker_rows"]:
        updated.append(f"{row['doctype']}::{row['name']}")

    draft_seed = ensure_demo_payroll_closing_draft(company=company.name)
    for row in draft_seed["draft_rows"]:
        updated.append(f"{row['doctype']}::{row['name']}")

    structure, was_created = ensure_salary_structure(company.name)
    (created if was_created else updated).append(f"Salary Structure::{structure.name}")

    for employee in employee_names:
        doc, created_assignment = ensure_salary_structure_assignment(employee, company.name, structure.name)
        (created if created_assignment else updated).append(f"Salary Structure Assignment::{doc.name}")

    frappe.db.commit()
    summary = {
        "created_or_updated": created + updated,
        "company": company.name,
        "holiday_list": holiday_list.name,
        "shift_type": shift.name,
        "salary_structure": structure.name,
        "employees": employee_names,
        "demo_blocker_seed": blocker_seed,
        "demo_payroll_closing_draft_seed": draft_seed,
        "demo_browser_credential_handoff": build_demo_browser_credential_handoff(),
        "demo_login": {
            "url": "http://10.0.0.58:8000/app",
            "username": "demo.hr.manager@node.pe.kr",
            "password": "***",
        },
    }
    print(json.dumps(summary, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
