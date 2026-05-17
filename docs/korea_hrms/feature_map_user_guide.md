# 한국형 HRMS 기능 맵 — 시연자/운영자 30분 이해 가이드

목표: 시연자/운영자가 이 문서 하나로 "어떤 메뉴가 어디에 있고, 한국 특화 기능이 표준 HRMS의 어디와 연결되는지"를 30분 안에 파악한다.

작성일: 2026-05-17
대상 URL: https://hrms.safeclaw.kr
대상 사이트: `hrms.localhost` (내부)

---

## 0. 두 가지 진입점 (중요)

| 진입점 | URL | 용도 |
|--------|-----|------|
| **Frappe 데스크 (관리자 UI)** | `/app` | DocType CRUD, 세팅, 보고서, 깊은 관리. 데스크탑 친화 |
| **HRMS PWA (모바일/직원 UI)** | `/hrms` | 출근/휴가/급여명세서/한국 페이롤 마감 UI. 모바일/태블릿 친화 |

→ **시연 시 두 곳 모두 보여주는 것이 핵심**. 같은 데이터를 다른 UI로 표현.

---

## 1. Frappe 데스크 (`/app`) 메뉴 구조

좌측 사이드바 워크스페이스 8개:

```
HR (인사)
├── Tenure (재직)            ← 직원 입퇴사, 휴직, 발령
├── Shift & Attendance      ← 근태, 출근 기록, 교대
├── Leaves                  ← 휴가 신청, 배정, 정책
├── Performance             ← 인사평가
├── Recruitment             ← 채용
├── Expenses                ← 경비 청구
└── HR Setup                ← 부서, 직급, 회사 세팅

Payroll (급여)
└── Payroll                 ← 급여 항목, 급여 구조, 급여명세서, 급여 처리
```

→ **표준 ERPNext/HRMS 메뉴는 영어 기반**. 한글화 적용으로 라벨만 한글로 표시 (예: "HR" → "인사", "Leaves" → "휴가").

---

## 2. 한국 특화 모듈 — 어디에 어떻게 노출되나

한국 특화 DocType 4개 + south_korea 도메인 모듈 30+개. 표준 HRMS 위에 얹는 구조.

### 2-1. 한국 DocType 4개 (`/app`에서 검색하면 나옴)

| DocType | 한글 | 진입 | 역할 |
|---------|------|------|------|
| `Korea Workplace Profile` | 한국 사업장 프로필 | `/app/korea-workplace-profile` | 한국 노무법 기준 사업장 정보 (5인 이상 여부, 산업, 근로감독지청 등) |
| `Korea Employment Profile` | 한국 고용 프로필 | `/app/korea-employment-profile` | 한국 노무법 기준 직원 (4대보험, 외국인 여부, 입퇴사 등) |
| `Korea Payroll Closing Draft` | 한국 급여마감 초안 | `/app/korea-payroll-closing-draft` | 사업장별 월 급여마감 작업 흐름 |
| `Korea Payroll Closing Review Audit Log` | 검토 감사 로그 | `/app/korea-payroll-closing-review-audit-log` | 마감 검토 이력 (감사/내부통제) |

### 2-2. HRMS PWA (`/hrms`)에서의 한국 화면

```
/hrms/dashboard/korea-payroll-closing      ← 한국 급여마감 대시보드 (사업장별 마감 진행률)
/hrms/korea-payroll-closing-session/:name  ← 한국 급여마감 세션 (특정 사업장/월 상세)
/hrms/dashboard/korea-payroll-review-audit-logs ← 검토 감사 로그 목록
/hrms/korea-payroll-review-audit-logs/:name     ← 감사 로그 상세
```

→ **시연의 메인 무대 = `/hrms/dashboard/korea-payroll-closing`**. 다른 화면들은 여기서 파생.

### 2-3. south_korea 도메인 모듈 (백엔드, UI 직접 노출 X)

`hrms/regional/south_korea/`의 30+ Python 모듈. UI에서 직접 보이지 않지만 API/계산/검증 엔진:

| 모듈군 | 역할 |
|--------|------|
| `payroll_closing_*` (16개) | 한국 페이롤 마감 워크플로우 (draft/review/apply/session/worklist/evidence) |
| `payroll_salary_slip_adapter` | 표준 Salary Slip에 한국 4대보험/소득세 항목 자동 주입 (before_validate hook) |
| `payroll_entry_adapter` | 표준 Payroll Entry에 한국 마감 정보 연결 |
| `statutory_payroll` | 4대보험/소득세 법정 계산 |
| `attendance_summary` | 한국 근태 마감 (cutoff 기반) |
| `attendance_closing_api` | 근태 마감 API |
| `annual_leave` | 한국 연차 계산 (1년 미만/이상/회계연도 기준) |
| `leave_allocation_adapter` | 표준 Leave Allocation에 한국 연차 자동 배정 |
| `employment_contract` | 표준/한국 고용계약서 생성 |
| `expense_settlement` | 한국 경비 정산 (식대/교통비/통신비 등 비과세 한도 적용) |
| `compliance_checklist` | 한국 노무 컴플라이언스 진단 체크리스트 |
| `compliance_diagnosis_api` | 진단 결과 API |
| `kakao_notification` | 카카오 알림톡 발송 |
| `mobile_ess_mss` | 모바일 직원 셀프서비스 (ESS) / 매니저 셀프서비스 (MSS) |
| `approval_inbox` | 통합 결재 인박스 (휴가/경비/계약 등 모아보기) |
| `admin_dashboard` | 관리자 대시보드 데이터 |
| `closing_center` | 마감 센터 (페이롤/근태/연차 통합 마감 콘솔) |
| `payroll_closing_access_policy` | 마감 접근 권한 정책 (RBAC) |
| `demo_seed` | 시연용 데모 데이터 생성 |

→ 표준 HRMS DocType + Workflow에 **side-effect-free adapter/hook**으로 얹는 패턴. 표준 코어를 건드리지 않음.

---

## 3. 표준 ↔ 한국 모듈 연결 다이어그램

```
[표준 HRMS]                              [한국 모듈]
─────────────────────────────────────────────────────
Company (회사)            ←연결→     Korea Workplace Profile
                                      (1:N, 사업장별 한국 프로필)

Employee (직원)           ←연결→     Korea Employment Profile
                                      (1:1, 4대보험/외국인 등)
                          ←hook→     leave_allocation_adapter
                                      (입사 시 연차 자동 배정)

Salary Component         ←seed→      hrms/regional/south_korea/data/
(급여 항목)                           salary_components.json
                                      (한국 법정 4대보험/소득세 항목 자동 생성)

Salary Slip              ←before_validate hook→
(급여명세서)                          payroll_salary_slip_adapter
                                      (법정 공제 idempotent 주입)

Payroll Entry            ←연결→     Korea Payroll Closing Draft
(급여 처리)                           (1:1, 한국 사업장 단위 마감)

Leave Allocation         ←hook→     annual_leave + leave_allocation_adapter
(휴가 배정)                          (한국 연차 자동 계산)

Leave Application        ←표준 그대로 사용
(휴가 신청)

Attendance               ←feed→     attendance_summary
(출근기록)                           (월 마감 시 집계)

Expense Claim            ←feed→     expense_settlement
(경비 청구)                           (비과세 한도 자동 계산)

Employment Contract      ←표준 + → employment_contract
(고용계약서)                          (한국 양식)
```

---

## 4. 시연 시나리오 — 7화면 순서 (15-20분)

### 화면 1: 로그인
- URL: https://hrms.safeclaw.kr/login
- 보여줄 것: 한글화된 로그인 페이지 (로그인/이메일/비밀번호/잊으셨나요)

### 화면 2: HRMS PWA 메인
- URL: https://hrms.safeclaw.kr/hrms
- 로그인 후 자동 진입
- 보여줄 것: 모바일 친화 UI, 한글 메뉴 ("출근/휴가/급여명세서")

### 화면 3: 한국 급여마감 대시보드 ⭐ (메인)
- URL: https://hrms.safeclaw.kr/hrms/dashboard/korea-payroll-closing
- 보여줄 것:
  - **사업장별 마감 진행률** (서울 본사/강남 매장)
  - **차단요인 (blocker) 목록** — 4대보험 미가입자, 누락 근태 등
  - **read-only fixture fallback** — 데이터 없을 때 fallback UI 표시
- 시연 메시지: "사업장 단위로 페이롤 마감 진행 상태를 한눈에"

### 화면 4: 한국 급여마감 세션
- URL: 화면 3에서 카드 클릭 → `/hrms/korea-payroll-closing-session/:name`
- 보여줄 것:
  - 특정 사업장 + 월의 상세 마감 작업
  - 사람 승인 대기 상태 (`draft_pending_human_approval`)
  - 증빙 packet
- 시연 메시지: "AI는 보조, 실제 마감은 사람 승인 필수"

### 화면 5: Frappe 데스크 — Korea Payroll Closing Draft
- URL: https://hrms.safeclaw.kr/app/korea-payroll-closing-draft
- 보여줄 것: 데스크탑 관리자 UI에서 같은 데이터를 표/필터로 조회
- 시연 메시지: "관리자는 데스크에서 깊은 관리, 직원은 PWA에서 빠른 작업"

### 화면 6: 표준 Salary Slip + 한국 hook
- URL: https://hrms.safeclaw.kr/app/salary-slip
- 보여줄 것:
  - 표준 ERPNext Salary Slip 화면
  - 한국 법정 공제 항목이 자동으로 주입된 row들 (4대보험, 소득세, 지방세)
- 시연 메시지: "표준 HRMS 그대로 사용. 한국 법정 공제만 hook으로 자동 추가"

### 화면 7: 검토 감사 로그
- URL: https://hrms.safeclaw.kr/hrms/dashboard/korea-payroll-review-audit-logs
- 보여줄 것: 마감 검토 이력 + 감사 추적
- 시연 메시지: "내부통제/감사 대응 — 누가 언제 무엇을 검토/승인했는지"

---

## 5. 시연용 데모 데이터

현재 사이트에 시드된 데이터:

```
회사: 노란봉투법 데모

사업장 (Branch):
- 서울 본사
- 강남 매장

직원:
- 민지 김    (회사: 노란봉투법 데모, 사업장: 서울 본사)
- 현우 박    (회사: 노란봉투법 데모, 사업장: 강남 매장)

한국 페이롤 마감 Draft: 1건
- 사업장: 서울 본사
- 기간: 2026-05-01 ~ 2026-05-31
- 상태: draft_pending_human_approval

표준 Payroll Entry: 0건 (의도적, 사용자 검증 시 만들면 됨)
```

---

## 6. 핵심 디자인 원칙 — 시연 메시지

1. **AI는 보조자 (assistant_only)** — 모든 mutation (저장/승인/제출/전송)은 사람 승인 필수
2. **표준 HRMS 위에 얹는 구조** — 표준 코어 수정 없음. 한국 모듈은 hook/adapter로 결합
3. **사이드이펙트 없는 read-only 기본** — preview/검증은 mutation 없이, mutation은 명시 승인 후
4. **fixture fallback** — 런타임 데이터 없을 때도 UI는 살아있는 fallback 표시 (Vercel/정적 시연 호환)
5. **증빙 + 감사 추적** — 모든 마감 결정에 증빙 packet + audit log
6. **모바일 + 데스크탑 양립** — `/hrms` (PWA) + `/app` (Desk)

---

## 7. 자주 묻는 시연 질문 답변

**Q. 표준 ERPNext인데 한국 노무법에 맞을까?**
A. 표준 ERPNext는 글로벌 회계/HR. 한국 특화 영역은 우리가 `hrms/regional/south_korea/`로 추가. 4대보험/연차/공휴일/마감 워크플로우 등.

**Q. 자동화 어느 수준?**
A. 계산/집계/검증은 시스템이 자동화하고, AI는 비교·체크리스트·초안 보조 역할만 수행합니다. **mutation (저장/승인/제출)은 사람 승인 필수**이며 자동 승인/자동 제출은 없습니다.

**Q. 다른 회사도 쓸 수 있나?**
A. 멀티 테넌트. Frappe site 단위로 분리. 회사/사업장 단위로 데이터 격리.

**Q. 모바일 지원?**
A. `/hrms`가 PWA. 홈 화면 추가 → 앱처럼 사용. 출근/휴가/명세서 조회 모두 모바일 친화.

**Q. 한글화 완성도?**
A. 1차 batch 완료 (Frappe 1,866 / ERPNext 2,027 / HRMS 916 entries). 자주 보이는 UI와 한국 페이롤 마감/사람 승인/assistant-only 가드레일 문자열을 우선 한글화했습니다. 빈도 낮은 시스템 메시지는 일부 영어가 남아 있으며 후속 batch에서 계속 줄입니다.

**Q. 카카오 알림은?**
A. `kakao_notification` 모듈 있음. 알림톡 발송 가능. 운영 시 비즈니스 채널 + 템플릿 등록 필요.

---

## 8. 다음 단계 (운영자 액션)

1. **Gate 15 PR #225 closeout** — PO placeholder/syntax, Korea regional smoke, browser runtime JS guardrail, frontend build 결과를 PR에 반영하고 source-of-truth 문서를 Gate 15 기준으로 정리
2. **후속 한글화 batch** — 빈도 낮은 HRMS 시스템 메시지와 데모 중 노출되는 잔여 영어 우선 처리
3. **시연 데이터 추가** — 직원 10명 + 마감 3개월치로 풍부하게
4. **카카오 알림 채널 연동** — 비즈니스 채널 가입 + 템플릿 등록
5. **컴플라이언스 진단 결과** — 첫 진단 실행해서 결과 화면 채우기

---

## 부록 A. 빠른 URL 모음

```
로그인:           https://hrms.safeclaw.kr/login
HRMS PWA 메인:    https://hrms.safeclaw.kr/hrms
한국 마감 대시:    https://hrms.safeclaw.kr/hrms/dashboard/korea-payroll-closing
검토 감사 로그:    https://hrms.safeclaw.kr/hrms/dashboard/korea-payroll-review-audit-logs
Frappe 데스크:    https://hrms.safeclaw.kr/app
직원 목록:        https://hrms.safeclaw.kr/app/employee
한국 사업장:      https://hrms.safeclaw.kr/app/korea-workplace-profile
한국 고용 프로필:  https://hrms.safeclaw.kr/app/korea-employment-profile
한국 페이롤 마감:  https://hrms.safeclaw.kr/app/korea-payroll-closing-draft
표준 급여명세서:   https://hrms.safeclaw.kr/app/salary-slip
휴가 배정:        https://hrms.safeclaw.kr/app/leave-allocation
부서:             https://hrms.safeclaw.kr/app/department
지점/사업장:      https://hrms.safeclaw.kr/app/branch
```

## 부록 B. 관련 문서

- `docs/korea_hrms_user_verification_30min.md` — 30분 사용자 검증 절차 (read-only)
- `docs/korea_hrms/implementation_decisions.md` — PR별 구현 결정 기록
- `HERMES_WORKSPACE.md` — Gate 1-14 진행 기록 + cron 자율 진행 상태
- `AGENTS.md` — 워크스페이스 작업 룰
