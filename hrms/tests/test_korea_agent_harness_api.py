# -*- coding: utf-8 -*-
"""agent_harness_api.py 테스트 — whitelist 래퍼 (조건부 frappe).

framework-free: hrms/__init__.py가 frappe를 import하므로 패키지 import 대신
spec_from_file_location으로 api 모듈을 직접 로드한다. frappe는 FakeFrappe 스텁을
sys.modules에 주입해 흉내낸다(insurance_filing_api 테스트 컨벤션).
실행: python3 hrms/tests/test_korea_agent_harness_api.py

핵심 검증:
- provider 미설정(config 없음) → not_configured, 어떤 LLM/네트워크 호출도 0회.
- 미등록 skill_name → unknown_skill(명시적 오류 status).
- provider + tool_registry 주입 시 → 에이전트 루프로 스킬을 실제 실행(completed).
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SK_DIR = _REPO_ROOT / "hrms" / "regional" / "south_korea"
API_PATH = _SK_DIR / "agent_harness_api.py"
_CORE_DIR = _SK_DIR / "agent_harness"


class FakeFrappe:
	"""whitelist no-op + conf 만 제공하는 최소 스텁 (provider config 해석용)."""

	def __init__(self, conf=None):
		self.conf = conf if conf is not None else {}

	def whitelist(self):
		def decorator(fn):
			return fn

		return decorator


def load_api(fake_frappe=None):
	old_frappe = sys.modules.get("frappe")
	if fake_frappe is not None:
		sys.modules["frappe"] = fake_frappe
	else:
		sys.modules.pop("frappe", None)
	try:
		spec = importlib.util.spec_from_file_location("korea_agent_harness_api", API_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		return module
	finally:
		if old_frappe is not None:
			sys.modules["frappe"] = old_frappe
		else:
			sys.modules.pop("frappe", None)


def _load_core(name):
	spec = importlib.util.spec_from_file_location(name, _CORE_DIR / f"{name}.py")
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


class TestNotConfigured(unittest.TestCase):
	def test_no_frappe_returns_not_configured(self):
		# frappe 자체가 없어도 로드 가능해야 하고, provider 미설정 → not_configured.
		mod = load_api(fake_frappe=None)
		result = mod.run_agent_skill("hourly_closing_prep")
		self.assertEqual(result["status"], "not_configured")
		self.assertTrue(result["requires_provider_config"])

	def test_empty_conf_returns_not_configured(self):
		mod = load_api(fake_frappe=FakeFrappe(conf={}))
		result = mod.run_agent_skill("insurance_reconcile")
		self.assertEqual(result["status"], "not_configured")

	def test_config_key_present_still_not_configured_in_poc(self):
		# PoC: config 키가 있어도 실제 LLM 클라이언트는 배선하지 않는다 → not_configured.
		mod = load_api(fake_frappe=FakeFrappe(conf={mod_key(): "x"}))
		result = mod.run_agent_skill("hourly_closing_prep")
		self.assertEqual(result["status"], "not_configured")


def mod_key():
	# API 모듈의 config 키 상수를 참조(하드코딩 문자열 중복 방지).
	mod = load_api(fake_frappe=None)
	return mod.PROVIDER_CONFIG_KEY


class TestUnknownSkill(unittest.TestCase):
	def test_unknown_skill_status(self):
		# 미등록 스킬은 provider 여부와 무관하게 명시적 오류 status.
		mod = load_api(fake_frappe=None)
		result = mod.run_agent_skill("does_not_exist")
		self.assertEqual(result["status"], "unknown_skill")
		self.assertEqual(result["skill_name"], "does_not_exist")
		self.assertIn("hourly_closing_prep", result["available"])

	def test_unknown_skill_checked_before_provider(self):
		# provider 미설정 상태에서도 미등록 스킬은 not_configured가 아니라 unknown_skill.
		mod = load_api(fake_frappe=FakeFrappe(conf={}))
		result = mod.run_agent_skill("nope")
		self.assertEqual(result["status"], "unknown_skill")


class TestNoTools(unittest.TestCase):
	def test_provider_injected_but_no_tools(self):
		# provider가 주입돼도 tool_registry 없으면 실행하지 않는다(도구 바인딩 필요).
		mod = load_api(fake_frappe=None)

		def provider(convo):
			return {"text": "should not run"}

		result = mod.run_agent_skill("hourly_closing_prep", provider=provider)
		self.assertEqual(result["status"], "no_tools")


class TestInjectedRun(unittest.TestCase):
	"""provider + tool_registry 주입 시 에이전트 루프가 실제 스킬을 실행하는지(happy path)."""

	def test_hourly_prep_completes_with_injected_provider(self):
		mod = load_api(fake_frappe=None)
		tool_mod = _load_core("tool_registry")
		reg = tool_mod.ToolRegistry()
		reg.register_tool(
			"list_hourly_payroll_proposals",
			lambda **kw: {"proposals": [{"emp": "A"}, {"emp": "B"}]},
			{},
			read_only=True,
		)

		def provider(convo):
			# 도구 결과가 대화에 반영되기 전이면 스킬 step대로 도구 호출
			for m in convo:
				if m.get("role") == "tool" and m.get("tool") == "list_hourly_payroll_proposals":
					count = len(m["result"]["result"]["proposals"])
					return {"text": f"시급 마감 준비 완료 — 제안 {count}명 검토 대상"}
			return {"tool_call": {"name": "list_hourly_payroll_proposals", "args": {}}}

		result = mod.run_agent_skill(
			"hourly_closing_prep", provider=provider, tool_registry=reg
		)
		self.assertEqual(result["status"], "completed")
		self.assertEqual(result["skill_name"], "hourly_closing_prep")
		self.assertEqual([c["tool"] for c in result["tool_calls"]], ["list_hourly_payroll_proposals"])
		self.assertIn("제안 2명", result["final_text"])


class TestFreeformQA(unittest.TestCase):
	"""자유 질의 빌트인 스킬 hr_freeform_qa — 도구 필요시에만 호출(US-3)."""

	def test_freeform_no_tool_call_completes(self):
		# (a) 도구 0회, 바로 텍스트 응답 → completed, tool_calls 0건.
		mod = load_api(fake_frappe=None)
		tool_mod = _load_core("tool_registry")
		reg = tool_mod.ToolRegistry()  # 빈 레지스트리 — no_tools 회피용(None 아님)

		captured = {}

		def provider(convo):
			captured["messages"] = [dict(m) for m in convo]
			return {"text": "연차는 1년 만근 시 15일 발생합니다."}

		result = mod.run_agent_skill(
			"hr_freeform_qa", {"question": "연차 며칠?"}, provider=provider, tool_registry=reg
		)
		self.assertNotEqual(result["status"], "unknown_skill")
		self.assertEqual(result["status"], "completed")
		self.assertEqual(result["skill_name"], "hr_freeform_qa")
		self.assertEqual(result["tool_calls"], [])
		self.assertIn("15일", result["final_text"])
		# question이 user 메시지 args로 전달되는지 확인.
		msgs = captured["messages"]
		self.assertEqual(msgs[1]["role"], "user")
		self.assertEqual(msgs[1]["args"]["question"], "연차 며칠?")

	def test_freeform_one_tool_call_then_answer(self):
		# (b) tool_call 1회(list_hourly_payroll_proposals) 후 텍스트 → tool_calls 1건, completed.
		mod = load_api(fake_frappe=None)
		tool_mod = _load_core("tool_registry")
		reg = tool_mod.ToolRegistry()
		reg.register_tool(
			"list_hourly_payroll_proposals",
			lambda **kw: {"proposals": [{"emp": "A"}, {"emp": "B"}]},
			{"description": "시급 제안 조회"},
			read_only=True,
		)

		def provider(convo):
			for m in convo:
				if m.get("role") == "tool" and m.get("tool") == "list_hourly_payroll_proposals":
					count = len(m["result"]["result"]["proposals"])
					return {"text": f"현재 시급 제안 대상은 {count}명입니다."}
			return {"tool_call": {"name": "list_hourly_payroll_proposals", "args": {}}}

		result = mod.run_agent_skill(
			"hr_freeform_qa",
			{"question": "이번 달 시급 대상 몇 명?"},
			provider=provider,
			tool_registry=reg,
		)
		self.assertEqual(result["status"], "completed")
		self.assertEqual(
			[c["tool"] for c in result["tool_calls"]], ["list_hourly_payroll_proposals"]
		)
		self.assertIn("2명", result["final_text"])


class TestCalcTools(unittest.TestCase):
	"""framework-free 계산·지식검색 도구 — frappe 없이도 등록·호출 가능해야 한다."""

	def _registry(self):
		mod = load_api(fake_frappe=None)
		reg = _load_core("tool_registry").ToolRegistry()
		mod._register_calc_tools(reg)
		return reg

	def test_calc_tools_registered(self):
		reg = self._registry()
		names = set(reg.list_tools())
		for expected in (
			"calc_weekly_holiday_allowance",
			"calc_daily_worker_payroll",
			"calc_ordinary_hourly_wage",
			"calc_unused_leave_allowance",
			"build_employment_contract",
			"calc_design_inclusive_wage",
			"calc_audit_inclusive_wage",
			"calc_annual_leave_promotion",
			"calc_payslip_breakdown",
			"search_labor_knowledge",
			"check_work_rules_required_items",
			"work_rules_amendment_procedure",
		):
			self.assertIn(expected, names)

	def test_build_employment_contract_via_registry(self):
		reg = self._registry()
		result = reg.call(
			"build_employment_contract",
			{
				"data": {
					"company": {
						"company_name": "가나다 주식회사",
						"representative_name": "홍길동",
						"address": "서울시 강남구 테헤란로 1",
						"business_registration_number": "123-45-67890",
					},
					"employee": {"employee_name": "김철수", "address": "서울시 송파구 올림픽로 2"},
					"workplace": "본사",
					"job_description": "인사 관리",
					"contract_period": {"start_date": "2026-08-01"},
					"scheduled_work": {"start_time": "09:00", "end_time": "18:00", "work_days": "월~금"},
					"holidays": "매주 일요일",
					"annual_leave": "근로기준법 제60조에 따름",
					"wage_components": [{"component": "기본급", "amount": 2500000}],
					"wage_payment_date": "매월 25일",
					"wage_payment_method": "계좌 입금",
				}
			},
			human_approved=False,
		)
		self.assertTrue(result["result"]["required_fields_complete"])
		self.assertEqual(result["result"]["wage_total"], 2500000)

	def test_weekly_holiday_via_registry(self):
		reg = self._registry()
		result = reg.call(
			"calc_weekly_holiday_allowance",
			{"contracted_weekly_hours": 20, "hourly_rate": 10320},
			human_approved=False,
		)
		self.assertEqual(result["result"]["allowance"], 41280)

	def test_daily_worker_via_registry(self):
		reg = self._registry()
		result = reg.call(
			"calc_daily_worker_payroll",
			{"daily_wage": 160000, "days_worked": 4},
			human_approved=False,
		)
		self.assertEqual(result["result"]["income_tax_total"], 1080.0)

	def test_ordinary_and_unused_leave(self):
		reg = self._registry()
		r1 = reg.call("calc_ordinary_hourly_wage", {"monthly_base_salary": 2156880}, human_approved=False)
		self.assertEqual(r1["result"]["ordinary_hourly_wage"], 10320.0)
		r2 = reg.call("calc_unused_leave_allowance", {"monthly_base_salary": 2156880, "unused_days": 5}, human_approved=False)
		self.assertEqual(r2["result"]["allowance"], 412800.0)

	def test_design_inclusive_wage_via_registry(self):
		reg = self._registry()
		result = reg.call(
			"calc_design_inclusive_wage",
			{"total_monthly": 2500000, "fixed_ot_hours": 20, "minimum_hourly_wage": 10320},
			human_approved=False,
		)
		self.assertEqual(result["result"]["base_pay"], 2186192)
		self.assertEqual(result["result"]["fixed_ot_pay"], 313808)
		self.assertEqual(result["result"]["total"], 2500000)
		self.assertTrue(result["result"]["legal_floor_ok"])

	def test_audit_inclusive_wage_via_registry(self):
		reg = self._registry()
		result = reg.call(
			"calc_audit_inclusive_wage",
			{
				"base_pay": 2156880,
				"fixed_ot_pay": 250000,
				"fixed_ot_hours": 20,
				"minimum_hourly_wage": 10320,
			},
			human_approved=False,
		)
		self.assertEqual(result["result"]["expected_ot_pay"], 309600)
		self.assertEqual(result["result"]["ot_shortfall"], 59600)
		self.assertTrue(any("부족" in w for w in result["result"]["warnings"]))
	def test_check_work_rules_required_items_via_registry(self):
		reg = self._registry()
		result = reg.call(
			"check_work_rules_required_items",
			{"rules_outline": {"11": "직장 내 괴롭힘 예방 교육과 발생 시 조치를 규정한다"}},
			human_approved=False,
		)
		covered_hos = {item["ho"] for item in result["result"]["covered"]}
		self.assertIn("11", covered_hos)

	def test_work_rules_amendment_procedure_via_registry(self):
		reg = self._registry()
		result = reg.call(
			"work_rules_amendment_procedure",
			{"is_disadvantageous": True, "has_majority_union": False},
			human_approved=False,
		)
		self.assertEqual(result["result"]["requirement"], "consent")
		self.assertIn("근로자 과반수", result["result"]["subject"])
	def test_annual_leave_promotion_via_registry(self):
		reg = self._registry()
		result = reg.call(
			"calc_annual_leave_promotion",
			{"hire_date": "2020-01-01", "as_of": "2026-07-05", "is_first_year": False},
			human_approved=False,
		)
		self.assertEqual(result["result"]["expiry_date"], "2027-01-01")
		self.assertEqual(result["result"]["stage"], "1차_촉구_기간")
		self.assertTrue(any("제61조" in c for c in result["result"]["legal_basis"]))
	def test_payslip_breakdown_via_registry(self):
		reg = self._registry()
		result = reg.call(
			"calc_payslip_breakdown",
			{
				"employee": "김철수",
				"period": "2026-07",
				"payment_date": "2026-08-10",
				"wage_type": "monthly",
				"base_salary": 2156880,
			},
			human_approved=False,
		)
		payload = result["result"]
		self.assertEqual(payload["gross_pay"], 2156880)
		self.assertIn("209h", payload["earnings"][0]["basis"])
		self.assertTrue(payload["compliance"]["compliant"])

	def test_knowledge_search_unconfigured_fails_closed(self):
		reg = self._registry()
		result = reg.call("search_labor_knowledge", {"query": "주휴수당 발생 요건"}, human_approved=False)
		self.assertFalse(result["result"]["configured"])
		self.assertEqual(result["result"]["documents"], [])


class TestResolveProviderToolSpecs(unittest.TestCase):
	"""config 경로(hermes)에서 provider 생성 시 tool_specs가 전달되어
	프롬프트 프로토콜 툴콜링이 활성화되어야 한다."""

	def test_resolve_provider_passes_tool_specs(self):
		conf = {
			"korea_agent_harness_provider": "hermes",
			"hermes_gateway_url": "http://127.0.0.1:8130",
			"agent_llm_api_key": "k",
			"agent_llm_provider": "openai",
			"agent_llm_model": "gpt-5.5",
		}
		mod = load_api(fake_frappe=FakeFrappe(conf=conf))
		captured = {}

		class _StubHP:
			HermesProviderError = mod._hermes_provider.HermesProviderError

			@staticmethod
			def make_hermes_provider(**kwargs):
				captured.update(kwargs)
				return lambda messages: {"text": "ok"}

		mod._hermes_provider = _StubHP
		specs = {"get_x": {"description": "d", "args": {}}}
		provider = mod._resolve_provider(tool_specs=specs)
		self.assertIsNotNone(provider)
		self.assertEqual(captured.get("tool_specs"), specs)


class TestSystemPromptInjection(unittest.TestCase):
	"""하네스가 messages[0]에 시스템 프롬프트를 소유·주입하는지(US-1)."""

	def test_system_prompt_is_first_message(self):
		mod = load_api(fake_frappe=None)
		tool_mod = _load_core("tool_registry")
		reg = tool_mod.ToolRegistry()
		reg.register_tool(
			"list_hourly_payroll_proposals",
			lambda **kw: {"proposals": []},
			{"description": "시급 제안 조회"},
			read_only=True,
		)

		captured = {}

		def provider(convo):
			# 최초 호출 시점의 대화를 기록하고 바로 종료(도구 호출 없음).
			captured["messages"] = [dict(m) for m in convo]
			return {"text": "완료"}

		result = mod.run_agent_skill(
			"hourly_closing_prep", provider=provider, tool_registry=reg
		)
		self.assertEqual(result["status"], "completed")

		msgs = captured["messages"]
		self.assertEqual(msgs[0]["role"], "system")
		content = msgs[0]["content"]
		# (a) 스킬명
		self.assertIn("hourly_closing_prep", content)
		# (b) 등록 도구명
		self.assertIn("list_hourly_payroll_proposals", content)
		# (c) 자체 셸/외부 도구 금지 지시
		self.assertIn("tool_registry", content)
		self.assertIn("외부 도구 사용 금지", content)
		# 기존 user 메시지는 시스템 프롬프트 뒤에 온다.
		self.assertEqual(msgs[1]["role"], "user")
		self.assertEqual(msgs[1]["skill"], "hourly_closing_prep")


class TestProviderError(unittest.TestCase):
	"""provider 실행 중 예외 → 표준화된 provider_error(traceback 미노출) (US-2)."""

	def _run_with_raising_provider(self, exc):
		mod = load_api(fake_frappe=None)
		tool_mod = _load_core("tool_registry")
		reg = tool_mod.ToolRegistry()
		reg.register_tool(
			"list_hourly_payroll_proposals",
			lambda **kw: {"proposals": []},
			{},
			read_only=True,
		)

		def provider(convo):
			raise exc

		return mod.run_agent_skill(
			"hourly_closing_prep", provider=provider, tool_registry=reg
		)

	def test_generic_exception_returns_provider_error(self):
		result = self._run_with_raising_provider(RuntimeError("gateway 500 폭발"))
		self.assertEqual(result["status"], "provider_error")
		self.assertEqual(result["skill_name"], "hourly_closing_prep")
		# traceback 미노출 + 300자 이하 요약.
		self.assertNotIn("Traceback", result["error"])
		self.assertLessEqual(len(result["error"]), 300)
		self.assertIn("gateway 500 폭발", result["error"])

	def test_hermes_provider_error_returns_provider_error(self):
		hp = _load_core("hermes_provider")
		result = self._run_with_raising_provider(
			hp.HermesProviderError("gateway 연결 실패")
		)
		self.assertEqual(result["status"], "provider_error")
		self.assertNotIn("Traceback", result["error"])
		self.assertLessEqual(len(result["error"]), 300)

	def test_error_summary_truncated_to_300(self):
		result = self._run_with_raising_provider(RuntimeError("x" * 500))
		self.assertEqual(result["status"], "provider_error")
		self.assertLessEqual(len(result["error"]), 300)


class TestPiiRedactionOnToolResults(unittest.TestCase):
	"""도구 결과가 대화(→LLM)로 들어가기 전 PII가 구조적으로 제거되는지 (보안 P1-④)."""

	def _run_with_leaky_tool(self):
		mod = load_api(fake_frappe=None)
		tool_mod = _load_core("tool_registry")
		reg = tool_mod.ToolRegistry()
		reg.register_tool(
			"leaky_lookup",
			lambda **kw: {
				"employee_name": "김하늘",
				"resident_registration_number": "9001012345617",
				"note": "메모 900101-2345617 포함",
				"gross_pay": 3120400,
			},
			{"description": "PII가 섞인 조회 결과"},
			True,
		)
		calls = {"n": 0}
		captured = {}

		def provider(convo):
			calls["n"] += 1
			if calls["n"] == 1:
				return {"tool_call": {"name": "leaky_lookup", "args": {}}}
			captured["convo"] = [dict(m) if isinstance(m, dict) else m for m in convo]
			return {"text": "done"}

		result = mod.run_agent_skill("hr_freeform_qa", {"question": "x"}, provider=provider, tool_registry=reg)
		return result, captured

	def test_rrn_never_reaches_provider_conversation(self):
		result, captured = self._run_with_leaky_tool()
		self.assertEqual(result["status"], "completed")
		convo_text = str(captured["convo"])
		self.assertNotIn("9001012345617", convo_text)      # 전체 주민번호 원문 금지
		self.assertNotIn("900101-2345617", convo_text)     # 하이픈형 원문 금지
		self.assertIn("김하늘", convo_text)                  # 업무 데이터는 보존
		self.assertIn("3120400", convo_text)

	def test_returned_tool_calls_also_redacted(self):
		result, _ = self._run_with_leaky_tool()
		self.assertNotIn("9001012345617", str(result["tool_calls"]))


if __name__ == "__main__":
	unittest.main()
