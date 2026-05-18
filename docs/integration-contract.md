# Korea Payroll Engine ↔ Frappe HRMS Integration Contract

> 목적: Frappe HRMS를 HR 백본으로 두고, 한국 급여자동화 엔진을 별도 SoT로 운영하기 위한 최소 통합 계약을 정의한다.

## 1. 결론

- Frappe HRMS는 **직원/조직/근태/휴가의 SoT**로 유지한다.
- 한국 급여자동화 엔진은 **급여 룰/계산/4대보험/원천세/명세 생성의 SoT**로 유지한다.
- 두 시스템은 **포크 통합이 아니라 API 계약으로 병렬 결합**한다.
- 주민등록번호/계좌번호 등 PII는 Frappe DB에 저장하지 않고 **privacy_broker 경유 조회**를 원칙으로 한다.

---

## 2. System of Truth (SoT) 분할

| 데이터 영역 | 단일 진실의 원천(SoT) | 비고 |
|---|---|---|
| 직원 마스터 | Frappe HRMS | Employee, Department, Branch, Company |
| 조직/부서/사업장 | Frappe HRMS | 운영/권한/UI 기준 |
| 근태/출퇴근/휴가 | Frappe HRMS | Attendance, Leave Application, Shift Assignment |
| 급여 룰/계산식 | 급여자동화 엔진 | 한국 법/보험/원천세 업데이트 독립 반영 |
| 4대보험/원천세 계산 결과 | 급여자동화 엔진 | 계산 후 Frappe로 push |
| 급여명세 결과 | 급여자동화 엔진 | Frappe는 조회/발급/감사 로그 용도 |
| 주민번호/계좌 등 PII | privacy_broker / secure store | Frappe 비저장 원칙 |

---

## 3. 설계 원칙

1. **Frappe 내부 급여 계산 로직에 한국 룰을 깊게 박아넣지 않는다.**
2. **급여 결과는 외부 엔진이 계산하고 Frappe는 수신/표시/추적한다.**
3. **PII는 저장하지 않고 참조 토큰/마스킹 값만 남긴다.**
4. **룰 엔진 변경은 Frappe 재배포 없이 독립 배포 가능해야 한다.**
5. **기존 Salary Slip을 완전 대체하지 말고, 1차는 확장/연결 계층으로 붙인다.**

---

## 4. 서버측 산출물 1 — 외부 급여엔진 수신용 스키마

### 4.1 권장 방식
1차는 **Custom DocType + Salary Slip 링크**로 간다.

이유:
- 코어 `Salary Slip` 직접 대수술보다 충돌이 적다.
- 한국 전용 데이터셋을 통째로 버전 관리하기 쉽다.
- 추후 Frappe/ERPNext 업그레이드 충돌을 줄일 수 있다.

### 4.2 신규 Custom DocType 제안

#### A. `Korea Payroll Result`
외부 급여엔진 계산 결과의 헤더 문서.

**목적**
- 월별 급여 계산 1건의 수신/상태/감사 추적
- `Salary Slip` 또는 별도 명세 문서와 연결

**권장 필드**

| fieldname | type | 설명 |
|---|---|---|
| payroll_result_id | Data (unique) | 외부 엔진 결과 ID |
| payroll_run_id | Data | 외부 엔진 실행 배치 ID |
| employee | Link(Employee) | Frappe 직원 ID |
| employee_name | Data / fetch | 표시용 |
| company | Link(Company) | 회사 |
| branch | Link(Branch) | 사업장 |
| department | Link(Department) | 부서 |
| pay_period_start | Date | 지급 대상 시작일 |
| pay_period_end | Date | 지급 대상 종료일 |
| pay_date | Date | 실제 지급일 |
| payroll_status | Select | Draft / Received / Posted / Error / Cancelled |
| currency | Link(Currency) or Data | KRW |
| gross_pay | Currency | 총지급액 |
| total_deductions | Currency | 총공제액 |
| net_pay | Currency | 실지급액 |
| taxable_income | Currency | 과세대상액 |
| non_taxable_income | Currency | 비과세액 |
| national_pension_employee | Currency | 국민연금 근로자 부담 |
| health_insurance_employee | Currency | 건강보험 근로자 부담 |
| long_term_care_employee | Currency | 장기요양 근로자 부담 |
| employment_insurance_employee | Currency | 고용보험 근로자 부담 |
| income_tax | Currency | 소득세 |
| local_income_tax | Currency | 지방소득세 |
| salary_slip | Link(Salary Slip) | 연결된 Frappe 급여명세 |
| source_engine | Data | 예: korea-payroll-engine |
| source_engine_version | Data | 룰셋/엔진 버전 |
| ruleset_version | Data | 법령/요율 버전 |
| privacy_token | Data | privacy_broker 참조 토큰 |
| pii_masked_account | Data | 마스킹된 계좌 표시값 |
| pii_masked_id | Data | 마스킹된 식별값 |
| raw_payload_json | Long Text / Code | 외부 응답 원문(JSON) |
| validation_errors | Long Text | 수신 검증 오류 |
| received_at | Datetime | 수신 시각 |
| posted_at | Datetime | Frappe 반영 시각 |

#### B. `Korea Payroll Result Item`
헤더의 child table. 지급/공제 항목 상세.

**권장 필드**

| fieldname | type | 설명 |
|---|---|---|
| item_type | Select | earning / deduction / employer_contribution / tax |
| item_code | Data | 외부 엔진 코드 |
| item_label | Data | 예: 기본급, 식대, 국민연금 |
| amount | Currency | 금액 |
| taxable | Check | 과세 여부 |
| display_order | Int | 표기 순서 |
| note | Small Text | 비고 |
| source_rule_ref | Data | 룰 참조 키 |

#### C. `Korea Payroll Result Attendance Summary`
헤더의 child table. 계산 근거가 된 근태 요약.

**권장 필드**

| fieldname | type | 설명 |
|---|---|---|
| work_date | Date | 기준일 |
| attendance_status | Data | Present / Leave / Half Day 등 |
| shift_type | Data | 교대 |
| regular_hours | Float | 소정근로 |
| overtime_hours | Float | 연장근로 |
| night_hours | Float | 야간근로 |
| holiday_hours | Float | 휴일근로 |
| leave_days | Float | 휴가 일수 |
| note | Small Text | 비고 |

### 4.3 Salary Slip 확장 방안
1차는 `Salary Slip`을 계산 엔진으로 쓰지 않고, **표시/링크 계층**으로 활용한다.

**Custom Field 제안 (Salary Slip)**

| fieldname | type | 설명 |
|---|---|---|
| custom_external_payroll_result | Link(Korea Payroll Result) | 외부 결과 링크 |
| custom_external_payroll_run_id | Data | 외부 배치 ID |
| custom_external_ruleset_version | Data | 법령/요율 버전 |
| custom_payroll_source | Select | Frappe / External Korea Engine |
| custom_pii_masked_account | Data | 마스킹 계좌 |
| custom_pii_masked_id | Data | 마스킹 식별값 |
| custom_net_pay_final | Currency | 외부 계산 최종 실지급액 |

**권고**
- `Salary Slip.earnings/deductions` child table 재활용은 가능하되, 1차는 `Korea Payroll Result Item`을 원본으로 둔다.
- Frappe 표준 급여 계산 버튼/프로세스와 혼동되지 않도록 UI 문구에 `External Payroll Result` 계층을 둔다.

---

## 5. 서버측 산출물 2 — 직원 마스터 Export API 설계

### 5.1 목적
외부 급여엔진이 급여 계산 전 최신 직원/조직 기준정보를 pull 할 수 있어야 한다.

### 5.2 엔드포인트 제안

**Method**: `GET`

**Frappe whitelisted path 제안**
- `/api/method/hrms.api.korea_integration.export_employees`

### 5.3 Query Params

| param | required | 설명 |
|---|---|---|
| company | optional | 회사 필터 |
| branch | optional | 사업장 필터 |
| modified_after | optional | 증분 동기화 기준시각 |
| employee | optional | 단일 직원 조회 |
| include_inactive | optional | 비활성 포함 여부 |
| page | optional | 페이지 |
| page_size | optional | 기본 100 |

### 5.4 응답 스키마

```json
{
  "data": [
    {
      "employee_id": "HR-EMP-0001",
      "employee_number": "E0001",
      "employee_name": "홍길동",
      "company": "Winners Co",
      "branch": "Seoul HQ",
      "department": "Operations",
      "designation": "Manager",
      "employment_type": "정규직",
      "date_of_joining": "2026-01-10",
      "relieving_date": null,
      "status": "Active",
      "holiday_list": "2026 Seoul Holiday",
      "default_shift": "Day Shift",
      "payroll_frequency": "Monthly",
      "bank_account_masked": "신한 110-***-123456",
      "privacy_token": "pbk_emp_xxx",
      "modified": "2026-04-25 11:00:00"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 100,
    "has_more": false
  }
}
```

### 5.5 포함 필드 최소 집합
- employee_id (`Employee.name`)
- employee_number
- employee_name
- company
- branch
- department
- designation
- employment_type
- date_of_joining
- relieving_date
- status
- holiday_list
- default_shift
- payroll_frequency (custom or derived)
- privacy_token
- bank_account_masked
- modified

### 5.6 제외 필드
- 주민등록번호 원문
- 계좌번호 원문
- 주민등록 뒷자리
- 세무/보험 신고식별자 원문

---

## 6. 서버측 산출물 3 — 근태 데이터 Export API 설계

### 6.1 목적
외부 급여엔진이 급여 계산 기간의 근태/휴가 데이터를 안정적으로 가져가야 한다.

### 6.2 Export 대상을 분리한다
근태는 한 엔드포인트에 전부 욱여넣지 말고 아래처럼 분리한다.

1. Attendance export
2. Leave Application export
3. Shift Assignment / Shift Type export
4. Holiday List export

### 6.3 Attendance API

**Method**: `GET`

**Path 제안**
- `/api/method/hrms.api.korea_integration.export_attendance`

**Query Params**
- `company`
- `branch`
- `employee`
- `from_date` (required)
- `to_date` (required)
- `modified_after`
- `page`
- `page_size`

**응답 예시**
```json
{
  "data": [
    {
      "attendance_id": "HR-ATT-2026-0001",
      "employee_id": "HR-EMP-0001",
      "attendance_date": "2026-04-01",
      "status": "Present",
      "shift_type": "Day Shift",
      "in_time": "2026-04-01 09:01:00",
      "out_time": "2026-04-01 18:34:00",
      "working_hours": 8.5,
      "late_entry": 0,
      "early_exit": 0,
      "overtime_type": null,
      "actual_overtime_duration": 0,
      "modified": "2026-04-01 19:00:00"
    }
  ]
}
```

### 6.4 Leave Application API

**Method**: `GET`

**Path 제안**
- `/api/method/hrms.api.korea_integration.export_leave_applications`

**응답 최소 필드**
- leave_application_id
- employee_id
- leave_type
- from_date
- to_date
- half_day
- half_day_date
- total_leave_days
- status
- description
- modified

### 6.5 Shift / Holiday API

**Shift Path 제안**
- `/api/method/hrms.api.korea_integration.export_shift_assignments`

**Holiday Path 제안**
- `/api/method/hrms.api.korea_integration.export_holidays`

**필요 이유**
- 연장/야간/휴일근로 계산은 근태 레코드만으로는 불완전할 수 있다.
- 교대/휴일 기준 원천이 함께 가야 외부 엔진이 법정 가산을 재현 가능하다.

---

## 7. 수신 API 설계 — 외부 급여결과 → Frappe Push

### 7.1 목적
외부 엔진이 계산 완료된 월별 결과를 Frappe로 push 한다.

### 7.2 엔드포인트 제안

**Method**: `POST`

**Path 제안**
- `/api/method/hrms.api.korea_integration.receive_payroll_result`

### 7.3 요청 스키마

```json
{
  "payroll_result_id": "kpay_2026_04_emp_0001",
  "payroll_run_id": "run_2026_04_batch_01",
  "source_engine": "korea-payroll-engine",
  "source_engine_version": "0.9.3",
  "ruleset_version": "kr-2026.04",
  "employee_id": "HR-EMP-0001",
  "company": "Winners Co",
  "branch": "Seoul HQ",
  "pay_period_start": "2026-04-01",
  "pay_period_end": "2026-04-30",
  "pay_date": "2026-05-05",
  "currency": "KRW",
  "gross_pay": 3200000,
  "total_deductions": 412340,
  "net_pay": 2787660,
  "taxable_income": 3000000,
  "non_taxable_income": 200000,
  "statutory_deductions": {
    "national_pension_employee": 135000,
    "health_insurance_employee": 106350,
    "long_term_care_employee": 9760,
    "employment_insurance_employee": 27000,
    "income_tax": 121000,
    "local_income_tax": 12100
  },
  "items": [
    {
      "item_type": "earning",
      "item_code": "BASE_PAY",
      "item_label": "기본급",
      "amount": 2800000,
      "taxable": 1,
      "display_order": 1
    },
    {
      "item_type": "earning",
      "item_code": "MEAL",
      "item_label": "식대",
      "amount": 200000,
      "taxable": 0,
      "display_order": 2
    }
  ],
  "attendance_summary": [
    {
      "work_date": "2026-04-01",
      "attendance_status": "Present",
      "regular_hours": 8,
      "overtime_hours": 0,
      "night_hours": 0,
      "holiday_hours": 0,
      "leave_days": 0
    }
  ],
  "privacy": {
    "privacy_token": "pbk_emp_xxx",
    "pii_masked_account": "신한 110-***-123456",
    "pii_masked_id": "900101-1******"
  },
  "raw_payload_json": {}
}
```

### 7.4 서버 검증 규칙
- `employee_id`가 Frappe에 존재해야 함
- `company`/`branch`가 employee와 논리적으로 맞아야 함
- 동일 `payroll_result_id` 중복 수신 방지
- `gross_pay >= net_pay`
- 항목 합계와 헤더 합계 일치 여부 검증
- PII 평문 포함 시 저장 거부 또는 마스킹 후 오류 로그

### 7.5 처리 결과
- `Korea Payroll Result` 생성 또는 업데이트
- 선택적으로 `Salary Slip` 연결/생성
- 감사 로그 기록
- 실패 시 validation_errors 저장

---

## 8. PII 경계 정책

### 8.1 저장 원칙
Frappe에는 아래만 허용한다.
- 직원 ID
- 이름
- 사번
- 마스킹된 표시값
- privacy token

Frappe에 아래는 금지한다.
- 주민등록번호 전문
- 계좌번호 전문
- 카드/세무/보험 식별자 전문

### 8.2 privacy_broker 연동 원칙
- 급여 계산 직전에만 secure store 조회
- 조회는 privacy token 기반
- 결과 저장 시 마스킹값만 사용
- 감사 로그에는 토큰과 요청 시각만 남김

---

## 9. 데이터 마이그레이션 순서

1. **직원 마스터 동기화**
   - 기존 사업장 YAML/기초 데이터 → Frappe Employee
2. **근태 입력 UI 전환**
   - 입력은 Frappe, 계산은 외부 엔진 유지
3. **급여 결과 Push 연동**
   - 외부 엔진 → `Korea Payroll Result` → 필요 시 Salary Slip 링크
4. **명세서 발급 UI 정리**
   - Frappe 또는 별도 프론트로 발급 계층 구성

---

## 10. 구현 우선순위 (서버측 Claude 작업지시)

### Phase 1 — 문서/스키마
1. `docs/integration-contract.md` 유지/보강
2. `Korea Payroll Result` / child table DocType 스키마 초안 작성
3. `Salary Slip` custom field 목록 작성

### Phase 2 — Export API
1. `hrms/api/korea_integration.py` 생성
2. `export_employees()` 구현
3. `export_attendance()` 구현
4. `export_leave_applications()` 구현
5. `export_shift_assignments()` / `export_holidays()` 구현

### Phase 3 — Import API
1. `receive_payroll_result()` 구현
2. 입력 검증/중복 방지/감사 로그 추가
3. `Korea Payroll Result` 저장
4. 필요 시 `Salary Slip` 링크

---

## 11. 오픈 이슈

1. `Employee` 원본은 HRMS 단독 DocType가 아니라 ERPNext 영역과 결합되어 있을 수 있으므로, 필드 매핑 구현 시 실제 런타임 메타 확인 필요
2. `Salary Slip`을 단순 링크 대상으로 둘지, 외부 결과로 일부 필드를 동기화할지 결정 필요
3. `privacy_broker` 호출 주체를 Frappe로 둘지, 외부 급여엔진 내부로 둘지 보안 흐름 확정 필요
4. 인증은 기본 Frappe API key/secret로 시작 가능하나, 추후 엔진 전용 integration user + IP 제한 검토 필요

---

## 12. 권고

당장 구현은 **커스텀 DocType + export/import API**까지로 제한하는 것이 맞다.
`Salary Slip`의 한국 완전자동화를 먼저 하려 들면 코어 충돌이 커진다.

즉, 서버측 1차 목표는 이것이다.
- Frappe는 HR 운영 SoT
- 외부 엔진은 급여 계산 SoT
- 둘 사이 계약은 `docs/integration-contract.md`와 `hrms/api/korea_integration.py`로 고정
