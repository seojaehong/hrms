"""Tests for hrms/regional/south_korea/holiday_seed.py.

Frappe를 fake 모듈로 교체해 네트워크/DB 없이 실행.
"""

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SEED_PATH = _ROOT / "hrms" / "regional" / "south_korea" / "holiday_seed.py"
_FETCH_PATH = _ROOT / "hrms" / "regional" / "south_korea" / "holiday_fetch.py"


# ---------------------------------------------------------------------------
# Minimal Frappe fake (Holiday List / Holiday doctypes)
# ---------------------------------------------------------------------------
class FakeHolidayListDoc:
    """Simulates a Frappe Holiday List document."""

    def __init__(self, name: str, from_date: str, to_date: str, company=None):
        self.holiday_list_name = name
        self.name = name
        self.from_date = from_date
        self.to_date = to_date
        self.company = company
        self.holidays: list[dict] = []
        self._saved = False

    def append(self, field: str, row: dict):
        if field == "holidays":
            self.holidays.append(row)

    def insert(self, ignore_permissions=False):
        pass

    def save(self, ignore_permissions=False):
        self._saved = True


class FakeFrappeDB:
    def __init__(self, existing_lists=None, existing_holidays=None):
        # existing_lists: set of holiday list names that "exist"
        self._existing_lists: set = set(existing_lists or [])
        # existing_holidays: dict {list_name: [(holiday_date, description), ...]}
        self._existing_holidays: dict = existing_holidays or {}

    def exists(self, doctype: str, name: str) -> bool:
        if doctype == "Holiday List":
            return name in self._existing_lists
        return False

    def get_all(self, doctype, filters=None, fields=None):
        if doctype == "Holiday":
            parent = (filters or {}).get("parent", "")
            rows = self._existing_holidays.get(parent, [])
            return [
                {"holiday_date": r[0], "description": r[1]} for r in rows
            ]
        return []


class FakeFrappeModule(types.SimpleNamespace):
    def __init__(self, existing_lists=None, existing_holidays=None):
        super().__init__()
        self.db = FakeFrappeDB(existing_lists, existing_holidays)
        self.whitelist = lambda *args, **kwargs: (lambda fn: fn)
        self._created_docs: list = []
        self._saved_docs: list = []
        # Track docs created via get_doc
        self._holiday_list_docs: dict[str, FakeHolidayListDoc] = {}

    def get_all(self, doctype, filters=None, fields=None, **kwargs):
        """frappe.get_all — delegates to db.get_all for Holiday doctype."""
        return self.db.get_all(doctype, filters=filters, fields=fields)

    def get_doc(self, payload_or_name, name=None):
        # Called as frappe.get_doc("Holiday List", "name")
        if isinstance(payload_or_name, str):
            doctype = payload_or_name
            doc_name = name
            if doctype == "Holiday List":
                if doc_name in self._holiday_list_docs:
                    return self._holiday_list_docs[doc_name]
                doc = FakeHolidayListDoc(
                    doc_name,
                    f"{str(doc_name)[-4:]}-01-01",
                    f"{str(doc_name)[-4:]}-12-31",
                )
                self._holiday_list_docs[doc_name] = doc
                return doc
        # Called as frappe.get_doc({"doctype": ..., ...})
        if isinstance(payload_or_name, dict):
            doctype = payload_or_name.get("doctype")
            if doctype == "Holiday List":
                list_name = payload_or_name.get("holiday_list_name") or payload_or_name.get("name")
                doc = FakeHolidayListDoc(
                    list_name,
                    payload_or_name.get("from_date", ""),
                    payload_or_name.get("to_date", ""),
                    payload_or_name.get("company"),
                )
                self._holiday_list_docs[list_name] = doc
                self._created_docs.append(payload_or_name)
                return doc
        return types.SimpleNamespace(insert=lambda **kw: None)

    def throw(self, message, exc=None):
        raise RuntimeError(message)

    def log_error(self, *args, **kwargs):
        pass


# ---------------------------------------------------------------------------
# Loader helper
# ---------------------------------------------------------------------------
def _load_seed_module(fake_frappe: FakeFrappeModule):
    """Load holiday_seed.py with fake frappe injected."""
    # Also ensure fetch module is loadable
    fetch_spec = importlib.util.spec_from_file_location(
        "hrms.regional.south_korea.holiday_fetch", _FETCH_PATH
    )
    fetch_mod = importlib.util.module_from_spec(fetch_spec)
    sys.modules["hrms.regional.south_korea.holiday_fetch"] = fetch_mod
    fetch_spec.loader.exec_module(fetch_mod)

    sys.modules["frappe"] = fake_frappe

    seed_spec = importlib.util.spec_from_file_location(
        "hrms.regional.south_korea.holiday_seed", _SEED_PATH
    )
    seed_mod = importlib.util.module_from_spec(seed_spec)
    sys.modules["hrms.regional.south_korea.holiday_seed"] = seed_mod
    seed_spec.loader.exec_module(seed_mod)

    return seed_mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestSeedHolidayListHumanApprovalGate(unittest.TestCase):
    """human_approved=False は fail-closed でデータを書かない."""

    def setUp(self):
        self.fake_frappe = FakeFrappeModule()
        self.mod = _load_seed_module(self.fake_frappe)

    def tearDown(self):
        sys.modules.pop("frappe", None)
        sys.modules.pop("hrms.regional.south_korea.holiday_seed", None)
        sys.modules.pop("hrms.regional.south_korea.holiday_fetch", None)

    def test_not_approved_returns_applied_false(self):
        result = self.mod.seed_korea_holiday_list(year=2025, human_approved=False)
        self.assertFalse(result["applied"])
        self.assertFalse(result["human_approval_verified"])
        self.assertEqual(result["new_count"], 0)

    def test_not_approved_does_not_create_doc(self):
        self.mod.seed_korea_holiday_list(year=2025, human_approved=False)
        self.assertEqual(len(self.fake_frappe._created_docs), 0)

    def test_not_approved_default_list_name(self):
        result = self.mod.seed_korea_holiday_list(year=2025, human_approved=False)
        self.assertEqual(result["holiday_list"], "한국 공휴일 2025")

    def test_not_approved_custom_list_name_preserved(self):
        result = self.mod.seed_korea_holiday_list(
            year=2025,
            holiday_list_name="테스트리스트",
            human_approved=False,
        )
        self.assertEqual(result["holiday_list"], "테스트리스트")


class TestSeedHolidayListApproved(unittest.TestCase):
    """human_approved=True: 새 Holiday List 생성 + 공휴일 삽입."""

    def setUp(self):
        self.fake_frappe = FakeFrappeModule()
        self.mod = _load_seed_module(self.fake_frappe)

    def tearDown(self):
        sys.modules.pop("frappe", None)
        sys.modules.pop("hrms.regional.south_korea.holiday_seed", None)
        sys.modules.pop("hrms.regional.south_korea.holiday_fetch", None)

    def test_approved_returns_applied_true(self):
        result = self.mod.seed_korea_holiday_list(year=2025, human_approved=True)
        self.assertTrue(result["applied"])
        self.assertTrue(result["human_approval_verified"])

    def test_approved_creates_holiday_list(self):
        result = self.mod.seed_korea_holiday_list(year=2025, human_approved=True)
        self.assertIn("한국 공휴일 2025", self.fake_frappe._holiday_list_docs)

    def test_approved_inserts_correct_count(self):
        result = self.mod.seed_korea_holiday_list(year=2025, human_approved=True)
        self.assertGreater(result["new_count"], 0)
        self.assertEqual(result["existing_count"], 0)

    def test_approved_custom_list_name(self):
        result = self.mod.seed_korea_holiday_list(
            year=2026,
            holiday_list_name="위너스_2026",
            human_approved=True,
        )
        self.assertEqual(result["holiday_list"], "위너스_2026")
        self.assertIn("위너스_2026", self.fake_frappe._holiday_list_docs)

    def test_approved_source_is_hardcoded_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            result = self.mod.seed_korea_holiday_list(year=2025, human_approved=True)
        self.assertEqual(result["source"], "hardcoded")

    def test_approved_returns_year(self):
        result = self.mod.seed_korea_holiday_list(year=2027, human_approved=True)
        self.assertEqual(result["year"], 2027)


class TestSeedHolidayListIdempotent(unittest.TestCase):
    """이미 같은 날짜+이름 있으면 no-op (idempotent)."""

    def setUp(self):
        # Pre-populate: 신정 already exists
        self.fake_frappe = FakeFrappeModule(
            existing_lists={"한국 공휴일 2025"},
            existing_holidays={
                "한국 공휴일 2025": [("2025-01-01", "신정")],
            },
        )
        self.mod = _load_seed_module(self.fake_frappe)

    def tearDown(self):
        sys.modules.pop("frappe", None)
        sys.modules.pop("hrms.regional.south_korea.holiday_seed", None)
        sys.modules.pop("hrms.regional.south_korea.holiday_fetch", None)

    def test_existing_holiday_not_duplicated(self):
        result = self.mod.seed_korea_holiday_list(year=2025, human_approved=True)
        self.assertGreaterEqual(result["existing_count"], 1)
        # 신정 (Jan 1) should be counted as existing
        doc = self.fake_frappe._holiday_list_docs.get("한국 공휴일 2025")
        if doc:
            new_holidays = [h for h in doc.holidays if h["holiday_date"] == "2025-01-01"]
            self.assertEqual(len(new_holidays), 0, "신정 should not be re-inserted")

    def test_new_holidays_added_alongside_existing(self):
        result = self.mod.seed_korea_holiday_list(year=2025, human_approved=True)
        self.assertGreater(result["new_count"], 0)
        self.assertEqual(result["existing_count"], 1)


class TestSeedHolidayListMulti(unittest.TestCase):
    """seed_korea_holiday_list_multi — 여러 연도 일괄 시드."""

    def setUp(self):
        self.fake_frappe = FakeFrappeModule()
        self.mod = _load_seed_module(self.fake_frappe)

    def tearDown(self):
        sys.modules.pop("frappe", None)
        sys.modules.pop("hrms.regional.south_korea.holiday_seed", None)
        sys.modules.pop("hrms.regional.south_korea.holiday_fetch", None)

    def test_default_years_are_2025_2026_2027(self):
        results = self.mod.seed_korea_holiday_list_multi(human_approved=False)
        years = [r["year"] for r in results]
        self.assertEqual(years, [2025, 2026, 2027])

    def test_custom_years(self):
        results = self.mod.seed_korea_holiday_list_multi(
            years=[2025, 2026], human_approved=False
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["year"], 2025)
        self.assertEqual(results[1]["year"], 2026)

    def test_multi_not_approved_all_applied_false(self):
        results = self.mod.seed_korea_holiday_list_multi(human_approved=False)
        self.assertTrue(all(not r["applied"] for r in results))

    def test_multi_approved_all_applied_true(self):
        results = self.mod.seed_korea_holiday_list_multi(human_approved=True)
        self.assertTrue(all(r["applied"] for r in results))


class TestSeedFrappeNotAvailable(unittest.TestCase):
    """frappe import 불가 시 RuntimeError."""

    def setUp(self):
        # Make frappe unavailable by patching holiday_seed module's frappe attr to None
        self.fake_frappe = FakeFrappeModule()
        self.mod = _load_seed_module(self.fake_frappe)
        # Directly patch the module's frappe reference to None
        self._orig_frappe = self.mod.frappe
        self.mod.frappe = None

    def tearDown(self):
        self.mod.frappe = self._orig_frappe
        sys.modules.pop("frappe", None)
        sys.modules.pop("hrms.regional.south_korea.holiday_seed", None)
        sys.modules.pop("hrms.regional.south_korea.holiday_fetch", None)

    def test_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            self.mod.seed_korea_holiday_list(year=2025, human_approved=True)


if __name__ == "__main__":
    unittest.main()
