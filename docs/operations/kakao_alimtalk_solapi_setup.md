# 카카오 알림톡 SOLAPI 셋업 가이드

HRMS Korea — 알림톡 발송 연동 실무 가이드 (2026 기준)

---

## 개요

HRMS Korea는 임금명세서 발행, 휴가 승인/반려, 급여 마감, 컴플라이언스 알림, 계약 갱신, 근태 수정 알림을 카카오 알림톡으로 발송합니다.
발송 채널은 **SOLAPI** (공식 카카오 알림톡 공식 대행사) 를 사용합니다.
실제 카카오 API 직접 호출 없이 SOLAPI HTTP API를 경유합니다.

---

## 1단계: 카카오 비즈니스 채널 개설

### 1-A. channels.kakao.com 접속

1. https://business.kakao.com → 카카오 비즈니스 채널 신청
2. 카카오 계정 로그인 → "채널 만들기"
3. 채널 종류: **비즈니스 채널** (알림톡 발송 전용 채널)

### 1-B. 필요 서류

| 서류 | 비고 |
|---|---|
| 사업자등록증 | 법인/개인사업자 모두 가능 |
| 통신판매업 신고증 | 온라인 서비스 제공 시 필요 (없으면 생략 가능) |
| 채널 프로필 이미지 | 정방형, 최소 640x640px |

> **친구톡 1,000명 제한 없음**: 알림톡은 거래 관계에 있는 수신자(근로자 등)에게만 발송하므로 친구톡 친구 수와 무관합니다.

### 1-C. 발신 프로필 등록 (pf_id 발급)

카카오 비즈니스 채널이 심사를 통과하면 **발신 프로필 ID (pf_id)** 가 발급됩니다.
형식 예: `PF_XXXXXXXXXXXXXXXXXX`

이 값을 환경변수 또는 HRMS 설정에 등록합니다 (4단계 참조).

---

## 2단계: SOLAPI 가입 및 API 키 발급

### 2-A. SOLAPI 가입

1. https://solapi.com → 회원가입 (사업자 인증 권장)
2. 좌측 메뉴: **알림톡 관리** → 발신 프로필 연동

### 2-B. API 키 발급

1. 우측 상단 프로필 → **API 키 관리**
2. "새 API 키 발급" → **API Key** 와 **API Secret** 복사
3. 키는 절대 코드에 하드코딩 금지 — 환경변수로만 관리

### 2-C. 발신 프로필 등록

1. SOLAPI 콘솔 → **카카오 알림톡** → **발신 프로필 관리**
2. "발신 프로필 추가" → 카카오 채널 검색 또는 pf_id 직접 입력
3. 연동 완료 후 `pfId` 확인

### 2-D. 비용 안내 (2026 기준)

| 채널 | 단가 | 비고 |
|---|---|---|
| 알림톡 | **8.4원/건** | 부가세 별도 |
| 친구톡 (텍스트) | 15원/건 | 마케팅용 |
| SMS 대체 발송 | 20원/건 | 알림톡 수신 거부 시 자동 fallback |

> 예산 계산: 직원 100명 × 월 3회 (명세서 + 휴가 + 기타) = 월 약 **2,520원**

---

## 3단계: 알림톡 템플릿 등록

HRMS Korea 표준 템플릿 7종을 SOLAPI 콘솔에서 등록합니다.

### 3-A. 등록 절차

1. SOLAPI 콘솔 → **알림톡 관리** → **템플릿 관리** → "템플릿 추가"
2. 아래 표의 각 템플릿을 순서대로 등록
3. 카카오 검수 신청 → 승인까지 **1~3 영업일** 소요

### 3-B. 표준 템플릿 7종

각 템플릿의 내용은 `hrms/regional/south_korea/data/kakao_alimtalk_templates.json` 파일을 기준으로 합니다.
변수 형식은 `#{변수명}` (카카오 알림톡 표준).

| template_id | 제목 | 변수 | 트리거 |
|---|---|---|---|
| `korea_wage_statement` | 임금명세서 발행 알림 | employee_name, period, total_amount, link | Salary Slip 제출 |
| `korea_leave_approved` | 휴가 승인 알림 | employee_name, leave_type, from_date, to_date, leave_days, approver_name | Leave Application Approved |
| `korea_leave_rejected` | 휴가 반려 알림 | employee_name, leave_type, from_date, to_date, approver_name, reason | Leave Application Rejected |
| `korea_payroll_closing` | 급여 마감 안내 | company_name, period, closing_datetime, employee_count, total_amount | Payroll Closing 마감 전 |
| `korea_compliance_alert` | 노무 컴플라이언스 알림 | company_name, alert_title, alert_description, due_date, contact_info | 컴플라이언스 이벤트 발생 |
| `korea_contract_renewal` | 근로계약 갱신 안내 | employee_name, expiry_date, confirm_deadline, hr_contact | 계약 만료 D-30/D-7 |
| `korea_attendance_correction` | 근태 수정 처리 완료 | employee_name, correction_date, correction_detail, processor_name, processed_at | 근태 수정 완료 |

### 3-C. 템플릿 카테고리 (카카오 분류)

모든 HRMS 알림톡 템플릿은 **"업무 안내"** 카테고리로 등록합니다.

---

## 4단계: HRMS 환경변수 등록

### 4-A. Frappe site_config 방식 (권장)

```bash
bench --site hrms.localhost set-config solapi_api_key "YOUR_API_KEY"
bench --site hrms.localhost set-config solapi_api_secret "YOUR_API_SECRET"
bench --site hrms.localhost set-config kakao_pf_id "PF_XXXXXXXXXXXXXXXXXX"
```

### 4-B. 환경변수 방식

```bash
export SOLAPI_API_KEY="YOUR_API_KEY"
export SOLAPI_API_SECRET="YOUR_API_SECRET"
```

> **우선순위**: 환경변수 → Frappe site_config 순으로 탐색합니다.
> 자격증명이 없으면 자동으로 dry-run 모드로 전환됩니다.

### 4-C. 등록 확인

```bash
bench --site hrms.localhost execute hrms.regional.south_korea.kakao_notification.get_kakao_credentials
# 반환값: {"api_key": "...", "api_secret": "..."}  ← None 이면 미등록
```

---

## 5단계: 발송 검증 (dry-run → 실제 발송)

### 5-A. dry-run 검증 (발송 없이 preview + 비용 추정)

```bash
bench --site hrms.localhost execute \
  hrms.regional.south_korea.kakao_notification.send_kakao_alimtalk \
  --kwargs '{
    "pf_id": "PF_XXXXXXXXXXXXXXXXXX",
    "template_id": "korea_wage_statement",
    "to": "010****5678",
    "template_variables": {
      "employee_name": "홍길동",
      "period": "2026-05",
      "total_amount": "3,000,000",
      "link": "https://hrms.example.com/payslip/SS-001"
    },
    "human_approved": true,
    "dry_run": true
  }'
```

기대 응답:

```json
{
  "contract_type": "korea_kakao_alimtalk_send_v1",
  "sent": false,
  "dry_run": true,
  "cost_estimate_krw": 8.4,
  "mock_response": {"messageId": "DRY-RUN-...", "statusCode": "2000"},
  "masked_to": "010-****-5678",
  "reason": "dry_run_requested"
}
```

### 5-B. 실제 발송 (본인 휴대폰 테스트)

```bash
bench --site hrms.localhost execute \
  hrms.regional.south_korea.kakao_notification.send_kakao_alimtalk \
  --kwargs '{
    "pf_id": "PF_XXXXXXXXXXXXXXXXXX",
    "template_id": "korea_wage_statement",
    "to": "010YOURPHONE",
    "template_variables": {
      "employee_name": "테스트",
      "period": "2026-05",
      "total_amount": "0",
      "link": "https://hrms.example.com"
    },
    "human_approved": true,
    "dry_run": false
  }'
```

성공 시 `sent: true`, `message_id: "MSG-..."` 반환.

---

## 6단계: 발송 이력 및 비용 추적

### 현재 구조 (Phase 2-C)

발송 이력은 Frappe **Comment** 형태로 Salary Slip / Leave Application 문서에 첨부됩니다.
delivery audit event 구조(`build_kakao_delivery_audit_event`)로 재시도/성공/실패 상태를 기록합니다.

조회 방법:

```python
# 발송 대기 Comment 목록
import frappe
comments = frappe.get_all(
    "Comment",
    filters={"content": ["like", "%카카오 알림톡%"]},
    fields=["reference_doctype", "reference_name", "content", "creation"],
    order_by="creation desc",
    limit=100,
)
```

### Phase 2-D (예정): DocType 프로모션

발송 Comment → `Korea Kakao Send Log` DocType 으로 승격 예정.
월별 비용 집계, 재시도 관리, 수신 거부 목록 관리 기능 포함.

---

## 7단계: SMS 대체 발송 (Fallback) — 설계 예정

> **현재 상태**: Phase 2-D 설계 예정. 아직 구현되지 않았습니다.

알림톡 발송 실패(수신 거부, 채널 오류 등) 시 SMS 자동 대체 발송 흐름:

```
send_kakao_alimtalk() → sent=False, reason="send_error: ..."
  → SMS fallback 큐 등록 (build_sms_fallback_queue_item — Phase 2-D)
  → SOLAPI SMS /messages/v4/send 발송
  → 단가: 20원/건
```

구현 시 `notification_dispatcher.py` 의 `on_salary_slip_submit` 에 fallback 분기를 추가합니다.

---

## 장애 대응

| 상황 | 원인 | 조치 |
|---|---|---|
| `no_credentials_dry_run` | API 키 미등록 | 4단계 재확인 |
| `Solapi HTTP 400` | 템플릿 미등록 또는 변수 오류 | 3단계 템플릿 검수 완료 확인 |
| `Solapi HTTP 401` | API 키/시크릿 불일치 | 2-B 재발급 |
| `invalid_pf_id` | 발신 프로필 미연동 | 2-C 발신 프로필 등록 확인 |
| `human_approval_required` | human_approved=False | True 로 변경 후 재호출 |

---

## 참고 링크

- SOLAPI 공식 문서: https://docs.solapi.com
- 카카오 비즈니스: https://business.kakao.com
- 알림톡 템플릿 가이드: https://kakaobusiness.gitbook.io/main/bizmessage/alimtalk
- HRMS 코드: `hrms/regional/south_korea/kakao_notification.py`
- 템플릿 카탈로그: `hrms/regional/south_korea/data/kakao_alimtalk_templates.json`
