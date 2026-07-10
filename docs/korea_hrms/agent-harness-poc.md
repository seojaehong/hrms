# Agent Harness PoC (하네스 엔지니어링 코어)

작성: 2026-07-10. 성격: **PoC** — LLM provider는 주입식(테스트=fake)이라 API 키·네트워크 없이 동작한다.
북극성: [`docs/korea_hrms/hermes-ontology-north-star.md`](hermes-ontology-north-star.md) — 이 PoC는 그 문서의 "Hermes PoC → 백엔드 분리" 수렴 경로의 첫 단계다.

## 무엇인가 (한 줄)
스킬 정의 · 도구 레지스트리 · 프롬프트 빌더 · 에이전트 루프를 **framework-free 모듈**(모듈 상단 `frappe` import 금지)로 조립한, LLM 벤더 독립적 에이전트 하네스 코어. 확정 행위는 사람 승인 게이트(fail-closed), 테넌트 격리·급여 1원 단위 검증을 불변 원칙으로 강제 주입한다.

## ① 아키텍처

코어는 `hrms/regional/south_korea/agent_harness/`에 4개 모듈로 나뉜다. 얇은 사이트 노출은 `agent_harness_api.py`(조건부 frappe)가 담당한다.

```
                       ┌─────────────────────────────────────────────┐
                       │  agent_harness_api.py  (조건부 frappe 래퍼)   │
                       │  run_agent_skill(skill_name, args, provider) │
                       │   · provider 미설정 → not_configured (NW 0회) │
                       │   · 미등록 skill  → unknown_skill            │
                       └───────────────┬─────────────────────────────┘
                                       │  (spec_from_file_location로 코어 동적 로드)
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                               ▼
┌────────────────┐          ┌────────────────────┐          ┌──────────────────┐
│ skill_registry │          │  prompt_builder    │          │   agent_loop     │
│  스킬 정의 검증  │          │  시스템 프롬프트 조립  │          │  provider 주입식  │
│  ·validate     │          │  ①불변 도메인 원칙   │          │  도구 호출 루프    │
│  ·SkillRegistry│──skill──▶│  ②스킬 ③도구스펙     │          │  run_agent_loop  │
│   register/get │          │  ④테넌트(가변·마지막)  │          │  (provider 자율)  │
└────────────────┘          └─────────┬──────────┘          └────────┬─────────┘
        ▲                             │ tool_specs                   │ tool_registry.call
        │ builtin_skills              ▼                              ▼
┌────────────────┐          ┌────────────────────────────────────────────────┐
│ builtin_skills │          │           tool_registry.py                     │
│ 2종 스킬 정의    │─tools───▶│  ToolRegistry: 화이트리스트 바인딩              │
│ hourly_closing │          │   · 미등록 도구 호출 → ToolError (fn 미호출)     │
│ insurance_recon│          │   · read_only=False + human_approved≠True →     │
└────────────────┘          │       blocked (fail-closed, fn 미호출)          │
                            │   · get_call_log() 구조화 호출 로그              │
                            └────────────────────────────────────────────────┘
```

관계 요약:
- **skill_registry** — 스킬 정의 dict(`name`/`description`/`steps`/`requires_approval`/`output_summary_template`)를 검증·등록·조회. `steps[i]["tool"]` 이름이 tool_registry에 등록된 도구명과 매칭되는 계약.
- **tool_registry** — 이름→callable+스펙+`read_only` 바인딩. 화이트리스트 밖 호출은 `ToolError`, 비승인 write는 `blocked`(둘 다 `fn` 미호출). 모든 호출은 `get_call_log()`에 구조화 누적.
- **prompt_builder** — `build_system_prompt(skill_defn, tool_specs, tenant_context)`. 불변부(원칙·스킬·도구스펙)를 앞, 가변부(테넌트)를 마지막에 두어 prefix 캐싱 극대화. 원칙은 모듈 상수(`IMMUTABLE_DOMAIN_PRINCIPLES`)라 호출자가 덮어쓸 수 없다.
- **agent_loop** — `run_agent_loop(provider, messages, tool_registry, max_steps)`. provider 응답이 `{"text":...}`면 종료, `{"tool_call":{...}}`면 tool_registry로 실행 후 대화에 결과 추가하고 계속. `max_steps` 도달 시 무한루프 없이 `max_steps_exceeded`.
- **builtin_skills** — 실무 스킬 2종(`hourly_closing_prep`, `insurance_reconcile`)을 순수 dict로 정의. `register_builtin_skills(registry)`로 등록.
- **agent_harness_api** — `insurance_filing_api.py` 컨벤션(조건부 frappe import + `_whitelist` no-op + `_load_core` 동적 로드). provider 미설정이면 네트워크 0회로 `not_configured` 반환.

## ② north-star와의 관계 (무엇을 유지, 무엇을 교체)

Hermes 런타임 내재화 단계에서 **이 인터페이스(계약)는 유지**하고 **내부 구현만 교체**한다.

| 계층 | PoC 구현 | Hermes 내재화 시 | 유지/교체 |
|------|----------|------------------|-----------|
| 스킬 스키마 | dict + `validate_skill_definition` | 동일 스키마 유지 | **유지** (계약) |
| 도구 레지스트리 | `ToolRegistry` 화이트리스트 + 승인 게이트 | 동일 계약, 백엔드만 Hermes 도구 배선 | **유지** (계약) |
| 프롬프트 조립 계약 | `build_system_prompt` 4섹션·캐시 친화 | Hermes `prompt_builder.py`를 하네스로 수정, 4섹션·불변 원칙 유지 | **유지** (계약) |
| provider | 주입식 callable(fake) | Hermes `run_agent.AIAgent` 실제 LLM 클라이언트 배선 | **교체** (내부) |
| 루프 구현 | `run_agent_loop`(단순 while) | Hermes 세션(FTS5)·컨텍스트 압축·Cron 내장 루프 | **교체** (내부) |
| 불변 원칙 | 1원 단위·승인 게이트·테넌트 격리 | 동일 원칙 강제 주입(하네스 엔지니어링) | **유지** (원칙) |

즉 스킬 정의 스키마·도구 레지스트리·프롬프트 조립 계약은 안정 API로 남고, provider·루프 구현부는 Hermes 런타임으로 갈아끼운다. 확정 행위=사람 승인 게이트(fail-closed)와 테넌트 데이터 격리는 어느 구현에서도 불변이다.

## ③ 사용 예 (스킬 등록 → fake provider로 실행)

```python
import importlib.util, pathlib

BASE = pathlib.Path("hrms/regional/south_korea/agent_harness")

def _load(name):
	spec = importlib.util.spec_from_file_location(name, BASE / f"{name}.py")
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod

skill_registry = _load("skill_registry")
tool_registry = _load("tool_registry")
builtin_skills = _load("builtin_skills")
agent_loop = _load("agent_loop")

# 1) 빌트인 스킬 등록
skills = skill_registry.SkillRegistry()
builtin_skills.register_builtin_skills(skills)   # hourly_closing_prep / insurance_reconcile

# 2) 도구 레지스트리에 (fake) 도구 바인딩 — 조회 도구는 read_only=True
tools = tool_registry.ToolRegistry()
tools.register_tool(
	"list_hourly_payroll_proposals",
	lambda **kw: {"proposals": [{"emp": "A"}, {"emp": "B"}]},   # 제안 2명
	spec={"desc": "시급 마감 제안 조회"},
	read_only=True,
)

# 3) fake provider — 스킬 순서대로 도구 호출 후 최종 요약 (실제 LLM 없음)
def fake_provider(messages):
	called = any(m.get("role") == "tool" for m in messages)
	if not called:
		return {"tool_call": {"name": "list_hourly_payroll_proposals", "args": {}}}
	# 대화에 실린 도구 결과에서 수치 추출 (tool_registry 반환은 한 겹 언랩: result["result"])
	for m in messages:
		if m.get("role") == "tool":
			n = len(m["result"]["result"]["proposals"])
			return {"text": f"시급 마감 준비: 제안 {n}명 검토 완료."}
	return {"text": "제안 없음."}

# 4) 에이전트 루프 실행
result = agent_loop.run_agent_loop(fake_provider, [], tools, max_steps=8)
print(result["status"], "|", result["final_text"])
# → completed | 시급 마감 준비: 제안 2명 검토 완료.
```

사이트(Frappe)에서는 얇은 래퍼를 통해 노출하되, provider 미설정이면 네트워크 0회로 거부한다:

```python
from hrms.regional.south_korea.agent_harness_api import run_agent_skill
run_agent_skill("hourly_closing_prep", {})   # provider 미설정 → {"status": "not_configured", ...}
```

## ④ 테스트 실행법

품질검사 = 각 테스트 파일을 `python3`로 직접 실행(별도 러너 없음). 코어는 `spec_from_file_location`으로 직접 로드하므로 frappe 불필요.

```bash
python3 hrms/tests/test_korea_agent_harness_skill_registry.py   # 17 tests
python3 hrms/tests/test_korea_agent_harness_tool_registry.py    # 13 tests
python3 hrms/tests/test_korea_agent_harness_prompt_builder.py   #  8 tests
python3 hrms/tests/test_korea_agent_harness_agent_loop.py       # 10 tests
python3 hrms/tests/test_korea_agent_harness_builtin_skills.py   # 10 tests
python3 hrms/tests/test_korea_agent_harness_api.py              #  7 tests
```

전 6개 파일 `OK`(총 65 테스트) 확인 시 하네스 PoC 그린. `agent_harness_api.py` 테스트는 `FakeFrappe(conf={})` 스텁을 `sys.modules`에 주입해 `not_configured`·`unknown_skill` 경로를 네트워크 0회로 검증한다.
