"""
Unit tests for hrms/regional/south_korea/mobile_attendance.py.

Uses FakeFrappeModule pattern — no live Frappe/DB required.
Run with: python -m pytest hrms/tests/test_korea_mobile_attendance.py -v
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest


# ---------------------------------------------------------------------------
# Fake infrastructure
# ---------------------------------------------------------------------------


class FakeFrappeError(Exception):
    pass


class FakeDB:
    def __init__(self):
        self._docs: dict[tuple, dict] = {}
        self._set_value_calls: list = []
        self._existing_doctypes: set[str] = {"Employee", "Employee Checkin", "File"}

    def exists(self, doctype, name):
        if doctype == "DocType":
            return name if name in self._existing_doctypes else None
        key = (doctype, name if isinstance(name, str) else str(name))
        return key[1] if key in self._docs else None

    def get_value(self, doctype, name_or_filters, fieldname=None, order_by=None, as_dict=False):
        # Support filters dict (used by _get_workplace_coords for profile lookup).
        if isinstance(name_or_filters, dict):
            # Find first matching record.
            for (dt, n), rec in self._docs.items():
                if dt != doctype:
                    continue
                match = all(rec.get(k) == v for k, v in name_or_filters.items())
                if match:
                    if fieldname is None:
                        return rec if as_dict else n
                    if isinstance(fieldname, list):
                        return {f: rec.get(f) for f in fieldname} if as_dict else tuple(rec.get(f) for f in fieldname)
                    return rec.get(fieldname)
            return None

        key = (doctype, str(name_or_filters))
        rec = self._docs.get(key)
        if rec is None:
            return None
        if fieldname is None:
            return rec if as_dict else key[1]
        if isinstance(fieldname, list):
            return {f: rec.get(f) for f in fieldname} if as_dict else tuple(rec.get(f) for f in fieldname)
        return rec.get(fieldname)

    def set_value(self, doctype, name, field_or_dict, value=None, *args, **kwargs):
        self._set_value_calls.append((doctype, name, field_or_dict, value))
        key = (doctype, name)
        rec = self._docs.setdefault(key, {"doctype": doctype, "name": name})
        if isinstance(field_or_dict, dict):
            rec.update(field_or_dict)
        else:
            rec[field_or_dict] = value

    def add_doc(self, doctype, name, **fields):
        key = (doctype, name)
        self._docs[key] = {"doctype": doctype, "name": name, **fields}


class FakeDoc:
    """Minimal Frappe doc stub returned by get_doc()."""

    def __init__(self, payload: dict, db: FakeDB):
        self.__dict__.update(payload)
        self._db = db
        self.name: str | None = None

    def insert(self, ignore_permissions: bool = False):
        # Auto-assign name if not set (simulate Frappe naming).
        if not self.name:
            doctype = self.__dict__.get("doctype", "Doc")
            count = sum(1 for (dt, _) in self._db._docs if dt == doctype)
            self.name = f"{doctype.replace(' ', '-').upper()}-{count + 1:04d}"
        key = (self.__dict__["doctype"], self.name)
        self._db._docs[key] = {**self.__dict__, "name": self.name}
        return self


class FakeFrappeModule(types.SimpleNamespace):
    def __init__(self):
        super().__init__()
        self.db = FakeDB()
        self._ = lambda x: x
        self.whitelist = lambda *a, **kw: (lambda fn: fn)
        self.throw = self._throw
        self.log_error = lambda *a, **kw: None
        self.get_traceback = lambda: ""
        self.local = types.SimpleNamespace(form_dict={}, request=None)

    def _throw(self, message, exc=None):
        raise FakeFrappeError(message)

    def get_doc(self, payload: dict):
        return FakeDoc(dict(payload), self.db)


# ---------------------------------------------------------------------------
# Helper to load the module under test
# ---------------------------------------------------------------------------

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "hrms"
    / "regional"
    / "south_korea"
    / "mobile_attendance.py"
)


def _load_module(fake_frappe: FakeFrappeModule):
    sys.modules["frappe"] = fake_frappe
    spec = importlib.util.spec_from_file_location("test_mobile_attendance_module", MODULE_PATH)
    assert spec is not None and spec.loader is not None, f"Cannot load module from {MODULE_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHaversine(unittest.TestCase):
    """Pure math tests — no Frappe dependency."""

    def setUp(self):
        self.fake_frappe = FakeFrappeModule()
        self.module = _load_module(self.fake_frappe)

    def tearDown(self):
        sys.modules.pop("frappe", None)

    def test_same_point_is_zero(self):
        d = self.module._haversine_metres(37.5, 127.0, 37.5, 127.0)
        self.assertAlmostEqual(d, 0.0, places=3)

    def test_known_distance_seoul_busan(self):
        # Seoul (37.5665, 126.9780) ↔ Busan (35.1796, 129.0756) ≈ 325 km.
        d = self.module._haversine_metres(37.5665, 126.9780, 35.1796, 129.0756)
        self.assertGreater(d, 320_000)
        self.assertLess(d, 340_000)

    def test_one_hundred_metres_north(self):
        # Moving ~100 m north (≈ 0.0009°) from (37.5, 127.0).
        d = self.module._haversine_metres(37.5, 127.0, 37.5009, 127.0)
        self.assertGreater(d, 90)
        self.assertLess(d, 110)


class TestBuildWarnings(unittest.TestCase):
    def setUp(self):
        self.fake_frappe = FakeFrappeModule()
        self.module = _load_module(self.fake_frappe)

    def tearDown(self):
        sys.modules.pop("frappe", None)

    def test_no_warnings_when_accurate_and_near(self):
        # 50 m accuracy, 100 m from workplace.
        warnings, distance = self.module._build_warnings(
            50.0, (37.5000, 127.0000), 37.5009, 127.0000
        )
        self.assertEqual(warnings, [])
        self.assertIsNotNone(distance)

    def test_low_accuracy_warning(self):
        warnings, distance = self.module._build_warnings(
            150.0, None, 37.5, 127.0
        )
        self.assertTrue(any("gps_accuracy_low" in w for w in warnings))
        self.assertIsNone(distance)

    def test_distance_warning_when_far(self):
        # Place workplace at (37.5, 127.0); employee at ~1 km north.
        warnings, distance = self.module._build_warnings(
            30.0, (37.5000, 127.0000), 37.5090, 127.0000
        )
        self.assertTrue(any("distance_from_workplace" in w for w in warnings))
        self.assertIsNotNone(distance)
        self.assertGreater(distance, 500)

    def test_no_distance_warning_when_no_workplace(self):
        warnings, distance = self.module._build_warnings(
            30.0, None, 37.5, 127.0
        )
        self.assertFalse(any("distance_from_workplace" in w for w in warnings))
        self.assertIsNone(distance)


class TestRecordMobileCheckin(unittest.TestCase):
    def setUp(self):
        self.fake_frappe = FakeFrappeModule()
        self.module = _load_module(self.fake_frappe)
        # Register a test employee.
        self.fake_frappe.db.add_doc("Employee", "EMP-0001", employee_name="Kim Worker", status="Active")

    def tearDown(self):
        sys.modules.pop("frappe", None)

    def _call(self, **overrides):
        defaults = dict(
            employee="EMP-0001",
            check_type="IN",
            timestamp="2026-05-17 09:00:00",
            gps_latitude=37.5665,
            gps_longitude=126.9780,
            accuracy_meters=15.0,
            human_approved=True,
        )
        defaults.update(overrides)
        return self.module.record_mobile_checkin(**defaults)

    # --- Success path -------------------------------------------------------

    def test_successful_checkin_returns_contract_envelope(self):
        result = self._call()
        self.assertEqual(result["contract_type"], "korea_mobile_attendance_record_v1")
        self.assertEqual(result["runtime_action"], "mobile_checkin")
        self.assertTrue(result["applied"])
        self.assertIsNotNone(result["attendance_name"])
        self.assertIsInstance(result["warnings"], list)
        self.assertEqual(result["data"]["employee"], "EMP-0001")
        self.assertEqual(result["data"]["check_type"], "IN")
        self.assertEqual(result["data"]["gps_latitude"], 37.5665)

    def test_checkout_accepted(self):
        result = self._call(check_type="OUT")
        self.assertEqual(result["data"]["check_type"], "OUT")

    def test_employee_checkin_doc_inserted(self):
        result = self._call()
        name = result["attendance_name"]
        key = ("Employee Checkin", name)
        doc = self.fake_frappe.db._docs.get(key)
        self.assertIsNotNone(doc, "Employee Checkin doc should be in fake DB")
        self.assertEqual(doc["log_type"], "IN")
        self.assertEqual(doc["employee"], "EMP-0001")

    # --- human_approved gate ------------------------------------------------

    def test_human_approved_false_is_rejected(self):
        with self.assertRaises(FakeFrappeError) as ctx:
            self._call(human_approved=False)
        self.assertIn("human_approved", str(ctx.exception))

    def test_human_approved_string_true_accepted(self):
        result = self._call(human_approved="true")
        self.assertTrue(result["applied"])

    def test_human_approved_string_false_rejected(self):
        with self.assertRaises(FakeFrappeError):
            self._call(human_approved="false")

    # --- Validation ---------------------------------------------------------

    def test_missing_employee_raises(self):
        with self.assertRaises(FakeFrappeError):
            self._call(employee=None)

    def test_unknown_employee_raises(self):
        with self.assertRaises(FakeFrappeError) as ctx:
            self._call(employee="EMP-9999")
        self.assertIn("Employee not found", str(ctx.exception))

    def test_invalid_check_type_raises(self):
        with self.assertRaises(FakeFrappeError) as ctx:
            self._call(check_type="LUNCH")
        self.assertIn("check_type", str(ctx.exception))

    def test_invalid_latitude_raises(self):
        with self.assertRaises(FakeFrappeError) as ctx:
            self._call(gps_latitude=95.0)
        self.assertIn("gps_latitude", str(ctx.exception))

    def test_invalid_longitude_raises(self):
        with self.assertRaises(FakeFrappeError) as ctx:
            self._call(gps_longitude=-200.0)
        self.assertIn("gps_longitude", str(ctx.exception))

    def test_negative_accuracy_raises(self):
        with self.assertRaises(FakeFrappeError) as ctx:
            self._call(accuracy_meters=-1.0)
        self.assertIn("accuracy_meters", str(ctx.exception))

    def test_unknown_payload_key_raises(self):
        with self.assertRaises((FakeFrappeError, TypeError)):
            # Extra positional/keyword arg should be rejected.
            self.module.record_mobile_checkin(
                employee="EMP-0001",
                check_type="IN",
                timestamp="2026-05-17 09:00:00",
                gps_latitude=37.5,
                gps_longitude=127.0,
                accuracy_meters=10.0,
                human_approved=True,
                _unknown_field="bad",
            )

    # --- GPS accuracy warning -----------------------------------------------

    def test_low_accuracy_adds_warning(self):
        result = self._call(accuracy_meters=200.0)
        self.assertTrue(any("gps_accuracy_low" in w for w in result["warnings"]))

    def test_good_accuracy_no_warning(self):
        result = self._call(accuracy_meters=50.0)
        self.assertFalse(any("gps_accuracy_low" in w for w in result["warnings"]))

    # --- Selfie handling ----------------------------------------------------

    def test_valid_selfie_doc_attached(self):
        # Register a file doc in fake DB.
        self.fake_frappe.db.add_doc("File", "FILE-0001", file_name="selfie.jpg")
        result = self._call(selfie_file_doc_name="FILE-0001")
        self.assertEqual(result["data"]["selfie_file_doc_name"], "FILE-0001")
        self.assertIsNotNone(result["attendance_name"])

    def test_nonexistent_selfie_doc_raises(self):
        with self.assertRaises(FakeFrappeError) as ctx:
            self._call(selfie_file_doc_name="FILE-MISSING")
        self.assertIn("Selfie file not found", str(ctx.exception))

    def test_no_selfie_is_accepted(self):
        result = self._call()
        self.assertIsNone(result["data"]["selfie_file_doc_name"])

    # --- Workplace distance (no profile configured) -------------------------

    def test_no_workplace_profile_no_distance_warning(self):
        # DocType "Korea Workplace Profile" is NOT in fake DB existing doctypes.
        result = self._call()
        self.assertFalse(any("distance_from_workplace" in w for w in result["warnings"]))

    # --- Workplace distance (profile configured) ----------------------------

    def test_distance_warning_when_workplace_profile_exists(self):
        # Register the custom doctype and a workplace profile for EMP-0001.
        self.fake_frappe.db._existing_doctypes.add("Korea Workplace Profile")
        self.fake_frappe.db.add_doc(
            "Korea Workplace Profile",
            "KWP-0001",
            employee="EMP-0001",
            is_active=1,
            workplace_latitude=37.5665,
            workplace_longitude=126.9780,
        )
        # Check in from a location ~1 km away.
        result = self._call(gps_latitude=37.5755, gps_longitude=126.9780)
        self.assertTrue(any("distance_from_workplace" in w for w in result["warnings"]))
        self.assertIsNotNone(result["distance_from_workplace_meters"])
        self.assertGreater(result["distance_from_workplace_meters"], 500)

    def test_no_distance_warning_when_within_threshold(self):
        self.fake_frappe.db._existing_doctypes.add("Korea Workplace Profile")
        self.fake_frappe.db.add_doc(
            "Korea Workplace Profile",
            "KWP-0002",
            employee="EMP-0001",
            is_active=1,
            workplace_latitude=37.5665,
            workplace_longitude=126.9780,
        )
        # Check in from 10 m away.
        result = self._call(gps_latitude=37.5666, gps_longitude=126.9780)
        self.assertFalse(any("distance_from_workplace" in w for w in result["warnings"]))
        self.assertIsNotNone(result["distance_from_workplace_meters"])
        self.assertLess(result["distance_from_workplace_meters"], 500)

    def test_distance_from_workplace_none_when_no_profile(self):
        result = self._call()
        self.assertIsNone(result["distance_from_workplace_meters"])


if __name__ == "__main__":
    unittest.main()
