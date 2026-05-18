# Korea HRMS 1-Month Launch Plan

> 목표: 1개월 안에 한국 중소사업장/다지점 사업장에 바로 쓸 수 있는 HRMS 베타를 런칭한다.

## 1) 결론
- 현재 레포는 Frappe/ERPNext/HRMS까지 설치 가능한 상태이며, 한국화는 아직 비어 있다.
- 가장 빠른 전략은 **코어 포크 최소화 + 한국 전용 설정/커스텀필드/급여 컴포넌트/번역/운영 템플릿**을 얹는 방식이다.
- 1개월 런칭 범위는 `인사기본정보 + 근태/휴가 + 연장근로 + 급여기초 + 한국어 UI + 한국 운영가이드`로 제한하는 것이 현실적이다.

## 2) 런칭 범위(MVP)
### 포함
1. 한국어 관리자/직원 UI
2. Employee 한국 필드
   - 주민등록번호 뒷자리는 저장 금지 또는 마스킹 정책
   - 생년월일
   - 휴대전화
   - 주소
   - 은행/예금주/계좌번호
   - 입사일/퇴사일/고용형태
3. 조직/근태
   - 사업장/부서/직무/직책
   - Shift Type
   - Attendance
   - Leave Policy
4. 급여 기초
   - 기본급
   - 식대
   - 직책수당
   - 연장/야간/휴일 가산용 컴포넌트
   - 4대보험/원천세는 1차 자동계산보다 수동/보조 입력 중심으로 출발
5. 문서/운영
   - 회사 세팅 체크리스트
   - 월마감 체크리스트
   - 샘플 급여구조

### 제외(1개월 내 무리)
- 한국 세법/4대보험 완전자동 계산 엔진
- 전자근로계약/전자서명 전체 플로우
- 정부기관 직접 연동
- 복잡한 퇴직금/평균임금 예외 계산 자동화

## 3) 현재 확인된 갭
1. `hrms/locale`에 한국어 번역 파일 없음
2. `hrms/regional`에는 India/UAE만 존재, 한국 regional setup 부재
3. 한국 급여 컴포넌트/퇴직금/연장근로 가이드 데이터 부재
4. country-specific onboarding 문서 부재

## 4) 4주 실행계획
## Week 1 — 기반 고정
- Docker/로그인 검증 완료
- 한국 런칭 범위 확정
- 한국 필수 데이터모델 목록 확정
- 번역 우선순위 200개 문구 추출
- 샘플 Company / Department / Shift / Leave 구조 설계

## Week 2 — 한국 기본 스캐폴드
- 한국어 번역 1차
- Employee/Company 커스텀 필드 정의
- Salary Component 한국 기본 세트 작성
- Holiday List / Leave Policy 샘플 작성
- 월마감 운영 가이드 작성

## Week 3 — 급여/근태 베타화
- 연장/야간/휴일 근로 처리 정책 반영
- 급여구조/급여명세서 한국식 표기 보강
- 관리자 테스트 시나리오 작성
- 실제 샘플 사업장 데이터 입력

## Week 4 — 파일럿/런칭 준비
- 운영자 UAT
- 오류 수정
- 초기 고객 온보딩 문서 작성
- 데모 계정/샘플 데이터 정리
- 런칭 체크리스트 점검

## 5) 우선 수정 파일 후보
- `hrms/locale/ko.po`
- `hrms/overrides/company.py` (regional 연결 검토 시)
- `hrms/regional/<korea-country-slug>/setup.py`
- `hrms/regional/<korea-country-slug>/data/salary_components.json`
- `hrms/hr/doctype/employee/...`
- `hrms/payroll/print_format/salary_slip_standard/...`
- `frontend/` 또는 `roster/` 내 한국어 라벨 노출 지점

## 6) 검증 기준
- Docker up 후 로그인 가능
- 관리자 주요 메뉴 한국어 노출
- Employee 생성/수정 가능
- Shift/Attendance/Leave 생성 가능
- Salary Component / Salary Structure 생성 가능
- 샘플 급여명세서 출력 가능

## 7) 운영 원칙
- 코어 로직 대수술보다 설정/fixtures/custom fields 우선
- 법적 계산은 초기엔 보조/체크리스트형으로 두고, 숫자 자동화는 검증 후 확장
- 주민번호 등 민감정보는 최소수집/마스킹/비저장 원칙 우선
