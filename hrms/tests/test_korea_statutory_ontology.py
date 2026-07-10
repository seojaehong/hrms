# -*- coding: utf-8 -*-
"""법정 확정값(최저임금 등) 온톨로지 리더 — framework-free. TDD: RED 먼저.

최저임금 같은 법정 수치가 "인자로 아무거나" 들어가면 안 된다(2026=10,320인데 10,030으로
스모크한 사고). published 온톨로지 노드(출처 있는 확정값)에서만 로드한다.

실행: python3 hrms/tests/test_korea_statutory_ontology.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import tempfile
import unittest

_SK = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea"


def _load(name, sub=""):
	path = _SK / (sub + name + ".py") if sub else _SK / (name + ".py")
	spec = importlib.util.spec_from_file_location(name, path)
	m = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(m)
	return m


_stat = _load("statutory_ontology", "ontology/")

_PUBLISHED = """---
node_id: 최저임금_2026
kind: 법정수치
label: 2026년 최저임금
review_state: published
value: 10320
effective_year: 2026
sources:
- 최저임금위원회 고시 (2026 적용)
---
2026년 적용 최저임금은 시급 10,320원이다.
"""

_DRAFT = """---
node_id: 최저임금_2027
kind: 법정수치
label: 2027년 최저임금(초안)
review_state: draft
value: 11000
effective_year: 2027
sources:
- 미정
---
초안 — 승인 전.
"""


def _wiki_with(*node_texts):
	tmp = tempfile.mkdtemp()
	d = pathlib.Path(tmp) / "법정수치"
	d.mkdir(parents=True)
	for i, t in enumerate(node_texts):
		(d / f"n{i}.md").write_text(t, encoding="utf-8")
	return pathlib.Path(tmp)


class TestMinimumWage(unittest.TestCase):
	def test_published_2026_returns_10320(self):
		root = _wiki_with(_PUBLISHED)
		self.assertEqual(_stat.get_minimum_hourly_wage(root, 2026), 10320)

	def test_draft_not_returned(self):
		# draft만 있는 연도는 확정값 없음 → None (published 게이트)
		root = _wiki_with(_DRAFT)
		self.assertIsNone(_stat.get_minimum_hourly_wage(root, 2027))

	def test_unknown_year_none(self):
		root = _wiki_with(_PUBLISHED)
		self.assertIsNone(_stat.get_minimum_hourly_wage(root, 2099))

	def test_10030_would_be_violation_at_2026(self):
		# 사고 재현: 10,030은 2026 최저(10,320) 미달 → 위반
		root = _wiki_with(_PUBLISHED)
		mw = _stat.get_minimum_hourly_wage(root, 2026)
		self.assertGreater(mw, 10030)


class TestRealRepoNode(unittest.TestCase):
	def test_repo_has_published_2026_minimum_wage(self):
		# 실제 레포 wiki에 2026 최저임금 published 노드가 있어야 한다
		root = pathlib.Path(__file__).resolve().parents[2] / "wiki" / "ontology"
		self.assertEqual(_stat.get_minimum_hourly_wage(root, 2026), 10320)


if __name__ == "__main__":
	unittest.main()
