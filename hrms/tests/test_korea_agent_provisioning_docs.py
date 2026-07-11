# -*- coding: utf-8 -*-
"""에이전트 자동 프로비저닝 문서 검증 (US-5).

docs/korea_hrms/agent-provisioning.md 가 존재하고, 자동 프로비저닝 흐름의
필수 개념(가입→플랜→apply, 멱등성, 보안: calc_only 토큰 스코프·시크릿 마스킹,
10만 확장 크론/셀프서브 연결점)을 담고 있는지, 실제 함수/CLI 사용법과
일치하는 키워드를 포함하는지 확인한다. MILESTONES 에 M-provisioning 링크 확인.
실행: python3 hrms/tests/test_korea_agent_provisioning_docs.py
"""

from __future__ import annotations

import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_DOC = _REPO_ROOT / "docs" / "korea_hrms" / "agent-provisioning.md"
_MILESTONES = _REPO_ROOT / "docs" / "korea_hrms" / "DEVELOPMENT-MILESTONES.md"


class TestProvisioningDoc(unittest.TestCase):
	def test_doc_exists(self):
		self.assertTrue(_DOC.exists(), f"문서 없음: {_DOC}")

	def test_doc_covers_required_concepts(self):
		text = _DOC.read_text(encoding="utf-8")
		required = [
			"build_agent_provisioning_plan",  # 플랜 빌더
			"provision_agent.py",  # CLI
			"--apply",  # 가입→플랜→apply 흐름
			"dry-run",  # fail-safe 기본
			"멱등",  # 멱등성
			"calc_only",  # 계산전용 토큰 스코프(보안)
			"마스킹",  # 시크릿 마스킹(보안)
			"크론",  # 10만 확장: 크론
			"셀프서브",  # 10만 확장: 셀프서브
			"10만",  # 상용 규모
		]
		for token in required:
			self.assertIn(token, text, f"문서에 '{token}' 누락")

	def test_milestones_links_provisioning(self):
		text = _MILESTONES.read_text(encoding="utf-8")
		self.assertIn("M-provisioning", text)
		self.assertIn("agent-provisioning.md", text)


if __name__ == "__main__":
	unittest.main()
