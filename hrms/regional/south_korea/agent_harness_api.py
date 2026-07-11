# -*- coding: utf-8 -*-
"""Frappe 연동 API — Agent Harness 스킬 실행 엔드포인트 (whitelist 래퍼).

이 모듈은 Frappe RPC 레이어에 노출되는 함수를 정의한다.
내부 로직(스킬 등록·도구 실행·에이전트 루프)은 agent_harness/ 코어에 위임한다.

테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import한다 (insurance_filing_api.py 컨벤션).

안전 불변식:
  - LLM provider 미설정이면 어떤 LLM/네트워크 호출도 하지 않고 즉시 not_configured
    반환 (fail-closed). provider 해석은 config 읽기만 하며 클라이언트를 만들지 않는다.
  - 미등록 skill_name은 명시적 오류 status(unknown_skill)로 거부한다(조용한 통과 금지).
  - 확정 행위(requires_approval) 도구는 코어 tool_registry가 human_approved 게이트로 차단.
"""

from __future__ import annotations

import importlib.util as _ilu
import pathlib as _pl
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Frappe 조건부 import — framework-free 테스트 환경에서 안전하게 로드
# ---------------------------------------------------------------------------
try:
	import frappe as _frappe  # noqa: PLC0415

	_FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
	_frappe = None  # type: ignore[assignment]
	_FRAPPE_AVAILABLE = False


def _whitelist(fn):
	"""@frappe.whitelist() 데코레이터 — Frappe 없으면 no-op."""
	if _FRAPPE_AVAILABLE and _frappe is not None:
		return _frappe.whitelist()(fn)
	return fn


# ---------------------------------------------------------------------------
# agent_harness 코어 동적 로드 (importlib으로 frappe 패키지 경로 우회)
# 코어는 agent_harness/ 하위 디렉터리에 있다(래퍼 자신의 디렉터리가 아님).
# ---------------------------------------------------------------------------
_CORE_DIR = _pl.Path(__file__).resolve().parent / "agent_harness"


def _load_core(name: str):
	path = _CORE_DIR / f"{name}.py"
	spec = _ilu.spec_from_file_location(f"_korea_agent_harness_{name}_core", path)
	module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
	spec.loader.exec_module(module)  # type: ignore[union-attr]
	return module


_skill_registry = _load_core("skill_registry")
_builtin_skills = _load_core("builtin_skills")
_agent_loop = _load_core("agent_loop")
_tool_registry_mod = _load_core("tool_registry")
_llm_credentials = _load_core("llm_credentials")
_hermes_provider = _load_core("hermes_provider")
_prompt_builder = _load_core("prompt_builder")
_pii_filter = _load_core("pii_filter")


class _RedactingRegistry:
	"""tool_registry 프록시 — 도구 결과가 대화(→LLM)로 나가기 전 PII를 구조적으로 제거.

	보안플랜 P1-④: 지시문이 아니라 코드로 차단. call() 반환(agent_loop이 대화와
	tool_calls에 그대로 싣는 구조화 dict)을 redact_sensitive로 통과시킨다.
	나머지 메서드는 위임.
	"""

	def __init__(self, inner: Any):
		self._inner = inner

	def call(self, name: str, args: dict | None = None, *, human_approved: bool = False) -> dict:
		result = self._inner.call(name, args, human_approved=human_approved)
		return _pii_filter.redact_sensitive(result)

	def __getattr__(self, attr: str) -> Any:
		return getattr(self._inner, attr)

# site config 키 — 이 키가 있어야 provider가 설정된 것으로 본다(값 읽기만, 네트워크 없음).
PROVIDER_CONFIG_KEY = "korea_agent_harness_provider"
# hermes provider일 때 gateway 주소 (예: http://172.17.0.1:8130 — 컨테이너→호스트)
HERMES_GATEWAY_URL_KEY = "hermes_gateway_url"


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


@_whitelist
def run_agent_skill(
	skill_name: str,
	args: dict | None = None,
	human_approved: bool | str = False,
	provider: Callable[[list], dict] | None = None,
	tool_registry: Any | None = None,
	max_steps: int = 8,
) -> dict[str, Any]:
	"""빌트인 스킬을 에이전트 루프로 실행한다(프로바이더 주입식).

	Args:
		skill_name: 실행할 빌트인 스킬 이름(hourly_closing_prep / insurance_reconcile).
		args: 스킬/도구에 전달할 인자(선택).
		human_approved: 확정 행위 도구 승인 여부(코어 tool_registry 게이트로 전파).
		provider: callable(messages)->dict. 미지정 시 site config에서 해석.
		tool_registry: 도구 레지스트리(주입식). provider가 있을 때만 사용.
		max_steps: 에이전트 루프 상한.

	Returns:
		- 미등록 스킬: {'status': 'unknown_skill', 'available': [...]} (LLM 호출 없음).
		- provider 미설정: {'status': 'not_configured', ...} (LLM/네트워크 0회).
		- 실행: {'status': 'completed'|'max_steps_exceeded', 'final_text': ..., ...}.
	"""
	args = dict(args or {})

	# --- 1) 스킬 존재 검증 (순수 in-memory 조회 — 네트워크 없음) ---
	registry = _skill_registry.SkillRegistry()
	_builtin_skills.register_builtin_skills(registry)
	if not registry.has(skill_name):
		return {
			"status": "unknown_skill",
			"skill_name": skill_name,
			"available": registry.list_skills(),
			"reason": f"미등록 스킬: '{skill_name}' (빌트인 스킬만 실행 가능).",
		}

	# --- 2) provider 설정 게이트 (config 읽기만 — 네트워크 0회, fail-closed 유지) ---
	if provider is None and not _provider_configured():
		return {
			"status": "not_configured",
			"skill_name": skill_name,
			"reason": (
				f"LLM provider 미설정 — site config '{PROVIDER_CONFIG_KEY}' 없이는 "
				"스킬을 실행하지 않습니다 (네트워크 호출 0회)."
			),
			"requires_provider_config": True,
		}

	# --- 3) 도구 바인딩 (provider 생성보다 먼저 — config 경로 provider가 도구 스펙으로
	#        프롬프트 프로토콜 툴콜링을 켜려면 스펙이 필요하다) ---
	if tool_registry is None:
		tool_registry = _build_default_tool_registry()  # 빌트인 조회 도구 바인딩
	if tool_registry is None:
		return {
			"status": "no_tools",
			"skill_name": skill_name,
			"reason": "tool_registry 미주입 — 도구 바인딩 없이는 스킬을 실행하지 않습니다.",
		}

	# --- 3-1) provider 생성 (설정 게이트 통과분만 — 생성 실패 시 fail-closed) ---
	if provider is None:
		specs_for_provider = {
			name: tool_registry.get_spec(name) for name in tool_registry.list_tools()
		}
		provider = _resolve_provider(tool_specs=specs_for_provider)
	if provider is None:
		return {
			"status": "not_configured",
			"skill_name": skill_name,
			"reason": "provider 생성 실패 — 자격증명/게이트웨이 설정을 확인하세요.",
			"requires_provider_config": True,
		}

	# PII 방어선: 도구 결과가 대화(→LLM)로 나가기 전 구조적으로 리댁션 (P1-④)
	tool_registry = _RedactingRegistry(tool_registry)

	skill = registry.get(skill_name)
	# 하네스가 시스템 프롬프트를 소유한다 — provider(Hermes 등)가 자체 셸 도구로
	# 이탈하지 못하도록 불변 원칙·스킬·등록 도구 스펙을 조립해 messages[0]에 주입한다.
	tool_specs = {
		name: tool_registry.get_spec(name) for name in tool_registry.list_tools()
	}
	system_prompt = _prompt_builder.build_system_prompt(skill, tool_specs, {})
	messages = [
		{"role": "system", "content": system_prompt},
		{"role": "user", "skill": skill_name, "args": args},
	]
	try:
		loop_result = _agent_loop.run_agent_loop(
			provider, messages, tool_registry, max_steps=max_steps
		)
	except Exception as exc:  # provider/네트워크/기타 실행 실패 표준화
		# 원문 traceback은 frappe.log_error로만 시도(실패·부재해도 무시).
		# 응답에는 절대 traceback을 노출하지 않는다 — 클래스명+메시지 요약(300자).
		_log_error_best_effort(exc, skill_name)
		summary = f"{type(exc).__name__}: {exc}"
		return {
			"status": "provider_error",
			"skill_name": skill_name,
			"error": summary[:300],
		}
	return {
		"status": loop_result["status"],
		"skill_name": skill_name,
		"final_text": loop_result["final_text"],
		"steps": loop_result["steps"],
		"tool_calls": loop_result["tool_calls"],
	}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _log_error_best_effort(exc: BaseException, skill_name: str) -> None:
	"""원문 traceback을 frappe.log_error로만 기록 시도한다(best-effort).

	frappe가 없거나 log_error 자체가 실패해도 조용히 무시한다 — 응답 경로에는
	절대 영향을 주지 않는다(traceback은 클라이언트에 노출하지 않는다).
	"""
	if not (_FRAPPE_AVAILABLE and _frappe is not None):
		return
	try:
		import traceback as _tb  # noqa: PLC0415

		_frappe.log_error(
			message=_tb.format_exc(),
			title=f"run_agent_skill provider_error: {skill_name}",
		)
	except Exception:  # 로깅 실패는 무시(응답 불변)
		pass


def _provider_configured() -> bool:
	"""provider 설정 존재 여부만 판정 (client 생성·네트워크 없음 — fail-closed 게이트용)."""
	if not (_FRAPPE_AVAILABLE and _frappe is not None):
		return False
	conf = getattr(_frappe, "conf", None)
	if not conf:
		return False
	if str(conf.get(PROVIDER_CONFIG_KEY) or "").strip().lower() != "hermes":
		return False
	return bool(str(conf.get(HERMES_GATEWAY_URL_KEY) or "").strip())


def _resolve_provider(tool_specs: dict | None = None) -> Callable[[list], dict] | None:
	"""site config에서 provider를 해석한다.

	- `korea_agent_harness_provider` == "hermes":
	  llm_credentials(BYOK→플랫폼) + `hermes_gateway_url`로 HermesProvider 생성.
	  provider 객체 생성은 네트워크 0회 — 실제 호출은 스킬 실행 시.
	- 그 외 값/미설정/자격증명 불충분 → None (호출부가 not_configured fail-closed).
	"""
	if not (_FRAPPE_AVAILABLE and _frappe is not None):
		return None
	conf = getattr(_frappe, "conf", None)
	if not conf:
		return None
	provider_name = str(conf.get(PROVIDER_CONFIG_KEY) or "").strip().lower()
	if provider_name != "hermes":
		return None
	base_url = str(conf.get(HERMES_GATEWAY_URL_KEY) or "").strip()
	if not base_url:
		return None
	import os as _os  # noqa: PLC0415

	creds = _llm_credentials.resolve_llm_credentials(conf, _os.environ)
	if creds.get("status") != "ok":
		return None
	try:
		return _hermes_provider.make_hermes_provider(
			base_url=base_url, credentials=creds, tool_specs=tool_specs
		)
	except _hermes_provider.HermesProviderError:
		return None


def _register_calc_tools(registry) -> None:
	"""framework-free 계산·지식검색 도구 등록 — frappe 불필요, 전부 read_only.

	계산 도구는 statutory 2026 정렬 엔진(daily_worker/hourly_wage)을 그대로 노출하고,
	지식검색은 v2 시맨틱 retriever(env 게이트 — 미설정 시 fail-closed 빈 결과)를 쓴다.
	"""
	import importlib.util as _ilu
	import pathlib as _pl

	base = _pl.Path(__file__).resolve().parent

	def _load(name):
		spec = _ilu.spec_from_file_location(f"korea_calc_{name}", base / f"{name}.py")
		mod = _ilu.module_from_spec(spec)
		spec.loader.exec_module(mod)
		return mod

	hourly = _load("hourly_wage")
	daily = _load("daily_worker")
	contract_doc = _load("employment_contract_doc")
	inclusive = _load("inclusive_wage")
	wr = _load("work_rules")
	promotion = _load("annual_leave_promotion")
	breakdown = _load("payslip_breakdown")
	severance_settlement = _load("severance_settlement")

	def calc_weekly_holiday_allowance(*, contracted_weekly_hours, hourly_rate, perfect_attendance=True):
		allowance = hourly.weekly_holiday_allowance(
			contracted_weekly_hours=contracted_weekly_hours,
			hourly_rate=hourly_rate,
			perfect_attendance=bool(perfect_attendance),
		)
		return {"allowance": allowance, "legal_basis": hourly.legal_basis_base()}

	def calc_daily_worker_payroll(*, daily_wage, days_worked, additional_wages=0, employment_period_months=0):
		return daily.calculate_daily_worker_payroll(
			daily_wage=float(daily_wage),
			days_worked=int(days_worked),
			additional_wages=float(additional_wages),
			employment_period_months=int(employment_period_months),
		)

	def calc_ordinary_hourly_wage(*, monthly_base_salary):
		return {"ordinary_hourly_wage": float(hourly.ordinary_hourly_wage(monthly_base_salary))}

	def calc_unused_leave_allowance(*, monthly_base_salary, unused_days):
		return {"allowance": float(hourly.unused_leave_allowance(monthly_base_salary, unused_days))}

	def build_employment_contract(*, data):
		return contract_doc.build_employment_contract(data)
	def calc_design_inclusive_wage(
		*, total_monthly, fixed_ot_hours, fixed_night_hours=0, fixed_holiday_hours=0, minimum_hourly_wage
	):
		r = inclusive.design_inclusive_wage(
			total_monthly,
			fixed_ot_hours,
			fixed_night_hours=fixed_night_hours,
			fixed_holiday_hours=fixed_holiday_hours,
			minimum_hourly_wage=minimum_hourly_wage,
		)
		return {
			"ordinary_hourly_wage": float(r["ordinary_hourly_wage"]),
			"base_pay": r["base_pay"],
			"fixed_ot_pay": r["fixed_ot_pay"],
			"night_pay": r["night_pay"],
			"holiday_pay": r["holiday_pay"],
			"total": r["total"],
			"legal_floor_ok": r["legal_floor_ok"],
			"warnings": r["warnings"],
		}

	def calc_audit_inclusive_wage(
		*,
		base_pay,
		fixed_ot_pay=0,
		fixed_ot_hours=0,
		fixed_night_pay=0,
		fixed_night_hours=0,
		fixed_holiday_pay=0,
		fixed_holiday_hours=0,
		minimum_hourly_wage,
	):
		r = inclusive.audit_inclusive_wage(
			base_pay=base_pay,
			fixed_ot_pay=fixed_ot_pay,
			fixed_ot_hours=fixed_ot_hours,
			fixed_night_pay=fixed_night_pay,
			fixed_night_hours=fixed_night_hours,
			fixed_holiday_pay=fixed_holiday_pay,
			fixed_holiday_hours=fixed_holiday_hours,
			minimum_hourly_wage=minimum_hourly_wage,
		)
		return {
			"ordinary_hourly_wage": float(r["ordinary_hourly_wage"]),
			"expected_ot_pay": r["expected_ot_pay"],
			"expected_night_pay": r["expected_night_pay"],
			"expected_holiday_pay": r["expected_holiday_pay"],
			"ot_shortfall": r["ot_shortfall"],
			"night_shortfall": r["night_shortfall"],
			"holiday_shortfall": r["holiday_shortfall"],
			"legal_floor_ok": r["legal_floor_ok"],
			"overtime_limit_ok": r["overtime_limit_ok"],
			"warnings": r["warnings"],
		}
	def check_work_rules_required_items(*, rules_outline):
		return wr.check_required_items(rules_outline)

	def work_rules_amendment_procedure(*, is_disadvantageous, has_majority_union=None):
		return wr.amendment_procedure(
			bool(is_disadvantageous),
			has_majority_union=None if has_majority_union is None else bool(has_majority_union),
		)
	def calc_annual_leave_promotion(*, hire_date, as_of, is_first_year=False):
		import datetime as _dt

		def _to_date(value):
			if isinstance(value, _dt.date):
				return value
			return _dt.date.fromisoformat(str(value))

		result = promotion.promotion_schedule(
			_to_date(hire_date), _to_date(as_of), is_first_year=bool(is_first_year)
		)
		return {
			key: (value.isoformat() if isinstance(value, _dt.date) else value)
			for key, value in result.items()
		}
	def calc_payslip_breakdown(**kwargs):
		return breakdown.build_payslip_breakdown(**kwargs)
	def calc_severance_settlement(*, severance_pay, service_years):
		return severance_settlement.calculate_severance_income_tax(
			severance_pay=severance_pay, service_years=service_years,
		)

	def search_labor_knowledge(*, query, top_k=5):
		try:
			sc = _load("semantic_config")
			retriever = sc.build_semantic_retriever_from_env()
		except Exception:
			retriever = None
		if retriever is None:
			return {"configured": False, "documents": [],
				"note": "시맨틱 검색 미설정(env) — 근거 검색 없이 답하지 말고 미설정임을 알릴 것"}
		docs = retriever(str(query))[: int(top_k)]
		return {"configured": True, "documents": docs}

	registry.register_tool(
		"calc_weekly_holiday_allowance", calc_weekly_holiday_allowance,
		{"description": "1주 주휴수당 계산 (주 15h+개근 요건, min(주소정,40)/40x8 x 시급)",
		 "args": {"contracted_weekly_hours": "필수", "hourly_rate": "필수(원)", "perfect_attendance": "선택(기본 true)"}},
		True,
	)
	registry.register_tool(
		"calc_daily_worker_payroll", calc_daily_worker_payroll,
		{"description": "일용직 급여·원천징수 계산 (소액부징수 지급합산·납부 10원 절사·고용보험 0.9% — 국세청 정렬)",
		 "args": {"daily_wage": "필수(원)", "days_worked": "필수", "additional_wages": "선택(비과세)", "employment_period_months": "선택"}},
		True,
	)
	registry.register_tool(
		"calc_ordinary_hourly_wage", calc_ordinary_hourly_wage,
		{"description": "통상시급 = 기본급 / 209 (포괄임금 실무)", "args": {"monthly_base_salary": "필수(원)"}},
		True,
	)
	registry.register_tool(
		"calc_unused_leave_allowance", calc_unused_leave_allowance,
		{"description": "미사용 연차수당 = 기본급/209 x 8 x 미사용일수", "args": {"monthly_base_salary": "필수(원)", "unused_days": "필수"}},
		True,
	)
	registry.register_tool(
		"build_employment_contract", build_employment_contract,
		{"description": "근로계약서 데이터 빌더 (근기법 §17 필수기재 누락 검출, raise 아님 — missing[] 반환)",
		 "args": {"data": "필수(dict) — company/employee/workplace/job_description/contract_period/"
					"scheduled_work/holidays/annual_leave/wage_components/wage_payment_date/wage_payment_method"}},
		True,
	)
	registry.register_tool(
		"calc_design_inclusive_wage", calc_design_inclusive_wage,
		{"description": "포괄임금 설계: 총액→통상시급 기준 기본급/고정연장/고정야간/고정휴일수당 분해"
			" (t=total/(209+1.5xH_ot+0.5xH_night+1.5xH_hol), 근로기준법 §56)",
		 "args": {"total_monthly": "필수(원)", "fixed_ot_hours": "필수", "fixed_night_hours": "선택(기본 0)",
			"fixed_holiday_hours": "선택(기본 0)", "minimum_hourly_wage": "필수(원, 하드코딩 금지 — ontology 조회값 주입)"}},
		True,
	)
	registry.register_tool(
		"calc_audit_inclusive_wage", calc_audit_inclusive_wage,
		{"description": "포괄임금 역산 감사: 기존 계약(기본급+고정수당 기재액)의 적정 최소지급액 대비"
			" 부족분·최저임금 미달·주12h 한도 초과 검출 (경고 반환, raise 아님)",
		 "args": {"base_pay": "필수(원)", "fixed_ot_pay": "선택(기본 0)", "fixed_ot_hours": "선택(기본 0)",
			"fixed_night_pay": "선택(기본 0)", "fixed_night_hours": "선택(기본 0)",
			"fixed_holiday_pay": "선택(기본 0)", "fixed_holiday_hours": "선택(기본 0)",
			"minimum_hourly_wage": "필수(원, 하드코딩 금지 — ontology 조회값 주입)"}},
		True,
	)
	registry.register_tool(
		"check_work_rules_required_items", check_work_rules_required_items,
		{"description": "취업규칙 개요가 근기법 §93 필수기재 14호를 커버하는지 키워드 candidate 판정(확정 아님)",
		 "args": {"rules_outline": "필수 — {호:텍스트} dict 또는 텍스트 list"}},
		True,
	)
	registry.register_tool(
		"work_rules_amendment_procedure", work_rules_amendment_procedure,
		{"description": "취업규칙 작성·변경 절차 판정 (근기법 §94 — 의견청취 vs 동의, 신고 첨부·게시 단계)",
		 "args": {"is_disadvantageous": "필수(불이익변경 여부, 판정은 호출측 책임)",
			  "has_majority_union": "선택(과반수 노조 유무, 미상이면 생략)"}},
		True,
	)
	registry.register_tool(
		"calc_annual_leave_promotion", calc_annual_leave_promotion,
		{"description": "근기법 §61 연차 사용촉진 기한표 + 현재 단계 판정 (1년미만 특칙 포함)",
		 "args": {"hire_date": "필수(YYYY-MM-DD)", "as_of": "필수(YYYY-MM-DD)", "is_first_year": "선택(기본 false)"}},
		True,
	)
	registry.register_tool(
		"calc_payslip_breakdown", calc_payslip_breakdown,
		{"description": "임금명세서 산정내역 분해(§48②) — 구성항목별 계산방법 문자열 + 공제내역 + 실지급액",
		 "args": {"employee": "필수", "period": "필수(YYYY-MM)", "payment_date": "필수(YYYY-MM-DD)",
			  "wage_type": "필수('monthly'|'hourly')", "base_salary": "monthly 필수(원)",
			  "hourly_rate": "hourly 필수(원)", "contracted_weekly_hours": "hourly 필수",
			  "regular_hours": "선택", "overtime_hours": "선택", "night_hours": "선택",
			  "holiday_work_hours": "선택", "annual_leave_hours": "선택"}},
		True,
	)
	registry.register_tool(
		"search_labor_knowledge", search_labor_knowledge,
		{"description": "노동법 지식 시맨틱 검색 (행정해석·판례·판정례·상담FAQ·최영우) — 답변 근거 인용용",
		 "args": {"query": "필수(자연어)", "top_k": "선택(기본 5)"}},
		True,
	)
	registry.register_tool(
		"calc_severance_settlement", calc_severance_settlement,
		{"description": "퇴직소득세 계산 (소득세법 §48 근속연수공제·환산급여공제 + §55② 산출세액, 10원 절사)",
		 "args": {"severance_pay": "필수(원, 퇴직소득금액)", "service_years": "필수(근속연수, 1년 미만 잔여는 올림)"}},
		True,
	)


def _build_default_tool_registry():
	"""빌트인 스킬용 기본 도구 바인딩 — 전부 조회·계산 전용(read_only=True).

	frappe 환경에서만 유효(각 도구가 사이트 조회를 씀). 확정 행위 도구는
	여기 없다 — 추가하려면 read_only=False로 등록해 승인 게이트를 태울 것.
	"""
	if not (_FRAPPE_AVAILABLE and _frappe is not None):
		return None
	from hrms.regional.south_korea import hourly_wage_api as _hw  # noqa: PLC0415
	from hrms.regional.south_korea import insurance_reconciliation_api as _ir  # noqa: PLC0415

	registry = _tool_registry_mod.ToolRegistry()
	registry.register_tool(
		"list_hourly_payroll_proposals",
		_hw.list_hourly_payroll_proposals,
		{
			"description": "기간의 시급제 직원 전원 gross 계산 제안 (계산 전용)",
			"args": {"period": "YYYY-MM (필수)", "company": "선택", "minimum_wage": "선택(원)"},
		},
		True,  # read_only
	)
	registry.register_tool(
		"reconcile_period_contributions",
		_ir.reconcile_period_contributions,
		{
			"description": "해당 월 제출 슬립 4대보험 공제 vs 공단 고지 대사 (계산 전용)",
			"args": {"year": "필수", "month": "필수", "notified": "고지 표준행 리스트(필수)", "company": "선택", "tolerance": "선택(원)"},
		},
		True,  # read_only
	)
	_register_calc_tools(registry)  # framework-free 계산·지식검색 도구 동봉
	return registry
