import importlib.util
import json
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCTYPE_ROOT = ROOT / "hrms" / "hr" / "doctype"


def load_json(name):
    path = DOCTYPE_ROOT / name / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def fields_by_name(doc):
    return {field["fieldname"]: field for field in doc["fields"] if "fieldname" in field}


class KoreaHRMSProfileSchemaTest(unittest.TestCase):
    def test_korea_workplace_profile_schema(self):
        doc = load_json("korea_workplace_profile")
        self.assertEqual(doc["name"], "Korea Workplace Profile")
        self.assertEqual(doc["module"], "HR")
        fields = fields_by_name(doc)
        expected = {
            "company": "Link",
            "branch": "Link",
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


if __name__ == "__main__":
    unittest.main()
