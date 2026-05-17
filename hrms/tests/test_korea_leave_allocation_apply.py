#!/usr/bin/env python3
"""Tests for hrms/regional/south_korea/leave_allocation_apply.py.

All tests run bench-free via file-path loading and frappe mocking.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "leave_allocation_apply.py"


def load_module():
    spec = importlib.util.spec_from_file_location("korea_leave_allocation_apply", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


VALID_DRAFT = {
    "contract_type": "korea_leave_allocation_draft_v1",
    "doctype": "Leave Allocation",
    "employee": "EMP-0001",
    "employee_name": "Kim Mina",
    "company": "Korea Demo Co",
    "leave_type": "Annual Leave",
    "from_date": "2026-01-01",
    "to_date": "2026-12-31",
    "new_leaves_allocated": 15.0,
    "unused_leaves": 15.0,
    "carry_forward": False,
    "requires_runtime_apply": True,
}


def _make_frappe_mock(existing_name=None, doc_name="LA-00001"):
    """Build a minimal frappe namespace mock."""
    fake_frappe = types.SimpleNamespace()

    # db mock
    db = MagicMock()
    db.exists.return_value = existing_name
    fake_frappe.db = db

    # get_doc mock
    saved_doc = MagicMock()
    saved_doc.name = doc_name
    doc = MagicMock()
    doc.insert.return_value = saved_doc
    fake_frappe.get_doc = MagicMock(return_value=doc)

    return fake_frappe


class TestKoreaLeaveAllocationApplyFailClosed(unittest.TestCase):
    """human_approved=False must return applied=False without any mutation."""

    def setUp(self):
        self.mod = load_module()

    def test_human_approved_false_returns_applied_false(self):
        result = self.mod.apply_korea_leave_allocation(
            draft=VALID_DRAFT,
            human_approved=False,
        )
        self.assertFalse(result["applied"])
        self.assertFalse(result["human_approval_verified"])
        self.assertFalse(result["idempotent_hit"])
        self.assertIsNone(result["leave_allocation_name"])
        self.assertEqual(result["contract_type"], "korea_leave_allocation_runtime_apply_v1")
        self.assertEqual(result["runtime_action"], "leave_allocation_runtime_apply")

    def test_human_approved_false_does_not_call_frappe(self):
        """No frappe DB or get_doc calls when human_approved=False."""
        fake_frappe = _make_frappe_mock()

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            # Reload module so it picks up the mock
            mod = load_module()
            result = mod.apply_korea_leave_allocation(
                draft=VALID_DRAFT,
                human_approved=False,
            )

        fake_frappe.db.exists.assert_not_called()
        fake_frappe.get_doc.assert_not_called()
        self.assertFalse(result["applied"])

    def test_human_approved_false_with_invalid_draft_still_fail_closed(self):
        """Even an invalid draft payload must not raise when human_approved=False."""
        result = self.mod.apply_korea_leave_allocation(
            draft={"contract_type": "wrong"},
            human_approved=False,
        )
        self.assertFalse(result["applied"])
        self.assertFalse(result["human_approval_verified"])


class TestKoreaLeaveAllocationApplyNewRecord(unittest.TestCase):
    """human_approved=True + no existing record → applied=True."""

    def setUp(self):
        self.mod = load_module()

    def test_creates_new_leave_allocation(self):
        fake_frappe = _make_frappe_mock(existing_name=None, doc_name="LA-00001")

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            result = mod.apply_korea_leave_allocation(
                draft=VALID_DRAFT,
                human_approved=True,
                apply_actor="hr-manager@example.com",
            )

        self.assertTrue(result["applied"])
        self.assertFalse(result["idempotent_hit"])
        self.assertEqual(result["leave_allocation_name"], "LA-00001")
        self.assertTrue(result["human_approval_verified"])
        self.assertEqual(result["apply_actor"], "hr-manager@example.com")
        self.assertEqual(result["contract_type"], "korea_leave_allocation_runtime_apply_v1")

    def test_calls_insert_not_submit(self):
        """Must call .insert() and never .submit()."""
        fake_frappe = _make_frappe_mock(existing_name=None, doc_name="LA-00002")

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            mod.apply_korea_leave_allocation(
                draft=VALID_DRAFT,
                human_approved=True,
                apply_actor="actor@example.com",
            )

        # get_doc called once for insert
        fake_frappe.get_doc.assert_called_once()
        inserted_doc = fake_frappe.get_doc.return_value
        inserted_doc.insert.assert_called_once()
        # submit must NOT be called
        inserted_doc.submit.assert_not_called()
        inserted_doc.approve.assert_not_called()

    def test_draft_reference_in_result(self):
        fake_frappe = _make_frappe_mock(existing_name=None)

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            result = mod.apply_korea_leave_allocation(
                draft=VALID_DRAFT,
                human_approved=True,
            )

        ref = result["draft_reference"]
        self.assertEqual(ref["employee"], "EMP-0001")
        self.assertEqual(ref["leave_type"], "Annual Leave")
        self.assertEqual(ref["contract_type"], "korea_leave_allocation_draft_v1")

    def test_actor_preserved_in_result(self):
        fake_frappe = _make_frappe_mock(existing_name=None)

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            result = mod.apply_korea_leave_allocation(
                draft=VALID_DRAFT,
                human_approved=True,
                apply_actor="payroll-bot@example.com",
            )

        self.assertEqual(result["apply_actor"], "payroll-bot@example.com")


class TestKoreaLeaveAllocationApplyIdempotent(unittest.TestCase):
    """human_approved=True + existing record → idempotent_hit=True."""

    def setUp(self):
        self.mod = load_module()

    def test_idempotent_hit_on_existing_record(self):
        fake_frappe = _make_frappe_mock(existing_name="LA-EXISTING")

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            result = mod.apply_korea_leave_allocation(
                draft=VALID_DRAFT,
                human_approved=True,
                apply_actor="hr@example.com",
            )

        self.assertFalse(result["applied"])
        self.assertTrue(result["idempotent_hit"])
        self.assertEqual(result["leave_allocation_name"], "LA-EXISTING")
        self.assertTrue(result["human_approval_verified"])

    def test_idempotent_hit_does_not_insert(self):
        """When record exists, get_doc must not be called for insertion."""
        fake_frappe = _make_frappe_mock(existing_name="LA-EXISTING")

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            mod.apply_korea_leave_allocation(
                draft=VALID_DRAFT,
                human_approved=True,
            )

        # db.exists is called; get_doc for insert must not be
        fake_frappe.db.exists.assert_called_once()
        fake_frappe.get_doc.assert_not_called()


class TestKoreaLeaveAllocationApplyMutationBoundary(unittest.TestCase):
    """Mutation boundary violations must raise."""

    def setUp(self):
        self.mod = load_module()

    def test_raises_when_frappe_not_available(self):
        """Without Frappe, mutation should raise RuntimeError.

        Skipped inside a running bench because evicting 'frappe' from
        sys.modules while the bench is active triggers a circular-import
        error in frappe/__init__.py, making the test unrunnable in that
        context.  The behaviour is fully covered by bench-free execution.
        """
        # Detect a real bench runtime — the test can't safely evict frappe there.
        real_frappe = sys.modules.get("frappe")
        if real_frappe is not None and hasattr(real_frappe, "db"):
            self.skipTest("Cannot evict frappe from sys.modules inside a live bench runtime")

        sys_modules_backup = sys.modules.pop("frappe", None)
        try:
            mod = load_module()
            with self.assertRaises(RuntimeError):
                mod.apply_korea_leave_allocation(
                    draft=VALID_DRAFT,
                    human_approved=True,
                )
        finally:
            if sys_modules_backup is not None:
                sys.modules["frappe"] = sys_modules_backup

    def test_raises_on_wrong_contract_type(self):
        """draft with wrong contract_type must raise ValueError even before frappe access."""
        bad_draft = {**VALID_DRAFT, "contract_type": "unknown_contract_v1"}
        fake_frappe = _make_frappe_mock()

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            with self.assertRaises(ValueError):
                mod.apply_korea_leave_allocation(
                    draft=bad_draft,
                    human_approved=True,
                )

    def test_raises_on_wrong_doctype(self):
        bad_draft = {**VALID_DRAFT, "doctype": "Payroll Entry"}
        fake_frappe = _make_frappe_mock()

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            with self.assertRaises(ValueError):
                mod.apply_korea_leave_allocation(
                    draft=bad_draft,
                    human_approved=True,
                )

    def test_raises_on_requires_runtime_apply_false(self):
        bad_draft = {**VALID_DRAFT, "requires_runtime_apply": False}
        fake_frappe = _make_frappe_mock()

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            with self.assertRaises(ValueError):
                mod.apply_korea_leave_allocation(
                    draft=bad_draft,
                    human_approved=True,
                )

    def test_raises_on_forbidden_score_field(self):
        bad_draft = {**VALID_DRAFT, "risk_score": 0.9}
        with self.assertRaises(ValueError):
            self.mod.apply_korea_leave_allocation(
                draft=bad_draft,
                human_approved=False,  # even fail-closed: score check runs first
            )

    def test_raises_on_probability_field(self):
        bad_draft = {**VALID_DRAFT, "probability": 0.5}
        with self.assertRaises(ValueError):
            self.mod.apply_korea_leave_allocation(
                draft=bad_draft,
                human_approved=False,
            )


class TestKoreaLeaveAllocationApplyWhitelist(unittest.TestCase):
    """API wrapper must apply frappe.whitelist() when Frappe is present."""

    def test_whitelist_applied_to_api_function(self):
        api_path = pathlib.Path(MODULE_PATH).with_name("leave_allocation_apply_api.py")
        calls = []

        def whitelist():
            def decorator(fn):
                calls.append(fn.__name__)
                fn.is_whitelisted_for_test = True
                return fn
            return decorator

        fake_frappe = types.SimpleNamespace(whitelist=whitelist)
        old_frappe = sys.modules.get("frappe")
        sys.modules["frappe"] = fake_frappe
        try:
            spec = importlib.util.spec_from_file_location("korea_leave_allocation_apply_api", api_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            if old_frappe is None:
                sys.modules.pop("frappe", None)
            else:
                sys.modules["frappe"] = old_frappe

        self.assertIn("apply_korea_leave_allocation_api", calls)
        self.assertTrue(module.apply_korea_leave_allocation_api.is_whitelisted_for_test)


if __name__ == "__main__":
    unittest.main()
