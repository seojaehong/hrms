"""Tests for hrms/regional/south_korea/subscription.py.

Framework-free 코어만 테스트 — frappe import 없음.
python -m pytest tests/test_korea_subscription.py -v
"""

import datetime as dt
import importlib.util
import pathlib
import sys
import unittest


# ---------------------------------------------------------------------------
# 모듈 격리 로드 (frappe 없이 실행)
# ---------------------------------------------------------------------------

def _load_subscription_module():
    spec = importlib.util.spec_from_file_location(
        "south_korea.subscription",
        pathlib.Path(__file__).parent.parent
        / "hrms/regional/south_korea/subscription.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sub = _load_subscription_module()


# ---------------------------------------------------------------------------
# get_plan
# ---------------------------------------------------------------------------

class TestGetPlan(unittest.TestCase):
    def test_returns_starter_plan(self):
        plan = sub.get_plan("starter")
        self.assertEqual(plan["monthly_price_krw"], 50_000)
        self.assertEqual(plan["max_employees"], 10)
        self.assertIn("기본 HR", plan["features"])

    def test_returns_growth_plan(self):
        plan = sub.get_plan("growth")
        self.assertEqual(plan["monthly_price_krw"], 150_000)
        self.assertEqual(plan["max_employees"], 50)

    def test_returns_enterprise_plan(self):
        plan = sub.get_plan("enterprise")
        self.assertEqual(plan["monthly_price_krw"], "협의")
        self.assertIsNone(plan["max_employees"])

    def test_unknown_tier_raises_value_error(self):
        with self.assertRaises(ValueError):
            sub.get_plan("nonexistent")

    def test_returns_copy_not_original(self):
        """PLAN_TIERS를 직접 변경하지 않는지 확인."""
        plan = sub.get_plan("starter")
        plan["monthly_price_krw"] = 0
        self.assertEqual(sub.PLAN_TIERS["starter"]["monthly_price_krw"], 50_000)


# ---------------------------------------------------------------------------
# calculate_monthly_invoice
# ---------------------------------------------------------------------------

class TestCalculateMonthlyInvoice(unittest.TestCase):
    def _period(self):
        return dt.date(2026, 5, 1), dt.date(2026, 5, 31)

    def test_starter_no_overage(self):
        start, end = self._period()
        result = sub.calculate_monthly_invoice(
            tier="starter",
            employee_count=5,
            period_start=start,
            period_end=end,
        )
        self.assertEqual(result["base_amount_krw"], 50_000)
        self.assertEqual(result["overage_count"], 0)
        self.assertEqual(result["overage_amount_krw"], 0)
        self.assertEqual(result["total_amount_krw"], 50_000)
        self.assertIsNone(result["note"])

    def test_starter_with_overage(self):
        start, end = self._period()
        # starter max=10, 15명 → 5명 초과
        result = sub.calculate_monthly_invoice(
            tier="starter",
            employee_count=15,
            period_start=start,
            period_end=end,
        )
        self.assertEqual(result["overage_count"], 5)
        self.assertEqual(result["overage_amount_krw"], 5 * sub.OVERAGE_PRICE_PER_EMPLOYEE_KRW)
        self.assertEqual(
            result["total_amount_krw"],
            50_000 + 5 * sub.OVERAGE_PRICE_PER_EMPLOYEE_KRW,
        )
        self.assertIsNotNone(result["note"])

    def test_growth_no_overage(self):
        start, end = self._period()
        result = sub.calculate_monthly_invoice(
            tier="growth",
            employee_count=50,
            period_start=start,
            period_end=end,
        )
        self.assertEqual(result["overage_count"], 0)
        self.assertEqual(result["total_amount_krw"], 150_000)

    def test_enterprise_returns_none_amounts(self):
        start, end = self._period()
        result = sub.calculate_monthly_invoice(
            tier="enterprise",
            employee_count=200,
            period_start=start,
            period_end=end,
        )
        self.assertIsNone(result["base_amount_krw"])
        self.assertIsNone(result["total_amount_krw"])
        self.assertEqual(result["overage_count"], 0)
        self.assertIsNotNone(result["note"])

    def test_period_dates_serialized_as_iso(self):
        start, end = self._period()
        result = sub.calculate_monthly_invoice(
            tier="starter",
            employee_count=1,
            period_start=start,
            period_end=end,
        )
        self.assertEqual(result["period_start"], "2026-05-01")
        self.assertEqual(result["period_end"], "2026-05-31")

    def test_unknown_tier_raises_value_error(self):
        start, end = self._period()
        with self.assertRaises(ValueError):
            sub.calculate_monthly_invoice(
                tier="ultra",
                employee_count=5,
                period_start=start,
                period_end=end,
            )


# ---------------------------------------------------------------------------
# initiate_subscription
# ---------------------------------------------------------------------------

class TestInitiateSubscription(unittest.TestCase):
    def _call(self, **overrides):
        kwargs = dict(
            company="테스트 주식회사",
            tier="starter",
            payment_method="toss",
            billing_email="admin@test.kr",
            human_approved=True,
            dry_run=True,
        )
        kwargs.update(overrides)
        return sub.initiate_subscription(**kwargs)

    def test_dry_run_returns_dry_run_status(self):
        result = self._call()
        self.assertEqual(result["status"], "dry_run")
        self.assertTrue(result["dry_run"])
        self.assertIn("KR-SUB-", result["subscription_id"])

    def test_dry_run_includes_invoice(self):
        result = self._call()
        self.assertIn("invoice", result)
        self.assertEqual(result["invoice"]["tier"], "starter")

    def test_human_not_approved_raises_permission_error(self):
        with self.assertRaises(PermissionError):
            self._call(human_approved=False)

    def test_invalid_tier_raises_value_error(self):
        with self.assertRaises(ValueError):
            self._call(tier="gold")

    def test_invalid_payment_method_raises_value_error(self):
        with self.assertRaises(ValueError):
            self._call(payment_method="paypal")

    def test_dry_run_false_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self._call(dry_run=False)

    def test_subscription_ids_are_unique(self):
        id1 = self._call()["subscription_id"]
        id2 = self._call()["subscription_id"]
        self.assertNotEqual(id1, id2)


# ---------------------------------------------------------------------------
# cancel_subscription
# ---------------------------------------------------------------------------

class TestCancelSubscription(unittest.TestCase):
    def test_cancel_returns_cancelled_status(self):
        result = sub.cancel_subscription(
            subscription_id="KR-SUB-ABCDEF123456",
            human_approved=True,
        )
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["subscription_id"], "KR-SUB-ABCDEF123456")
        self.assertIn("cancelled_at", result)

    def test_human_not_approved_raises_permission_error(self):
        with self.assertRaises(PermissionError):
            sub.cancel_subscription(
                subscription_id="KR-SUB-ABCDEF123456",
                human_approved=False,
            )


# ---------------------------------------------------------------------------
# upgrade_downgrade
# ---------------------------------------------------------------------------

class TestUpgradeDowngrade(unittest.TestCase):
    def test_upgrade_returns_plan_changed_status(self):
        result = sub.upgrade_downgrade(
            subscription_id="KR-SUB-ABCDEF123456",
            new_tier="growth",
            human_approved=True,
        )
        self.assertEqual(result["status"], "plan_changed")
        self.assertEqual(result["new_tier"], "growth")
        self.assertIn("changed_at", result)

    def test_human_not_approved_raises_permission_error(self):
        with self.assertRaises(PermissionError):
            sub.upgrade_downgrade(
                subscription_id="KR-SUB-ABCDEF123456",
                new_tier="growth",
                human_approved=False,
            )

    def test_invalid_new_tier_raises_value_error(self):
        with self.assertRaises(ValueError):
            sub.upgrade_downgrade(
                subscription_id="KR-SUB-ABCDEF123456",
                new_tier="platinum",
                human_approved=True,
            )


# ---------------------------------------------------------------------------
# list_invoices
# ---------------------------------------------------------------------------

class TestListInvoices(unittest.TestCase):
    def test_returns_empty_list_in_dry_run(self):
        result = sub.list_invoices(company="테스트 주식회사")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)


# ---------------------------------------------------------------------------
# payment adapter stubs
# ---------------------------------------------------------------------------

class TestStripeAdapterStub(unittest.TestCase):
    def _load(self):
        spec = importlib.util.spec_from_file_location(
            "south_korea.payments.stripe_adapter",
            pathlib.Path(__file__).parent.parent
            / "hrms/regional/south_korea/payments/stripe_adapter.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_charge_raises_not_implemented(self):
        adapter = self._load()
        with self.assertRaises(NotImplementedError):
            adapter.charge(
                subscription_id="x",
                amount_krw=50_000,
                customer_email="a@b.com",
            )

    def test_create_customer_raises_not_implemented(self):
        adapter = self._load()
        with self.assertRaises(NotImplementedError):
            adapter.create_customer(email="a@b.com", name="홍길동")

    def test_cancel_subscription_raises_not_implemented(self):
        adapter = self._load()
        with self.assertRaises(NotImplementedError):
            adapter.cancel_subscription(stripe_subscription_id="sub_xxx")

    def test_list_invoices_raises_not_implemented(self):
        adapter = self._load()
        with self.assertRaises(NotImplementedError):
            adapter.list_invoices(stripe_customer_id="cus_xxx")


class TestTossAdapterStub(unittest.TestCase):
    def _load(self):
        spec = importlib.util.spec_from_file_location(
            "south_korea.payments.toss_adapter",
            pathlib.Path(__file__).parent.parent
            / "hrms/regional/south_korea/payments/toss_adapter.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_charge_raises_not_implemented(self):
        adapter = self._load()
        with self.assertRaises(NotImplementedError):
            adapter.charge(
                subscription_id="x",
                amount_krw=50_000,
                order_name="테스트",
                customer_email="a@b.com",
                customer_name="홍길동",
            )

    def test_cancel_payment_raises_not_implemented(self):
        adapter = self._load()
        with self.assertRaises(NotImplementedError):
            adapter.cancel_payment(payment_key="pk_test_xxx")

    def test_list_invoices_raises_not_implemented(self):
        adapter = self._load()
        with self.assertRaises(NotImplementedError):
            adapter.list_invoices(order_id_prefix="KR-SUB-")


if __name__ == "__main__":
    unittest.main()
