from __future__ import annotations

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from hrms.setup import delete_custom_fields


RULES_FILE_PATH = ".hermes/KOREA_LEGAL_RULES_INPUT.yaml"


def setup():
    make_custom_fields()



def uninstall():
    delete_custom_fields(get_custom_fields())



def make_custom_fields(update=True):
    create_custom_fields(get_custom_fields(), update=update)



def get_custom_fields():
    return {
        "Company": [
            {
                "fieldname": "korea_hr_payroll_section",
                "label": "Korea HR & Payroll",
                "fieldtype": "Section Break",
                "insert_after": "default_payroll_payable_account",
                "collapsible": 1,
            },
            {
                "fieldname": "business_registration_number",
                "label": "Business Registration Number",
                "fieldtype": "Data",
                "insert_after": "korea_hr_payroll_section",
                "translatable": 0,
            },
            {
                "fieldname": "workplace_management_number",
                "label": "Workplace Management Number",
                "fieldtype": "Data",
                "insert_after": "business_registration_number",
                "translatable": 0,
            },
            {
                "fieldname": "korea_company_column_break",
                "fieldtype": "Column Break",
                "insert_after": "workplace_management_number",
            },
            {
                "fieldname": "default_work_location",
                "label": "Default Work Location",
                "fieldtype": "Data",
                "insert_after": "korea_company_column_break",
            },
            {
                "fieldname": "korea_rules_reference",
                "label": "Korea Rules Reference",
                "fieldtype": "Small Text",
                "default": RULES_FILE_PATH,
                "read_only": 1,
                "insert_after": "default_work_location",
                "description": "Server-side policy baseline file to update labor law, payroll, and social insurance assumptions.",
            },
        ],
        "Employee": [
            {
                "fieldname": "korea_employee_section",
                "label": "Korea Employee Data",
                "fieldtype": "Section Break",
                "insert_after": "bank_name",
                "collapsible": 1,
            },
            {
                "fieldname": "resident_registration_number",
                "label": "Resident Registration No. (Encrypted)",
                "fieldtype": "Password",
                "insert_after": "korea_employee_section",
                "description": "전체 주민등록번호(암호화 저장). 4대보험 신고 등 법정 용도에만 사용.",
                "print_hide": 1,
                "translatable": 0,
                "no_copy": 1,
            },
            {
                "fieldname": "rrn_masked",
                "label": "Resident Registration No. (Masked)",
                "fieldtype": "Data",
                "insert_after": "resident_registration_number",
                "description": "Store masked form only, e.g. 900101-1******.",
                "print_hide": 1,
                "translatable": 0,
                "read_only": 1,
            },
            {
                "fieldname": "employment_type_kr",
                "label": "Employment Type (KR)",
                "fieldtype": "Select",
                "options": "\nRegular\nFixed-term\nPart-time\nDispatch\nIntern",
                "insert_after": "rrn_masked",
                "translatable": 0,
            },
            {
                "fieldname": "work_location_name",
                "label": "Work Location",
                "fieldtype": "Data",
                "insert_after": "employment_type_kr",
            },
            {
                "fieldname": "workplace_management_number",
                "label": "Workplace Management Number (KR)",
                "fieldtype": "Data",
                "insert_after": "work_location_name",
                "description": "소속 사업장 관리번호 — 한 법인에 관리번호가 여러 개(본점/지점·상용/일용 분리성립)일 때 직원별 소속. 비우면 회사 기본 관리번호.",
                "translatable": 0,
            },
            {
                "fieldname": "korea_employee_column_break",
                "fieldtype": "Column Break",
                "insert_after": "work_location_name",
            },
            {
                "fieldname": "bank_account_holder_name",
                "label": "Bank Account Holder",
                "fieldtype": "Data",
                "insert_after": "korea_employee_column_break",
            },
            {
                "fieldname": "resident_zip_code",
                "label": "ZIP Code",
                "fieldtype": "Data",
                "insert_after": "bank_account_holder_name",
                "translatable": 0,
            },
            {
                "fieldname": "road_address",
                "label": "Road Address",
                "fieldtype": "Small Text",
                "insert_after": "resident_zip_code",
            },
        ],
        "Salary Component": [
            {
                "fieldname": "korea_component_category",
                "label": "Korea Component Category",
                "fieldtype": "Select",
                "options": "\nOrdinary Wage\nAllowance\nStatutory Deduction\nEmployer Statutory Contribution\nCompany-specific Deduction",
                "insert_after": "description",
                "depends_on": 'eval:doc.country == "South Korea" || !doc.country',
                "translatable": 0,
            },
            {
                "fieldname": "is_company_contribution_only",
                "label": "Company Contribution Only",
                "fieldtype": "Check",
                "insert_after": "korea_component_category",
                "depends_on": 'eval:doc.country == "South Korea" || !doc.country',
            },
        ],
    }
