# 운영자 매뉴얼 — HR 담당자용

> 대상: HR 담당자 / 노무 담당자 | 데모 URL: https://hrms.safeclaw.kr  
> 작성: 2026-05-18

---

## 1. 두 가지 UI — Frappe 데스크 vs HRMS PWA

이 시스템은 진입점이 두 개다. 같은 데이터를 다른 화면으로 본다.

| 구분 | URL | 주요 용도 | 권장 기기 |
|------|-----|-----------|-----------|
| **Frappe 데스크** | `/app` | 직원 추가, 세팅, 보고서, 깊은 관리 | PC / 노트북 |
| **HRMS PWA** | `/hrms` | 출근, 휴가, 급여명세서, 한국 페이롤 마감 대시보드 | 모바일 / 태블릿 (PC도 가능) |

**언제 어디를 쓰나:**
- 직원 등록, 회사/사업장 세팅, 급여 항목 설정 → **Frappe 데스크(`/app`)**
- 페이롤 마감 현황 확인, 출퇴근 기록, 휴가 신청 현황 → **HRMS PWA(`/hrms`)**
- 감사 추적, 상세 보고서 → **Frappe 데스크(`/app`)의 Report**

---

## 2. 한국 모듈 진입 경로 (Korea HR Workspace)

한국 특화 DocType 4개 — 데스크 상단 검색창에 이름 입력하거나 직접 URL 접속.

| 기능 | URL |
|------|-----|
| 한국 사업장 프로필 | `/app/korea-workplace-profile` |
| 한국 고용 프로필 | `/app/korea-employment-profile` |
| 한국 급여마감 초안 | `/app/korea-payroll-closing-draft` |
| 마감 검토 감사 로그 | `/app/korea-payroll-closing-review-audit-log` |
| 한국 급여마감 대시보드(PWA) | `/hrms/dashboard/korea-payroll-closing` |

> **Korea Workspace** 메뉴가 보이지 않으면: 데스크 좌측 사이드바 맨 아래 `All Workspaces` → 검색.

---

## 3. 흔한 작업 5가지

### 3-1. 신규 직원 입사

**소요 시간:** 약 5~10분

1. `/app/employee` → `+ New`
2. 필수 항목 입력:
   - 이름(Employee Name), 입사일(Date of Joining), 회사(Company), 사업장(Branch), 고용 형태(Employment Type)
3. 저장 후 **한국 고용 프로필 추가:**
   - `/app/korea-employment-profile` → `+ New`
   - Employee 필드에 방금 만든 직원 연결
   - 4대보험 가입 여부, 외국인 여부 등 기입
4. 연차 자동 배정 확인: `/app/leave-allocation` → 해당 직원 항목 생성 여부 확인
   - 미생성 시: `Leave Allocation` 수동 생성 또는 운영팀 문의

**체크리스트:**
- [ ] Employee 저장 완료
- [ ] Korea Employment Profile 연결
- [ ] Branch(사업장) 할당 확인
- [ ] 계정(User) 발급 필요 시: `/app/user` → `+ New` → Employee 연결 → `hr_user` 역할 부여

---

### 3-2. 월 페이롤 마감

**소요 시간:** 처음 10~20분, 익숙해지면 5분

**흐름:**

```
1. 한국 급여마감 대시보드 확인
   → /hrms/dashboard/korea-payroll-closing
   → 사업장별 마감 진행률 + 차단요인(blocker) 확인

2. 차단요인 해소
   → 4대보험 미가입자: Korea Employment Profile 수정
   → 누락 근태: /app/attendance 에서 해당 직원 출근기록 보완

3. 한국 급여마감 세션 진입
   → 대시보드에서 사업장 카드 클릭
   → 증빙 packet 검토 (법정 공제 항목, 연장수당 근거)
   → 상태: draft_pending_human_approval → 사람 검토 후 승인

4. Salary Slip 생성/확인
   → /app/salary-slip
   → 한국 법정 공제 항목(4대보험, 소득세, 지방소득세)이 자동 주입됨
   → 항목별 근거(법조문) 확인

5. 페이롤 처리 실행
   → /app/payroll-entry → Run Payroll
   → 직원 필터, 급여 기간 선택 → Submit
```

> **중요:** 모든 mutation(저장·승인·제출)은 사람이 직접 확인 후 진행. 시스템은 계산·집계·차단요인 감지까지만 자동, 최종 실행은 운영자 승인 필수.

---

### 3-3. 휴가 신청 승인

**소요 시간:** 2~3분

**직원이 신청하는 경우:**
1. 직원이 `/hrms` 모바일 → 휴가 메뉴 → 신청
2. HR 담당자에게 알림 → `/app/leave-application` → 해당 건 승인/거부

**HR 담당자가 대신 입력하는 경우:**
1. `/app/leave-application` → `+ New`
2. 직원, 휴가 유형, 기간 입력 → Submit
3. 상태 `Approved` 로 변경

**연차 잔여 확인:**
- `/app/leave-allocation` → 직원명으로 필터
- 현황: Allocated / Used / Balance

**자동 계산되는 것:**
- 1년 미만: 월차 (입사 다음달부터 개근 시 1일씩)
- 1년 이상: 근기법 60조 기준 자동 산정

---

### 3-4. 컴플라이언스 진단 실행

**소요 시간:** 5~10분

1. `/app/korea-workplace-profile` → 해당 사업장 선택
2. 하단 `Compliance Diagnosis` 섹션 또는 API 실행 버튼
3. 진단 카테고리 5개: 4대보험 / 임금체불 / 연장 / 직장 내 괴롭힘 / 임금명세서
4. 결과 확인: 항목별 OK / 위험 / 확인필요 상태
5. 위험/확인필요 항목 → 드릴다운해서 어떤 직원, 어떤 기간이 문제인지 확인

> 진단 결과는 **참고용 체크리스트**. 최종 법적 판단은 노무사와 협의.

**진단 주기 권장:** 월 1회 (페이롤 마감 전)

---

### 3-5. 임금명세서 발송

**소요 시간:** 5분 (초기 설정 후)

**사전 조건:**
- Salary Slip Submit 완료 상태
- 카카오 알림톡 채널 연동 (베타 기간 중 별도 안내)

**발송 흐름:**
1. `/app/salary-slip` → 이번 달 생성된 명세서 목록 확인
2. 일괄 선택 → `Send Pay Slip` 액션
3. 발송 방법 선택: 이메일 / 카카오 알림톡 (카카오 연동 완료 후)
4. 시행령 27조의2 7개 항목 자동 포함 여부 확인:
   - 기본급, 연장수당, 야간수당, 휴일수당, 공제 내역, 실지급액, 지급일
5. 발송 완료 → 로그 확인

**카카오 알림톡 미연동 시:** 이메일 발송 또는 PDF 다운로드 후 수동 전달

---

## 4. 트러블슈팅

### 로그인이 안 됩니다

- 비밀번호 초기화: `/app/user` → 해당 계정 → `Reset Password`
- 계정이 없는 경우: 운영팀(abc@winhr.co.kr) 에 계정 생성 요청

### 한국 급여마감 대시보드에 데이터가 안 뜹니다

- 정상 상황일 수 있음. 런타임 데이터(Korea Payroll Closing Draft)가 없으면 fixture(샘플) 화면 표시
- 실제 마감 Draft 생성: `/app/korea-payroll-closing-draft` → `+ New`

### 직원 추가 후 연차가 자동 배정되지 않습니다

- 입사일 기준 연차 계산은 `Leave Allocation` 생성 시점 확인
- 수동 생성: `/app/leave-allocation` → `+ New` → 직원 / 휴가 유형 / 배정 수 입력

### 4대보험 공제 항목이 Salary Slip에 안 보입니다

- Salary Structure 에 한국 법정 항목이 포함됐는지 확인: `/app/salary-structure`
- 포함 안 된 경우: 운영팀에 한국 급여 항목(seed data) 재적용 요청

### 급여 계산 결과가 예상과 다릅니다

- 급여 구조(Salary Structure) 기본급 / 수당 항목 확인
- 연장·야간·휴일 근태 기록이 정확히 입력됐는지 `/app/attendance` 확인
- 이상 시 슬랙 채널 또는 abc@winhr.co.kr 로 문의. 계산 근거(법조문 매핑) 함께 공유

### 페이지가 로딩이 안 됩니다

- 서버 상태 확인: abc@winhr.co.kr 또는 슬랙 채널 (`#hrms-ops`)
- 캐시 문제: 브라우저 시크릿/인코그니토 모드에서 재시도

---

## 5. 권한(Role) 구조

| 역할 | 접근 범위 |
|------|-----------|
| `HR Manager` | 전체 직원 데이터, 페이롤, 컴플라이언스 |
| `HR User` | 자기 회사 직원 데이터, 휴가 승인 |
| `Employee` | 본인 출근, 휴가 신청, 급여명세서 조회 |
| `System Manager` | 전체 시스템 세팅 (운영팀 전용) |

---

## 6. 지원 채널

| 채널 | 용도 | 응답 시간 |
|------|------|-----------|
| 슬랙 `#hrms-beta` | 일반 문의, 사용법 | 평일 4시간 이내 |
| 이메일 abc@winhr.co.kr | 계정/데이터 요청, 공식 문의 | 평일 24시간 이내 |
| 긴급 | 서버 다운 / 데이터 오류 | 슬랙 멘션 + 이메일 동시 발송 |

---

*관련 문서: `docs/onboarding/quickstart_5min.md` | `docs/korea_hrms/feature_map_user_guide.md`*
