"""테스트 — 한국 통합 검색 (framework-free).

실행:
    python -m pytest tests/test_korea_global_search.py -v
    # 또는
    python -m unittest tests.test_korea_global_search -v

설계 원칙:
    - Frappe 런타임 없이 동작 (data_loader 를 mock 으로 주입)
    - 권한 필터, snippet 빌더, 템플릿 렌더링, elapsed_ms 등 코어 로직만 검증
    - 실제 DB 쿼리 없음 → mutation 없음
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

# ---------------------------------------------------------------------------
# 모듈 로드 (Frappe 없이)
# ---------------------------------------------------------------------------

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "hrms"
    / "regional"
    / "south_korea"
    / "global_search.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("korea_global_search", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


M = _load_module()


# ---------------------------------------------------------------------------
# 헬퍼 / mock loader
# ---------------------------------------------------------------------------


def make_loader(rows_by_doctype: dict) -> callable:
    """고정 rows 를 반환하는 mock data_loader."""

    def loader(doctype, query, search_fields, extra_filters, limit):
        rows = rows_by_doctype.get(doctype, [])
        # extra_filters 의 owner_field 필터를 흉내냄
        filtered = []
        for row in rows:
            match = True
            for k, v in extra_filters.items():
                if row.get(k) != v:
                    match = False
                    break
            if match:
                filtered.append(row)
        return filtered[:limit]

    return loader


# ---------------------------------------------------------------------------
# 테스트 케이스
# ---------------------------------------------------------------------------


class TestBuildSearchSnippet(unittest.TestCase):
    def test_match_in_middle(self):
        doc = {"employee_name": "김철수", "department": "개발팀"}
        snippet = M.build_search_snippet(doc=doc, query="철수")
        self.assertIn("**철수**", snippet)

    def test_no_match_returns_prefix(self):
        doc = {"employee_name": "이영희", "department": "인사팀"}
        snippet = M.build_search_snippet(doc=doc, query="홍길동")
        self.assertNotIn("**", snippet)
        # 내용은 있어야 함
        self.assertTrue(len(snippet) > 0)

    def test_empty_query_returns_empty(self):
        doc = {"employee_name": "테스트"}
        snippet = M.build_search_snippet(doc=doc, query="")
        self.assertEqual(snippet, "")

    def test_max_length_respected(self):
        doc = {"field": "a" * 200}
        snippet = M.build_search_snippet(doc=doc, query="a", max_length=50)
        # snippet 자체는 마커와 ellipsis 포함하므로 대략적으로 확인
        self.assertLess(len(snippet.replace("**", "").replace("...", "")), 200)


class TestApplySearchPermissions(unittest.TestCase):
    RESULTS = [
        {"name": "EMP-0001", "employee": "EMP-0001"},
        {"name": "EMP-0002", "employee": "EMP-0002"},
    ]

    def test_admin_gets_all(self):
        out = M.apply_search_permissions(
            results=self.RESULTS,
            user_role="HR Manager",
            user_employee="EMP-0001",
            owner_field="employee",
        )
        self.assertEqual(len(out), 2)

    def test_employee_gets_only_own(self):
        out = M.apply_search_permissions(
            results=self.RESULTS,
            user_role="Employee",
            user_employee="EMP-0001",
            owner_field="employee",
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["name"], "EMP-0001")

    def test_employee_no_identity_gets_nothing(self):
        out = M.apply_search_permissions(
            results=self.RESULTS,
            user_role="Employee",
            user_employee=None,
            owner_field="employee",
        )
        self.assertEqual(out, [])

    def test_no_owner_field_blocks_employee(self):
        out = M.apply_search_permissions(
            results=self.RESULTS,
            user_role="Employee",
            user_employee="EMP-0001",
            owner_field=None,
        )
        self.assertEqual(out, [])

    def test_system_manager_gets_all(self):
        out = M.apply_search_permissions(
            results=self.RESULTS,
            user_role="System Manager",
            user_employee=None,
            owner_field="employee",
        )
        self.assertEqual(len(out), 2)


class TestGlobalSearchCore(unittest.TestCase):
    """global_search 종단 간 테스트 (mock loader 사용)."""

    EMPLOYEE_ROWS = [
        {
            "name": "EMP-0001",
            "employee_name": "김철수",
            "email": "kim@example.com",
            "designation": "팀장",
            "department": "개발팀",
            "employee": "EMP-0001",
        },
        {
            "name": "EMP-0002",
            "employee_name": "이영희",
            "email": "lee@example.com",
            "designation": "사원",
            "department": "인사팀",
            "employee": "EMP-0002",
        },
    ]

    ATTENDANCE_ROWS = [
        {
            "name": "ATT-0001",
            "employee": "EMP-0001",
            "attendance_date": "2026-05-01",
            "status": "Present",
        }
    ]

    def _loader(self, rows_by_doctype):
        return make_loader(rows_by_doctype)

    def test_returns_v1_contract(self):
        result = M.global_search(
            query="김",
            user_role="HR Manager",
            data_loader=self._loader({"Employee": self.EMPLOYEE_ROWS}),
        )
        self.assertEqual(result["contract_type"], "korea_global_search_result_v1")

    def test_query_reflected(self):
        result = M.global_search(
            query="철수",
            user_role="HR Manager",
            data_loader=self._loader({"Employee": self.EMPLOYEE_ROWS}),
        )
        self.assertEqual(result["query"], "철수")

    def test_empty_query_returns_zero(self):
        result = M.global_search(
            query="",
            user_role="HR Manager",
            data_loader=self._loader({}),
        )
        self.assertEqual(result["total_results"], 0)
        self.assertEqual(result["results_by_doctype"], {})

    def test_admin_sees_all_doctypes_with_results(self):
        result = M.global_search(
            query="EMP-0001",
            user_role="HR Manager",
            data_loader=self._loader(
                {
                    "Employee": self.EMPLOYEE_ROWS[:1],
                    "Attendance": self.ATTENDANCE_ROWS,
                }
            ),
        )
        self.assertIn("Employee", result["results_by_doctype"])
        self.assertIn("Attendance", result["results_by_doctype"])

    def test_employee_sees_only_own_data(self):
        result = M.global_search(
            query="EMP",
            user_role="Employee",
            user_employee="EMP-0001",
            data_loader=self._loader(
                {
                    "Employee": self.EMPLOYEE_ROWS,
                    "Attendance": self.ATTENDANCE_ROWS,
                }
            ),
        )
        # Employee doctype: owner_field=name, 직원은 자신 EMP-0001만
        emp_results = result["results_by_doctype"].get("Employee", [])
        for r in emp_results:
            # result card 의 name 은 EMP-0001
            self.assertEqual(r["name"], "EMP-0001")

    def test_hr_only_doctype_blocked_for_employee(self):
        # Korea Payroll Closing Draft 는 hr_only=True
        result = M.global_search(
            query="마감",
            user_role="Employee",
            user_employee="EMP-0001",
            data_loader=self._loader(
                {
                    "Korea Payroll Closing Draft": [
                        {
                            "name": "KPCD-0001",
                            "company": "Winners",
                            "pay_year_month": "2026-04",
                            "status": "Draft",
                        }
                    ]
                }
            ),
        )
        self.assertNotIn("Korea Payroll Closing Draft", result["results_by_doctype"])

    def test_hr_only_doctype_visible_for_admin(self):
        result = M.global_search(
            query="Winners",
            user_role="HR Manager",
            data_loader=self._loader(
                {
                    "Korea Payroll Closing Draft": [
                        {
                            "name": "KPCD-0001",
                            "company": "Winners",
                            "pay_year_month": "2026-04",
                            "status": "Draft",
                        }
                    ]
                }
            ),
        )
        self.assertIn("Korea Payroll Closing Draft", result["results_by_doctype"])

    def test_result_card_has_required_keys(self):
        result = M.global_search(
            query="김",
            user_role="HR Manager",
            data_loader=self._loader({"Employee": self.EMPLOYEE_ROWS[:1]}),
        )
        card = result["results_by_doctype"]["Employee"][0]
        for key in ("name", "label", "url", "pwa_url", "snippet", "doctype"):
            self.assertIn(key, card, f"결과 카드에 '{key}' 키 누락")

    def test_pwa_url_is_none_when_no_pwa_route(self):
        """직원 상세는 PWA 라우트가 없으므로 pwa_url=None → 데스크 폴백."""
        result = M.global_search(
            query="김",
            user_role="HR Manager",
            data_loader=self._loader({"Employee": self.EMPLOYEE_ROWS[:1]}),
        )
        card = result["results_by_doctype"]["Employee"][0]
        self.assertIsNone(card["pwa_url"])
        self.assertEqual(card["url"], "/app/employee/EMP-0001")

    def test_pwa_url_contains_name_for_routed_doctype(self):
        """PWA 라우트가 있는 doctype 은 pwa_url 에 name 포함."""
        rows = [
            {
                "name": "SS-0001",
                "employee": "EMP-0001",
                "employee_name": "김철수",
                "start_date": "2026-05-01",
                "end_date": "2026-05-31",
            }
        ]
        result = M.global_search(
            query="김",
            user_role="HR Manager",
            doctypes=["Salary Slip"],
            data_loader=self._loader({"Salary Slip": rows}),
        )
        card = result["results_by_doctype"]["Salary Slip"][0]
        self.assertEqual(card["pwa_url"], "/hrms/salary-slips/SS-0001")

    def test_pwa_url_templates_match_registered_pwa_routes(self):
        """pwa_url_template 은 frontend/src/router 에 실제 존재하는 라우트만 사용.

        (경로 중복/미존재 라우트 → 빈 화면 버그 회귀 방지)
        """
        allowed_prefixes = (
            "/hrms/salary-slips/",
            "/hrms/leave-applications/",
            "/hrms/korea-payroll-closing-session/",
        )
        for doctype, meta in M.SEARCHABLE_DOCTYPES.items():
            template = meta.get("pwa_url_template")
            if template is None:
                continue
            self.assertTrue(
                template.startswith(allowed_prefixes),
                f"{doctype}: PWA 미등록 경로 {template!r}",
            )

    def test_elapsed_ms_is_non_negative_int(self):
        result = M.global_search(
            query="김",
            user_role="HR Manager",
            data_loader=self._loader({"Employee": self.EMPLOYEE_ROWS[:1]}),
        )
        self.assertIsInstance(result["elapsed_ms"], int)
        self.assertGreaterEqual(result["elapsed_ms"], 0)

    def test_doctype_filter_restricts_search(self):
        result = M.global_search(
            query="EMP",
            user_role="HR Manager",
            doctypes=["Employee"],
            data_loader=self._loader(
                {
                    "Employee": self.EMPLOYEE_ROWS,
                    "Attendance": self.ATTENDANCE_ROWS,
                }
            ),
        )
        self.assertIn("Employee", result["results_by_doctype"])
        self.assertNotIn("Attendance", result["results_by_doctype"])

    def test_loader_exception_skips_doctype(self):
        """data_loader 가 예외를 던지면 해당 doctype 은 스킵."""

        def bad_loader(doctype, **kwargs):
            if doctype == "Attendance":
                raise RuntimeError("테이블 없음")
            return self.EMPLOYEE_ROWS[:1]

        result = M.global_search(
            query="EMP",
            user_role="HR Manager",
            data_loader=bad_loader,
        )
        # Employee 는 정상, Attendance 는 스킵
        self.assertIn("Employee", result["results_by_doctype"])
        self.assertNotIn("Attendance", result["results_by_doctype"])

    def test_company_filter_passed_to_loader(self):
        """company 필터가 loader 에게 extra_filters 로 전달됨."""
        calls = []

        def recording_loader(doctype, query, search_fields, extra_filters, limit):
            calls.append({"doctype": doctype, "extra_filters": extra_filters})
            return []

        M.global_search(
            query="테스트",
            user_role="HR Manager",
            company="Winners",
            doctypes=["Employee"],
            data_loader=recording_loader,
        )
        self.assertTrue(any(c["extra_filters"].get("company") == "Winners" for c in calls))

    def test_limit_per_doctype_honored(self):
        many_rows = [
            {
                "name": f"EMP-{i:04d}",
                "employee_name": f"직원{i}",
                "email": f"emp{i}@example.com",
                "designation": "사원",
                "department": "개발팀",
                "employee": f"EMP-{i:04d}",
            }
            for i in range(50)
        ]
        result = M.global_search(
            query="직원",
            user_role="HR Manager",
            doctypes=["Employee"],
            limit_per_doctype=5,
            data_loader=make_loader({"Employee": many_rows}),
        )
        emp_results = result["results_by_doctype"].get("Employee", [])
        self.assertLessEqual(len(emp_results), 5)


class TestSnippetEdgeCases(unittest.TestCase):
    def test_query_at_start(self):
        doc = {"field": "철수와 영희"}
        snippet = M.build_search_snippet(doc=doc, query="철수")
        self.assertIn("**철수**", snippet)

    def test_query_at_end(self):
        doc = {"field": "안녕 철수"}
        snippet = M.build_search_snippet(doc=doc, query="철수")
        self.assertIn("**철수**", snippet)

    def test_non_string_values_ignored(self):
        doc = {"count": 42, "flag": True, "employee_name": "김테스트"}
        # 예외 없이 동작해야 함
        snippet = M.build_search_snippet(doc=doc, query="김")
        self.assertIn("**김**", snippet)


if __name__ == "__main__":
    unittest.main()
