"""디자인 규율 감사기(scripts/design_audit.py) 테스트 — framework-free.

실행: python3 hrms/tests/test_design_audit.py

픽스처 뷰 문자열로 규칙 R1~R6 검출을 검증한다. 실제 레포 스캔은
스모크 1건(실행 가능 + 리포트 구조)만 확인 — 위반 수는 시점에 따라 변한다.
"""

import importlib.util
import pathlib
import sys
import unittest

_HERE = pathlib.Path(__file__).resolve()
_REPO = _HERE.parents[2]
_SCRIPT = _REPO / "scripts" / "design_audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("design_audit", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


audit = _load()


class TestRules(unittest.TestCase):
    def _violations(self, src, name="KoreaTest.vue", narrative=False):
        return audit.audit_source(src, name, narrative=narrative)

    def test_r1_pill_on_data_screen(self):
        src = '<button class="rounded-full bg-white">확인</button>'
        codes = [v["rule"] for v in self._violations(src)]
        self.assertIn("R1", codes)

    def test_r1_pill_allowed_on_narrative(self):
        src = '<button class="rounded-full">시작하기</button>'
        codes = [v["rule"] for v in self._violations(src, narrative=True)]
        self.assertNotIn("R1", codes)

    def test_r2_black_button(self):
        src = '<button class="bg-black text-white rounded-lg">저장</button>'
        codes = [v["rule"] for v in self._violations(src)]
        self.assertIn("R2", codes)

    def test_r2_ignores_non_button_black(self):
        """text-black 등 잉크 텍스트는 위반 아님."""
        src = '<span class="text-black">라벨</span>'
        codes = [v["rule"] for v in self._violations(src)]
        self.assertNotIn("R2", codes)

    def test_r3_amount_without_ink_class_warns(self):
        src = '<span class="text-sm">{{ formatKRW(total) }}</span>'
        found = [v for v in self._violations(src) if v["rule"] == "R3"]
        self.assertTrue(found)
        self.assertEqual(found[0]["level"], "error")

    def test_r3_amount_with_k_amount_ok(self):
        src = '<span class="k-amount">{{ formatKRW(total) }}</span>'
        codes = [v["rule"] for v in self._violations(src)]
        self.assertNotIn("R3", codes)

    def test_r3_amount_with_k_display_ok(self):
        src = '<div class="k-display">{{ formatKRW(total) }}</div>'
        codes = [v["rule"] for v in self._violations(src)]
        self.assertNotIn("R3", codes)

    def test_r4_hardcoded_gray(self):
        src = '<p class="text-gray-500">보조</p>'
        codes = [v["rule"] for v in self._violations(src)]
        self.assertIn("R4", codes)

    def test_r4_hardcoded_hex_in_class(self):
        src = '<div class="bg-[#123456]">x</div>'
        codes = [v["rule"] for v in self._violations(src)]
        self.assertIn("R4", codes)

    def test_r4_token_var_ok(self):
        src = '<div class="border-[var(--k-hairline)]">x</div>'
        codes = [v["rule"] for v in self._violations(src)]
        self.assertNotIn("R4", codes)

    def test_r5_pastel_on_data_screen(self):
        src = '<div class="k-block k-block--lime">금액표</div>'
        codes = [v["rule"] for v in self._violations(src)]
        self.assertIn("R5", codes)

    def test_r5_cream_exempt_on_data(self):
        """cream 블록은 결과 히어로 관례(기존 화면 표준) — 데이터 화면에서도 허용."""
        src = '<div class="k-block k-block--cream">통상시급</div>'
        codes = [v["rule"] for v in self._violations(src)]
        self.assertNotIn("R5", codes)

    def test_r5_pastel_allowed_on_narrative(self):
        src = '<div class="k-block k-block--lime">홈 히어로</div>'
        codes = [v["rule"] for v in self._violations(src, narrative=True)]
        self.assertNotIn("R5", codes)

    def test_r6_navy_on_button(self):
        src = '<button class="bg-[var(--k-ledger-navy)]">확정</button>'
        codes = [v["rule"] for v in self._violations(src)]
        self.assertIn("R6", codes)

    def test_r6_navy_on_amount_ok(self):
        src = '<span class="k-amount">{{ formatKRW(x) }}</span>'
        codes = [v["rule"] for v in self._violations(src)]
        self.assertNotIn("R6", codes)

    def test_r1_r2_multiline_button(self):
        """Vue 관례: 속성이 여러 줄로 갈라진 버튼도 검출해야 한다."""
        src = (
            "<button\n"
            "\t@click=\"run\"\n"
            "\tclass=\"w-full py-3 bg-black text-white rounded-full\"\n"
            ">\n확인\n</button>"
        )
        codes = [v["rule"] for v in self._violations(src)]
        self.assertIn("R1", codes)
        self.assertIn("R2", codes)

    def test_r3_multiline_element_with_class_on_previous_line(self):
        """k-display 클래스가 윗줄, 바인딩이 다음 줄인 멀티라인 요소는 오탐하지 않는다."""
        src = (
            '<div class="k-display k-settled">\n'
            "\t{{ formatKRW(statement.net_pay) }}\n"
            "</div>"
        )
        codes = [v["rule"] for v in self._violations(src)]
        self.assertNotIn("R3", codes)

    def test_violation_has_line_numbers(self):
        src = "<div>\n<button class=\"bg-black\">x</button>\n</div>"
        found = [v for v in self._violations(src) if v["rule"] == "R2"]
        self.assertEqual(found[0]["line"], 2)


class TestRepoScan(unittest.TestCase):
    def test_scan_runs_and_reports(self):
        report = audit.audit_repo(_REPO)
        self.assertIn("files_scanned", report)
        self.assertGreater(report["files_scanned"], 20)
        self.assertIn("violations", report)
        self.assertIn("error_count", report)
        self.assertIn("warn_count", report)


if __name__ == "__main__":
    unittest.main(verbosity=1)
