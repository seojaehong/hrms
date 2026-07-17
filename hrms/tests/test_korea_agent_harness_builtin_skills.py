# -*- coding: utf-8 -*-
"""agent_harness/builtin_skills.py 테스트 — 빌트인 스킬 2종 + E2E.

framework-free: 코어 모듈은 frappe import 없음. hrms/__init__.py가 frappe를
import하므로 spec_from_file_location으로 코어 파일을 직접 로드한다.
실행: python3 hrms/tests/test_korea_agent_harness_builtin_skills.py

E2E는 fake provider + fake 도구를 ToolRegistry에 등록해 agent_loop로 스킬을
실행한다. 최종 요약 text의 수치(제안 2명 / diff 1건)는 fake provider가
**대화에 반영된 도구 결과에서 직접 추출**해 스킬의 output_summary_template로
포맷한다 — agent_loop가 도구 결과를 대화에 되먹이지 않으면 수치가 어긋나 실패한다.
"""
import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_CORE_DIR = _REPO_ROOT / "hrms" / "regional" / "south_korea" / "agent_harness"


def _load(name):
	spec = importlib.util.spec_from_file_location(name, _CORE_DIR / f"{name}.py")
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


_builtin_mod = _load("builtin_skills")
_skill_mod = _load("skill_registry")
_tool_mod = _load("tool_registry")
_loop_mod = _load("agent_loop")

get_builtin_skills = _builtin_mod.get_builtin_skills
register_builtin_skills = _builtin_mod.register_builtin_skills
validate_skill_definition = _skill_mod.validate_skill_definition
SkillRegistry = _skill_mod.SkillRegistry
ToolRegistry = _tool_mod.ToolRegistry
run_agent_loop = _loop_mod.run_agent_loop


def _tool_results(messages):
	"""대화의 도구 메시지에서 이름→fn 반환값을 뽑는다(final provider가 소비).

	agent_loop이 대화에 넣는 도구 메시지의 "result"는 tool_registry의 구조화
	call dict({tool,args,status,result,...})이므로 실제 fn 반환은 ["result"]에 있다.
	"""
	out = {}
	for m in messages:
		if m.get("role") == "tool":
			out[m["tool"]] = m["result"].get("result")
	return out


class TestSkillDefinitions(unittest.TestCase):
	def test_core_builtin_skills_present(self):
		# 스킬은 계속 추가되므로 정확일치 대신 핵심 3종 존재만 단언(additive-safe).
		names = [s["name"] for s in get_builtin_skills()]
		for name in ("hourly_closing_prep", "insurance_reconcile", "hr_freeform_qa"):
			self.assertIn(name, names)

	def test_freeform_qa_is_freeform_with_empty_steps(self):
		# 자유 질의 스킬은 고정 steps 없이(freeform=True) validate를 통과해야 함.
		defn = {s["name"]: s for s in get_builtin_skills()}["hr_freeform_qa"]
		self.assertEqual(defn["steps"], [])
		self.assertTrue(defn["freeform"])
		self.assertFalse(defn["requires_approval"])
		self.assertIs(validate_skill_definition(defn), defn)

	def test_all_pass_validation(self):
		# AC: 빌트인 스킬은 US-001 스키마를 그대로 따르고 validate 통과
		for defn in get_builtin_skills():
			self.assertIs(validate_skill_definition(defn), defn)

	def test_read_only_skills_need_no_approval(self):
		for defn in get_builtin_skills():
			self.assertFalse(defn["requires_approval"])

	def test_insurance_reconcile_is_freeform(self):
		# 스텝 간 데이터 흐름(computed→대사)이 필요해 freeform으로 전환됨.
		defn = {s["name"]: s for s in get_builtin_skills()}["insurance_reconcile"]
		self.assertEqual(defn["steps"], [])
		self.assertTrue(defn["freeform"])
		# 실제 MCP 도구를 참조해야 함.
		self.assertIn("check_insurance_reconciliation", defn["description"])

	def test_hourly_closing_prep_is_freeform(self):
		defn = {s["name"]: s for s in get_builtin_skills()}["hourly_closing_prep"]
		self.assertEqual(defn["steps"], [])
		self.assertTrue(defn["freeform"])
		self.assertIn("get_tenant_records", defn["description"])

	def test_leave_manage_is_freeform(self):
		reg = SkillRegistry()
		register_builtin_skills(reg)
		self.assertTrue(reg.has("leave_manage"))
		defn = reg.get("leave_manage")
		self.assertEqual(defn["steps"], [])
		self.assertTrue(defn["freeform"])
		self.assertIn("calculate_annual_leave", defn["description"])

	def test_severance_settle_is_freeform(self):
		reg = SkillRegistry()
		register_builtin_skills(reg)
		self.assertTrue(reg.has("severance_settle"))
		defn = reg.get("severance_settle")
		self.assertEqual(defn["steps"], [])
		self.assertTrue(defn["freeform"])
		self.assertIn("calculate_severance", defn["description"])

	def test_no_phantom_tool_names(self):
		# 실재하지 않는 레거시 도구명이 남으면 에이전트가 fail-closed로 막힌다(회귀 가드).
		phantom = (
			"list_hourly_payroll_proposals",
			"reconcile_contributions",
			"summarize_reconciliation_ko",
		)
		blob = repr(get_builtin_skills())
		for name in phantom:
			self.assertNotIn(name, blob)

	def test_get_builtin_skills_returns_copies(self):
		# 반환값을 변형해도 다음 호출 원본이 오염되지 않아야 함
		get_builtin_skills()[0]["name"] = "MUTATED"
		self.assertEqual(get_builtin_skills()[0]["name"], "hourly_closing_prep")


class TestRegisterBuiltinSkills(unittest.TestCase):
	def test_register_into_registry(self):
		reg = SkillRegistry()
		names = register_builtin_skills(reg)
		for name in ("hourly_closing_prep", "insurance_reconcile", "hr_freeform_qa"):
			self.assertIn(name, names)
		self.assertTrue(reg.has("hourly_closing_prep"))
		self.assertTrue(reg.has("insurance_reconcile"))
		self.assertTrue(reg.has("hr_freeform_qa"))

	def test_duplicate_register_raises(self):
		reg = SkillRegistry()
		register_builtin_skills(reg)
		with self.assertRaises(ValueError):
			register_builtin_skills(reg)  # overwrite=False 기본

	def test_overwrite_allowed(self):
		reg = SkillRegistry()
		register_builtin_skills(reg)
		register_builtin_skills(reg, overwrite=True)  # 예외 없어야 함


class TestE2EHourlyClosingPrep(unittest.TestCase):
	def test_freeform_prep_drives_real_tool(self):
		# freeform 스킬: 에이전트가 실 도구(get_tenant_records)를 호출하고,
		# agent_loop이 도구 결과를 대화에 되먹여야 최종 수치가 맞는다.
		skills = SkillRegistry()
		register_builtin_skills(skills)
		defn = skills.get("hourly_closing_prep")
		self.assertTrue(defn["freeform"])

		reg = ToolRegistry()
		reg.register_tool(
			"get_tenant_records",
			lambda **kw: {"records": [{"emp": "A"}, {"emp": "B"}]},
			{},
			read_only=True,
		)

		def provider(convo):
			results = _tool_results(convo)
			if "get_tenant_records" not in results:
				return {"tool_call": {"name": "get_tenant_records", "args": {}}}
			count = len(results["get_tenant_records"]["records"])
			return {"text": f"시급 마감 검토 대상 {count}명"}

		out = run_agent_loop(provider, [{"role": "user", "text": "시급 마감 준비"}], reg)

		self.assertEqual(out["status"], "completed")
		self.assertEqual([c["tool"] for c in out["tool_calls"]], ["get_tenant_records"])
		self.assertIn("2명", out["final_text"])


class TestE2EInsuranceReconcile(unittest.TestCase):
	def test_freeform_reconcile_drives_real_tool(self):
		# freeform 스킬: 에이전트가 실 도구(check_insurance_reconciliation)를 호출하고,
		# 그 결과를 대화에 되먹여 최종 요약을 만든다.
		skills = SkillRegistry()
		register_builtin_skills(skills)
		defn = skills.get("insurance_reconcile")
		self.assertTrue(defn["freeform"])

		reg = ToolRegistry()
		recon_result = {"ok": False, "diffs": [{"emp": "A", "delta": 1}]}
		reg.register_tool(
			"check_insurance_reconciliation",
			lambda **kw: recon_result,
			{},
			read_only=True,
		)

		def provider(convo):
			results = _tool_results(convo)
			if "check_insurance_reconciliation" not in results:
				return {
					"tool_call": {
						"name": "check_insurance_reconciliation",
						"args": {"computed": [], "notified": []},
					}
				}
			diff_count = len(results["check_insurance_reconciliation"]["diffs"])
			return {"text": f"고지 대사 불일치 {diff_count}건"}

		out = run_agent_loop(provider, [{"role": "user", "text": "4대보험 대사"}], reg)

		self.assertEqual(out["status"], "completed")
		self.assertEqual(
			[c["tool"] for c in out["tool_calls"]],
			["check_insurance_reconciliation"],
		)
		self.assertIn("불일치 1건", out["final_text"])


if __name__ == "__main__":
	unittest.main()
