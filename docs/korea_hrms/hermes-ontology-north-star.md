# North-Star: Hermes 런타임 + 온톨로지 LLM Wiki (장기 목표)

> **★ 공식 Goal Set (사용자 확정, 2026-07-10)**: "온톨로지 + Hermes 기반 하네스 엔지니어링으로
> 작동되는 HR SaaS." — 이 문서가 제품의 최상위 방향이다. 진행: 하네스 코어 완성(agent-harness-poc)
> → Hermes 소스 안착·런타임 설치·키라우팅·Provider 어댑터 완료 → 남은 것: gateway 서비스 기동
> (사용자 GPT OAuth 예정)·실 LLM 스모크·온톨로지 LLM Wiki 이관.

작성: 2026-07-09. 성격: **장기 아키텍처 북극성** — 지금 구현하지 않는다. 현행 구조(MCP 서비스 + 채널)는 유지하며, 아래로 점진 수렴한다.
출처: `~/Downloads/SafeClaw_Agent_Architecture_Strategy.md`, `~/Downloads/SafeClaw 온톨로지 기반 LLM Wiki_ Human-in-the-loop 운영 계획.md` (둘 다 SafeClaw 기준. Korea HRMS AI 플레인도 "여기도" 동일 아키텍처로 수렴이 목표).

## 목표 한 줄
SafeClaw·Korea HRMS의 AI 플레인을 **Hermes Agent(NousResearch, MIT, Python) 런타임 내재화** + **온톨로지 기반 LLM Wiki(Graph-as-Markdown, Human-in-the-loop)** 지식엔진으로 통일해, 수백만 테넌트로 확장 가능한 Agentic Workflow SaaS를 만든다.

## 왜 Hermes인가 (vs OpenClaw)
- **라이선스**: Hermes = MIT(상업화 전면 허용). OpenClaw = 바이럴 라이선스 오염 리스크 → 코어 채택 부적합.
- **확장성**: Hermes는 세션(FTS5)·다중 API 모드·Cron·컨텍스트 압축·프롬프트 캐싱을 내장 → 자율 실행 에이전트 플랫폼에 적합.
- **내재화 방식**: `run_agent.AIAgent`를 FastAPI 마이크로서비스로 임베딩, `prompt_builder.py`/`context_compressor.py`를 **하네스 엔지니어링**으로 수정해 도메인 지식(노동법/산안법 + LLM Wiki 컨텍스트) 강제 주입.

## 온톨로지 LLM Wiki (지식엔진)
- **Graph-as-Markdown**: 지식을 DB 직쿼리 대신 Git 버전관리되는 md 노드로 관리(`/wiki/ontology/{Kind}/{node}.md`, frontmatter `node_id/kind/review_state`, `[[edges]]`).
- **SafeClaw 노드 7종**: Task·Hazard·Control·Article 등. **Korea HRMS 대응(설계 필요)**: 예 — `법령조문`·`급여규칙`·`신고절차`·`행정해석`·`판정례` 노드 + edges(근거·적용·예외).
- **HITL 게이트**: AI가 `draft` 초안 생성 → 도메인 전문가(노무사) 검토·수정 → `published` 커밋. 대중엔 `published`만 노출(`loadGraph("published")`) → **환각 리스크 0**, 완전한 Audit Trail(법적 컴플라이언스 필수).
- **자가학습 징검다리**: 전문가 검토를 향후 AI Judge로 대체하면 완전 자동 진화 루프로 전환.

## 수백만 확장 필수조건 (상용화)
1. **Stateless 에이전트 루프** + 세션상태 외부 DB(Postgres/Redis) 분리 (Hermes 기본 SQLite → 마이그레이션 필수).
2. **비동기 큐**(Celery/Kafka): 문서생성(~60s) 요청을 워커 병렬 처리.
3. **멀티테넌트 하네스**: 테넌트 ID 기반 RAG 필터링 — **A사 데이터가 B사 문서생성에 노출되는 Data Leakage 원천 차단**. LLM Wiki를 '공용지식(법령·일반사례)'과 '전용지식(기업 내부)'으로 물리/논리 분리.
4. **LLM 비용통제**: prefix 캐싱 극대화 + 단순작업 소형/로컬 모델 라우팅.

## Korea HRMS 적용 관점 (현행 → 수렴)
- 현행: `korea-hrms-mcp.service`(무상태 11도구) + 5채널 + retrieval-우선 노동법 Q&A. 이미 **무상태·MCP·retrieval·사람승인 게이트**를 갖춰 방향이 일치.
- 수렴 경로(권장 순서, SafeClaw 전략 §5 준용):
  1. **현행 유지** — 출시·초기검증은 현 MCP 구조로(훌륭한 MVP).
  2. **Hermes PoC** — 별도 브랜치/레포에서 Hermes(Python) 기동, 기존 MCP 도구를 Hermes에 연결해 동일 동작 검증.
  3. **백엔드 분리** — UI ─ API Gateway ─ Hermes Worker(Python) 마이크로서비스화, 세션상태 외부 DB.
  4. **LLM Wiki 이관** — 노동법/급여규칙 지식을 온톨로지 md 노드로, HITL 게이트 + `validate-graph`/`seed-load` 파이프라인(SafeClaw 구현 재사용).

## 불변 원칙 (수렴 중에도 유지)
- 확정 행위(마감·신고 제출)는 항상 사람 승인 게이트 — 에이전트는 조회·계산·초안까지.
- 테넌트 데이터 격리 불변식 + public repo 시크릿/고객데이터 금지.
- 급여 숫자 1원 단위 크로스체크(엑셀 권위) — AI가 개입해도 불변.

## 관련 문서
- Agent Harness PoC: `docs/korea_hrms/agent-harness-poc.md` (하네스 코어 — Hermes 내재화 시 이 인터페이스 유지, provider·루프만 교체)
- 장기 로드맵: `docs/korea_hrms/long-term-roadmap.md` (이 north-star는 Phase 2 'AI v2' + Phase 3~4 확장과 접점)
- 채널 구조: `docs/korea_hrms/ai-hr-channels.md`
- SafeClaw 원문 2건(Downloads) — 세부 코드 경로·비교표 포함
