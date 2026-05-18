# 5분 퀵스타트 — 처음 접속했을 때

> 대상: 베타 첫 접속자 | 데모 URL: https://hrms.safeclaw.kr

---

## Step 1: 로그인

**URL:** https://hrms.safeclaw.kr/login

1. 이메일과 비밀번호 입력 (베타 신청 시 전달된 계정)
2. 로그인 후 `/hrms` (HRMS PWA 대시보드)로 자동 이동
3. 처음 보이는 화면: 모바일 친화 메뉴 (출근 / 휴가 / 급여명세서)

> **팁:** 관리자 기능(직원 추가, 세팅 등)은 `/app` (Frappe 데스크)에서 진행. 직원용 셀프서비스는 `/hrms`에서 진행. 두 화면이 같은 데이터를 다르게 보여준다.

---

## Step 2: 한국 페이롤 마감 대시보드 둘러보기

**URL:** https://hrms.safeclaw.kr/hrms/dashboard/korea-payroll-closing

1. 좌측 메뉴 또는 직접 URL 접속
2. 사업장별 **마감 진행률 카드** 확인 — 완료 / 차단요인 / 미완 상태 한눈에 표시
3. **차단요인(blocker)** — 빨간색으로 표시된 항목: 4대보험 미가입자, 누락 근태 등
4. 카드 클릭 → 해당 사업장의 마감 세션 상세 진입

**여기서 확인할 것:**
- 내 회사 사업장이 몇 개 뜨는지
- 이번 달 마감 상태가 어느 단계인지
- 차단요인 내용 읽어보기

> 데이터가 없는 경우 fixture(샘플) 화면이 표시된다. 실제 직원/사업장 데이터 입력 후 runtime 데이터로 전환.

---

## Step 3: 직원 1명 추가 시도

**URL:** https://hrms.safeclaw.kr/app/employee

1. 우측 상단 `+ New` 클릭
2. 필수 입력: 이름 / 입사일 / 회사 / 사업장(Branch) / 고용 형태
3. 저장(Save) 클릭
4. 저장 후 `/app/korea-employment-profile` 에서 해당 직원의 **한국 고용 프로필** 추가
   - 4대보험 가입 여부 / 외국인 여부 / 기타 한국 법정 정보

**자주 막히는 지점:**
- Company, Branch 없으면 먼저 `/app/branch`에서 사업장 추가 필요
- 저장 안 되면 필수 항목 확인 (빨간 테두리 필드)

> 문의: 슬랙 `#hrms-beta` 채널 또는 abc@winhr.co.kr

---

## Step 4: 출근 체크 시도

**URL:** https://hrms.safeclaw.kr/hrms (모바일 or 태블릿 권장)

1. HRMS 메인 화면에서 **출근** 버튼 탭
2. GPS 위치 확인 팝업 → 허용
3. 출근 체크 완료 → 출근 기록이 `/app/attendance`에 자동 등록됨

**데스크탑에서도 가능:**
- `/app/attendance` → `+ New` → 직원명 / 날짜 / 상태(Present) 수동 입력

**GPS 출근 체크 사전 조건:**
- 직원에게 개별 계정 발급 필요 (`/app/user` → `+ New`)
- HR Manager 역할(role)이 아닌 Employee 역할 계정으로 로그인해야 출근 버튼 표시

---

## Step 5: 도움말 및 지원 채널

**즉시 지원:**
- 슬랙 채널 (베타 신청 시 초대 링크 전달)
- 이메일: abc@winhr.co.kr (평일 4시간 이내 응답)

**문서:**
- 운영자 매뉴얼: `docs/onboarding/operator_manual.md` (이 repo)
- 기능 맵 + 30분 이해 가이드: `docs/korea_hrms/feature_map_user_guide.md`
- 30분 검증 절차: `docs/korea_hrms_user_verification_30min.md`

**데모 데이터 초기화:**
- 테스트 데이터 정리가 필요하면 슬랙으로 요청 → 운영팀이 직접 초기화

---

## 다음 단계

퀵스타트 완료 후 권장 순서:

1. 회사 / 사업장 정보 세팅 (`/app/branch`, `/app/company`)
2. 직원 마스터 CSV import (운영팀 지원)
3. 페이롤 기본 세팅 (급여 항목, 급여 구조)
4. 첫 월 페이롤 마감 시험 실행
5. 임금명세서 발송 테스트
