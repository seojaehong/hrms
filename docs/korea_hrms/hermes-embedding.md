# Hermes Agent 임베딩 — 소스 안착 + BYOK 키 라우팅 (2026-07-10)

목표(사용자 확정): **Hermes(MIT) 소스를 그대로 우리 인프라 폴더에 꽂고**, 에이전트가
**각 테넌트의 OAuth/API 키(BYOK)** 또는 **플랫폼 키(운영자 지불)** 로 LLM을 호출하게 한다.
north-star(`hermes-ontology-north-star.md`)의 "Hermes PoC" 단계 실행이다.

## 1. 소스 안착 (완료)
- 위치: **claudebot-2 `~/workspaces/hermes-agent`** (docker 마운트 워크스페이스와 동급의 인프라 폴더)
- 핀: `vendor/HERMES_PIN` 참조 (`caf557be5b4c9ae75b3a7566d65d3df2c701c5df`, NousResearch/Hermes-Agent, MIT © 2025 Nous Research)
- hrms 레포(public 포크)에 212MB 소스를 직접 커밋하지 않는 이유: 레포 비대화 + upstream PR 오염.
  레포에는 핀·어댑터·키라우팅만 커밋 — 갱신 시 서버에서 `git fetch` 후 핀 파일 갱신.

## 2. 키 라우팅 (완료 — `agent_harness/llm_credentials.py`)
우선순위: **테넌트 BYOK → 플랫폼 폴백 → not_configured(fail-closed)**

| billing | 소스 | 비용 부담 |
|---|---|---|
| `byok` | 테넌트 site_config `agent_llm_api_key` (+`agent_llm_provider`/`agent_llm_model`) | 테넌트 |
| `platform` | 서버 env `PLATFORM_LLM_API_KEY` (+`PLATFORM_LLM_PROVIDER`/`PLATFORM_LLM_MODEL`) | 운영자 |

- provider 명칭은 Hermes cli-config와 호환(anthropic/openrouter/openai/gemini …) — Hermes가
  멀티 프로바이더·OAuth(`hermes auth`)를 네이티브 지원하므로 그대로 전달.
- 외부 응답에는 `public_status()`만 사용 — **키 원문 비노출**(api_key_present bool).

## 3. 실행 토폴로지 (다음 단계)
```
PWA/채널 → agent_harness_api.run_agent_skill (승인게이트·도구 화이트리스트)
              │  provider = HermesProvider(테넌트 자격증명)
              ▼
     Hermes gateway api_server (호스트 systemd, ~/workspaces/hermes-agent)
              │  per-request api_key/provider/model 주입
              ▼
        LLM (테넌트 키 or 플랫폼 키)
```
- 우리 하네스가 프롬프트(도메인 원칙·스킬·도구스펙)와 승인 게이트를 소유하고,
  Hermes는 루프·세션·프로바이더 어댑터를 담당 — north-star의 "인터페이스 유지, 내부 교체".

## 4. 남은 단계
1. 서버 venv 설치: `cd ~/workspaces/hermes-agent && python3 -m venv .venv && .venv/bin/pip install -e .`
   (host Python 3.10 — pyproject 요구버전 확인 필요, 미달 시 pyenv/uv)
2. `HermesProvider` 어댑터 — agent_loop의 provider 인터페이스(callable(messages)->dict)를
   Hermes gateway API 호출로 구현, llm_credentials로 키 해석
3. gateway systemd 서비스(korea-hrms-mcp 패턴) + 테넌트별 요청 스코프 키 주입
4. 스모크: 빌트인 스킬(hourly_closing_prep)을 실 LLM로 1회 실행 → 요약 품질 확인

## 사용자 투입 (USER_INPUT_HANDOFF 연동)
- 플랫폼 과금 모드: `PLATFORM_LLM_API_KEY`(Anthropic 권장) 서버 env 1개면 전 테넌트 가동
- 테넌트 BYOK 모드: 해당 사이트 `bench set-config agent_llm_api_key "..."`

## §보안 발견 (2026-07 실동)

**확인된 사실**
- 2026-07 실동에서 gateway의 Hermes 에이전트가 **우리 `tool_registry`를 거치지 않고
  자체 셸 도구(ubuntu 권한)로 직접 작업**했다.
- 그 과정에서 **3개 사이트 접근 흔적**이 확인되었다.
- 즉, 현재 상태로는 하네스가 소유한 승인 게이트·도구 화이트리스트를 우회할 수 있다.

**리스크**
- 테넌트에게 노출하기 전에 Hermes 자체 도구를 잠그지 않으면, 에이전트가
  테넌트 격리 경계를 넘어 다른 사이트 데이터/파일시스템에 접근할 수 있다.

**대응 계획 (3중 방어)**
1. **하네스 시스템 프롬프트 금지 지시** — 구현됨(US-1). `agent_harness/prompt_builder.py`의
   `IMMUTABLE_DOMAIN_PRINCIPLES`에 "도구는 제공된 `tool_registry` 경유로만 사용, 자체
   셸·파일시스템·브라우저 등 외부 도구 사용 금지" 원칙을 모듈 상수로 추가(호출자 덮어쓰기 불가).
   — 프롬프트 지시는 소프트 방어이며, 아래 (2)(3)의 하드 잠금이 필수.
2. **gateway 설정 잠금** — `scripts/hermes/gateway-config.template.yaml`(신설). 확인된
   `model.default`만 값으로 담고, 도구 잠금 키는 값 추측 없이 `TODO`로 표기.
3. **서버 조사 TODO** — claudebot-2 `~/workspaces/hermes-agent`의 `toolsets.py` /
   `cli-config.yaml.example`을 조사해 셸/파일/브라우저 툴셋 키와 비활성화 설정을 확정해야
   (2)의 `TODO`를 채울 수 있다.

**✅ 확정·라이브 적용 완료 (2026-07-10 서버 조사)**
- 잠금 키: `platform_toolsets:` → `api_server: []`(완전 잠금) 또는 `[mcp-korea_hrms]`(MCP만).
  MCP 동적 토올셋명 = `mcp-{서버명}`. mcp SDK는 옵션 의존성(`uv pip install mcp`).
- 적대적 검증: 잠금 후 에이전트가 "서버 로그/DB 조회 불가" 자인 → MCP 등록 후
  연차 15일+§60 3개항 인용을 테넌트 스코프 도구로만 산출(usage.jsonl 실호출 증거).
- 템플릿에 확정값 반영: `scripts/hermes/gateway-config.template.yaml`.

> **테넌트 노출 전제조건**: 위 (2)(3)의 Hermes 자체 도구 하드 잠금 완료가 테넌트에
> 에이전트를 노출하기 위한 필수 선행 조건이다.
