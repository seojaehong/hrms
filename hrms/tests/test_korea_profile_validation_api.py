import copy
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hrms" / "regional" / "south_korea" / "profile_validation_api.py"


def load_module():
    spec = importlib.util.spec_from_file_location("korea_profile_validation_api", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KoreaProfileValidationAPITest(unittest.TestCase):
    def test_preview_api_accepts_json_inputs_and_returns_preview_contract(self):
        module = load_module()
        workplace = {
            "company": "Acme Korea",
            "business_registration_number": " 123-45-67890 ",
            "workplace_management_number": " 12345678901 ",
        }
        employment = {
            "employee": "EMP-0001",
            "company": "Acme Korea",
            "workplace_profile": "SEOUL-HQ",
            "rrn_masked": " 900101-1****** ",
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-12-31",
        }

        result = module.preview_korea_hr_profile_validation(
            workplace_profile=json.dumps(workplace),
            employment_profile=json.dumps(employment),
            employee_company="Acme Korea",
            workplace_company="Acme Korea",
        )

        self.assertEqual(result["contract_type"], "korea_hr_profile_validation_preview_v1")
        self.assertEqual(result["runtime_action"], "preview_only")
        self.assertIs(result["requires_runtime_apply"], False)
        self.assertEqual(result["workplace_profile"]["normalized"]["business_registration_number"], "123-45-67890")
        self.assertEqual(result["employment_profile"]["normalized"]["rrn_masked"], "900101-1******")

    def test_preview_api_rejects_invalid_json_and_non_dict_payloads(self):
        module = load_module()

        with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
            module.preview_korea_hr_profile_validation(workplace_profile="{")

        with self.assertRaisesRegex(ValueError, "employment_profile must be a dict or JSON object"):
            module.preview_korea_hr_profile_validation(employment_profile=[])

    def test_preview_api_defensively_copies_outputs(self):
        module = load_module()
        workplace = {
            "business_registration_number": "123-45-67890",
            "workplace_management_number": "12345678901",
        }
        original = copy.deepcopy(workplace)

        result = module.preview_korea_hr_profile_validation(workplace_profile=workplace)
        result["workplace_profile"]["normalized"]["business_registration_number"] = "000-00-00000"

        second = module.preview_korea_hr_profile_validation(workplace_profile=workplace)
        self.assertEqual(workplace, original)
        self.assertEqual(second["workplace_profile"]["normalized"]["business_registration_number"], "123-45-67890")


if __name__ == "__main__":
    unittest.main()
