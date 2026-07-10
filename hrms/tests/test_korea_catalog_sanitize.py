# -*- coding: utf-8 -*-
"""행정해석 카탈로그 오염 정화(catalog_sanitize.py) 테스트.

배경: 스크래핑 아티팩트로 일부 노동관계 행정해석(휴업수당·수당·퇴직금 등)의
text 꼬리에 무관한 산업위생(노출기준·mg/㎥·총분진) 문장이 접합(graft)되어 있다.
v1 답변은 primary 문서 text 전문을 그대로 내보내므로, 휴업수당 질의에
'석탄분진을 총분진으로 채취하였을 때에는 …' 같은 이물 문장이 섞여 나갔다.

이 테스트는 순수 함수 strip_foreign_hygiene_tail()이:
- 노동 문서의 꼬리 산업위생 접합만 잘라내고,
- 본문 전체가 산업위생인 정상 문서는 건드리지 않으며,
- 산업위생 토큰이 없는 문서는 그대로 통과시키는지 검증한다.

framework-free: catalog_sanitize.py는 frappe import 없음.
실행: python3 hrms/tests/test_korea_catalog_sanitize.py
"""
import importlib.util
import io
import json
import pathlib
import re
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "hrms" / "regional" / "south_korea" / "catalog_sanitize.py"

_spec = importlib.util.spec_from_file_location("catalog_sanitize", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

strip_foreign_hygiene_tail = _mod.strip_foreign_hygiene_tail
is_labor_domain_title = _mod.is_labor_domain_title

_HYG = re.compile(r"(mg/㎥|㎎/㎥|㎍/㎥|호흡성분진|총분진|노출기준|ppm)")

_TITLE_460 = "휴업기간동안 통상임금 100%+700,000원을 휴업한 근로자에게 휴업수당으로 지급"
_TITLE_HYGIENE = "소음발생작업장의 특수건강진단 및 작업환경측정 노출기준 적용"

# 실제 오염 사례(idx460) — 휴업수당 행정해석 + 석탄분진 이물 꼬리
_CONTAM_460 = (
    "A사업장에서 신고된 계획을 준수하여 휴업을 실시하고 휴업기간동안 "
    "『통상임금 100%+700,000원』을 휴업한 근로자에게 휴업수당으로 지급한 바, "
    "주휴수당이 이중계산 지급되었다고 볼 수 있는지 여부. 동 기준이 1일을 기준으로 "
    "정한 것이라면, 주휴수당을 이중 지급한다는 의미는 아니라고 판단됨. 그러나, 철저한 "
    "조사를 통해 판단하시고 그에 따라 지원금을 지급. 석탄분진을 총분진으로 채취하였을 "
    "때에는 화학물질 및 물리적인자의 노출기준에 따라 5mg/㎥으로 적용하고, "
    "호흡성분진으로 채취할 경우에는 2mg/㎥으로 적용한다."
)

# 본문 전체가 산업위생인 정상 문서 — 건드리면 안 됨(첫 토큰이 앞부분에 등장)
_GENUINE_HYGIENE = (
    "유리규산 함유량에 따라 분진의 종류가 결정되는데 그 측정 방법의 노출기준 적용이 "
    "타당한지 여부. 호흡성분진으로 채취할 경우에는 2mg/㎥으로 적용하며, 유리규산 "
    "함유량이 높을수록 노출기준은 강화된다. 따라서 총분진 기준을 일률 적용할 수 없다."
)


class TestStripForeignHygieneTail(unittest.TestCase):
    def test_removes_coal_dust_graft_from_wage_interpretation(self):
        out = strip_foreign_hygiene_tail(_CONTAM_460, _TITLE_460)
        # 이물 산업위생 꼬리는 사라져야 한다
        self.assertNotIn("석탄분진", out)
        self.assertFalse(_HYG.search(out), "산업위생 토큰이 남아 있으면 안 됨")
        # 노동(휴업수당) 본문은 보존되어야 한다
        self.assertIn("휴업수당", out)
        self.assertIn("지원금을 지급", out)
        # 접합 경계(마침표)에서 깔끔히 잘려야 한다
        self.assertTrue(out.rstrip().endswith("지급."), out[-30:])

    def test_leaves_genuine_hygiene_document_untouched(self):
        # 본문 전체가 산업위생(첫 토큰이 앞부분) → 손대지 않음
        out = strip_foreign_hygiene_tail(_GENUINE_HYGIENE, _TITLE_HYGIENE)
        self.assertEqual(out, _GENUINE_HYGIENE)

    def test_hygiene_title_protects_multitopic_doc(self):
        # 제목에 산업위생 키워드가 있으면(다주제 문서) 꼬리 토큰이 뒤에 있어도 손대지 않음
        text = _CONTAM_460  # 동일 본문이라도
        out = strip_foreign_hygiene_tail(text, _TITLE_HYGIENE)
        self.assertEqual(out, text)

    def test_passthrough_when_no_hygiene_token(self):
        labor = (
            "연차유급휴가 미사용수당은 통상임금을 기준으로 산정하며, 퇴직 시 "
            "미사용 일수에 대하여 전액 지급하여야 한다."
        )
        self.assertEqual(strip_foreign_hygiene_tail(labor, "연차유급휴가 미사용수당 산정"), labor)

    def test_labor_domain_title_gate(self):
        self.assertTrue(is_labor_domain_title("휴업수당 주휴수당 이중지급 여부"))
        self.assertFalse(is_labor_domain_title("작업환경측정 노출기준 초과 여부"))
        self.assertFalse(is_labor_domain_title(""))

    def test_empty_and_none_safe(self):
        self.assertEqual(strip_foreign_hygiene_tail("", "휴업수당"), "")
        self.assertEqual(strip_foreign_hygiene_tail(None, "휴업수당"), None)


class TestShippedCatalogClean(unittest.TestCase):
    """배포되는 카탈로그 파일에 노동 문서 꼬리 산업위생 접합이 없어야 한다."""

    def test_catalog_has_no_coal_dust_in_wage_entries(self):
        cat_path = (
            _REPO_ROOT / "hrms" / "regional" / "south_korea" / "data"
            / "korea_admin_interpretation_catalog.json"
        )
        data = json.load(io.open(cat_path, encoding="utf-8"))
        offenders = []
        for i, e in enumerate(data):
            title = e.get("title") or ""
            text = e.get("text") or ""
            if not is_labor_domain_title(title):
                continue  # 산업위생/다주제 문서는 정화 대상 아님
            m = _HYG.search(text)
            if m and m.start() / max(len(text), 1) >= 0.6:
                offenders.append((i, title[:30]))
        self.assertEqual(offenders, [], f"노동 문서에 산업위생 꼬리 접합 잔존: {offenders}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
