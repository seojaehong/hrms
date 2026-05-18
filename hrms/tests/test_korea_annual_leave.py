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


class KoreaAnnualLeaveEngineTest(unittest.TestCase):
    def setUp(self):
        self.annual_leave = load_module()

    def test_first_year_monthly_accrual_is_one_day_per_completed_month_capped_at_eleven(self):
        result = self.annual_leave.calculate_annual_leave_entitlement(
            hire_date=dt.date(2026, 1, 15),
            as_of_date=dt.date(2026, 12, 15),
        )

        self.assertEqual(result["basis"], "Hire Date")
        self.assertEqual(result["service_years"], 0)
        self.assertEqual(result["monthly_accrual_days"], 11)
        self.assertEqual(result["annual_entitlement_days"], 0)
        self.assertEqual(result["total_entitlement_days"], 11)
        self.assertEqual(result["period_start"], dt.date(2026, 1, 15))
        self.assertEqual(result["period_end"], dt.date(2027, 1, 14))

    def test_one_year_anniversary_grants_fifteen_days(self):
        result = self.annual_leave.calculate_annual_leave_entitlement(
            hire_date=dt.date(2025, 5, 1),
            as_of_date=dt.date(2026, 5, 1),
        )

        self.assertEqual(result["service_years"], 1)
        self.assertEqual(result["monthly_accrual_days"], 0)
        self.assertEqual(result["annual_entitlement_days"], 15)
        self.assertEqual(result["total_entitlement_days"], 15)

    def test_long_service_adds_one_day_every_two_years_after_first_year_capped_at_twenty_five(self):
        three_years = self.annual_leave.calculate_annual_leave_entitlement(
            hire_date=dt.date(2023, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
        )
        twenty_one_years = self.annual_leave.calculate_annual_leave_entitlement(
            hire_date=dt.date(2005, 1, 1),
            as_of_date=dt.date(2026, 1, 1),
        )

        self.assertEqual(three_years["annual_entitlement_days"], 16)
        self.assertEqual(three_years["total_entitlement_days"], 16)
        self.assertEqual(twenty_one_years["annual_entitlement_days"], 25)
        self.assertEqual(twenty_one_years["total_entitlement_days"], 25)

    def test_fiscal_year_first_year_proration_uses_days_employed_in_fiscal_year(self):
        result = self.annual_leave.calculate_annual_leave_entitlement(
            hire_date=dt.date(2026, 7, 1),
            as_of_date=dt.date(2026, 12, 31),
            basis="Fiscal Year",
        )

        self.assertEqual(result["basis"], "Fiscal Year")
        self.assertEqual(result["period_start"], dt.date(2026, 1, 1))
        self.assertEqual(result["period_end"], dt.date(2026, 12, 31))
        self.assertEqual(result["monthly_accrual_days"], 5)
        self.assertEqual(result["annual_entitlement_days"], 7.56)
        self.assertEqual(result["total_entitlement_days"], 12.56)

    def test_fiscal_year_start_on_february_twenty_nine_clamps_to_valid_year_date(self):
        period_start, period_end = self.annual_leave.fiscal_period_for(
            dt.date(2025, 3, 1), fiscal_year_start_month=2, fiscal_year_start_day=29
        )

        self.assertEqual(period_start, dt.date(2025, 2, 28))
        self.assertEqual(period_end, dt.date(2026, 2, 27))

    def test_february_twenty_nine_hire_anniversary_uses_clamped_non_leap_year_date(self):
        result = self.annual_leave.calculate_annual_leave_entitlement(
            hire_date=dt.date(2024, 2, 29),
            as_of_date=dt.date(2025, 2, 28),
        )

        self.assertEqual(result["service_years"], 1)
        self.assertEqual(result["monthly_accrual_days"], 0)
        self.assertEqual(result["annual_entitlement_days"], 15)

    def test_fiscal_year_proration_can_be_capped_by_mid_year_employment_end_date(self):
        result = self.annual_leave.calculate_annual_leave_entitlement(
            hire_date=dt.date(2026, 7, 1),
            as_of_date=dt.date(2026, 12, 31),
            basis="Fiscal Year",
            employment_end_date=dt.date(2026, 9, 30),
        )

        self.assertEqual(result["employment_end_date"], dt.date(2026, 9, 30))
        self.assertEqual(result["monthly_accrual_days"], 2)
        self.assertEqual(result["annual_entitlement_days"], 3.78)
        self.assertEqual(result["total_entitlement_days"], 5.78)

    def test_fiscal_year_after_employment_end_uses_final_employment_period_not_future_period(self):
        result = self.annual_leave.calculate_annual_leave_entitlement(
            hire_date=dt.date(2024, 1, 1),
            as_of_date=dt.date(2027, 3, 1),
            basis="Fiscal Year",
            employment_end_date=dt.date(2026, 9, 30),
        )

        self.assertEqual(result["period_start"], dt.date(2026, 1, 1))
        self.assertEqual(result["period_end"], dt.date(2026, 12, 31))
        self.assertEqual(result["service_years"], 2)

    def test_fiscal_year_long_service_entitlement_uses_end_date_not_period_end_after_leave(self):
        result = self.annual_leave.calculate_annual_leave_entitlement(
            hire_date=dt.date(2023, 7, 1),
            as_of_date=dt.date(2026, 12, 31),
            basis="Fiscal Year",
            employment_end_date=dt.date(2026, 6, 30),
        )

        self.assertEqual(result["service_years"], 2)
        self.assertEqual(result["annual_entitlement_days"], 15)

    def test_hire_date_after_as_of_date_is_rejected(self):
        with self.assertRaises(ValueError):
            self.annual_leave.calculate_annual_leave_entitlement(
                hire_date=dt.date(2026, 5, 1),
                as_of_date=dt.date(2026, 4, 30),
            )

    def test_employment_end_date_before_hire_date_is_rejected(self):
        with self.assertRaises(ValueError):
            self.annual_leave.calculate_annual_leave_entitlement(
                hire_date=dt.date(2026, 5, 1),
                as_of_date=dt.date(2026, 12, 31),
                employment_end_date=dt.date(2026, 4, 30),
            )

    def test_fiscal_year_start_controls_must_be_plain_integers_not_bool(self):
        with self.assertRaisesRegex(ValueError, "fiscal_year_start_month must be an integer"):
            self.annual_leave.calculate_annual_leave_entitlement(
                hire_date=dt.date(2026, 1, 1),
                as_of_date=dt.date(2026, 12, 31),
                basis="Fiscal Year",
                fiscal_year_start_month=True,
            )

        with self.assertRaisesRegex(ValueError, "fiscal_year_start_day must be an integer"):
            self.annual_leave.calculate_annual_leave_entitlement(
                hire_date=dt.date(2026, 1, 1),
                as_of_date=dt.date(2026, 12, 31),
                basis="Fiscal Year",
                fiscal_year_start_day=False,
            )

    def test_fiscal_year_start_controls_must_reject_non_integral_values(self):
        for fieldname, kwargs in (
            ("fiscal_year_start_month", {"fiscal_year_start_month": 3.5}),
            ("fiscal_year_start_day", {"fiscal_year_start_day": "1.5"}),
        ):
            with self.subTest(fieldname=fieldname):
                with self.assertRaisesRegex(ValueError, f"{fieldname} must be an integer"):
                    self.annual_leave.calculate_annual_leave_entitlement(
                        hire_date=dt.date(2026, 1, 1),
                        as_of_date=dt.date(2026, 12, 31),
                        basis="Fiscal Year",
                        **kwargs,
                    )


if __name__ == "__main__":
    unittest.main()
