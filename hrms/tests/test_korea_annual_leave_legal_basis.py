import datetime as dt
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hrms" / "regional" / "south_korea" / "annual_leave.py"


def load_module():
    spec = importlib.util.spec_from_file_location("korea_annual_leave", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KoreaAnnualLeaveLegalBasisTest(unittest.TestCase):
    def setUp(self):
        self.annual_leave = load_module()

    def _basis(self, **kwargs):
        result = self.annual_leave.calculate_annual_leave_entitlement(**kwargs)
        self.assertIn("legal_basis", result)
        self.assertIsInstance(result["legal_basis"], list)
        for citation in result["legal_basis"]:
            self.assertIsInstance(citation, str)
        return result["legal_basis"]

    def test_first_service_year_cites_article_60_paragraph_2(self):
        legal_basis = self._basis(
            hire_date=dt.date(2026, 1, 15),
            as_of_date=dt.date(2026, 12, 15),
        )

        self.assertTrue(any("제60조제2항" in c for c in legal_basis), legal_basis)
        self.assertFalse(any("제60조제1항" in c for c in legal_basis), legal_basis)

    def test_one_year_case_cites_article_60_paragraph_1(self):
        legal_basis = self._basis(
            hire_date=dt.date(2025, 5, 1),
            as_of_date=dt.date(2026, 5, 1),
        )

        self.assertTrue(any("제60조제1항" in c for c in legal_basis), legal_basis)
        self.assertFalse(any("제60조제2항" in c for c in legal_basis), legal_basis)
        self.assertFalse(any("제60조제4항" in c for c in legal_basis), legal_basis)

    def test_long_service_case_includes_article_60_paragraph_4(self):
        legal_basis = self._basis(
            hire_date=dt.date(2023, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
        )

        self.assertTrue(any("제60조제1항" in c for c in legal_basis), legal_basis)
        self.assertTrue(any("제60조제4항" in c for c in legal_basis), legal_basis)

    def test_fiscal_year_first_year_cites_article_60_paragraph_2(self):
        legal_basis = self._basis(
            hire_date=dt.date(2026, 7, 1),
            as_of_date=dt.date(2026, 12, 31),
            basis="Fiscal Year",
        )

        self.assertTrue(any("제60조제2항" in c for c in legal_basis), legal_basis)

    def test_legal_basis_falls_back_when_no_published_ontology_node(self):
        # All ontology nodes are draft, so the published lookup returns nothing
        # and the module fallback constant must supply the citation base.
        self.assertTrue(hasattr(self.annual_leave, "_LEGAL_BASIS_BASE_FALLBACK"))
        base = self.annual_leave._LEGAL_BASIS_BASE_FALLBACK

        legal_basis = self._basis(
            hire_date=dt.date(2025, 5, 1),
            as_of_date=dt.date(2026, 5, 1),
        )

        self.assertTrue(legal_basis)
        for citation in legal_basis:
            self.assertTrue(citation.startswith(base), citation)

    def test_signature_unchanged_no_new_required_parameters(self):
        import inspect

        signature = inspect.signature(
            self.annual_leave.calculate_annual_leave_entitlement
        )
        self.assertEqual(
            list(signature.parameters),
            [
                "hire_date",
                "as_of_date",
                "basis",
                "fiscal_year_start_month",
                "fiscal_year_start_day",
                "employment_end_date",
            ],
        )


if __name__ == "__main__":
    unittest.main()
