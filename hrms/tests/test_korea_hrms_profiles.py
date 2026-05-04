import importlib.util
import json
import pathlib
import sys
import types
import unittest
from contextlib import contextmanager

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCTYPE_ROOT = ROOT / "hrms" / "hr" / "doctype"


def load_json(name):
    path = DOCTYPE_ROOT / name / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def fields_by_name(doc):
    return {field["fieldname"]: field for field in doc["fields"] if "fieldname" in field}


class ValidationError(Exception):
    pass


@contextmanager
def frappe_stub(employee_company=None, workplace_company=None):
    document_module = types.ModuleType("frappe.model.document")
    document_module.Document = type("Document", (), {})

    frappe_module = types.ModuleType("frappe")

    def throw(message):
        raise ValidationError(message)

    class DB:
        @staticmethod
        def get_value(doctype, name, fieldname):
            if doctype == "Employee" and fieldname == "company":
                return employee_company
            if doctype == "Korea Workplace Profile" and fieldname == "company":
                return workplace_company
            return None

    frappe_module.throw = throw
    frappe_module.db = DB()
    frappe_module._ = lambda message: message

    previous = {name: sys.modules.get(name) for name in ("frappe", "frappe.model", "frappe.model.document")}
    sys.modules["frappe"] = frappe_module
    sys.modules["frappe.model"] = types.ModuleType("frappe.model")
    sys.modules["frappe.model.document"] = document_module
    try:
        yield
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def load_doctype_module(module_name, employee_company=None, workplace_company=None):
    with frappe_stub(employee_company=employee_company, workplace_company=workplace_company):
        path = DOCTYPE_ROOT / module_name / f"{module_name}.py"
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def make_doc(cls, **values):
    doc = cls.__new__(cls)
    for key, value in values.items():
        setattr(doc, key, value)
    return doc


class KoreaHRMSProfileSchemaTest(unittest.TestCase):
    def test_korea_workplace_profile_schema(self):
        doc = load_json("korea_workplace_profile")
        self.assertEqual(doc["name"], "Korea Workplace Profile")
        self.assertEqual(doc["module"], "HR")
        fields = fields_by_name(doc)
        expected = {
            "company": "Link",
            "branch": "Link",
            "business_registration_number": "Data",
            "workplace_management_number": "Data",
            "workplace_name": "Data",
            "regular_employee_count": "Int",
            "leave_grant_basis": "Select",
            "standard_work_hours_per_day": "Float",
            "standard_work_hours_per_week": "Float",
            "attendance_cutoff_day": "Int",
            "payroll_cutoff_day": "Int",
            "payroll_payment_day": "Int",
            "uses_flexible_work": "Check",
        }
        for fieldname, fieldtype in expected.items():
            self.assertIn(fieldname, fields)
            self.assertEqual(fields[fieldname]["fieldtype"], fieldtype)
        self.assertEqual(fields["company"].get("options"), "Company")
        self.assertEqual(fields["company"].get("reqd"), 1)
        self.assertEqual(doc["title_field"], "workplace_name")

    def test_korea_employment_profile_schema(self):
        doc = load_json("korea_employment_profile")
        self.assertEqual(doc["name"], "Korea Employment Profile")
        self.assertEqual(doc["module"], "HR")
        fields = fields_by_name(doc)
        expected = {
            "employee": "Link",
            "company": "Link",
            "workplace_profile": "Link",
            "rrn_masked": "Data",
            "employment_contract_type": "Select",
            "contract_start_date": "Date",
            "contract_end_date": "Date",
            "scheduled_work_hours_per_week": "Float",
            "wage_type": "Select",
            "base_wage": "Currency",
            "inclusive_wage": "Check",
            "non_taxable_meal_allowance": "Currency",
            "leave_grant_basis_override": "Select",
        }
        for fieldname, fieldtype in expected.items():
            self.assertIn(fieldname, fields)
            self.assertEqual(fields[fieldname]["fieldtype"], fieldtype)
        self.assertEqual(fields["employee"].get("options"), "Employee")
        self.assertEqual(fields["employee"].get("reqd"), 1)
        self.assertEqual(fields["employee"].get("unique"), 1)
        self.assertEqual(fields["workplace_profile"].get("options"), "Korea Workplace Profile")
        self.assertEqual(fields["workplace_profile"].get("reqd"), 1)
        self.assertEqual(fields["rrn_masked"].get("print_hide"), 1)
        self.assertEqual(fields["rrn_masked"].get("allow_on_submit"), 0)
        self.assertEqual(doc["autoname"], "field:employee")
        self.assertEqual(doc["title_field"], "employee")

    def test_python_modules_define_document_classes(self):
        document_module = types.ModuleType("frappe.model.document")
        document_module.Document = type("Document", (), {})
        sys.modules.setdefault("frappe", types.ModuleType("frappe"))
        sys.modules.setdefault("frappe.model", types.ModuleType("frappe.model"))
        sys.modules["frappe.model.document"] = document_module

        cases = {
            "korea_workplace_profile": "KoreaWorkplaceProfile",
            "korea_employment_profile": "KoreaEmploymentProfile",
        }
        for module_name, class_name in cases.items():
            path = DOCTYPE_ROOT / module_name / f"{module_name}.py"
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertTrue(hasattr(module, class_name))


    def test_workplace_profile_validates_registration_and_management_numbers(self):
        module = load_doctype_module("korea_workplace_profile")
        cls = module.KoreaWorkplaceProfile

        valid_doc = make_doc(
            cls,
            business_registration_number=" 123-45-67890 ",
            workplace_management_number=" 12345678901 ",
        )
        valid_doc.validate()
        self.assertEqual(valid_doc.business_registration_number, "123-45-67890")
        self.assertEqual(valid_doc.workplace_management_number, "12345678901")

        invalid_business = make_doc(
            cls,
            business_registration_number="1234567890",
            workplace_management_number="12345678901",
        )
        with self.assertRaisesRegex(ValidationError, "business registration"):
            invalid_business.validate()

        invalid_workplace = make_doc(
            cls,
            business_registration_number="123-45-67890",
            workplace_management_number="ABC-123",
        )
        with self.assertRaisesRegex(ValidationError, "workplace management"):
            invalid_workplace.validate()

    def test_employment_profile_validates_masked_rrn_contract_dates_and_link_consistency(self):
        module = load_doctype_module(
            "korea_employment_profile",
            employee_company="Acme Korea",
            workplace_company="Acme Korea",
        )
        cls = module.KoreaEmploymentProfile

        valid_doc = make_doc(
            cls,
            employee="EMP-0001",
            company="Acme Korea",
            workplace_profile="SEOUL-HQ",
            rrn_masked=" 900101-1****** ",
        )
        valid_doc.validate()
        self.assertEqual(valid_doc.rrn_masked, "900101-1******")

        invalid_rrn = make_doc(cls, company="Acme Korea", rrn_masked="900101-1234567")
        with self.assertRaisesRegex(ValidationError, "masked RRN"):
            invalid_rrn.validate()

        wrong_employee_company_module = load_doctype_module(
            "korea_employment_profile",
            employee_company="Other Company",
            workplace_company="Acme Korea",
        )
        wrong_employee_company = make_doc(
            wrong_employee_company_module.KoreaEmploymentProfile,
            employee="EMP-0001",
            company="Acme Korea",
            rrn_masked="900101-1******",
        )
        with self.assertRaisesRegex(ValidationError, "Employee company"):
            wrong_employee_company.validate()

        wrong_workplace_company_module = load_doctype_module(
            "korea_employment_profile",
            employee_company="Acme Korea",
            workplace_company="Other Company",
        )
        wrong_workplace_company = make_doc(
            wrong_workplace_company_module.KoreaEmploymentProfile,
            employee="EMP-0001",
            company="Acme Korea",
            workplace_profile="SEOUL-HQ",
            rrn_masked="900101-1******",
        )
        with self.assertRaisesRegex(ValidationError, "Workplace Profile company"):
            wrong_workplace_company.validate()


if __name__ == "__main__":
    unittest.main()
