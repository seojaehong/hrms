#!/usr/bin/env python3
"""Tests for hrms/regional/south_korea/attendance_closing_apply.py.

All tests run bench-free via file-path loading and frappe mocking.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "attendance_closing_apply.py"


def load_module():
    spec = importlib.util.spec_from_file_location("korea_attendance_closing_apply", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


VALID_SNAPSHOT = {
    "workplace": "SEOUL-01",
    "period_start": "2026-05-01",
    "period_end": "2026-05-31",
    "employees": ["EMP-001"],
    "summary_by_employee": {
        "EMP-001": {
            "records_count": 20,
            "present_days": 20.0,
            "working_hours": 160.0,
        }
    },
    "summary_hash": "abc123",
    "blocking_messages": [],
    "status": "Ready To Close",
}

BLOCKED_SNAPSHOT = {
    **VALID_SNAPSHOT,
    "blocking_messages": ["EMP-001: unresolved half-day attendance must be classified before closing"],
    "status": "Blocked",
}


def _make_frappe_mock(existing_draft_name="KPCD-0001", existing_snapshot=None):
    """Build a minimal frappe namespace mock for attendance closing apply."""
    fake_frappe = types.SimpleNamespace()

    db = MagicMock()

    def db_get_value(doctype, filters, fieldname):
        if doctype == "Korea Payroll Closing Draft" and fieldname == "name":
            return existing_draft_name
        if doctype == "Korea Payroll Closing Draft" and fieldname == "attendance_snapshot":
            return existing_snapshot
        return None

    db.get_value = MagicMock(side_effect=db_get_value)
    fake_frappe.db = db

    # get_doc → doc with save()
    saved_doc = MagicMock()
    saved_doc.attendance_snapshot = None
    saved_doc.save = MagicMock(return_value=saved_doc)
    fake_frappe.get_doc = MagicMock(return_value=saved_doc)

    return fake_frappe, saved_doc


class TestKoreaAttendanceClosingApplyFailClosed(unittest.TestCase):
    """human_approved=False must return applied=False without mutation."""

    def setUp(self):
        self.mod = load_module()

    def test_fail_closed_on_human_approved_false(self):
        result = self.mod.apply_korea_attendance_closing(
            snapshot=VALID_SNAPSHOT,
            human_approved=False,
        )
        self.assertFalse(result["applied"])
        self.assertFalse(result["human_approval_verified"])
        self.assertFalse(result["idempotent_hit"])
        self.assertIsNone(result["korea_payroll_closing_draft_name"])
        self.assertEqual(result["contract_type"], "korea_attendance_closing_runtime_apply_v1")
        self.assertEqual(result["runtime_action"], "attendance_closing_runtime_apply")

    def test_fail_closed_returns_blocking_messages(self):
        result = self.mod.apply_korea_attendance_closing(
            snapshot=BLOCKED_SNAPSHOT,
            human_approved=False,
        )
        self.assertFalse(result["applied"])
        self.assertEqual(len(result["blocking_messages"]), 1)

    def test_fail_closed_does_not_call_frappe(self):
        fake_frappe, saved_doc = _make_frappe_mock()

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            mod.apply_korea_attendance_closing(
                snapshot=VALID_SNAPSHOT,
                human_approved=False,
            )

        fake_frappe.db.get_value.assert_not_called()
        fake_frappe.get_doc.assert_not_called()

    def test_fail_closed_with_invalid_snapshot(self):
        """Even an invalid snapshot must not raise when human_approved=False."""
        result = self.mod.apply_korea_attendance_closing(
            snapshot={"no_workplace": True},
            human_approved=False,
        )
        self.assertFalse(result["applied"])


class TestKoreaAttendanceClosingApplyNewRecord(unittest.TestCase):
    """human_approved=True + existing draft, no prior snapshot → applied=True."""

    def setUp(self):
        self.mod = load_module()

    def test_applies_snapshot_to_existing_draft(self):
        fake_frappe, saved_doc = _make_frappe_mock(
            existing_draft_name="KPCD-0001",
            existing_snapshot=None,
        )

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            result = mod.apply_korea_attendance_closing(
                snapshot=VALID_SNAPSHOT,
                human_approved=True,
                apply_actor="payroll-admin@example.com",
            )

        self.assertTrue(result["applied"])
        self.assertFalse(result["idempotent_hit"])
        self.assertEqual(result["korea_payroll_closing_draft_name"], "KPCD-0001")
        self.assertTrue(result["human_approval_verified"])
        self.assertEqual(result["apply_actor"], "payroll-admin@example.com")
        self.assertEqual(result["blocking_messages"], [])

    def test_calls_save_not_submit(self):
        fake_frappe, saved_doc = _make_frappe_mock(existing_draft_name="KPCD-0001")

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            mod.apply_korea_attendance_closing(
                snapshot=VALID_SNAPSHOT,
                human_approved=True,
            )

        # save called once; submit must NOT be called
        saved_doc.save.assert_called_once()
        saved_doc.submit.assert_not_called()
        saved_doc.approve.assert_not_called()
        saved_doc.cancel.assert_not_called()

    def test_snapshot_written_to_doc(self):
        """attendance_snapshot field must be set on the doc before save."""
        fake_frappe, saved_doc = _make_frappe_mock(existing_draft_name="KPCD-0001")

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            mod.apply_korea_attendance_closing(
                snapshot=VALID_SNAPSHOT,
                human_approved=True,
            )

        # attendance_snapshot must have been set to a JSON string
        self.assertIsNotNone(saved_doc.attendance_snapshot)
        parsed = json.loads(saved_doc.attendance_snapshot)
        self.assertEqual(parsed["workplace"], "SEOUL-01")

    def test_blocked_snapshot_still_saves(self):
        """Blocked snapshots must still be persisted (status not promoted by this call)."""
        fake_frappe, saved_doc = _make_frappe_mock(existing_draft_name="KPCD-0001")

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            result = mod.apply_korea_attendance_closing(
                snapshot=BLOCKED_SNAPSHOT,
                human_approved=True,
            )

        self.assertTrue(result["applied"])
        self.assertEqual(len(result["blocking_messages"]), 1)
        saved_doc.save.assert_called_once()

    def test_actor_preserved_in_result(self):
        fake_frappe, _ = _make_frappe_mock()

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            result = mod.apply_korea_attendance_closing(
                snapshot=VALID_SNAPSHOT,
                human_approved=True,
                apply_actor="supervisor@example.com",
            )

        self.assertEqual(result["apply_actor"], "supervisor@example.com")


class TestKoreaAttendanceClosingApplyIdempotent(unittest.TestCase):
    """human_approved=True + draft with existing snapshot → idempotent_hit=True."""

    def test_idempotent_hit_when_snapshot_already_present(self):
        existing_json = json.dumps(VALID_SNAPSHOT)
        fake_frappe, saved_doc = _make_frappe_mock(
            existing_draft_name="KPCD-0001",
            existing_snapshot=existing_json,
        )

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            result = mod.apply_korea_attendance_closing(
                snapshot=VALID_SNAPSHOT,
                human_approved=True,
            )

        self.assertTrue(result["applied"])
        self.assertTrue(result["idempotent_hit"])
        # save is still called (snapshot is overwritten)
        saved_doc.save.assert_called_once()

    def test_idempotent_overwrites_snapshot(self):
        """Re-apply with updated snapshot should overwrite the stored JSON."""
        existing_json = json.dumps({**VALID_SNAPSHOT, "summary_hash": "old_hash"})
        fake_frappe, saved_doc = _make_frappe_mock(
            existing_draft_name="KPCD-0001",
            existing_snapshot=existing_json,
        )

        updated_snapshot = {**VALID_SNAPSHOT, "summary_hash": "new_hash"}

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            mod.apply_korea_attendance_closing(
                snapshot=updated_snapshot,
                human_approved=True,
            )

        parsed = json.loads(saved_doc.attendance_snapshot)
        self.assertEqual(parsed["summary_hash"], "new_hash")


class TestKoreaAttendanceClosingApplyMutationBoundary(unittest.TestCase):
    """Mutation boundary violations must raise."""

    def setUp(self):
        self.mod = load_module()

    def test_raises_when_frappe_not_available(self):
        """Without Frappe, mutation should raise RuntimeError.

        Skipped inside a running bench because evicting 'frappe' from
        sys.modules while the bench is active triggers a circular-import
        error in frappe/__init__.py.  Covered by bench-free execution.
        """
        real_frappe = sys.modules.get("frappe")
        if real_frappe is not None and hasattr(real_frappe, "db"):
            self.skipTest("Cannot evict frappe from sys.modules inside a live bench runtime")

        sys_modules_backup = sys.modules.pop("frappe", None)
        try:
            mod = load_module()
            with self.assertRaises(RuntimeError):
                mod.apply_korea_attendance_closing(
                    snapshot=VALID_SNAPSHOT,
                    human_approved=True,
                )
        finally:
            if sys_modules_backup is not None:
                sys.modules["frappe"] = sys_modules_backup

    def test_raises_lookup_when_no_draft_exists(self):
        """LookupError when no Korea Payroll Closing Draft found."""
        fake_frappe, _ = _make_frappe_mock(existing_draft_name=None)

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            with self.assertRaises(LookupError):
                mod.apply_korea_attendance_closing(
                    snapshot=VALID_SNAPSHOT,
                    human_approved=True,
                )

    def test_raises_on_missing_workplace(self):
        bad_snapshot = {**VALID_SNAPSHOT, "workplace": ""}
        fake_frappe, _ = _make_frappe_mock()

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            with self.assertRaises(ValueError):
                mod.apply_korea_attendance_closing(
                    snapshot=bad_snapshot,
                    human_approved=True,
                )

    def test_raises_on_forbidden_score_field(self):
        bad_snapshot = {**VALID_SNAPSHOT, "risk_score": 0.8}
        with self.assertRaises(ValueError):
            self.mod.apply_korea_attendance_closing(
                snapshot=bad_snapshot,
                human_approved=False,  # score check runs before fail-closed
            )

    def test_raises_on_probability_field(self):
        bad_snapshot = {**VALID_SNAPSHOT, "probability": 0.3}
        with self.assertRaises(ValueError):
            self.mod.apply_korea_attendance_closing(
                snapshot=bad_snapshot,
                human_approved=False,
            )

    def test_raises_on_invalid_period_start(self):
        bad_snapshot = {**VALID_SNAPSHOT, "period_start": "not-a-date"}
        fake_frappe, _ = _make_frappe_mock()

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            mod = load_module()
            with self.assertRaises(ValueError):
                mod.apply_korea_attendance_closing(
                    snapshot=bad_snapshot,
                    human_approved=True,
                )


class TestKoreaAttendanceClosingApplyWhitelist(unittest.TestCase):
    """API wrapper must apply frappe.whitelist() when Frappe is present."""

    def test_whitelist_applied_to_api_function(self):
        api_path = pathlib.Path(MODULE_PATH).with_name("attendance_closing_apply_api.py")
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
            spec = importlib.util.spec_from_file_location("korea_attendance_closing_apply_api", api_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            if old_frappe is None:
                sys.modules.pop("frappe", None)
            else:
                sys.modules["frappe"] = old_frappe

        self.assertIn("apply_korea_attendance_closing_api", calls)
        self.assertTrue(module.apply_korea_attendance_closing_api.is_whitelisted_for_test)


if __name__ == "__main__":
    unittest.main()
