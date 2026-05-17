"""Tests for hrms/regional/south_korea/holiday_fetch.py.

네트워크 없이 실행 가능: urllib.request.urlopen을 mock 처리.
"""

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Load module under test without Frappe in path
# ---------------------------------------------------------------------------
_ROOT = pathlib.Path(__file__).resolve().parents[2]
_FETCH_PATH = _ROOT / "hrms" / "regional" / "south_korea" / "holiday_fetch.py"


def _load_fetch_module():
    spec = importlib.util.spec_from_file_location("holiday_fetch", _FETCH_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Canned XML fixtures (encoded as UTF-8 bytes — Korean chars not valid in b"")
# ---------------------------------------------------------------------------
_VALID_XML_JAN_2026 = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    "<response>\n"
    "    <header>\n"
    "        <resultCode>00</resultCode>\n"
    "        <resultMsg>OK</resultMsg>\n"
    "    </header>\n"
    "    <body>\n"
    "        <items>\n"
    "            <item>\n"
    "                <dateName>신정</dateName>\n"  # 신정
    "                <isHoliday>Y</isHoliday>\n"
    "                <locdate>20260101</locdate>\n"
    "                <seq>1</seq>\n"
    "            </item>\n"
    "        </items>\n"
    "        <numOfRows>50</numOfRows>\n"
    "        <pageNo>1</pageNo>\n"
    "        <totalCount>1</totalCount>\n"
    "    </body>\n"
    "</response>"
).encode("utf-8")

_EMPTY_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    "<response>\n"
    "    <header>\n"
    "        <resultCode>00</resultCode>\n"
    "        <resultMsg>OK</resultMsg>\n"
    "    </header>\n"
    "    <body>\n"
    "        <items/>\n"
    "        <numOfRows>50</numOfRows>\n"
    "        <pageNo>1</pageNo>\n"
    "        <totalCount>0</totalCount>\n"
    "    </body>\n"
    "</response>"
).encode("utf-8")

_ERROR_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    "<response>\n"
    "    <header>\n"
    "        <resultCode>30</resultCode>\n"
    "        <resultMsg>SERVICE KEY IS NOT REGISTERED ERROR</resultMsg>\n"
    "    </header>\n"
    "    <body/>\n"
    "</response>"
).encode("utf-8")

_NON_HOLIDAY_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    "<response>\n"
    "    <header>\n"
    "        <resultCode>00</resultCode>\n"
    "        <resultMsg>OK</resultMsg>\n"
    "    </header>\n"
    "    <body>\n"
    "        <items>\n"
    "            <item>\n"
    "                <dateName>평일</dateName>\n"  # 평일
    "                <isHoliday>N</isHoliday>\n"
    "                <locdate>20260102</locdate>\n"
    "                <seq>1</seq>\n"
    "            </item>\n"
    "        </items>\n"
    "        <numOfRows>50</numOfRows>\n"
    "        <pageNo>1</pageNo>\n"
    "        <totalCount>1</totalCount>\n"
    "    </body>\n"
    "</response>"
).encode("utf-8")


def _make_mock_urlopen(xml_bytes: bytes):
    """urlopen context manager mock that returns xml_bytes."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=xml_bytes)))
    cm.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=cm)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestIsSubstitute(unittest.TestCase):
    def setUp(self):
        self.mod = _load_fetch_module()

    def test_substitute_name_returns_true(self):
        self.assertTrue(self.mod.is_substitute("대체공휴일(삼일절)"))
        self.assertTrue(self.mod.is_substitute("대체공휴일(어린이날/부처님오신날)"))
        self.assertTrue(self.mod.is_substitute("대체공휴일(추석)"))

    def test_regular_holiday_returns_false(self):
        self.assertFalse(self.mod.is_substitute("신정"))
        self.assertFalse(self.mod.is_substitute("설날"))
        self.assertFalse(self.mod.is_substitute("광복절"))
        self.assertFalse(self.mod.is_substitute(""))

    def test_none_like_returns_false(self):
        self.assertFalse(self.mod.is_substitute(""))


class TestGetHardcoded(unittest.TestCase):
    def setUp(self):
        self.mod = _load_fetch_module()

    def test_2025_returns_nonempty_list(self):
        holidays = self.mod.get_hardcoded(2025)
        self.assertIsInstance(holidays, list)
        self.assertGreater(len(holidays), 0)

    def test_2026_returns_nonempty_list(self):
        holidays = self.mod.get_hardcoded(2026)
        self.assertGreater(len(holidays), 0)

    def test_2027_returns_nonempty_list(self):
        holidays = self.mod.get_hardcoded(2027)
        self.assertGreater(len(holidays), 0)

    def test_unsupported_year_returns_empty(self):
        self.assertEqual(self.mod.get_hardcoded(1900), [])
        self.assertEqual(self.mod.get_hardcoded(2099), [])

    def test_each_item_has_required_keys(self):
        for year in (2025, 2026, 2027):
            for item in self.mod.get_hardcoded(year):
                self.assertIn("date", item)
                self.assertIn("name", item)
                self.assertIn("is_substitute", item)
                self.assertEqual(item["source"], "hardcoded")

    def test_date_format_is_iso(self):
        import datetime
        for year in (2025, 2026, 2027):
            for item in self.mod.get_hardcoded(year):
                # Must be parseable YYYY-MM-DD
                dt = datetime.date.fromisoformat(item["date"])
                self.assertEqual(dt.year, year)

    def test_2025_representative_dates(self):
        holidays = self.mod.get_hardcoded(2025)
        dates_by_name = {h["name"]: h["date"] for h in holidays}
        # 5 representative checks
        self.assertEqual(dates_by_name["신정"], "2025-01-01")
        self.assertEqual(dates_by_name["삼일절"], "2025-03-01")
        self.assertEqual(dates_by_name["대체공휴일(삼일절)"], "2025-03-03")
        self.assertEqual(dates_by_name["추석"], "2025-10-06")
        self.assertEqual(dates_by_name["기독탄신일"], "2025-12-25")

    def test_2026_representative_dates(self):
        holidays = self.mod.get_hardcoded(2026)
        dates_by_date = {h["date"]: h["name"] for h in holidays}
        # 5 representative checks
        self.assertEqual(dates_by_date["2026-01-01"], "신정")
        self.assertEqual(dates_by_date["2026-03-02"], "대체공휴일(삼일절)")
        self.assertIn("2026-06-03", dates_by_date)  # 선거일
        self.assertEqual(dates_by_date["2026-09-28"], "대체공휴일(추석연휴)")
        self.assertEqual(dates_by_date["2026-10-05"], "대체공휴일(개천절)")

    def test_2027_representative_dates(self):
        holidays = self.mod.get_hardcoded(2027)
        dates_by_date = {h["date"]: h["name"] for h in holidays}
        # 5 representative checks
        self.assertEqual(dates_by_date["2027-01-01"], "신정")
        self.assertEqual(dates_by_date["2027-02-08"], "대체공휴일(설날)")
        self.assertEqual(dates_by_date["2027-06-07"], "대체공휴일(현충일)")
        self.assertEqual(dates_by_date["2027-10-04"], "대체공휴일(개천절)")
        self.assertEqual(dates_by_date["2027-10-11"], "대체공휴일(한글날)")

    def test_2025_substitute_flags(self):
        holidays = self.mod.get_hardcoded(2025)
        subs = [h for h in holidays if h["is_substitute"]]
        sub_dates = {h["date"] for h in subs}
        self.assertIn("2025-03-03", sub_dates)  # 대체공휴일(삼일절)
        self.assertIn("2025-05-06", sub_dates)  # 대체공휴일(어린이날/부처님오신날)
        self.assertIn("2025-10-08", sub_dates)  # 대체공휴일(추석)

    def test_2026_substitute_flags(self):
        holidays = self.mod.get_hardcoded(2026)
        subs = {h["date"] for h in holidays if h["is_substitute"]}
        self.assertIn("2026-03-02", subs)
        self.assertIn("2026-05-25", subs)
        self.assertIn("2026-08-17", subs)
        self.assertIn("2026-09-28", subs)
        self.assertIn("2026-10-05", subs)

    def test_2027_substitute_flags(self):
        holidays = self.mod.get_hardcoded(2027)
        subs = {h["date"] for h in holidays if h["is_substitute"]}
        self.assertIn("2027-02-08", subs)
        self.assertIn("2027-06-07", subs)
        self.assertIn("2027-08-16", subs)
        self.assertIn("2027-10-04", subs)
        self.assertIn("2027-10-11", subs)


class TestFetchHolidaysNoKey(unittest.TestCase):
    """API 키 없을 때 hardcoded fallback이 작동하는지 확인."""

    def setUp(self):
        self.mod = _load_fetch_module()

    def test_no_key_returns_hardcoded(self):
        import os
        env = os.environ.copy()
        env.pop("DATA_GO_KR_SERVICE_KEY", None)
        with patch.dict("os.environ", {}, clear=True):
            result = self.mod.fetch_holidays(2025)
        self.assertGreater(len(result), 0)
        self.assertTrue(all(h["source"] == "hardcoded" for h in result))

    def test_invalid_year_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.mod.fetch_holidays(1900)

    def test_invalid_year_high_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.mod.fetch_holidays(2200)

    def test_unknown_supported_year_returns_empty_not_raise(self):
        # 2030 이 hardcoded에 없으면 빈 리스트 (fallback 정상 처리)
        with patch.dict("os.environ", {}, clear=True):
            result = self.mod.fetch_holidays(2030)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)


class TestFetchWithApiSuccess(unittest.TestCase):
    """API 키 있고 API 성공 시 source=api 반환."""

    def setUp(self):
        self.mod = _load_fetch_module()

    def test_api_success_returns_api_source(self):
        # 12개월 중 1월만 실제 항목, 나머지는 empty
        def side_effect(*args, **kwargs):
            url = args[0].get_full_url() if hasattr(args[0], "get_full_url") else str(args[0])
            if "solMonth=01" in url:
                xml_bytes = _VALID_XML_JAN_2026
            else:
                xml_bytes = _EMPTY_XML
            cm = MagicMock()
            cm.__enter__ = MagicMock(
                return_value=MagicMock(read=MagicMock(return_value=xml_bytes))
            )
            cm.__exit__ = MagicMock(return_value=False)
            return cm

        with patch("urllib.request.urlopen", side_effect=side_effect):
            result = self.mod.fetch_with_api(2026, "FAKE_KEY", 5.0)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["date"], "2026-01-01")
        self.assertEqual(result[0]["name"], "신정")
        self.assertEqual(result[0]["source"], "api")
        self.assertFalse(result[0]["is_substitute"])

    def test_api_filters_non_holiday(self):
        """isHoliday=N 항목은 포함하지 않는다."""
        mock_open = _make_mock_urlopen(_NON_HOLIDAY_XML)
        with patch("urllib.request.urlopen", mock_open):
            result = self.mod.fetch_with_api(2026, "FAKE_KEY", 5.0)
        self.assertEqual(result, [])

    def test_api_error_xml_raises(self):
        """resultCode!=00이면 ValueError."""
        mock_open = _make_mock_urlopen(_ERROR_XML)
        with patch("urllib.request.urlopen", mock_open):
            with self.assertRaises(ValueError):
                self.mod.fetch_with_api(2025, "FAKE_KEY", 5.0)


class TestFetchHolidaysApiFallback(unittest.TestCase):
    """API 실패 시 hardcoded fallback."""

    def setUp(self):
        self.mod = _load_fetch_module()

    def test_network_error_falls_back_to_hardcoded(self):
        import urllib.error

        with patch.dict("os.environ", {"DATA_GO_KR_SERVICE_KEY": "FAKE_KEY"}):
            with patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError("connection refused"),
            ):
                result = self.mod.fetch_holidays(2025)

        self.assertGreater(len(result), 0)
        self.assertTrue(all(h["source"] == "hardcoded" for h in result))

    def test_timeout_falls_back_to_hardcoded(self):
        import socket

        with patch.dict("os.environ", {"DATA_GO_KR_SERVICE_KEY": "FAKE_KEY"}):
            with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
                result = self.mod.fetch_holidays(2026)

        self.assertGreater(len(result), 0)
        self.assertTrue(all(h["source"] == "hardcoded" for h in result))

    def test_api_key_from_env_used(self):
        """환경변수 DATA_GO_KR_SERVICE_KEY를 사용한다."""
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(req)
            raise Exception("abort")

        with patch.dict("os.environ", {"DATA_GO_KR_SERVICE_KEY": "ENV_KEY"}):
            with patch("urllib.request.urlopen", fake_urlopen):
                result = self.mod.fetch_holidays(2025)

        # urlopen이 호출됐으므로 API 경로 진입 확인
        self.assertGreater(len(calls), 0)
        # fallback으로 hardcoded 반환
        self.assertTrue(all(h["source"] == "hardcoded" for h in result))


class TestParseApiXml(unittest.TestCase):
    """_parse_api_xml 내부 파서 검증."""

    def setUp(self):
        self.mod = _load_fetch_module()

    def test_valid_xml_parses_correctly(self):
        items = self.mod._parse_api_xml(_VALID_XML_JAN_2026)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["date"], "2026-01-01")
        self.assertEqual(items[0]["name"], "신정")
        self.assertFalse(items[0]["is_substitute"])

    def test_empty_items_returns_empty(self):
        items = self.mod._parse_api_xml(_EMPTY_XML)
        self.assertEqual(items, [])

    def test_error_result_code_raises(self):
        with self.assertRaises(ValueError):
            self.mod._parse_api_xml(_ERROR_XML)


if __name__ == "__main__":
    unittest.main()
