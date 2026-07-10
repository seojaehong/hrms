# SafeClaw HR — 최종 개발 고지 (Milestones, 2026-07-10 확정)

PRD v2(`PRD-v2.md`)와 실구현 상태를 정합시킨 **실행 고지**. 각 고지는 기계 검증
가능한 완료 기준을 가지며, 통과 전 다음 고지로 넘어가지 않는다(autoresearch 원칙).

## 확정된 설계 결정 (그릴 결과)
- **도구 경로**: 확정 행위(mutation) 도구 = **MCP 경유 + 승인큐 필수**. 조회·계산 도구 =
  인프로세스(tool_registry) 허용. Hermes가 도구를 직접 잡는 시점에 조회도 MCP로 일괄 전환 검토.
  (PRD 원칙 2는 이 완화안으로 해석 — mutation에 대해서는 문자 그대로)
- **온톨로지 형식**: Graph-as-Markdown(north-star) — frontmatter `node_id/kind/review_state`,
  HITL draft→published 게이트. 첫 노드 = 근로기준법 §60(연차).
- **과금**: 테넌트 BYOK → 플랫폼 키 폴백(구현 완료, billing 태그 귀속).

---

## M0 — 기반 완성 ✅ (2026-07-10 현재 라이브)
하네스 코어(스킬·도구·프롬프트·루프, 81테스트) · Hermes 소스 안착+런타임(uv py3.12)+
gateway systemd(:8130, 격리 홈) · 키 라우팅 · E2E 체인 검증(상류 OAuth 직전까지) ·
시급제 전 구간 · 주민번호 체인 · 다관리번호 · 고지 대사 파이프라인 · CODEF 스캐폴드 ·
hr.safeclaw.kr 랜딩 · 테스트 게이트(108파일/1,482+케이스).

## M1 — 에이전트 실동 (즉시, 사용자 OAuth 후 1~2일)
**"HRMS 안에서 스킬로 급여" 첫 실증.**
1. 사용자: `hermes auth`(격리 홈) → 스모크 재실행
2. prompt_builder를 run_agent_skill에 배선(도메인 원칙+스킬+도구스펙 시스템 프롬프트)
3. ai_chat 2세대: 기존 retrieval 답변 불가 시 Hermes 에이전트 폴백(조회 도구만) —
   1세대 경로는 무LLM 폴백으로 유지(비용·장애 대비)
4. 채널 1개(텔레그램) 실전: "6월 시급제 마감 준비해줘" → 제안 요약 응답
- **완료 기준**: 텔레그램 질의 → 에이전트가 조회 도구 호출 → 요약 응답(저장 0회),
  gateway 로그에 billing 태그 기록. PRD Phase 1 완료 기준 충족.

## M2 — 온톨로지 첫 노드: §60 연차 (M1 후 1~2주)
**Explainable의 시작.**
1. `wiki/ontology/` 구조 신설 — 법령조문·급여규칙 노드(md, draft/published)
2. §60 연차 규칙을 노드로 추출, `annual_leave.py`가 published 노드에서 규칙 로드
3. 검증 스크립트(validate-graph — 고아 노드·무출처 엣지 차단) + 게이트 편입
4. 에이전트 연차 응답에 근거 조항 자동 인용
- **완료 기준**: 연차 계산 응답에 "근로기준법 제60조 제1항" 인용 + 노드 수정은
  draft→사람 승인→published로만 반영(테스트로 증명). PRD Phase 2 완료 기준 충족.

## M3 — 고지 대사 실전 + CODEF (병행 가능)
1. 노호 6월 실데이터 대사 1회(공단 xlsx + column_map) — 차이 0 또는 전건 규명
2. CODEF 데모 키 연동 검증 → 정식 전환 판단(영업문의 3+1 질문)
- **완료 기준**: 실 대사 리포트 1건이 results 저널에 keep으로 기록.

## M4 — 확정 행위 게이트 E2E (M1~2 후)
**첫 mutation 도구 개통 — 여기부터 PRD 원칙 2 문자 그대로.**
1. "시급제 제안 → 급여 마감 드래프트 반영" 도구를 **MCP 서버 경유 + read_only=False**로 등록
2. 에이전트 상신 → Draft + `requires_human_approval` → 결재함 승인 → 반영(기존
   payroll_closing_draft_apply 재사용)
- **완료 기준**: 에이전트가 상신한 건이 사람 승인 없이는 절대 반영되지 않음을
  적대적 테스트(모델이 human_approved 위조)로 증명 + 승인 후 반영 E2E 1건.

## M5 — 중대재해처벌법: SafeClaw 모듈 통합 (북극성, PRD Phase 3)
⚠️ **신규 구축 아님** — 중처법 도메인은 **별도 모듈 SafeClaw**(safeguard-contest-mvp,
www.safeclaw.kr)에서 이미 진행 중: 안전 온톨로지(Task·Hazard·Control·Article 노드,
core-triples.json, graph-store published 게이트)와 문서 생성 파이프라인 보유.
따라서 M5 = **두 제품의 통합**:
1. SafeClaw 온톨로지 스키마를 M2 온톨로지 형식과 정렬(동일 draft/published HITL)
2. HR 테넌트 데이터(직원·국적·근태) ↔ SafeClaw 안전문서 파이프라인 연결
3. hrms의 compliance_checklist를 SafeClaw 온톨로지 노드로 매핑(중복 구현 금지)
4. 다국어 안전문서 전파(번역도 승인 게이트 — 오역=중대 리스크) + Read Receipt 증빙
- **완료 기준**: PRD Phase 3 기준(중처법 §4 체크리스트 자동 실행→보완 초안→노무사
  승인 큐) — 단 실행 엔진은 SafeClaw 모듈, HR 데이터는 hrms가 공급.

---

## 사용자 투입 지도 (고지별)
| 고지 | 필요한 것 |
|---|---|
| M1 | **GPT OAuth**(`hermes auth`, 명령 준비됨) |
| M2 | §60 노드 초안의 노무사 검토·승인(HITL 첫 실행) |
| M3 | 공단 고지 xlsx 1개 + column_map / CODEF 데모 가입 |
| M4 | 결재함 승인 1회(실증) |
| 상시 | USER_INPUT_HANDOFF.md TIER1~2 키들 |

## 고지 통과 규율
- **TDD 철칙(사용자 상설 지시 2026-07-10, 모든 개발 레벨)**: 프로덕션 코드 전에 실패하는
  테스트 먼저 — RED(의도된 사유로 실패) 실행 확인 → 최소 구현 → GREEN 확인 → 리팩터.
  테스트가 즉시 통과하면 잘못된 테스트. 랄프 루프는 progress.txt 패턴으로 강제,
  인라인 작업도 동일. 커밋에 `tdd: red→green` 표기.
- 게이트: `bash scripts/run_korea_tests.sh` 전체 그린 + 해당 고지 완료 기준 실측
- 기록: results.tsv keep 저널 · 큰 구현은 랄프 루프(오퍼레이터+워크트리 패턴)
- 불변식: 숫자 1원 단위 · 확정=사람 승인 · 테넌트 격리 · 키/고객데이터 레포 금지
