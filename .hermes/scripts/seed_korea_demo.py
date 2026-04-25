import json
from pathlib import Path

import frappe
from frappe.utils import getdate


def ensure_doc(doctype, name=None, filters=None, values=None):
    values = values or {}
    if name and frappe.db.exists(doctype, name):
        doc = frappe.get_doc(doctype, name)
    elif filters and frappe.db.exists(doctype, filters):
        doc = frappe.get_doc(doctype, filters)
    else:
        payload = {"doctype": doctype, **values}
        if name:
            payload["name"] = name
        doc = frappe.get_doc(payload).insert(ignore_permissions=True)
        return doc, True

    changed = False
    for key, value in values.items():
        if doc.get(key) != value:
            doc.set(key, value)
            changed = True
    if changed:
        doc.save(ignore_permissions=True)
    return doc, False


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
            "new_password": "DemoHRMS!2026",
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


def main():
    created = []
    updated = []

    holiday_list, changed = ensure_holiday_list()
    (updated if changed else created).append(f"Holiday List::{holiday_list.name}")

    company, company_created = ensure_company()
    (created if company_created else updated).append(f"Company::{company.name}")

    for name in ["운영", "매장운영"]:
        doc, was_created = ensure_department(company.name, name)
        (created if was_created else updated).append(f"Department::{doc.name}")

    for name in ["HR Manager", "Store Supervisor"]:
        doc, was_created = ensure_designation(name)
        (created if was_created else updated).append(f"Designation::{doc.name}")

    for name in ["Full-time", "Part-time"]:
        doc, was_created = ensure_employment_type(name)
        (created if was_created else updated).append(f"Employment Type::{doc.name}")

    for name in ["서울 본사", "강남 매장"]:
        doc, was_created = ensure_branch(name)
        (created if was_created else updated).append(f"Branch::{doc.name}")

    shift, shift_created = ensure_shift_type(holiday_list.name)
    (created if shift_created else updated).append(f"Shift Type::{shift.name}")

    leave_configs = [
        ("Annual Leave", {"is_earned_leave": 1, "earned_leave_frequency": "Monthly", "is_carry_forward": 1, "maximum_carry_forwarded_leaves": 25}),
        ("Sick Leave", {"is_lwp": 0, "is_carry_forward": 0}),
        ("Family Event Leave", {"is_lwp": 0, "is_carry_forward": 0}),
    ]
    for leave_name, options in leave_configs:
        doc, was_created = ensure_leave_type(leave_name, **options)
        (created if was_created else updated).append(f"Leave Type::{doc.name}")

    ensure_user("demo.hr.manager@node.pe.kr", "Demo", "Manager")
    ensure_user("demo.store@node.pe.kr", "Demo", "Store")

    employees = [
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
        employee_names.append(doc.name)
        (created if was_created else updated).append(f"Employee::{doc.name}")

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
        "demo_login": {
            "url": "http://10.0.0.58:8000/app",
            "username": "demo.hr.manager@node.pe.kr",
            "password": "DemoHRMS!2026",
        },
    }
    print(json.dumps(summary, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
