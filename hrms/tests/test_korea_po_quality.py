"""Tests for hrms/locale/ko.po translation quality (PWA-exposed strings).

프레임워크-프리: frappe import 없이 순수 .po 파싱 + assert.
직접 실행 가능: `python3 hrms/tests/test_korea_po_quality.py`
"""

import pathlib
import re
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PO_PATH = _ROOT / "hrms" / "locale" / "ko.po"


def _parse_po(path: pathlib.Path) -> dict:
    """아주 단순한 .po 파서: msgid -> msgstr 매핑.

    - 여러 줄에 걸친 문자열(연속되는 따옴표 줄)도 이어붙인다.
    - 헤더 블록(msgid "")은 별도 키 ""로 저장되어 자연스럽게 검사 대상에서
      제외된다 (빈 msgstr 검사 시 msgid가 ""인 항목은 건너뛴다).
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    entries = []  # list of (msgid, msgstr)
    i = 0
    n = len(lines)

    def _unquote(line: str) -> str:
        # line is like: msgid "some text" — extract the quoted content.
        match = re.match(r'^\s*(?:msgid|msgstr)\s*"(.*)"\s*$', line)
        if match:
            return match.group(1)
        # continuation line: just "text"
        match = re.match(r'^\s*"(.*)"\s*$', line)
        if match:
            return match.group(1)
        return ""

    while i < n:
        line = lines[i]
        if line.startswith("msgid "):
            msgid_parts = [_unquote(line)]
            i += 1
            while i < n and lines[i].startswith('"'):
                msgid_parts.append(_unquote(lines[i]))
                i += 1
            msgid = "".join(msgid_parts)

            msgstr_parts = []
            if i < n and lines[i].startswith("msgstr "):
                msgstr_parts.append(_unquote(lines[i]))
                i += 1
                while i < n and lines[i].startswith('"'):
                    msgstr_parts.append(_unquote(lines[i]))
                    i += 1
            msgstr = "".join(msgstr_parts)

            entries.append((msgid, msgstr))
        else:
            i += 1

    # msgid 중복 없이 마지막 항목 기준으로 dict 구성(파일에 중복 msgid가
    # 있으면 안 되므로, 있을 경우 아래 duplicate 체크 테스트가 잡아낸다).
    mapping = {}
    for msgid, msgstr in entries:
        mapping[msgid] = msgstr

    return mapping, entries


class TestKoreaPoTranslationQuality(unittest.TestCase):
    """PWA 노출 문자열의 번역 품질 (자연스러운 한국어 어순)."""

    EXPECTED = {
        "Request Attendance": "출근기록 신청",
        "Request a Shift": "교대근무 신청",
        "Request Leave": "휴가 신청",
        "Claim an Expense": "경비 청구",
        "Request an Advance": "선급금 신청",
        "View Salary Slips": "급여명세서 보기",
        "Quick Links": "빠른 링크",
        "Salary": "급여",
        "Home": "홈",
        "Attendance": "출근기록",
        "Leaves": "휴가",
        "Expenses": "경비",
        "Check In": "출근",
        "Check Out": "퇴근",
        "My Profile": "내 프로필",
        "Notifications": "알림",
        "Salary Slips": "급여명세서",
        "Leave Balance": "휴가 잔여",
        "Upcoming Holidays": "다가오는 공휴일",
        # 데스크 노출 코어 문자열 (frappe ko 누락분 — 노호 런칭 검증에서 실측)
        "Status": "상태",
        "Draft": "임시저장",
        "Department": "부서",
        "Full Name": "이름",
        "Reports": "리포트",
        "Notification": "알림",
        "Getting Started": "시작 안내",
        "Login to Korea HRMS": "Korea HRMS 로그인",
    }

    @classmethod
    def setUpClass(cls):
        cls.mapping, cls.entries = _parse_po(_PO_PATH)

    def test_po_file_exists(self):
        self.assertTrue(_PO_PATH.exists(), f"{_PO_PATH} not found")

    def test_no_duplicate_msgid(self):
        seen = {}
        dupes = []
        for msgid, _msgstr in self.entries:
            if msgid == "":
                continue
            seen[msgid] = seen.get(msgid, 0) + 1
        for msgid, count in seen.items():
            if count > 1:
                dupes.append((msgid, count))
        self.assertEqual(dupes, [], f"Duplicate msgid found: {dupes}")

    def test_expected_translations(self):
        for msgid, expected_msgstr in self.EXPECTED.items():
            with self.subTest(msgid=msgid):
                self.assertIn(msgid, self.mapping, f"msgid {msgid!r} not found in ko.po")
                self.assertEqual(
                    self.mapping[msgid],
                    expected_msgstr,
                    f"msgid {msgid!r}: expected {expected_msgstr!r}, got {self.mapping.get(msgid)!r}",
                )

    def test_no_empty_msgstr_excluding_header(self):
        empty = [
            msgid
            for msgid, msgstr in self.entries
            if msgid != "" and msgstr == ""
        ]
        self.assertEqual(empty, [], f"Empty msgstr found (excluding header) for: {empty}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    unittest.main()
