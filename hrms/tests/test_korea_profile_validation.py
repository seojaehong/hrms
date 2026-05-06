import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hrms" / "regional" / "south_korea" / "profile_validation.py"


def load_module():
    spec = importlib.util.spec_from_file_location("korea_profile_validation", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KoreaProfileValidationTest(unittest.TestCase):
    def test_workplace_profile_validation_normalizes_identifiers_without_mutating_input(self):
        module = load_module()
        source = {
            "company": "Acme Korea",
            "business_registration_number": " 123-45-67890 ",
            "workplace_management_number": " 12345678901 ",
        }
        original = copy.deepcopy(source)

        result = module.validate_workplace_profile(source)

        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["normalized"]["business_registration_number"], "123-45-67890")
        self.assertEqual(result["normalized"]["workplace_management_number"], "12345678901")
        self.assertEqual(source, original)

    def test_workplace_profile_validation_allows_blank_optional_identifiers(self):
        module = load_module()
        source = {"company": "Acme Korea"}

        result = module.validate_workplace_profile(source)

        self.assertTrue(result["valid"])
        self.assertNotIn("business_registration_number", result["normalized"])
        self.assertNotIn("workplace_management_number", result["normalized"])

    def test_workplace_profile_validation_rejects_invalid_identifiers(self):
        module = load_module()

        with self.assertRaisesRegex(ValueError, "business_registration_number"):
            module.validate_workplace_profile(
                {
                    "business_registration_number": "1234567890",
                    "workplace_management_number": "12345678901",
                }
            )

        with self.assertRaisesRegex(ValueError, "workplace_management_number"):
            module.validate_workplace_profile(
                {
                    "business_registration_number": "123-45-67890",
                    "workplace_management_number": "ABC-123",
                }
            )

    def test_employment_profile_validation_normalizes_masked_rrn_dates_and_companies(self):
        module = load_module()
        source = {
            "employee": "EMP-0001",
            "company": "Acme Korea",
            "workplace_profile": "SEOUL-HQ",
            "rrn_masked": " 900101-1****** ",
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-12-31",
        }
        original = copy.deepcopy(source)

        result = module.validate_employment_profile(
            source,
            employee_company="Acme Korea",
            workplace_company="Acme Korea",
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["normalized"]["rrn_masked"], "900101-1******")
        self.assertEqual(result["normalized"]["contract_start_date"], "2026-01-01")
        self.assertEqual(result["normalized"]["contract_end_date"], "2026-12-31")
        self.assertEqual(source, original)

    def test_employment_profile_validation_allows_blank_optional_rrn_and_normalizes_company(self):
        module = load_module()
        source = {"company": " Acme Korea "}

        result = module.validate_employment_profile(source, employee_company="Acme Korea")

        self.assertTrue(result["valid"])
        self.assertEqual(result["normalized"]["company"], "Acme Korea")
        self.assertNotIn("rrn_masked", result["normalized"])

    def test_employment_profile_validation_rejects_raw_rrn_bad_date_range_and_company_mismatch(self):
        module = load_module()

        with self.assertRaisesRegex(ValueError, "rrn_masked"):
            module.validate_employment_profile({"company": "Acme Korea", "rrn_masked": "900101-1234567"})

        with self.assertRaisesRegex(ValueError, "contract_end_date must be on or after contract_start_date"):
            module.validate_employment_profile(
                {
                    "company": "Acme Korea",
                    "rrn_masked": "900101-1******",
                    "contract_start_date": "2026-12-31",
                    "contract_end_date": "2026-01-01",
                }
            )

        with self.assertRaisesRegex(ValueError, "employee_company must match employment profile company"):
            module.validate_employment_profile(
                {"company": "Acme Korea", "rrn_masked": "900101-1******"},
                employee_company="Other Company",
            )

        with self.assertRaisesRegex(ValueError, "workplace_company must match employment profile company"):
            module.validate_employment_profile(
                {"company": "Acme Korea", "rrn_masked": "900101-1******"},
                workplace_company="Other Company",
            )


if __name__ == "__main__":
    unittest.main()
