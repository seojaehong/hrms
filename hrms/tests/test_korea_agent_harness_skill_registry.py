# -*- coding: utf-8 -*-
"""agent_harness/skill_registry.py 테스트 — 스킬 정의 스키마 + 레지스트리.

framework-free: skill_registry.py는 frappe import 없음.
hrms/__init__.py가 frappe를 import하므로 spec_from_file_location으로 직접 로드.
실행: python3 hrms/tests/test_korea_agent_harness_skill_registry.py
"""
import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = (
	_REPO_ROOT / "hrms" / "regional" / "south_korea" / "agent_harness" / "skill_registry.py"
)

_spec = importlib.util.spec_from_file_location("skill_registry", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

validate_skill_definition = _mod.validate_skill_definition
SkillRegistry = _mod.SkillRegistry


def _valid_defn(name="hourly_closing_prep"):
	return {
		"name": name,
		"description": "시급 마감 준비 — 제안 조회 후 요약",
		"steps": [
			{"tool": "list_hourly_payroll_proposals", "args": {"site": "S1"}},
		],
		"requires_approval": False,
		"output_summary_template": "{count}건 제안",
	}


class TestValidateSkillDefinition(unittest.TestCase):
	def test_valid_passes(self):
		defn = _valid_defn()
		self.assertIs(validate_skill_definition(defn), defn)

	def test_not_dict(self):
		with self.assertRaises(ValueError):
			validate_skill_definition(["not", "a", "dict"])

	def test_missing_key(self):
		defn = _valid_defn()
		del defn["steps"]
		with self.assertRaises(ValueError) as cm:
			validate_skill_definition(defn)
		self.assertIn("steps", str(cm.exception))

	def test_wrong_type(self):
		defn = _valid_defn()
		defn["description"] = 123
		with self.assertRaises(ValueError):
			validate_skill_definition(defn)

	def test_requires_approval_not_bool(self):
		defn = _valid_defn()
		defn["requires_approval"] = "yes"
		with self.assertRaises(ValueError):
			validate_skill_definition(defn)

	def test_empty_name(self):
		defn = _valid_defn(name="   ")
		with self.assertRaises(ValueError):
			validate_skill_definition(defn)

	def test_empty_steps(self):
		defn = _valid_defn()
		defn["steps"] = []
		with self.assertRaises(ValueError) as cm:
			validate_skill_definition(defn)
		self.assertIn("steps", str(cm.exception))

	def test_step_missing_tool(self):
		defn = _valid_defn()
		defn["steps"] = [{"args": {}}]
		with self.assertRaises(ValueError) as cm:
			validate_skill_definition(defn)
		self.assertIn("tool", str(cm.exception))

	def test_step_empty_tool(self):
		defn = _valid_defn()
		defn["steps"] = [{"tool": "  ", "args": {}}]
		with self.assertRaises(ValueError):
			validate_skill_definition(defn)

	def test_step_args_not_dict(self):
		defn = _valid_defn()
		defn["steps"] = [{"tool": "t", "args": ["bad"]}]
		with self.assertRaises(ValueError):
			validate_skill_definition(defn)

	def test_step_args_optional(self):
		defn = _valid_defn()
		defn["steps"] = [{"tool": "t"}]  # args 생략 허용
		self.assertIs(validate_skill_definition(defn), defn)


class TestSkillRegistry(unittest.TestCase):
	def test_register_and_get(self):
		reg = SkillRegistry()
		defn = _valid_defn()
		reg.register(defn)
		self.assertIs(reg.get("hourly_closing_prep"), defn)
		self.assertTrue(reg.has("hourly_closing_prep"))

	def test_register_invalid_raises(self):
		reg = SkillRegistry()
		bad = _valid_defn()
		bad["steps"] = []
		with self.assertRaises(ValueError):
			reg.register(bad)
		self.assertEqual(reg.list_skills(), [])

	def test_duplicate_rejected(self):
		reg = SkillRegistry()
		reg.register(_valid_defn())
		with self.assertRaises(ValueError):
			reg.register(_valid_defn())

	def test_duplicate_overwrite(self):
		reg = SkillRegistry()
		reg.register(_valid_defn())
		new = _valid_defn()
		new["description"] = "changed"
		reg.register(new, overwrite=True)
		self.assertEqual(reg.get("hourly_closing_prep")["description"], "changed")

	def test_get_unregistered_raises(self):
		reg = SkillRegistry()
		with self.assertRaises(KeyError):
			reg.get("nope")

	def test_list_skills_order(self):
		reg = SkillRegistry()
		reg.register(_valid_defn(name="a"))
		reg.register(_valid_defn(name="b"))
		self.assertEqual(reg.list_skills(), ["a", "b"])


if __name__ == "__main__":
	unittest.main()
