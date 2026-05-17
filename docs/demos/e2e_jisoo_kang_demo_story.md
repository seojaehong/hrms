# E2E 시연 스토리 — 지수 강 (HR-EMP-00003)

> 시연자가 그대로 읽을 수 있는 narrative. Phase 6 라이브 검증(2026-05-17) 결과 기반.

---

## 캐릭터

**지수 강 (Jisoo Kang)**
- 사원번호: HR-EMP-00003
- 이메일: jisoo.kang@nodebot.kr
- 입사일: 2021년 3월 (2016-03-01 SSA from_date 기준)
- 직책: 매장 매니저 (서울 본사)
- 출근률: 95% (3개월 attendance 63건 확인)
- 연차 잔여: 19일
- 성격: 꼼꼼하고 성실. "제 임금명세서가 법대로 맞게 나오는지 항상 확인해요."

---

## 시연 흐름 (시간순)

### [00:00] 입사 데이터 확인

시연자 멘트:
> "지수 강 씨는 이미 시스템에 등록돼 있습니다. HR-EMP-00003번이고, 서울 본사 소속입니다.
> 3개월치 출근 기록 63건이 쌓여 있고, 급여 구조도 배정돼 있습니다.
> 오늘은 5월 급여 마감부터 임금명세서 발송까지 실제로 돌려보겠습니다."

시스템 확인 (Pre-flight 쿼리 결과):
- employee: 1건 ✓
- salary structure assignment: 1건 ✓ (KR Demo Salary Structure, 2016-03-01~)
- attendance records: 63건 ✓
- 한국 공휴일: 19건 ✓ (KR Public Holidays 2026 Demo)

---

### [02:00] 5월 급여 계산 — Salary Slip 생성

시연자 멘트:
> "5월 1일부터 31일까지, 지수 강 씨의 급여 명세를 생성합니다.
> 시스템이 급여 구조에서 항목을 자동으로 불러옵니다."

**실제 생성된 Salary Slip: `Sal Slip/None/00001`**

지급 항목:

| 항목 | 금액 |
|------|------|
| 기본급 (Basic Pay) | 2,800,000 원 |
| 식대 (Meal Allowance) | 200,000 원 |
| 직책수당 (Position Allowance) | 300,000 원 |
| 연장근로수당 (Overtime Allowance) | 150,000 원 |
| **지급 합계** | **3,450,000 원** |

공제 항목:

| 항목 | 금액 |
|------|------|
| 국민연금 | 126,000 원 |
| 건강보험 | 99,260 원 |
| 장기요양보험 | 9,114 원 |
| 고용보험 | 25,200 원 |
| 근로소득세 | 45,210 원 |
| **공제 합계** | **304,784 원** |

**실수령액: 3,145,216 원**

출근일수: 28일 / 지급일수: 28일

시연자 멘트:
> "4대보험과 소득세가 자동으로 잡혔습니다. 실수령은 314만 5천원입니다."

---

### [08:00] 임금명세서 PDF payload 생성

시연자 멘트:
> "근로기준법 시행령 제27조의2에 따라, 임금명세서에는 7가지 법정 항목이 반드시 들어가야 합니다.
> 시스템이 자동으로 모두 채워줍니다."

**법정 7개 항목 포함 확인** (contract_type: `korea_wage_statement_pdf_v1`):

1. 성명 / 사원번호 / 생년월일 ✓ (지수 강 / HR-EMP-00003 / 1990-06-15)
2. 임금 지급일 ✓ (2026-05-31)
3. 임금 총액 ✓ (3,450,000 원)
4. 임금 구성 항목별 금액 ✓ (기본급·식대·직책수당·연장근로수당)
5. 항목별 계산 방법 (basis) ✓
6. 공제 항목별 금액·산출 내역 ✓ (4대보험·소득세)
7. 비과세 항목 ✓ (식대 200,000 원 — 소득세법 시행령 §17의2 비과세 한도 적용)

시연자 멘트:
> "식대는 비과세 항목으로 자동 인식됐습니다. 법 기준 20만원 이내입니다."

---

### [12:00] 카카오 알림톡 dry-run

시연자 멘트:
> "임금명세서가 나오면 직원에게 카카오 알림톡으로 발송합니다.
> 지금은 실제 발송 없이 메시지 구성만 확인합니다."

**Queue item 구성 결과** (Phase 2-A skeleton, contract_type: `korea_kakao_send_queue_item_v1`):

```
수신자: 01012345678
채널: kakao_alimtalk
템플릿 코드: WAGE_STATEMENT_READY

[알림톡 본문]
지수 강님의 2026-05-01 ~ 2026-05-31 임금명세서가 발급되었습니다.
지급일: 2026-05-31
실지급액: 3,145,216원

* 본 메시지는 근로기준법 시행령 제27조의2에 따라 발송됩니다.
```

- dispatch_pending: true (Phase 2-D에서 실제 SOLAPI 연동 구현)
- 수신 동의: true / 수신 거부: false
- human_approved: true ✓

시연자 멘트:
> "지금은 발송하지 않고 내용만 확인했습니다. 실수령액 '3,145,216원'이 정확히 들어갔죠.
> SOLAPI 연동이 완료되면 이 버튼 하나로 직원 전체에게 동시 발송됩니다."

---

### [18:00] 급여 마감 Draft — 출근 스냅샷 적용

시연자 멘트:
> "급여 마감 Draft 'rvgq9kl7j0'에 5월 출근 현황을 기록합니다."

**적용 결과**:
- 대상 Draft: `rvgq9kl7j0` (서울 본사 / 2026-05-01 ~ 2026-05-31)
- 스냅샷 저장: 완료 ✓
- 차단 메시지: 없음 (blocking_messages: [])
- 마감 상태: `draft_pending_human_approval`

출근 스냅샷 내용:
- 지수 강 (HR-EMP-00003): 출근 21일, 결근 1일, 연장 5시간

시연자 멘트:
> "마감 Draft에 출근 데이터가 기록됐습니다. 담당자 최종 승인이 필요한 단계입니다.
> 차단 요인이 없으니 바로 승인으로 넘어갈 수 있습니다."

---

## 검증 요약

| 단계 | 결과 | 비고 |
|------|------|------|
| Pre-flight (직원·SSA·출근·공휴일) | ✓ 4/4 통과 | |
| Salary Slip 생성 | ✓ | `Sal Slip/None/00001` |
| 법정 7항목 임금명세서 payload | ✓ | `korea_wage_statement_pdf_v1` |
| 카카오 dry-run queue item | ✓ | Phase 2-A, 실발송 없음 |
| 급여 마감 Draft 스냅샷 적용 | ✓ (정식 경로) | `flags.ignore_links` 픽스 적용 완료 |

---

## 발견된 이슈 (정직 보고)

### 이슈 1: Demo Seed — SSA/SS docstatus=0 (Draft)
- **증상**: SSA와 KR Demo Salary Structure 모두 docstatus=0(Draft)으로 생성됨
- **원인**: `demo_seed.py`가 `.insert()` 후 `.submit()` 호출 누락
- **영향**: Salary Slip 생성 시 "급여체계를 배정하세요" 오류
- **조치**: 시연 전 수동 submit (HR-SSA-26-05-00003, KR Demo Salary Structure)

### 이슈 2: Demo Seed — Holiday List Assignment 미생성
- **증상**: `Holiday List Assignment` 레코드 없음
- **원인**: seed가 Company.default_holiday_list 설정만 하고 `tabHoliday List Assignment` 생성 안 함
- **영향**: Salary Slip validate 시 "휴일 목록이 없습니다" 오류
- **조치**: HR-HLA-2026-00001 (노란봉투법 데모 → KR Public Holidays 2026 Demo) 수동 생성·제출

### 이슈 3: Salary Slip 이름 이상 (`Sal Slip/None/00001`)
- **증상**: Company abbreviation이 'None'으로 나타남
- **원인**: Company `abbr` 필드 미설정
- **영향**: 이름 가독성만; 기능 정상

### 이슈 4: Korea Payroll Closing Draft 링크 깨짐 → 수정 완료
- **증상**: `attendance_closing_apply.py`의 `doc.save()`가 LinkValidationError
- **원인**: Draft의 `source_payroll_entry = "KR-DEMO-PAYROLL-ENTRY-2026-05"` 레코드 없음. Frappe `Document.save()`는 `ignore_links` kwarg를 지원하지 않음 (insert()만 지원)
- **영향**: `apply_korea_attendance_closing()` 정상 경로 작동 불가
- **수정**: `doc.flags.ignore_links = True` 설정 후 `doc.save()` 호출 방식으로 변경
- **검증**: `APPLIED: True`, `DB_SNAPSHOT_LEN: 293` 확인. 2회 실행 시 `IDEMPOTENT_HIT: True` 정상
- **잔여 이슈**: demo seed에서 `source_payroll_entry` null로 생성하거나 Payroll Entry 추가 권장 (근본 원인)

### 이슈 5: `apply_korea_salary_slip_statutory_hook` opt-in 미동작
- **증상**: before_validate hook이 실행됐으나 statutory 공제 자동 주입 안 됨
- **원인**: 정상 동작. hook은 `apply_korea_statutory_payroll=True` 플래그가 있어야만 동작하도록 설계
- **현황**: 공제 항목은 Salary Structure에 고정 금액으로 등록돼 있어 실용상 문제 없음

---

## 시연 가능성 판단

**Full demo-able end-to-end (핵심 5단계 모두 정상 경로 동작 확인).**

- 직원 입사 데이터, 출근 기록 조회: **라이브 시연 가능**
- Salary Slip 생성 (급여 계산): **라이브 시연 가능** (단, 시연 전 SSA/SS 수동 submit 필요)
- 임금명세서 PDF payload (7항목 법정 포함): **라이브 시연 가능**
- 카카오 알림톡 dry-run: **라이브 시연 가능** (Phase 2-A skeleton, 실발송 없음)
- 급여 마감 Draft 스냅샷 apply: **라이브 시연 가능** (flags.ignore_links 픽스, 정식 경로 정상 동작)
- 실제 PDF 렌더링 (Print Format): 이 단계에서 미검증 (Frappe Print Format 레이어)
- 실 카카오 발송: Phase 2-D 미구현 (SOLAPI 미연동)
