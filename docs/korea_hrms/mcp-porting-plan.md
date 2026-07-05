# MCP 이식 계획 — Korea HRMS (Frappe HRMS 포크)

작성: 2026-07-05 (Fable 5 세션). 상태: **계획 수립만 완료, 구현 미착수.**
계보: SafeClaw(safeguard-contest-mvp) → K-Climate Lab(`k-climate-lab/docs/mcp-ai-connect-porting-plan.md` Phase A 완료) → **본 레포 3번째 이식**.

## 0. 현황 진단 (2026-07-05 검토)

- Frappe HRMS 포크(develop, 커밋 1만+)에 **Korea 모듈을 PR 150건 자체 개발**: `hrms/regional/south_korea/` 58파일 + DocType 4종 + Korea 테스트 58파일.
- 설계가 이식에 유리함: **순수 파이썬 코어(frappe 미의존) + 얇은 `*_api.py` 래퍼** 2층 분리 (`docs/korea_hrms/implementation_decisions.md`의 의도적 결정). 코어는 bench 없이 동작.
- 테스트 실행 함정: `pytest`는 수집 단계에서 `hrms/__init__` → frappe import로 전멸. **`python3 hrms/tests/test_korea_*.py` 직접 실행**이 정상 경로 (annual_leave 13/13 OK 실측). 테스트 자체가 `importlib.util.spec_from_file_location`으로 코어를 파일 경로 로드하는 패턴 — MCP 서버도 같은 패턴을 쓴다.
- **배포 있음(정정)**: NOHO 베타 런칭(5월말, PR #250~#255 — docker bench + ubuntu 호스트 systemd 백업 타이머, Lighthouse 75+, 온보딩 자료 6종). 로컬 리포가 5/20에 멈춰 있었을 뿐이다. → Phase B(HTTP+토큰) 선행조건이 이미 충족일 수 있음. 구현 착수 시 **서버 생존·docker 컨테이너 상태부터 확인**(reference_oracle_server.md 참조). 단 실무 가치의 최단 경로는 여전히 Phase A(stdio, 서버 무관)이다.

## 1. 앞의 두 이식과 뭐가 다른가

| | SafeClaw / K-Climate Lab | Korea HRMS |
|---|---|---|
| 스택 | Next.js + Supabase (원격 배포) | Python / Frappe (배포 없음) |
| 전송 | Streamable HTTP + Bearer 토큰 | **stdio** (로컬 Claude Desktop/Code 연결) — 토큰 계층 불필요 |
| 도구 소스 | API 라우트 self-fetch | **순수 코어 직접 import** (테스트와 같은 파일경로 로드) |
| 스토리 | "어떤 AI든 꽂으면 안전관리자/기후교육 조교" | **"어떤 AI든 꽂으면 노무 계산기"** — 연차·법정공제·근태마감을 추론이 아니라 계산으로 |

즉 3층 구조 중 **② MCP 서버(도구 계층)만 이식**하고, ① 토큰 ③ 온보딩 UI는 bench를 실배포하는 시점의 Phase B로 미룬다.

## 2. Phase A — stdio MCP 서버 (1 세션 규모)

신규 디렉터리 `mcp_server/` (frappe 앱 패키지 밖, 독립 실행):

- `mcp_server/server.py` — 공식 `mcp` Python SDK(FastMCP). 코어는 `importlib` 파일 경로 로드(테스트 패턴 재사용, `import hrms` 금지 — frappe가 딸려온다).
- `mcp_server/requirements.txt` — `mcp` 단독.
- 실행: `python3 mcp_server/server.py` (stdio). Claude Code 연결: `claude mcp add korea-hrms -- python3 <repo>/mcp_server/server.py`.

### 도구 후보 (코어 시그니처 실측 기준, 6종)

| 도구 | 코어 |
|---|---|
| `calculate_annual_leave` | `annual_leave.calculate_annual_leave_entitlement` (근로기준법 연차 산정 — 1년미만 월할, 기산일/회계연도) |
| `summarize_attendance` | `attendance_summary.summarize_attendance` + `closing_period_for` (근태 마감 요약) |
| `validate_attendance_closing` | `attendance_summary.validate_summary_closable` + `build_closing_snapshot` |
| `build_statutory_payroll` | `statutory_payroll.build_statutory_payroll_snapshot` (4대보험·법정공제 — 정책 명시 요구, 침묵 기본값 없음) |
| `run_compliance_diagnosis` | `compliance_checklist.build_compliance_diagnosis` (노동법 컴플라이언스 체크) |
| `get_salary_component_presets` | `statutory_payroll.load_korea_salary_component_presets` |

원칙 (앞 두 이식에서 검증): AI가 **추론이 아니라 조회/계산으로 답하게** 한다. 특히 연차·공제는 급여 실무 도메인이라 **1원/1일 단위 검증** 대상 — 도구 출력에 산정 근거(basis) 필드를 그대로 노출한다.

### 검증 (autoresearch 모드1 keep 조건)

1. 기존 Korea 테스트 직접 실행 회귀 (frappe 불요 파일 전수 — 러너 스크립트 `mcp_server/run_core_tests.py`로 목록 고정)
2. MCP 실측: stdio로 tools/list + `calculate_annual_leave`(입사 1년 케이스=15일) + `build_statutory_payroll` 1건 — **급여자동화 엔진/실데이터와 3건 크로스체크**
3. results.tsv 기록 후 커밋

## 3. Phase B — 원격화 (NOHO 베타 서버 생존 확인 후)

- Frappe 앱으로 Streamable HTTP 엔드포인트 + Bearer 토큰(DocType `Korea MCP Token`, sha256 해시 저장 — SafeClaw mcp_tokens 스키마를 DocType으로 번역)
- 기존 `*_api.py` whitelist 래퍼 25종을 도구로 승격 (실데이터 조회 계층)
- 발급 UI는 Frappe Desk가 이미 있으므로 SafeClaw의 온보딩 페이지 대신 DocType 폼 재사용

## 4. 함정 목록

- `pytest`/`import hrms` 금지 — frappe ModuleNotFoundError. 파일 경로 import + 직접 실행만.
- 이 레포는 **public 포크** — 시크릿·고객 실데이터 절대 커밋 금지 (Git 시크릿 사고 재발방지 플레이북 적용). 크로스체크용 실데이터는 레포 밖에서.
- 브랜치는 develop (main 아님).
- Windows: `python3`(WindowsApps) 사용, `sys.stdout.reconfigure(encoding='utf-8')`.
- statutory_payroll은 정책(요율) 명시 입력 요구 — 도구 설명에 "요율은 당해연도 값을 호출자가 제공" 명시(연도 하드코딩 금지).

## 5. 장기

세 프로젝트(SafeClaw/K-Climate/HRMS)가 같은 패턴을 공유하게 되면 — "도메인 코어 + MCP 도구 계층 + (원격이면) 해시 토큰" — 공용 스캐폴드 추출 후보. npm(safeclaw)과 별개로 Python 쪽은 FastMCP가 이미 골격이라 추출 실익은 낮음; 문서 패턴만 공유한다.
