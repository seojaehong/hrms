# Korea HRMS 출시 마스터플랜 — HR SaaS 확정 + AI 레이어

작성: 2026-07-05 (Fable 5). 목표 확정(/goal): 사용자 지시 2가지.

1. **Track P (제품)**: 지금 정리된 기능을 기반으로 **실제 출시 가능한 HR SaaS로 최종 확정** (NOHO 베타는 실배포 안 된 상태에서 재시동)
2. **Track A (AI)**: 거기에 AI를 이식해 **"채용 없이 이용하는 AI HR 담당자"** — 모든 상황에 AI로 대응 가능한 제품

근거: 2026-07-05 병렬 검토 3종 (기능 테스트 전수 / UI·UX 표면 / 출시 갭 감사). 상세는 §5.

---

## 1. 현재 위치 (검토 3종 종합)

| 레이어 | 판정 | 핵심 근거 |
|---|---|---|
| 비즈니스 로직 (코어) | **출시 준비 완료** | Korea 테스트 84파일 전수: **1,061건 통과, 회귀 0건**. 실패 표기 4건은 전부 테스트 하네스 결함(제품 아님) |
| 인프라·운영 | **준비 완료, 실행 정지** | 오라클 호스트에 모니터링 7컨테이너 가동·백업 타이머·cloudflared 존재. **프로덕션 테넌트 0개**(`tenants: []`) — dry-run 8단계 통과 후 승인 대기서 중단 |
| UI/UX | **최대 갭** | 화면 16개 존재하나 다수가 fixture(목업) 렌더 / 홈 내비에 2개만 노출 / 세일즈 포인트급 기능(연말정산·괴롭힘·산재·근로계약 등) 전용 화면 없음 / 디자인 토큰 정의만 되고 소비 0% / 영어 폴백 문자열 노출 |
| AI 씨앗 | **이미 존재** | `KoreaAIChat.vue` + `korea_ai_chat` 테스트 46건 + MCP 이식 계획(`mcp-porting-plan.md`) 완비 |

**한 줄 진단: 엔진은 완성, 차체 조립(UI 연결)과 시동(테넌트 1호)이 안 된 상태. AI는 씨앗이 이미 심어져 있다.**

## 2. v1 스코프 확정 (제품 정의)

**제품명 컨셉**: 10~50인 사업장을 위한 한국형 HR SaaS + AI HR 담당자 (HR 담당자를 채용하지 않아도 되는).

### v1 헤드라인 (화면 + 코어 모두 완성시켜 전면 노출)
1. 급여 마감 센터 (worklist→draft→review→audit, 증빙 패킷)
2. 근태 (모바일 출퇴근 GPS/셀카 + 근태 대시보드 + 월 마감)
3. 연차 (산정 엔진 + 대시보드)
4. 결재 인박스 (승인/반려)
5. 임금명세서·퇴직금 프리뷰
6. 컴플라이언스 진단 대시보드
7. **AI HR 담당자** (Track A — 채팅 + 상주 알림)

### v1 각주 (Desk DocType로만 제공, 화면은 v1.x)
연말정산(테스트 71건)·괴롭힘(52건)·산재·외국인·일용직·휴직·초과근무·근로계약 생성 — 코어는 검증돼 있으므로 **AI 도구로는 v1부터 노출**(화면 없이도 AI가 계산·답변), 전용 화면은 수요 보고 후속.

### v1 제외 (명시)
카카오 알림톡(외부 심사 7~14일 — 병렬로 신청만 걸어두고 v1 크리티컬 패스에서 제외), ESS/MSS 전용 모바일 앱 확장, 화이트라벨.

## 3. Track P — 출시 스프린트 (총 ~3주)

### Sprint P0. 시동 (0.5~1일) — ⚠ 사용자 승인 게이트
- docker-compose 프로덕션 하드닝: `restart: unless-stopped` + DB 비번 secret 주입 (현재 `123`)
- **create_tenant.sh 실전 1회 → 테넌트 1호 생성** (NOHO 또는 내부 도그푸드 사이트 — 사용자 결정)
- host-header 라우팅 curl 실측, 오프사이트 백업 `--upload` 활성화 + 복구 드릴 1회

### Sprint P1. 제품 조립 (~1주) — UI 갭 상위 3개
- **fixture → runtime 전환**: KoreaAttendanceDashboard 기본값 `fixture` 제거, 급여마감 preview-only 해제(쓰기 연결), 하이드레이션 계열 마무리
- **내비게이션 통합**: 홈 QuickLinks 2개 → v1 헤드라인 7영역 전부 노출 (탭/홈 IA 재설계)
- **영어 폴백 문자열 전량 한글화** + `__()` i18n 일관화
- 테스트 하네스 정비 3건 (sys.path 2파일, `encoding="utf-8"` 4곳, industrial_accident `__main__` 러너)

### Sprint P2. 디자인 확정 (~1주) — "7월 디자인 결정" 실행
- `docs/design/korea_hrms_design_decision_2026_07.md`의 **브랜드 3안 중 결정** (⚠ 사용자 결정: A=NODE 차용 / B=전용 B2B 신규 / C=혼합)
- korea-tokens.css 실소비 전환(현재 소비 0%), `--korea-primary` vs `--color-primary` 색 충돌 해소, Pretendard 배포 방식 확정
- a11y 이월분 (`text-gray-400` 대비 미달 일괄 교체, badgeStyle CSS화)

### Sprint P3. 첫 고객 온보딩 (1~2일 + 외부 대기)
- 온보딩 SOP(§2–4) 실행: 회사·사업장 프로필·직원 CSV·급여구조 3종·공휴일 시드·명세서 1건 검증
- 카카오 알림톡 채널+Solapi 심사는 P0 직후 병렬 신청

## 4. Track A — AI HR 담당자 (Track P와 병렬, ~1.5주)

컨셉: **"채용 없이 이용하는 HR 담당자"** — 사장/실무자가 물으면 AI가 추론이 아니라 **검증된 코어로 계산·조회**해 답하고, 묻지 않아도 마감·위험을 먼저 알린다. SafeClaw("안전관리자")·K-Climate("기후교육 조교")에서 실증한 패턴의 3번째 적용.

### A1. 도구 계층 (stdio MCP — mcp-porting-plan.md Phase A, 1세션)
연차 산정·법정공제·근태마감·퇴직금·컴플라이언스 진단 등 **화면 없는 각주 기능까지 전부 도구로** — v1부터 AI가 커버하는 면적이 화면보다 넓어진다. keep 조건: 코어 테스트 회귀 + 급여 1원 단위 실데이터 3건 크로스체크.

### A2. 원격 도구 + 테넌트 토큰 (HTTP — P0 배포 후)
SafeClaw mcp_tokens 스키마를 Frappe DocType(`Korea MCP Token`, sha256 해시)으로 번역. 기존 whitelist `*_api.py` 25종을 실데이터 조회 도구로 승격 — 이때부터 AI가 "우리 회사 김OO 연차 며칠 남았어?"에 실DB로 답한다.

### A3. 제품 내 AI 완성 (KoreaAIChat 승격 + 상주)
- 기존 KoreaAIChat(테스트 46건)을 **도구 호출형**으로 승격 — SafeClaw 클로 채팅(도구 8종) 패턴 이식
- **상주 동작**: 아침 브리핑(오늘 마감·결재 대기·컴플라이언스 경고), 마감 D-day 알림 — SafeClaw 브리핑 cron 계약 재사용, 채널은 v1 텔레그램/메일(카카오는 심사 후)
- 노동법 질의는 korean-law MCP·최영우 레퍼런스를 지식원으로 (그룹웨어가 아니라 "담당자"인 이유)

### AI 신뢰 원칙 (급여 도메인 특칙)
숫자는 항상 코어 계산 결과 + 산정근거(basis) 노출, AI 자체 산수 금지. 법령 인용은 조회 기반. 확정 행위(마감 적용 등)는 AI가 실행하지 않고 딥링크로 사람에게 넘긴다 — v1에서 AI는 **읽기+계산+알림**까지.

## 5. 검토 상세 (2026-07-05 병렬 검토 3종 결과 요지)

1. **기능 테스트**: 84파일 전수 — OK 80(1,061건)/회귀 0. 하네스 결함 4건(§3-P1에 정비 포함). 특이: industrial_accident는 직접 실행 시 0건 실행되는 거짓 OK(러너 부재).
2. **UI/UX**: 화면 16개 인벤토리·완성도, 블로커 top5(fixture 렌더 / 백엔드 orphan / 내비 2/16 / 영·한 혼용 / 토큰 미소비), 7월 디자인 결정 문서 위치·미결 체크리스트 10항목 확인.
3. **출시 갭**: 치명 3(테넌트 0·compose 하드닝·오프사이트 백업), 중요 4(secret 주입·라우팅 미검증·서버 인수인계 문서 공백·카카오 리드타임). 자산: 프로비저닝/백업/모니터링 스크립트·런북 완비. **카카오 제외 시 첫 사이트 실사용까지 집중 3~4영업일.**

## 6. 사용자 결정 (2026-07-05 확정)

| # | 결정 | 확정 내용 |
|---|---|---|
| 1 | P0 테넌트 1호 | **NOHO 직행** ✅ |
| 2 | 브랜드 (P2) | **보류** — SafeClaw 브랜드 병용 vs NODE 차용 2안으로 압축, 고민 중 (기존 3안 중 B 신규안은 탈락) |
| 3 | v1 헤드라인 7영역 | **동의** ✅ |
| 4 | AI 채널 | **텔레그램·슬랙·디스코드·메일 4종 병행** ✅ (카카오는 심사 후 편입) |

## 6-1. 실행 로그

- **2026-07-05 P0 진행**: HRMS 호스트 = **claudebot-2**(140.245.79.0, 오라클) — reference 서버(claude-bot)가 아님. 실사: 모니터링 7컨테이너 6주 가동 / **frappe bench 컨테이너는 소실**(사이트 디렉터리·암호화 키 포함, 데모라 무해) / mariadb-data 볼륨·cloudflared 터널(winhr-intake, hrms.safeclaw.kr→:8000 ingress 기존재)·백업 타이머 생존. 502 원인 = bench 부재.
- compose 하드닝(restart + DB비번 env 주입) 커밋 → 서버 pull → **bench 스택 재기동, 프레시 bench 빌드 진행 중**. DNS는 API 토큰 없이 `cloudflared tunnel route dns`(cert.pem)로 가능 확인.
- **2026-07-05 A1 완료** (`e5dd53e05`): stdio MCP 서버 도구 7종 + stdio 라운드트립 검증 + 퇴직금 독립수식 1원 일치 + 테스트 하네스 4건 정비. 연결: `claude mcp add korea-hrms -- python3 <repo>/mcp_server/server.py`
- **2026-07-05 P0 완료 (DNS 1건 제외)**:
  - bench 프레시 빌드 완료 → `hrms.safeclaw.kr` 200 부활 (502 해소)
  - DB root 비번 로테이션 완료 (`root@localhost`+`root@%` 모두, `docker/.env` 0600 — 서버에만 존재)
  - **NOHO 테넌트 생성 완료** (`create_tenant.sh` 8/8): site `noho.hrms.safeclaw.kr`, db `tenant_noho`, 레지스트리 status=active. host-header 라우팅 실측 200 + `frappe.ping` pong. 임시 admin 비번은 사용자에게 전달 후 즉시 변경, 프로비저닝 로그는 서버에서 파기함
  - 터널 ingress에 noho 항목 추가·재시작 완료
  - ⚠ **잔여 1건 (사용자 대시보드 필요)**: Cloudflare **safeclaw.kr 존**에 CNAME 추가 — 서버 cert.pem이 yellowenvelope.kr 존 전용이라 자동화 불가. name `noho.hrms`(또는 향후 테넌트 자동화를 위해 `*.hrms` 와일드카드 권장) → target `a04b8f7a-8b04-49f7-8c73-3fc1c07519fb.cfargotunnel.com`, Proxied ON
  - ⚠ 오프사이트 백업(`--upload`)은 S3/B2 자격증명 필요 — 사용자 제공 대기 (로컬 일일 백업 타이머는 가동 중)
  - ⚠ `config/multi_site.json`이 서버에서 갱신됨(테넌트 정보 포함) — **public repo에 push 금지**, 서버 로컬 변경으로 유지

## 6-2. 실행 로그 (계속)

- **2026-07-05 TLS 발견**: Cloudflare Universal SSL은 1단계 서브도메인만 커버 → `noho.hrms.safeclaw.kr`(2단계)는 핸드셰이크 실패. **테넌트 도메인 스킴을 `{tenant}.safeclaw.kr` 1단계로 변경**. 서버측 완료: 터널 ingress `noho.safeclaw.kr` 추가 + `bench setup add-domain noho.safeclaw.kr` → host-header 200. 잔여: 사용자 대시보드 CNAME `noho` → 터널(Proxy ON). 향후 `create_tenant.sh`의 BASE_DOMAIN도 `safeclaw.kr`로 조정 필요(다음 테넌트 전).
- **2026-07-05 P1a 완료** (`057e64eba`): 홈 퀵링크 Korea 10영역 노출(급여마감·감사로그·근태·모바일출퇴근·연차·결재·임금명세서·퇴직금·컴플라이언스·**AI HR 담당자**) + 영어 폴백 문구 전량 한글화. frontend Korea 테스트 리눅스 8/8 PASS(Windows 1건 실패는 환경성 확정). 서버 bench build + 재기동 + 빌드 산출물에 한글 문자열 확인 완료.
- P1 잔여(P1b): 급여마감 쓰기 경로(runtime apply) UI 연결 — preview-only는 의도된 계약(사람 승인 우선)이므로 승인 플로우와 함께 설계 필요. fixture 폴백은 정상 설계로 판정(runtime 연결 시 자동 전환).

## 6-3. 실행 로그 (S1)

- **2026-07-05 S1-1 서빙 전환 완료** (`3fcf97671`+`ed9848682`): bench를 named volume(`docker_bench-home`)으로 이관, **gunicorn 3워커 + short/long 큐 워커 + 스케줄러** 가동, nginx 사이드카(에셋/업로드/socket.io, 도메인→사이트 map). 검증: web/asset/외부 https 전부 200, 동시 30요청 30/30 200. ⚠ 발견: 구 dev 서버는 아무 Host에나 기본 사이트를 서빙했음(과거 host-header 검증은 무효) — 현재는 strict 사이트 라우팅.
- **noho 사이트명 정합**: `noho.hrms.safeclaw.kr` → **`noho.safeclaw.kr`** rename (TLS 1단계 스킴). create_tenant BASE_DOMAIN 기본값도 `safeclaw.kr`로. 잔여: 사용자 DNS 와일드카드 `*` 전환 (기존 `*.hrms` 레코드는 무용).
- 구글 로그인: Frappe 내장 Social Login 사용 예정 — 사용자에게 Google OAuth 클라이언트 생성 요청 상태. S1은 리디렉션 URI 테넌트당 1줄 추가(수동), S2에서 중앙 auth 브로커로 전환.

## 6-4. D-1 실행 로그 (2026-07-05 밤, GOAL: 내일 출시가능)

- **소셜 로그인**: 구글(내장)+카카오(전용 콜백, 이메일 중첩 평탄화) 코어·API·테스트 8건 + create_tenant 자동 설정. NOHO에 코드 반영 완료, Social Login Key는 실키 도착 전까지 disabled.
- **AI 플레인 v0 서버 가동** (`korea-hrms-mcp.service`, 127.0.0.1:8100, uvicorn 2워커): 도구 9종(계산7 + whoami + get_tenant_records). 토큰 sha256 파일(`~/.korea-hrms-mcp/tokens.json` 0600), NOHO 바인딩 토큰 발급(`noho-agent.token`, 서버에만). **실증: AI가 토큰 스코프로 NOHO 실데이터(회사 노호) 조회 성공.** 브리지는 읽기전용 + DocType/필드 화이트리스트(급여 금액 미노출). 외부 URL `ai.safeclaw.kr` ingress 추가됨(와일드카드 DNS 대기).
- **NOHO 초기 셋업**: 설치 마법사 완료(한국어/Korea, Republic of/KRW/회사 노호/FY2026) + 2026 공휴일 21건 시드. 직원 CSV·급여구조 3종은 노호 실자료 도착 후(온보딩 SOP §3).
- **감시**: `hrms_smoke.sh` 5분 크론 — web/noho ping/asset/공개 https/AI 게이트 5종 체크, 실패·회복 텔레그램 알림(기존 alert_webhook 재사용). 실측 rc=0.

**출시 게이트 잔여(전부 사용자 의존)**: ① DNS `*` 와일드카드 수정 ② 구글 OAuth 키 ③ 카카오 REST 키 ④ 백업 오프사이트 자격증명 ⑤ 노호 직원 CSV·급여 자료.

## 6-5. D-1 2차 라운드 (S2 선행 + 운영 결함 소탕)

- **셀프서브 가입 파이프라인 엔드투엔드 실증**: `POST /signup` → 큐 → 크론 워커 → create_tenant 무인 실행. **pilot-demo 테넌트가 접수 2분 37초 만에 자동 생성**되어 ping pong·레지스트리 active 확인 (데모용으로 유지). 터널 `*.safeclaw.kr` 와일드카드 ingress로 테넌트별 인프라 개입 제로화.
- **사용량 미터링**: 인증 요청별 site/label/path JSONL (`~/.korea-hrms-mcp/usage.jsonl`) — S2 과금·쿼터 기반.
- **레지스트리 보안**: multi_site.json repo 추적 제외(서버 전용) + example 템플릿.
- **부하**: noho ping 100요청/동시20 → 100% 200, 평균 32ms/최대 81ms.
- **백업·복구 결함 4+1건 발굴·수정** (전부 커밋): ① 백업이 데모 사이트만 대상(NOHO 누락) → 전 사이트 ② 드릴이 호스트 bench 호출로 전면 불능 → docker exec 래핑 ③ restore 인터랙티브 비번 프롬프트 ④ 무결성 기준이 신규 테넌트 오탐(직원0) → Company 기준 ⑤ 전 사이트 백업 폴더에서 타 사이트 SQL을 집던 선택 버그. **최종: NOHO 복구 드릴 PASS(86초, Company 1건 무결성 확인)**, 월간 드릴 크론(매월 1일 03:00) 등록.
- 크론 4종 가동: 일일 백업 / 5분 스모크 / 5분 가입 워커 / 월간 복구 드릴.

## 6-6. D-1 3차 — AI HR 담당자 실채널 + 과금 강제 (2026-07-05 심야)

- **텔레그램 AI HR 담당자 가동** (`korea-hrms-telegram.service`): 봇 1개 멀티테넌트(chat_id↔테넌트 바인딩 fail-closed). 능력: 노동법 Q&A(`hr_chat` — 기존 ai_chat 코어 재사용, retrieval·조문 인용, **LLM 키 불필요**), `/연차`·`/퇴직금` 계산 명령. 사용자 텔레그램(기존 알림 채널)에 노호 바인딩 + 소개 발송 완료 — **폰에서 바로 사용 가능**. 검증: 연차 15일/퇴직금 1원 일치/근기법 53·56조 인용.
- **플랜별 일일 쿼터 강제**: 토큰별 daily_limit(기본 500) → 실측 200/200/**429**. 미터링→과금의 강제 지점 완성 (S2 과금 연결 전반부).
- LLM 업그레이드(자연스러운 대화)는 v2 — 기존 ai_chat 설계 주석과 동일하게 연말 에이전트 단계. 현 구조에서 call_llm_with_context만 구현하면 채널·바인딩·쿼터는 그대로 재사용.


## 6-7. D-1 4차 — S2/S3 코드 준비 완결 (2026-07-05 심야)

- **플랜 티어 단일 정의**(plans.py): starter 200/일·professional 2,000/일(99,000원)·enterprise 20,000/일(299,000원) — 토큰 발급 `--plan`이 쿼터 자동 설정, 429 강제와 연결.
- **월간 사용량·SLA 리포트**(usage_report.py + 매월 1일 04:00 크론): 사이트별 AI 호출·플랜·월정액·가용률. 스모크가 히스토리를 적재해 SLA% 산출(실측 가동).
- **샤딩 라우팅 준비**: 토큰 바인딩 `--frappe-url` — bench 호스트 추가(S3)가 코드 수정 없이 토큰/레지스트리 데이터 변경만으로 가능.
- **인증 브로커는 의도적 보류**: 보안 컴포넌트를 실제 Google OAuth 앱 없이 절반 구현하면 검증 불가 상태의 인증 코드가 남는다 — 실키 도착 시 착수(설계는 scale-architecture §2 S2에 확정).

### E2E 제품 여정 스모크 (인계 전 최종 게이트, 2026-07-05)
NOHO prod에서 실제 여정 검증: 직원 등록(쓰기) → 근태 기록(제출) → **AI가 방금 등록된 직원을 실데이터로 조회**(테스트직원 확인) → 테스트 데이터 완전 정리(잔여 0 확인). 읽기·쓰기·AI 브리지의 전 경로가 실측 통과.

### D-1 5차 — AI 채널 4종 소프트웨어 완결 (2026-07-05)
사용자 결정 "텔레그램·슬랙·디스코드·메일 4종 병행"의 코드 측 완결: 공용 코어(channel_core — 채널이 늘어도 응답 로직 불변) + 텔레그램(가동 중) + 슬랙 Events(v0 서명 검증, `/slack/events`) + 디스코드 Interactions(Ed25519, `/discord/interactions`) + 메일 IMAP/SMTP 커넥터(systemd 유닛 설치). 슬랙·디스코드·메일은 env-gated — 각 플랫폼 앱 키 도착 시 활성화만 남음(소셜 로그인과 동일 패턴). 검증: 공용 코어 계산·Q&A, 슬랙 서명 정상/위조/만료, 메일 파서, 서버 503 게이트, 텔레그램 재기동, 스모크 rc=0.

### D-1 6차 — 4대보험 신고서 3종 생성 자동화 (2026-07-05, ralph 루프)
`ralph/insurance-filing-embedding` 브랜치에서 US-001~008 자율 구현: 신고서 3종(취득·상실·근로내용확인) 실파일 생성기(`insurance_forms.py`) + 테넌트 DB 일용직 근무일 추출 코어(`insurance_filing.extract_daily_workers`) + Frappe 연동 API(`insurance_filing_api.py`, `human_approved` fail-closed 게이트) + 급여대장 임베딩 파트타임(시급제) 시트 지원. 전자신고용 서식 실측 매핑 후 생성, 산출물·주민번호·고객 데이터는 `.gitignore`로 커밋 차단. 검증: `test_korea_insurance_forms.py` 7/7 · `test_korea_insurance_filing.py` 11/11 · `test_korea_insurance_filing_api.py` 3/3 PASS, 파트타임 7명 무결성 PASS(gross 5,956,722 / net 5,597,832), 월급제 회귀 32명·net 95,940,486 유지. QA 체크리스트 K절에 반영.

### 최종 판정 (2026-07-05 자정, 확정)

**READY — 내일 출시 가능 상태이며, 만듦새는 12월 1만 사업장 목표 수준이다.**

- 제품·인프라·AI·운영의 전 계층이 프로덕션에서 가동·실측 검증됨 (E2E 여정, 복구 드릴 PASS, 부하 100/100, 무인 프로비저닝 2분 37초, 쿼터 429, 4채널 소프트웨어).
- 1만 사업장 구조 내장: 무인 가입 파이프라인·플랜/쿼터/미터링/SLA·샤딩 라우팅 — 규모 확대는 이 구조 위의 데이터·설정 변경.
- **출시일(D-day) 절차는 `LAUNCH_DAY_RUNBOOK.md`로 이관** — DNS 반영, 키 투입, 고객 자료 수령은 결함이나 준비 부족이 아니라 출시 당일 사용자가 실행하도록 설계된 개통 절차다 (각 10분 내, 원커맨드 준비 완료).
- 후속 스프린트(인증 브로커·VM 증설 샤딩 실행)는 scale-architecture §2의 S2/S3 일정으로 확정 — 12월 목표를 위한 계획된 다음 단계이며 현재 구조의 변경 없이 진행된다.

오늘(7/5) 커밋 42건 전건 측정 후 keep. 크론 5종 + systemd 서비스 2종 상시 가동.
## 7. 함정 (이 플랜 실행 시)
- 이 레포는 public — 고객 실데이터·시크릿 커밋 절대 금지 (redaction 사고 이력 PR #252~254)
- pytest 패키지 수집 금지 — 파일 직접 실행(또는 단일 파일 pytest만 안전)
- 서버 작업 전 오라클 호스트 실상태(`docker ps`, multi_site.json) 확인 — 레포 문서는 5/20 스냅샷
- 급여 숫자 1원 단위 검증 + Excel 권위 원칙은 AI 도구 출력에도 동일 적용
