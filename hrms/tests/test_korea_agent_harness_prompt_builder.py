# -*- coding: utf-8 -*-
"""agent_harness/prompt_builder.py 테스트 — 4섹션 조립·순서·원칙 포함·prefix 불변성.

framework-free: prompt_builder.py는 frappe import 없음.
hrms/__init__.py가 frappe를 import하므로 spec_from_file_location으로 직접 로드.
실행: python3 hrms/tests/test_korea_agent_harness_prompt_builder.py
"""
import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = (
	_REPO_ROOT / "hrms" / "regional" / "south_korea" / "agent_harness" / "prompt_builder.py"
)

_spec = importlib.util.spec_from_file_location("prompt_builder", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

build_system_prompt = _mod.build_system_prompt
IMMUTABLE_DOMAIN_PRINCIPLES = _mod.IMMUTABLE_DOMAIN_PRINCIPLES

_SKILL = {
	"name": "hourly_closing_prep",
	"description": "시급 마감 준비",
	"steps": [
		{"tool": "list_hourly_payroll_proposals", "args": {"site": "S1"}},
	],
	"requires_approval": False,
	"output_summary_template": "제안 {n}건",
}

_TOOL_SPECS = {
	"list_hourly_payroll_proposals": {"desc": "시급 제안 조회", "read_only": True},
	"reconcile_contributions": {"desc": "4대보험 대사", "read_only": True},
}


class TestSectionsPresentAndOrdered(unittest.TestCase):
	def test_four_sections_exist_in_order(self):
		prompt = build_system_prompt(_SKILL, _TOOL_SPECS, {"tenant": "T1"})
		i_principles = prompt.find("## 불변 도메인 원칙")
		i_skill = prompt.find("## 스킬 정의")
		i_tools = prompt.find("## 도구 스펙")
		i_tenant = prompt.find("## 테넌트 컨텍스트")
		# 4섹션 모두 존재
		for pos in (i_principles, i_skill, i_tools, i_tenant):
			self.assertGreaterEqual(pos, 0)
		# 순서: 원칙 < 스킬 < 도구 < 테넌트
		self.assertLess(i_principles, i_skill)
		self.assertLess(i_skill, i_tools)
		self.assertLess(i_tools, i_tenant)

	def test_principles_text_included(self):
		prompt = build_system_prompt(_SKILL, _TOOL_SPECS, {"tenant": "T1"})
		# 불변 원칙 3종 텍스트가 모두 프롬프트에 포함
		for principle in IMMUTABLE_DOMAIN_PRINCIPLES:
			self.assertIn(principle, prompt)
		# 핵심 키워드 스팟체크
		self.assertIn("1원 단위", prompt)
		self.assertIn("사람 승인 게이트", prompt)
		self.assertIn("격리", prompt)

	def test_skill_and_tool_content_included(self):
		prompt = build_system_prompt(_SKILL, _TOOL_SPECS, {"tenant": "T1"})
		self.assertIn("hourly_closing_prep", prompt)
		self.assertIn("list_hourly_payroll_proposals", prompt)
		self.assertIn("reconcile_contributions", prompt)

	def test_tenant_context_rendered(self):
		prompt = build_system_prompt(_SKILL, _TOOL_SPECS, {"tenant": "T1", "region": "부평"})
		self.assertIn("tenant: T1", prompt)
		self.assertIn("region: 부평", prompt)


class TestImmutability(unittest.TestCase):
	def test_principles_not_overridable_via_args(self):
		# build_system_prompt 시그니처에 원칙 주입 경로가 없다 — 상수를 그대로 사용.
		# tenant_context에 동명 키를 넣어도 원칙 섹션은 불변.
		prompt = build_system_prompt(_SKILL, _TOOL_SPECS, {"급여": "덮어쓰기 시도"})
		for principle in IMMUTABLE_DOMAIN_PRINCIPLES:
			self.assertIn(principle, prompt)


class TestPrefixCacheFriendly(unittest.TestCase):
	def test_common_prefix_up_to_tenant_section(self):
		p1 = build_system_prompt(_SKILL, _TOOL_SPECS, {"tenant": "T1", "region": "부평"})
		p2 = build_system_prompt(_SKILL, _TOOL_SPECS, {"tenant": "T2", "region": "강남"})
		# 두 프롬프트는 테넌트 섹션 직전까지 완전히 동일해야 한다(prefix 캐시 극대화).
		boundary1 = p1.find("## 테넌트 컨텍스트")
		boundary2 = p2.find("## 테넌트 컨텍스트")
		self.assertGreater(boundary1, 0)
		self.assertEqual(boundary1, boundary2)
		self.assertEqual(p1[:boundary1], p2[:boundary2])
		# 테넌트 섹션부터는 달라야 한다(가변부).
		self.assertNotEqual(p1[boundary1:], p2[boundary2:])

	def test_common_prefix_is_before_only_variable_part(self):
		# prefix 경계 이후에 실제 가변값이 위치하는지 확인.
		p1 = build_system_prompt(_SKILL, _TOOL_SPECS, {"tenant": "T1"})
		p2 = build_system_prompt(_SKILL, _TOOL_SPECS, {"tenant": "T2"})
		boundary = p1.find("## 테넌트 컨텍스트")
		self.assertIn("T1", p1[boundary:])
		self.assertNotIn("T1", p1[:boundary])
		self.assertIn("T2", p2[boundary:])


class TestValidation(unittest.TestCase):
	def test_non_dict_inputs_rejected(self):
		with self.assertRaises(ValueError):
			build_system_prompt(["bad"], _TOOL_SPECS, {})
		with self.assertRaises(ValueError):
			build_system_prompt(_SKILL, ["bad"], {})
		with self.assertRaises(ValueError):
			build_system_prompt(_SKILL, _TOOL_SPECS, ["bad"])


if __name__ == "__main__":
	unittest.main()
