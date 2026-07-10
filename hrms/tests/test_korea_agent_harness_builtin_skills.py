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
	def test_two_builtin_skills(self):
		skills = get_builtin_skills()
		names = [s["name"] for s in skills]
		self.assertEqual(names, ["hourly_closing_prep", "insurance_reconcile"])

	def test_all_pass_validation(self):
		# AC: 빌트인 스킬은 US-001 스키마를 그대로 따르고 validate 통과
		for defn in get_builtin_skills():
			self.assertIs(validate_skill_definition(defn), defn)

	def test_read_only_skills_need_no_approval(self):
		for defn in get_builtin_skills():
			self.assertFalse(defn["requires_approval"])

	def test_insurance_reconcile_is_two_step(self):
		defn = {s["name"]: s for s in get_builtin_skills()}["insurance_reconcile"]
		tools = [step["tool"] for step in defn["steps"]]
		self.assertEqual(tools, ["reconcile_contributions", "summarize_reconciliation_ko"])

	def test_get_builtin_skills_returns_copies(self):
		# 반환값을 변형해도 다음 호출 원본이 오염되지 않아야 함
		get_builtin_skills()[0]["name"] = "MUTATED"
		self.assertEqual(get_builtin_skills()[0]["name"], "hourly_closing_prep")


class TestRegisterBuiltinSkills(unittest.TestCase):
	def test_register_into_registry(self):
		reg = SkillRegistry()
		names = register_builtin_skills(reg)
		self.assertEqual(names, ["hourly_closing_prep", "insurance_reconcile"])
		self.assertTrue(reg.has("hourly_closing_prep"))
		self.assertTrue(reg.has("insurance_reconcile"))

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
	def test_prep_summary_reflects_two_proposals(self):
		skills = SkillRegistry()
		register_builtin_skills(skills)
		defn = skills.get("hourly_closing_prep")

		reg = ToolRegistry()
		# fake list_hourly_payroll_proposals: 제안 2명 반환
		reg.register_tool(
			"list_hourly_payroll_proposals",
			lambda **kw: {"proposals": [{"emp": "A"}, {"emp": "B"}]},
			{},
			read_only=True,
		)

		def provider(convo):
			# 아직 도구 결과가 없으면 스킬 step대로 도구 호출
			results = _tool_results(convo)
			if "list_hourly_payroll_proposals" not in results:
				step = defn["steps"][0]
				return {"tool_call": {"name": step["tool"], "args": step["args"]}}
			# 도구 결과가 대화에 반영됨 → 실제 수치로 요약 포맷
			count = len(results["list_hourly_payroll_proposals"]["proposals"])
			return {"text": defn["output_summary_template"].format(proposal_count=count)}

		out = run_agent_loop(provider, [{"role": "user", "text": "시급 마감 준비"}], reg)

		self.assertEqual(out["status"], "completed")
		self.assertEqual([c["tool"] for c in out["tool_calls"]], ["list_hourly_payroll_proposals"])
		self.assertIn("제안 2명", out["final_text"])


class TestE2EInsuranceReconcile(unittest.TestCase):
	def test_reconcile_summary_reflects_one_diff(self):
		skills = SkillRegistry()
		register_builtin_skills(skills)
		defn = skills.get("insurance_reconcile")

		reg = ToolRegistry()
		# fake reconcile_contributions: diff 1건 반환
		recon_result = {"ok": False, "match_count": 1, "diffs": [{"emp": "A", "delta": 1}]}
		reg.register_tool("reconcile_contributions", lambda **kw: recon_result, {}, read_only=True)
		# fake summarize_reconciliation_ko: 대사 결과 dict를 받아 사람용 요약 문자열
		reg.register_tool(
			"summarize_reconciliation_ko",
			lambda **kw: f"고지 대사 불일치 — diff {len(recon_result['diffs'])}건",
			{},
			read_only=True,
		)

		def provider(convo):
			results = _tool_results(convo)
			# 스킬 steps를 순서대로 소진
			for step in defn["steps"]:
				if step["tool"] not in results:
					return {"tool_call": {"name": step["tool"], "args": step["args"]}}
			# 두 도구 결과 모두 대화에 반영됨 → 수치로 최종 요약
			diff_count = len(results["reconcile_contributions"]["diffs"])
			return {"text": defn["output_summary_template"].format(diff_count=diff_count)}

		out = run_agent_loop(provider, [{"role": "user", "text": "4대보험 대사"}], reg)

		self.assertEqual(out["status"], "completed")
		self.assertEqual(
			[c["tool"] for c in out["tool_calls"]],
			["reconcile_contributions", "summarize_reconciliation_ko"],
		)
		# summarize 도구 결과가 대화에 반영됐는지도 확인
		self.assertIn("diff 1건", _tool_results(out["messages"])["summarize_reconciliation_ko"])
		self.assertIn("불일치 1건", out["final_text"])


if __name__ == "__main__":
	unittest.main()
