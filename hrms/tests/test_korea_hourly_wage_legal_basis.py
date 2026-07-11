# -*- coding: utf-8 -*-
"""주휴수당 법적 근거 인용 — published 온톨로지 노드 우선, 폴백 상수. TDD: RED 먼저."""
import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hrms" / "regional" / "south_korea" / "hourly_wage.py"


def load_module():
    spec = importlib.util.spec_from_file_location("korea_hourly_wage", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PUBLISHED_55 = """---
node_id: 근로기준법_제55조
kind: 법령조항
label: 휴일
review_state: published
sources:
- 근로기준법 제55조 (온톨로지 마커)
---
주휴일 조문.
"""


def _wiki_with(*node_texts):
    tmp = tempfile.mkdtemp()
    d = pathlib.Path(tmp) / "법령조항"
    d.mkdir(parents=True)
    for i, t in enumerate(node_texts):
        (d / f"n{i}.md").write_text(t, encoding="utf-8")
    return pathlib.Path(tmp)


class HourlyWageLegalBasisTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_published_node_wins(self):
        # sources[0]에 마커를 심어 폴백이 아닌 온톨로지 경로임을 증명한다
        root = _wiki_with(_PUBLISHED_55)
        self.assertEqual(self.mod.legal_basis_base(root), "근로기준법 제55조 (온톨로지 마커)")

    def test_empty_root_falls_back(self):
        root = pathlib.Path(tempfile.mkdtemp())
        self.assertEqual(self.mod.legal_basis_base(root), "근로기준법 제55조")

    def test_default_root_uses_repo_wiki(self):
        # 실레포 §55 노드는 published
        self.assertEqual(self.mod.legal_basis_base(), "근로기준법 제55조")


if __name__ == "__main__":
    unittest.main()
