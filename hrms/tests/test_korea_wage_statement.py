#!/usr/bin/env python3
"""근로기준법 시행령 §27조의2 임금명세서 PDF payload + 카카오 발송 path 테스트.

검증 범위:
  - 7개 법정 기재 사항 완전성
  - PDF payload 구성 (read-only, side-effect-free)
  - 비과세 항목 자동 인식 (명시적 플래그 + 라벨 패턴)
  - 카카오 발송 fail-closed (human_approved 검증)
  - 카카오 queue item 구성 (payload 계약)
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

_SOUTH_KOREA = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea"

WS_MODULE_PATH = _SOUTH_KOREA / "wage_statement.py"
KAKAO_MODULE_PATH = _SOUTH_KOREA / "wage_statement_kakao.py"


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _base_slip(**overrides) -> dict:
    base = {
        "name": "SAL-2026-05-0001",
        "employee": "HR-EMP-0001",
        "employee_name": "김민준",
        "employee_id": "EMP-2023-0042",
        "employee_birth_date": "1990-03-15",
        "company": "노무법인 위너스",
        "department": "개발팀",
        "designation": "시니어 엔지니어",
        "period_start": "2026-05-01",
        "period_end": "2026-05-31",
        "payment_date": "2026-05-25",
        "earnings": [
            {"label": "기본급", "amount": 3_000_000, "basis": "월 고정급 (근로계약서 기준)"},
            {"label": "직책수당", "amount": 200_000, "basis": "직위 수당 내규 §3"},
            {"label": "식대", "amount": 200_000, "basis": "소득세법 시행령 §17의2 비과세 한도 내"},
            {"label": "차량유지비", "amount": 150_000, "basis": "소득세법 시행령 §12 비과세 (자가운전 보조금)"},
        ],
        "deductions": [
            {"label": "국민연금", "amount": 135_000, "basis": "기준소득월액 3,000,000 × 4.5%"},
            {"label": "건강보험", "amount": 106_350, "basis": "기준소득월액 3,000,000 × 3.545%"},
            {"label": "장기요양보험", "amount": 13_772, "basis": "건강보험료 106,350 × 12.95%"},
            {"label": "고용보험", "amount": 27_000, "basis": "기준소득월액 3,000,000 × 0.9%"},
            {"label": "소득세", "amount": 52_140, "basis": "간이세액표 (과세표준 적용)"},
            {"label": "지방소득세", "amount": 5_210, "basis": "소득세 52,140 × 10%"},
        ],
    }
    base.update(overrides)
    return base


class TestKoreaWageStatementPdfPayload(unittest.TestCase):
    def setUp(self):
        self.mod = _load(WS_MODULE_PATH, "korea_wage_statement")

    # ── 기본 구성 ────────────────────────────────────────────────

    def test_returns_correct_contract_type_and_mutation_boundary(self):
        payload = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=_base_slip(), actor="hr.manager@winhr.co.kr"
        )
        self.assertEqual(payload["contract_type"], "korea_wage_statement_pdf_v1")
        self.assertEqual(payload["runtime_action"], "pdf_payload_only")
        self.assertFalse(payload["requires_runtime_apply"])
        self.assertTrue(payload["requires_human_approval"])
        self.assertEqual(payload["ai_role"], "assistant_only")
        self.assertIn("no_submit", payload["mutation_boundary"])
        self.assertIn("no_send", payload["mutation_boundary"])

    # ── 법정 7개 항목 완전성 검증 ────────────────────────────────

    def test_all_seven_statutory_fields_are_present(self):
        """근로기준법 시행령 §27조의2 — 7개 법정 기재 사항 전부 포함."""
        payload = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=_base_slip(), actor="hr.manager@winhr.co.kr"
        )
        # §1 근로자 특정 정보
        for required in ("employee_name", "employee_birth_date", "employee_id"):
            with self.subTest(statutory_field=required):
                self.assertIn(required, payload)
                self.assertTrue(payload[required], f"{required} must not be empty")
        # §2 임금 지급일
        self.assertIn("payment_date", payload)
        self.assertTrue(payload["payment_date"])
        # §3 임금 총액
        self.assertIn("gross_pay", payload)
        self.assertIsInstance(payload["gross_pay"], int)
        # §4·§5 항목별 금액·계산 방법 (basis)
        self.assertIn("earnings", payload)
        self.assertTrue(payload["earnings"])
        for row in payload["earnings"]:
            with self.subTest(label=row["label"]):
                self.assertIn("label", row)
                self.assertIn("amount", row)
                self.assertIn("basis", row)
        # §6 공제 항목별 금액·산출
        self.assertIn("deductions", payload)
        for row in payload["deductions"]:
            self.assertIn("label", row)
            self.assertIn("amount", row)
            self.assertIn("basis", row)
        # §7 비과세 항목
        self.assertIn("tax_exempt_items", payload)

    # ── 금액 계산 검증 ───────────────────────────────────────────

    def test_gross_pay_total_deductions_net_pay_are_correct(self):
        payload = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=_base_slip(), actor="test@winhr.co.kr"
        )
        expected_gross = 3_000_000 + 200_000 + 200_000 + 150_000
        expected_deductions = 135_000 + 106_350 + 13_772 + 27_000 + 52_140 + 5_210
        self.assertEqual(payload["gross_pay"], expected_gross)
        self.assertEqual(payload["total_deductions"], expected_deductions)
        self.assertEqual(payload["net_pay"], expected_gross - expected_deductions)

    # ── §7 비과세 항목 자동 인식 ─────────────────────────────────

    def test_tax_exempt_items_auto_detected_by_label(self):
        """식대·차량유지비 → 라벨 패턴으로 비과세 자동 인식."""
        payload = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=_base_slip(), actor="test@winhr.co.kr"
        )
        exempt_labels = {item["label"] for item in payload["tax_exempt_items"]}
        self.assertIn("식대", exempt_labels)
        self.assertIn("차량유지비", exempt_labels)
        self.assertNotIn("기본급", exempt_labels)
        self.assertNotIn("직책수당", exempt_labels)

    def test_explicit_is_tax_exempt_flag_overrides_label_heuristic(self):
        """is_tax_exempt=True/False 명시 플래그가 라벨 자동 인식보다 우선."""
        slip = _base_slip(
            earnings=[
                {"label": "기본급", "amount": 3_000_000, "basis": "월 고정급", "is_tax_exempt": False},
                # 식대이지만 명시적으로 과세 처리
                {"label": "식대", "amount": 200_000, "basis": "과세처리", "is_tax_exempt": False},
                # 임의 항목이지만 명시적으로 비과세
                {"label": "연구활동비", "amount": 100_000, "basis": "연구비 규정", "is_tax_exempt": True},
            ],
            deductions=[],
        )
        payload = self.mod.build_korea_wage_statement_pdf_payload(salary_slip=slip, actor="test@winhr.co.kr")
        exempt_labels = {item["label"] for item in payload["tax_exempt_items"]}
        self.assertNotIn("식대", exempt_labels, "explicit False should suppress auto-detection")
        self.assertIn("연구활동비", exempt_labels, "explicit True should be respected")

    def test_육아수당_label_is_auto_detected_as_tax_exempt(self):
        slip = _base_slip(
            earnings=[
                {"label": "기본급", "amount": 3_000_000, "basis": "월 고정급"},
                {"label": "육아수당", "amount": 100_000, "basis": "소득세법 시행령 §12"},
            ],
            deductions=[],
        )
        payload = self.mod.build_korea_wage_statement_pdf_payload(salary_slip=slip, actor="test@winhr.co.kr")
        exempt_labels = {item["label"] for item in payload["tax_exempt_items"]}
        self.assertIn("육아수당", exempt_labels)

    def test_tax_exempt_cap_exceeded_flag_set_for_식대_over_200k(self):
        """식대 200,000원 초과 시 tax_exempt_cap_exceeded 플래그 설정."""
        slip = _base_slip(
            earnings=[
                {"label": "기본급", "amount": 3_000_000, "basis": "월 고정급"},
                {"label": "식대", "amount": 250_000, "basis": "200,000 한도 초과"},
            ],
            deductions=[],
        )
        payload = self.mod.build_korea_wage_statement_pdf_payload(salary_slip=slip, actor="test@winhr.co.kr")
        식대_rows = [r for r in payload["earnings"] if r["label"] == "식대"]
        self.assertEqual(len(식대_rows), 1)
        self.assertTrue(식대_rows[0].get("tax_exempt_cap_exceeded"))
        self.assertEqual(식대_rows[0].get("tax_exempt_cap"), 200_000)

    # ── 입력 검증 ────────────────────────────────────────────────

    def test_rejects_missing_required_fields(self):
        required_fields = [
            "name", "employee", "employee_name", "employee_birth_date",
            "company", "period_start", "period_end", "payment_date",
        ]
        for field in required_fields:
            slip = _base_slip()
            slip.pop(field)
            with self.subTest(missing_field=field):
                with self.assertRaises((ValueError, TypeError)):
                    self.mod.build_korea_wage_statement_pdf_payload(
                        salary_slip=slip, actor="test@winhr.co.kr"
                    )

    def test_rejects_invalid_iso_dates(self):
        for bad_date, field in [
            ("not-a-date", "employee_birth_date"),
            ("2026-02-30", "period_start"),
            ("2026/05/01", "payment_date"),
        ]:
            slip = _base_slip(**{field: bad_date})
            with self.subTest(field=field, bad_date=bad_date):
                with self.assertRaises(ValueError):
                    self.mod.build_korea_wage_statement_pdf_payload(
                        salary_slip=slip, actor="test@winhr.co.kr"
                    )

    def test_rejects_period_start_after_period_end(self):
        slip = _base_slip(period_start="2026-06-01", period_end="2026-05-31")
        with self.assertRaises(ValueError):
            self.mod.build_korea_wage_statement_pdf_payload(salary_slip=slip, actor="test@winhr.co.kr")

    def test_rejects_fractional_and_scientific_amounts(self):
        for bad_amount in (True, "1e6", "1000.50", "Infinity", -1):
            slip = _base_slip(
                earnings=[{"label": "기본급", "amount": bad_amount, "basis": "월 고정급"}],
                deductions=[],
            )
            with self.subTest(bad_amount=bad_amount):
                with self.assertRaises((ValueError, TypeError)):
                    self.mod.build_korea_wage_statement_pdf_payload(
                        salary_slip=slip, actor="test@winhr.co.kr"
                    )

    def test_rejects_empty_actor(self):
        with self.assertRaises(ValueError):
            self.mod.build_korea_wage_statement_pdf_payload(salary_slip=_base_slip(), actor="")

    def test_rejects_non_dict_salary_slip(self):
        with self.assertRaises(ValueError):
            self.mod.build_korea_wage_statement_pdf_payload(salary_slip="not-a-dict", actor="test@winhr.co.kr")

    def test_rejects_empty_earnings(self):
        slip = _base_slip(earnings=[])
        with self.assertRaises(ValueError):
            self.mod.build_korea_wage_statement_pdf_payload(salary_slip=slip, actor="test@winhr.co.kr")

    def test_rejects_invalid_is_tax_exempt_non_bool(self):
        slip = _base_slip(
            earnings=[
                {"label": "기본급", "amount": 3_000_000, "basis": "월 고정급", "is_tax_exempt": 1},
            ],
            deductions=[],
        )
        with self.assertRaises(ValueError):
            self.mod.build_korea_wage_statement_pdf_payload(salary_slip=slip, actor="test@winhr.co.kr")

    # ── 구조 검증 ────────────────────────────────────────────────

    def test_print_labels_contains_all_seven_statutory_sections(self):
        payload = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=_base_slip(), actor="test@winhr.co.kr"
        )
        labels = payload["print_labels"]
        for key in ("employee_name", "employee_birth_date", "employee_id",
                    "payment_date", "gross_pay", "earnings", "deductions",
                    "tax_exempt_items", "net_pay"):
            with self.subTest(label_key=key):
                self.assertIn(key, labels)

    def test_calculation_basis_combines_earnings_and_deductions(self):
        payload = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=_base_slip(), actor="test@winhr.co.kr"
        )
        sections = {row["section"] for row in payload["calculation_basis"]}
        self.assertIn("지급", sections)
        self.assertIn("공제", sections)

    def test_checksum_changes_when_amount_changes(self):
        p1 = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=_base_slip(), actor="test@winhr.co.kr"
        )
        slip2 = _base_slip()
        slip2["earnings"][0]["amount"] = 3_100_000
        p2 = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=slip2, actor="test@winhr.co.kr"
        )
        self.assertNotEqual(p1["checksum"], p2["checksum"])

    def test_employee_id_falls_back_to_employee_field_when_not_provided(self):
        slip = _base_slip()
        slip.pop("employee_id")
        payload = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=slip, actor="test@winhr.co.kr"
        )
        self.assertEqual(payload["employee_id"], slip["employee"])

    def test_optional_department_and_designation_are_preserved(self):
        payload = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=_base_slip(), actor="test@winhr.co.kr"
        )
        self.assertEqual(payload["department"], "개발팀")
        self.assertEqual(payload["designation"], "시니어 엔지니어")

    def test_zero_deductions_are_allowed(self):
        slip = _base_slip(deductions=[])
        payload = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=slip, actor="test@winhr.co.kr"
        )
        self.assertEqual(payload["total_deductions"], 0)
        self.assertEqual(payload["deductions"], [])

    # ── PDF dry-run (render없이 payload 완전성 확인) ────────────

    def test_pdf_payload_dry_run_all_fields_serializable(self):
        """PDF payload이 JSON 직렬화 가능한지 확인 (dry-run)."""
        import json
        payload = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=_base_slip(), actor="pdf-dry-run@winhr.co.kr"
        )
        # JSON 직렬화 가능 = Frappe Print Format 렌더링 준비 완료
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertIn("korea_wage_statement_pdf_v1", serialized)
        self.assertIn("임금명세서", serialized)
        self.assertIn("payment_date", serialized)

    # ── HTML 렌더링 스모크 테스트 (§1~§7 실제 렌더 확인) ──────────

    def test_render_html_contains_all_seven_statutory_sections(self):
        """render_korea_wage_statement_html — §1~§7 법정 항목이 실제 HTML에 렌더링되는지 확인."""
        try:
            import jinja2  # noqa: F401
        except ImportError:
            self.skipTest("jinja2 not installed — skipping HTML render smoke test")

        payload = self.mod.build_korea_wage_statement_pdf_payload(
            salary_slip=_base_slip(), actor="html-render-test@winhr.co.kr"
        )
        html = self.mod.render_korea_wage_statement_html(payload=payload)

        # §1 — 성명·생년월일·사원번호가 실제 HTML에 포함
        self.assertIn("김민준", html, "§1 employee_name missing from rendered HTML")
        self.assertIn("1990-03-15", html, "§1 employee_birth_date missing from rendered HTML")
        self.assertIn("EMP-2023-0042", html, "§1 employee_id missing from rendered HTML")

        # §2 — 임금 지급일
        self.assertIn("2026-05-25", html, "§2 payment_date missing from rendered HTML")

        # §3 — 임금 총액 (gross_pay 3,550,000원 = 3,000,000+200,000+200,000+150,000)
        self.assertIn("3,550,000", html, "§3 gross_pay missing from rendered HTML")

        # §4·§5 — 항목별 금액과 계산 방법 (basis)
        self.assertIn("기본급", html, "§4 earnings item missing")
        self.assertIn("월 고정급 (근로계약서 기준)", html, "§5 basis (계산방법) missing from rendered HTML")

        # §6 — 공제 항목별 금액·산출
        self.assertIn("국민연금", html, "§6 deduction item missing")
        self.assertIn("기준소득월액 3,000,000 × 4.5%", html, "§6 deduction basis missing")

        # §7 — 비과세 항목 (식대·차량유지비가 별도 섹션에 표시)
        self.assertIn("비과세", html, "§7 tax-exempt badge missing from rendered HTML")
        self.assertIn("식대", html, "§7 식대 exempt item missing from rendered HTML")

        # 실지급액 (net_pay)
        expected_net = 3_550_000 - (135_000 + 106_350 + 13_772 + 27_000 + 52_140 + 5_210)
        self.assertIn(f"{expected_net:,}", html, "net_pay missing from rendered HTML")

        # HTML 구조 기본 확인
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("근로기준법 시행령 제27조의2", html)

    def test_render_html_rejects_wrong_contract_type(self):
        """render_korea_wage_statement_html — 잘못된 contract_type 거부."""
        with self.assertRaises(ValueError):
            self.mod.render_korea_wage_statement_html(payload={"contract_type": "wrong_type"})

    def test_render_html_rejects_non_dict_payload(self):
        """render_korea_wage_statement_html — dict가 아닌 payload 거부."""
        with self.assertRaises(TypeError):
            self.mod.render_korea_wage_statement_html(payload="not-a-dict")


class TestWageStatementKakao(unittest.TestCase):
    def setUp(self):
        self.ws_mod = _load(WS_MODULE_PATH, "korea_wage_statement")
        self.kakao_mod = _load(KAKAO_MODULE_PATH, "korea_wage_statement_kakao")

    def _valid_payload(self) -> dict:
        return self.ws_mod.build_korea_wage_statement_pdf_payload(
            salary_slip=_base_slip(), actor="hr.manager@winhr.co.kr"
        )

    # ── send_korea_wage_statement_kakao fail-closed ──────────────

    def test_send_rejects_human_approved_not_true(self):
        """human_approved가 정확히 bool True가 아니면 fail-closed."""
        for bad_approved in (False, 1, "yes", "true", None, 0, [], {}):
            with self.subTest(bad_approved=bad_approved):
                with self.assertRaises((ValueError, TypeError)):
                    self.kakao_mod.send_korea_wage_statement_kakao(
                        salary_slip=_base_slip(),
                        human_approved=bad_approved,
                    )

    def test_send_returns_stub_when_human_approved_is_true(self):
        result = self.kakao_mod.send_korea_wage_statement_kakao(
            salary_slip=_base_slip(),
            human_approved=True,
        )
        self.assertEqual(result["status"], "pending_phase_2d")
        self.assertEqual(result["runtime_action"], "stub_no_send")
        self.assertIn("no_send", result["mutation_boundary"])
        self.assertTrue(result["requires_phase_2d"])
        self.assertTrue(result["human_approved"])

    def test_send_rejects_non_dict_salary_slip(self):
        with self.assertRaises(TypeError):
            self.kakao_mod.send_korea_wage_statement_kakao(
                salary_slip="not-a-dict",
                human_approved=True,
            )

    # ── build_wage_statement_kakao_queue_item ────────────────────

    def test_queue_item_rejects_human_approved_not_true(self):
        payload = self._valid_payload()
        for bad in (False, 1, "yes", None):
            with self.subTest(bad=bad):
                with self.assertRaises((ValueError, TypeError)):
                    self.kakao_mod.build_wage_statement_kakao_queue_item(
                        wage_statement_payload=payload,
                        recipient_phone="010-1234-5678",
                        recipient_consent=True,
                        human_approved=bad,
                    )

    def test_queue_item_built_correctly_when_approved(self):
        payload = self._valid_payload()
        queue_item = self.kakao_mod.build_wage_statement_kakao_queue_item(
            wage_statement_payload=payload,
            recipient_phone="010-9876-5432",
            recipient_consent=True,
            human_approved=True,
            provider_key="demo_partner",
            max_attempts=3,
        )
        self.assertEqual(queue_item["queue_type"], "korea_kakao_send_queue_v1")
        self.assertEqual(queue_item["status"], "queued")
        self.assertEqual(queue_item["provider_key"], "demo_partner")
        self.assertEqual(queue_item["attempt_count"], 0)
        self.assertEqual(queue_item["max_attempts"], 3)
        self.assertTrue(queue_item["dedupe_key"].startswith("kakao:"))
        self.assertEqual(queue_item["phase"], "2-A-skeleton")
        self.assertTrue(queue_item["dispatch_pending"])

    def test_queue_item_payload_contains_wage_statement_variables(self):
        payload = self._valid_payload()
        queue_item = self.kakao_mod.build_wage_statement_kakao_queue_item(
            wage_statement_payload=payload,
            recipient_phone="01012345678",
            recipient_consent=True,
            human_approved=True,
        )
        variables = queue_item["payload"]["variables"]
        self.assertIn("employee_name", variables)
        self.assertIn("payment_date", variables)
        self.assertIn("period", variables)
        self.assertIn("net_pay", variables)
        self.assertEqual(variables["employee_name"], "김민준")
        self.assertEqual(variables["payment_date"], "2026-05-25")

    def test_queue_item_rejects_wrong_contract_type(self):
        bad_payload = {"contract_type": "something_else", "employee_name": "X"}
        with self.assertRaises(ValueError):
            self.kakao_mod.build_wage_statement_kakao_queue_item(
                wage_statement_payload=bad_payload,
                recipient_phone="01012345678",
                recipient_consent=True,
                human_approved=True,
            )

    def test_queue_item_rejects_opted_out_recipient(self):
        payload = self._valid_payload()
        with self.assertRaises(ValueError):
            self.kakao_mod.build_wage_statement_kakao_queue_item(
                wage_statement_payload=payload,
                recipient_phone="01012345678",
                recipient_consent=True,
                human_approved=True,
                opted_out=True,
            )

    def test_queue_item_rejects_no_recipient_consent(self):
        payload = self._valid_payload()
        with self.assertRaises(ValueError):
            self.kakao_mod.build_wage_statement_kakao_queue_item(
                wage_statement_payload=payload,
                recipient_phone="01012345678",
                recipient_consent=False,
                human_approved=True,
            )

    def test_queue_item_rejects_invalid_phone(self):
        payload = self._valid_payload()
        with self.assertRaises(ValueError):
            self.kakao_mod.build_wage_statement_kakao_queue_item(
                wage_statement_payload=payload,
                recipient_phone="02-1234-5678",  # 유선번호
                recipient_consent=True,
                human_approved=True,
            )

    def test_source_salary_slip_is_tracked_in_queue_item(self):
        payload = self._valid_payload()
        queue_item = self.kakao_mod.build_wage_statement_kakao_queue_item(
            wage_statement_payload=payload,
            recipient_phone="01012345678",
            recipient_consent=True,
            human_approved=True,
        )
        self.assertEqual(queue_item["wage_statement_source"], "SAL-2026-05-0001")


if __name__ == "__main__":
    unittest.main()
