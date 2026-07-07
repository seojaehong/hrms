"""
hrms/tests/test_korea_approval_inbox.py
결재 인박스 백엔드 단위 테스트.

Frappe에 의존하지 않는 독립 테스트 — FakeFrappe 패턴 사용.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import sys
import types
import unittest

# ---------------------------------------------------------------------------
# Fake 인프라
# ---------------------------------------------------------------------------

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "hrms"
    / "regional"
    / "south_korea"
    / "approval_inbox.py"
)


class FakeFrappeError(Exception):
    pass


class FakeDoc(types.SimpleNamespace):
    """frappe.get_doc() 반환값 시뮬레이터."""

    def __init__(self, doctype, name, **kwargs):
        super().__init__(doctype=doctype, name=name, **kwargs)
        self._saved = False
        self._comments_inserted = []

    def save(self, ignore_permissions=False):
        self._saved = True

    def insert(self, ignore_permissions=False):
        return self


class FakeDB:
    def __init__(self):
        self._doctype_exists = set()
        self._list_data: dict[str, list[dict]] = {}

    def exists(self, doctype, name):
        if doctype == "DocType":
            return name if name in self._doctype_exists else None
        return None

    def get_list(self, doctype, filters=None, fields=None, order_by=None, limit=None):
        return list(self._list_data.get(doctype, []))


class FakeFrappe(types.SimpleNamespace):
    def __init__(self):
        super().__init__()
        self.db = FakeDB()
        self._ = lambda s: s
        self.whitelist = lambda *a, **kw: (lambda fn: fn)
        self._docs: dict[tuple, FakeDoc] = {}
        self._comments: list[dict] = []
        self._get_list_calls: list[dict] = []
        self._throw_fn = self._default_throw
        self.log_error = lambda *a, **kw: None

    def _default_throw(self, message, exc=None):
        raise FakeFrappeError(message)

    @property
    def throw(self):
        return self._throw_fn

    def get_doc(self, payload_or_doctype, name=None):
        if isinstance(payload_or_doctype, dict):
            payload = dict(payload_or_doctype)
            doctype = payload.get("doctype")
            if doctype == "Comment":
                self._comments.append(payload)
                return FakeDoc(doctype="Comment", name="CMT-NEW")
            doc_name = payload.get("name", "NEW")
            return FakeDoc(doctype=doctype, name=doc_name, **{k: v for k, v in payload.items() if k not in ("doctype", "name")})
        # get_doc("DocType", "name") 형식
        doctype = payload_or_doctype
        key = (doctype, name)
        if key in self._docs:
            return self._docs[key]
        doc = FakeDoc(doctype=doctype, name=name)
        self._docs[key] = doc
        return doc

    def get_list(self, doctype, filters=None, fields=None, order_by=None, limit=None):
        self._get_list_calls.append(
            {"doctype": doctype, "filters": filters, "fields": fields}
        )
        return list(self.db._list_data.get(doctype, []))


def _load_module(fake_frappe: FakeFrappe):
    """approval_inbox.py를 격리된 네임스페이스에서 로드."""
    sys.modules["frappe"] = fake_frappe
    spec = importlib.util.spec_from_file_location("_test_approval_inbox", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# list_pending_approvals 테스트
# ---------------------------------------------------------------------------

class TestListPendingApprovals(unittest.TestCase):
    def setUp(self):
        self.fake = FakeFrappe()
        self.mod = _load_module(self.fake)

    def tearDown(self):
        sys.modules.pop("frappe", None)

    def test_returns_empty_when_no_doctypes_exist(self):
        """doctype이 없는 환경에서 빈 리스트 반환."""
        result = self.mod.list_pending_approvals(
            approver="test@example.com", as_of_date=dt.date(2026, 5, 1)
        )
        self.assertEqual(result, [])

    def test_raises_when_approver_is_empty(self):
        with self.assertRaises(FakeFrappeError):
            self.mod.list_pending_approvals(approver="", as_of_date=dt.date(2026, 5, 1))

    def test_returns_leave_applications_when_doctype_exists(self):
        """Leave Application doctype이 존재하고 데이터가 있으면 항목 반환."""
        self.fake.db._doctype_exists.add("Leave Application")
        self.fake.db._list_data["Leave Application"] = [
            {
                "name": "HR-LA-2026-00001",
                "employee_name": "민지 김",
                "leave_type": "연차",
                "from_date": dt.date(2026, 5, 10),
                "to_date": dt.date(2026, 5, 12),
                "total_leave_days": 3.0,
                "description": "여행",
                "creation": dt.datetime(2026, 5, 1, 9, 0, 0),
                "leave_approver": "approver@example.com",
            }
        ]

        result = self.mod.list_pending_approvals(
            approver="approver@example.com", as_of_date=dt.date(2026, 5, 1)
        )

        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertEqual(item["doctype"], "Leave Application")
        self.assertEqual(item["name"], "HR-LA-2026-00001")
        self.assertIn("민지 김", item["title"])
        self.assertEqual(item["applicant_name"], "민지 김")
        self.assertIn("requested_at", item)
        self.assertIn("url_app", item)
        self.assertIn("url_pwa", item)
        self.assertEqual(item["details"]["leave_type"], "연차")
        self.assertEqual(item["details"]["total_leave_days"], 3.0)

    def test_returns_expense_claims_when_doctype_exists(self):
        self.fake.db._doctype_exists.add("Expense Claim")
        self.fake.db._list_data["Expense Claim"] = [
            {
                "name": "EXP-2026-00001",
                "employee_name": "재홍 서",
                "total_claimed_amount": 50000,
                "currency": "KRW",
                "posting_date": dt.date(2026, 5, 5),
                "creation": dt.datetime(2026, 5, 5, 10, 0, 0),
                "expense_approver": "approver@example.com",
                "company": "노무법인 위너스",
            }
        ]

        result = self.mod.list_pending_approvals(
            approver="approver@example.com", as_of_date=dt.date(2026, 5, 1)
        )

        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertEqual(item["doctype"], "Expense Claim")
        self.assertEqual(item["name"], "EXP-2026-00001")
        self.assertIn("경비청구", item["title"])
        self.assertEqual(item["details"]["total_claimed_amount"], 50000)
        self.assertEqual(item["details"]["currency"], "KRW")

    def test_aggregates_multiple_doctypes(self):
        """여러 doctype 동시 활성화 시 합산 반환."""
        self.fake.db._doctype_exists.add("Leave Application")
        self.fake.db._doctype_exists.add("Expense Claim")
        self.fake.db._list_data["Leave Application"] = [
            {
                "name": "HR-LA-001",
                "employee_name": "A",
                "leave_type": "연차",
                "from_date": dt.date(2026, 5, 1),
                "to_date": dt.date(2026, 5, 1),
                "total_leave_days": 1.0,
                "description": "",
                "creation": dt.datetime(2026, 5, 1, 8, 0, 0),
                "leave_approver": "mgr@example.com",
            }
        ]
        self.fake.db._list_data["Expense Claim"] = [
            {
                "name": "EXP-001",
                "employee_name": "B",
                "total_claimed_amount": 10000,
                "currency": "KRW",
                "posting_date": dt.date(2026, 5, 2),
                "creation": dt.datetime(2026, 5, 2, 9, 0, 0),
                "expense_approver": "mgr@example.com",
                "company": "테스트",
            }
        ]

        result = self.mod.list_pending_approvals(
            approver="mgr@example.com", as_of_date=dt.date(2026, 5, 1)
        )

        self.assertEqual(len(result), 2)
        doctypes = {item["doctype"] for item in result}
        self.assertIn("Leave Application", doctypes)
        self.assertIn("Expense Claim", doctypes)

    def test_result_sorted_by_requested_at_desc(self):
        """결과가 requested_at 내림차순으로 정렬됨."""
        self.fake.db._doctype_exists.add("Leave Application")
        self.fake.db._list_data["Leave Application"] = [
            {
                "name": "HR-LA-OLD",
                "employee_name": "Old",
                "leave_type": "연차",
                "from_date": dt.date(2026, 4, 1),
                "to_date": dt.date(2026, 4, 1),
                "total_leave_days": 1.0,
                "description": "",
                "creation": dt.datetime(2026, 4, 1, 8, 0, 0),
                "leave_approver": "mgr@example.com",
            },
            {
                "name": "HR-LA-NEW",
                "employee_name": "New",
                "leave_type": "병가",
                "from_date": dt.date(2026, 5, 10),
                "to_date": dt.date(2026, 5, 10),
                "total_leave_days": 1.0,
                "description": "",
                "creation": dt.datetime(2026, 5, 10, 9, 0, 0),
                "leave_approver": "mgr@example.com",
            },
        ]

        result = self.mod.list_pending_approvals(
            approver="mgr@example.com", as_of_date=dt.date(2026, 5, 1)
        )

        self.assertEqual(result[0]["name"], "HR-LA-NEW")
        self.assertEqual(result[1]["name"], "HR-LA-OLD")

    def test_graceful_skip_when_missing_optional_doctype(self):
        """누락된 doctype 은 전체 실패 없이 스킵."""
        self.fake.db._doctype_exists.add("Leave Application")
        # Expense Claim, Payroll, Contract은 없음
        self.fake.db._list_data["Leave Application"] = [
            {
                "name": "HR-LA-001",
                "employee_name": "A",
                "leave_type": "연차",
                "from_date": dt.date(2026, 5, 1),
                "to_date": dt.date(2026, 5, 1),
                "total_leave_days": 1.0,
                "description": "",
                "creation": dt.datetime(2026, 5, 1, 8, 0, 0),
                "leave_approver": "mgr@example.com",
            }
        ]

        result = self.mod.list_pending_approvals(
            approver="mgr@example.com", as_of_date=dt.date(2026, 5, 1)
        )
        # Leave Application 하나만 반환
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["doctype"], "Leave Application")


# ---------------------------------------------------------------------------
# Korea Payroll Closing Draft 수집 테스트 (버그: "1 확정 대기 ↔ 인박스 0건")
# ---------------------------------------------------------------------------

_DRAFT_JSON_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "hrms"
    / "hr"
    / "doctype"
    / "korea_payroll_closing_draft"
    / "korea_payroll_closing_draft.json"
)


def _load_draft_doctype_def() -> dict:
    import json

    return json.loads(_DRAFT_JSON_PATH.read_text(encoding="utf-8"))


class TestPayrollClosingDraftInbox(unittest.TestCase):
    """마감 draft가 결재 인박스 '급여 마감' 항목으로 정확히 수집되는지."""

    ROW = {
        "name": "KPCD-0001",
        "company": "노무법인 위너스",
        "workplace": "노호",
        "period_start": dt.date(2026, 5, 1),
        "period_end": dt.date(2026, 5, 31),
        "status": "draft_pending_human_approval",
        "creation": dt.datetime(2026, 6, 1, 9, 0, 0),
    }

    def setUp(self):
        self.fake = FakeFrappe()
        self.mod = _load_module(self.fake)
        self.fake.db._doctype_exists.add("Korea Payroll Closing Draft")
        self.fake.db._list_data["Korea Payroll Closing Draft"] = [dict(self.ROW)]

    def tearDown(self):
        sys.modules.pop("frappe", None)

    def test_draft_pending_human_approval_appears_in_inbox(self):
        result = self.mod.list_pending_approvals(
            approver="mgr@example.com", as_of_date=dt.date(2026, 6, 1)
        )
        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertEqual(item["doctype"], "Korea Payroll Closing Draft")
        self.assertIn("페이롤마감", item["title"])
        self.assertIn("노호", item["title"])
        self.assertEqual(item["details"]["period_start"], "2026-05-01")
        self.assertEqual(item["details"]["period_end"], "2026-05-31")

    def test_url_pwa_uses_closing_session_route(self):
        """PWA에는 closing-draft 상세 라우트가 없으므로 세션 미리보기 라우트 사용."""
        result = self.mod.list_pending_approvals(
            approver="mgr@example.com", as_of_date=dt.date(2026, 6, 1)
        )
        self.assertEqual(
            result[0]["url_pwa"], "/hrms/korea-payroll-closing-session/KPCD-0001"
        )

    def test_collector_requests_only_fields_defined_in_doctype(self):
        """미존재 필드 요청 → get_list 예외 → 조용한 0건 버그의 회귀 방지.

        (과거 employee_name/pay_year_month를 요청해 doctype 필드에 없어 실패)
        """
        doctype_def = _load_draft_doctype_def()
        defined = {f["fieldname"] for f in doctype_def["fields"]}
        # Frappe 표준 메타 필드
        defined |= {"name", "creation", "modified", "owner", "docstatus"}

        self.mod.list_pending_approvals(
            approver="mgr@example.com", as_of_date=dt.date(2026, 6, 1)
        )
        calls = [
            c
            for c in self.fake._get_list_calls
            if c["doctype"] == "Korea Payroll Closing Draft"
        ]
        self.assertTrue(calls, "Korea Payroll Closing Draft get_list 호출 없음")
        for call in calls:
            unknown = set(call["fields"]) - defined
            self.assertEqual(
                unknown, set(), f"doctype에 없는 필드 요청: {sorted(unknown)}"
            )

    def test_collector_filters_by_pending_status(self):
        self.mod.list_pending_approvals(
            approver="mgr@example.com", as_of_date=dt.date(2026, 6, 1)
        )
        call = next(
            c
            for c in self.fake._get_list_calls
            if c["doctype"] == "Korea Payroll Closing Draft"
        )
        self.assertEqual(call["filters"]["status"], "draft_pending_human_approval")
        self.assertEqual(call["filters"]["docstatus"], 0)

    def test_approve_sets_status_within_allowed_select_options(self):
        """승인=문서 제출이 아니라 draft에 승인 기록(status 전이)만 남긴다.

        doctype JSON의 status Select options에 정의된 값으로만 전이해야 함
        (mutation_boundary=draft_only_no_submit_no_approve_no_send 준수,
         is_submittable=0 → submit 자체가 없음).
        """
        doctype_def = _load_draft_doctype_def()
        status_field = next(
            f for f in doctype_def["fields"] if f["fieldname"] == "status"
        )
        allowed = set(status_field["options"].split("\n"))
        self.assertFalse(doctype_def.get("is_submittable"), "draft는 비제출 doctype")

        draft = FakeDoc(
            doctype="Korea Payroll Closing Draft",
            name="KPCD-0001",
            status="draft_pending_human_approval",
        )
        self.fake._docs[("Korea Payroll Closing Draft", "KPCD-0001")] = draft

        result = self.mod.approve_item(
            doctype="Korea Payroll Closing Draft",
            name="KPCD-0001",
            approver="mgr@example.com",
            human_approved=True,
        )
        self.assertEqual(result["status"], "draft_human_approved")
        self.assertIn(draft.status, allowed)
        self.assertTrue(draft._saved)

    def test_reject_sets_status_within_allowed_select_options(self):
        doctype_def = _load_draft_doctype_def()
        status_field = next(
            f for f in doctype_def["fields"] if f["fieldname"] == "status"
        )
        allowed = set(status_field["options"].split("\n"))

        draft = FakeDoc(
            doctype="Korea Payroll Closing Draft",
            name="KPCD-0002",
            status="draft_pending_human_approval",
        )
        self.fake._docs[("Korea Payroll Closing Draft", "KPCD-0002")] = draft

        result = self.mod.reject_item(
            doctype="Korea Payroll Closing Draft",
            name="KPCD-0002",
            approver="mgr@example.com",
            human_approved=True,
            comment="검토 후 수정 필요",
        )
        self.assertEqual(result["status"], "draft_human_rejected")
        self.assertIn(draft.status, allowed)


# ---------------------------------------------------------------------------
# approve_item / reject_item 테스트
# ---------------------------------------------------------------------------

class TestApproveRejectItem(unittest.TestCase):
    def setUp(self):
        self.fake = FakeFrappe()
        self.mod = _load_module(self.fake)
        # 테스트용 문서 사전 등록
        leave_doc = FakeDoc(doctype="Leave Application", name="HR-LA-001", status="Open")
        self.fake._docs[("Leave Application", "HR-LA-001")] = leave_doc

        expense_doc = FakeDoc(
            doctype="Expense Claim", name="EXP-001", approval_status="Draft"
        )
        self.fake._docs[("Expense Claim", "EXP-001")] = expense_doc

    def tearDown(self):
        sys.modules.pop("frappe", None)

    def test_approve_leave_application_sets_status_approved(self):
        result = self.mod.approve_item(
            doctype="Leave Application",
            name="HR-LA-001",
            approver="mgr@example.com",
            human_approved=True,
        )
        self.assertEqual(result["status"], "Approved")
        self.assertEqual(result["actor"], "mgr@example.com")
        doc = self.fake._docs[("Leave Application", "HR-LA-001")]
        self.assertEqual(doc.status, "Approved")
        self.assertTrue(doc._saved)

    def test_approve_leave_application_records_audit_comment(self):
        self.mod.approve_item(
            doctype="Leave Application",
            name="HR-LA-001",
            approver="mgr@example.com",
            human_approved=True,
            comment="결재합니다",
        )
        self.assertEqual(len(self.fake._comments), 1)
        comment = self.fake._comments[0]
        self.assertEqual(comment["reference_doctype"], "Leave Application")
        self.assertEqual(comment["reference_name"], "HR-LA-001")
        self.assertIn("승인", comment["content"])
        self.assertIn("mgr@example.com", comment["content"])
        self.assertIn("human_approved=True", comment["content"])
        self.assertIn("결재합니다", comment["content"])

    def test_reject_leave_application_sets_status_rejected(self):
        result = self.mod.reject_item(
            doctype="Leave Application",
            name="HR-LA-001",
            approver="mgr@example.com",
            human_approved=True,
            comment="일정 충돌",
        )
        self.assertEqual(result["status"], "Rejected")
        doc = self.fake._docs[("Leave Application", "HR-LA-001")]
        self.assertEqual(doc.status, "Rejected")

    def test_reject_records_audit_comment_with_rejection_label(self):
        self.mod.reject_item(
            doctype="Leave Application",
            name="HR-LA-001",
            approver="mgr@example.com",
            human_approved=True,
            comment="인력 부족",
        )
        self.assertIn("반려", self.fake._comments[0]["content"])

    def test_approve_raises_when_human_approved_is_false(self):
        with self.assertRaises(FakeFrappeError):
            self.mod.approve_item(
                doctype="Leave Application",
                name="HR-LA-001",
                approver="mgr@example.com",
                human_approved=False,
            )

    def test_reject_raises_when_human_approved_is_false(self):
        with self.assertRaises(FakeFrappeError):
            self.mod.reject_item(
                doctype="Leave Application",
                name="HR-LA-001",
                approver="mgr@example.com",
                human_approved=False,
            )

    def test_approve_raises_when_approver_is_empty(self):
        with self.assertRaises(FakeFrappeError):
            self.mod.approve_item(
                doctype="Leave Application",
                name="HR-LA-001",
                approver="",
                human_approved=True,
            )

    def test_approve_raises_on_unsupported_doctype(self):
        with self.assertRaises(FakeFrappeError):
            self.mod.approve_item(
                doctype="Unknown Doctype",
                name="UNKNOWN-001",
                approver="mgr@example.com",
                human_approved=True,
            )

    def test_approve_expense_claim_sets_approval_status(self):
        result = self.mod.approve_item(
            doctype="Expense Claim",
            name="EXP-001",
            approver="mgr@example.com",
            human_approved=True,
        )
        self.assertEqual(result["approval_status"], "Approved")
        doc = self.fake._docs[("Expense Claim", "EXP-001")]
        self.assertEqual(doc.approval_status, "Approved")

    def test_reject_expense_claim_sets_approval_status_rejected(self):
        result = self.mod.reject_item(
            doctype="Expense Claim",
            name="EXP-001",
            approver="mgr@example.com",
            human_approved=True,
        )
        self.assertEqual(result["approval_status"], "Rejected")


# ---------------------------------------------------------------------------
# 헬퍼 함수 테스트
# ---------------------------------------------------------------------------

class TestHelpers(unittest.TestCase):
    def setUp(self):
        self.fake = FakeFrappe()
        self.mod = _load_module(self.fake)

    def tearDown(self):
        sys.modules.pop("frappe", None)

    def test_fmt_date_with_date_object(self):
        result = self.mod._fmt_date(dt.date(2026, 5, 1))
        self.assertEqual(result, "2026-05-01")

    def test_fmt_date_with_none(self):
        self.assertIsNone(self.mod._fmt_date(None))

    def test_fmt_datetime_with_datetime_object(self):
        result = self.mod._fmt_datetime(dt.datetime(2026, 5, 1, 9, 0, 0))
        self.assertEqual(result, "2026-05-01T09:00:00")

    def test_fmt_datetime_with_none(self):
        self.assertIsNone(self.mod._fmt_datetime(None))

    def test_doctype_exists_returns_false_when_db_none(self):
        self.fake.db = None
        result = self.mod._doctype_exists("Leave Application")
        self.assertFalse(result)

    def test_doctype_exists_returns_true_when_in_set(self):
        self.fake.db._doctype_exists.add("Leave Application")
        result = self.mod._doctype_exists("Leave Application")
        self.assertTrue(result)

    def test_doctype_exists_returns_false_for_missing(self):
        result = self.mod._doctype_exists("Korea Payroll Closing Draft")
        self.assertFalse(result)


class TestCountPendingForOthers(unittest.TestCase):
    """count_pending_for_others — 다른 결재자 앞 대기 건수 (read-only)."""

    def setUp(self):
        self.fake = FakeFrappe()
        self.mod = _load_module(self.fake)

    def tearDown(self):
        sys.modules.pop("frappe", None)

    def test_returns_zero_when_no_doctypes_exist(self):
        result = self.mod.count_pending_for_others(
            approver="me@example.com", as_of_date=dt.date(2026, 6, 1)
        )
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["by_doctype"], {})
        self.assertEqual(result["approver"], "me@example.com")

    def test_counts_only_items_assigned_to_other_approvers(self):
        self.fake.db._doctype_exists.add("Korea Payroll Closing Draft")
        self.fake.db._list_data["Korea Payroll Closing Draft"] = [
            {"name": "KPCD-1", "approver": "moon@noho.im"},
            {"name": "KPCD-2", "approver": "me@example.com"},
            {"name": "KPCD-3", "approver": ""},
        ]
        self.fake.db._doctype_exists.add("Leave Application")
        self.fake.db._list_data["Leave Application"] = [
            {"name": "LA-1", "leave_approver": "other@example.com"},
        ]

        result = self.mod.count_pending_for_others(
            approver="me@example.com", as_of_date=dt.date(2026, 6, 1)
        )

        # 내 것(KPCD-2)과 미배정("")은 제외, 타인 배정만 카운트
        self.assertEqual(result["by_doctype"]["Korea Payroll Closing Draft"], 1)
        self.assertEqual(result["by_doctype"]["Leave Application"], 1)
        self.assertEqual(result["total"], 2)

    def test_raises_when_approver_is_empty(self):
        with self.assertRaises(FakeFrappeError):
            self.mod.count_pending_for_others(approver="", as_of_date=dt.date(2026, 6, 1))


if __name__ == "__main__":
    unittest.main()
