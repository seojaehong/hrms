# (주)노호 HR 시스템 사용가이드

> 시스템: Korea HRMS + AI HR 담당자 · 발행: 2026-07-05 · 문의: 노무법인 담당자

## 1. 접속 주소

| 용도 | 주소 |
|---|---|
| **메인 접속(직원·관리자 공통)** | https://noho.safeclaw.kr |
| 모바일 앱(PWA — 홈 화면에 추가 가능) | https://noho.safeclaw.kr/hrms |
| 관리자 데스크(전체 데이터·설정) | https://noho.safeclaw.kr/app |
| 로그인 | https://noho.safeclaw.kr/login |

- 관리자 계정: `admin@noho.kr` (임시 비밀번호는 별도 전달 — **최초 로그인 시 즉시 변경**)
- 구글·카카오 로그인: 활성화 예정 (키 등록 즉시 로그인 화면에 버튼 표시)
- 모바일: 위 PWA 주소를 스마트폰 브라우저로 열고 "홈 화면에 추가"하면 앱처럼 사용

## 2. 주요 화면 바로가기 (모바일/PC 공통 — 홈의 Quick Links에서도 진입)

| 기능 | 주소 (https://noho.safeclaw.kr 뒤에 붙임) |
|---|---|
| 급여 마감 센터 | `/hrms/dashboard/korea-payroll-closing` |
| 급여 검토 감사 로그 | `/hrms/dashboard/korea-payroll-review-audit-logs` |
| 근태 대시보드 | `/hrms/dashboard/korea-attendance` |
| 모바일 출퇴근 (GPS·셀카) | `/hrms/dashboard/korea-mobile-checkin` |
| 연차 대시보드 | `/hrms/dashboard/korea-annual-leave` |
| 결재 인박스 (승인/반려) | `/hrms/dashboard/korea-approval-inbox` |
| 임금명세서 | `/hrms/dashboard/korea-wage-statement` |
| 퇴직금 미리보기 | `/hrms/dashboard/korea-severance-preview` |
| 컴플라이언스 진단 | `/hrms/dashboard/korea-compliance` |
| AI HR 담당자 (채팅) | `/hrms/dashboard/korea-ai-chat` |
| 통합 검색 | `/hrms/search` |

관리자 데스크(`/app`)의 **"한국 HR" 워크스페이스**에서 직원·연차·근태·급여 원장 전체를 관리합니다.

## 3. 첫 사용 순서 (관리자)

1. `admin@noho.kr` 로그인 → 비밀번호 변경
2. 직원 확인: 데스크 → 한국 HR → Employee — **2026년 5월 급여 기준 직원 명단이 이미 등록되어 있습니다** (급여 구조·5월 명세서 포함, 확정 대장과 전원 금액 일치 검증 완료)
3. 신규 직원 추가: Employee 신규 생성 또는 CSV 일괄 등록(제공된 템플릿)
4. 매월 급여: 급여 구조가 연결된 직원은 Salary Slip 생성으로 명세서 산출 → 급여 마감 센터에서 검토
5. 명세서 PDF: 각 Salary Slip 화면에서 인쇄(PDF) — 이메일 자동 발송은 발신 메일 계정 연결 후 활성화

## 4. AI HR 담당자 사용법

**텔레그램에서** (연결된 채팅에서 바로):
- 노동법·인사 질문을 그대로 입력 → 법령 조문 근거와 함께 답변
  - 예: "연장근로 수당은 얼마를 줘야 하나요?" → 근기법 53·56조 인용 답변
- `/연차 입사일 기준일` → 연차 자동 산정 (예: `/연차 2024-03-02 2026-07-05`)
- `/퇴직금 입사일 퇴직일 일평균임금` → 퇴직금 계산 (근퇴법 8조)
- `/help` → 사용법 안내

**사이트 안에서**: 위 표의 "AI HR 담당자" 화면에서 동일 질문 가능.

⚠ AI 답변은 보조 자료입니다. 급여·징계 등 확정 판단은 반드시 담당 노무사 검토를 거칩니다. AI는 데이터 조회·계산·안내만 하며 급여 확정 등 실행 행위는 하지 않습니다.

## 5. 직원 안내 (배포용 요약)

- 접속: https://noho.safeclaw.kr/hrms (홈 화면에 추가 권장)
- 출퇴근: "모바일 출퇴근"에서 체크인/체크아웃
- 연차 신청: 홈 → Request Leave / 신청 현황은 결재 인박스에서 확인
- 명세서: "임금명세서" 화면에서 본인 명세서 확인

## 6. 운영·보안 안내

- 데이터는 사업장 전용 공간(독립 DB)에 저장되며 타 사업장과 완전히 분리됩니다
- 매일 02:00 자동 백업 + 월 1회 복구 훈련이 수행됩니다
- 시스템 상태는 5분 간격으로 자동 점검되며 이상 시 관리자에게 즉시 알림이 갑니다
- 주민등록번호 등 민감정보는 암호화 저장됩니다

## 7. 문의

- 시스템·급여 문의: 노무법인 담당자
- 장애 신고: 담당자 연락처 (시스템이 자동 감지하지만 이용 중 이상 발견 시 연락)
