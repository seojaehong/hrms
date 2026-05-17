# 노란봉투법 데모 HRMS — 30분 시연 시나리오

> Frappe HRMS Korea 한국화 Wave 4 데모 가이드  
> 대상: 공인노무사·HR 실무자·경영진 참관  
> 시간: 30분 (Q&A 5분 별도)

---

## Pre-flight Check (시연 10분 전)

### 1. 서비스 확인

```bash
# Frappe 사이트 정상 여부
bench --site hrms.localhost status

# 데모 데이터 시드 (idempotent — 이미 실행했다면 skip 가능)
bench --site hrms.localhost execute \
    hrms.regional.south_korea.demo_seed.seed_korea_demo

# 결과 확인: employee_count == 10, branch_count == 3 이면 OK
```

### 2. 데이터 확인 체크리스트

| 항목 | 확인 명령 | 기대값 |
|------|-----------|--------|
| 직원 수 | `frappe.db.count("Employee", {"company": "노란봉투법 데모"})` | 10 |
| 사업장 수 | `frappe.db.count("Branch")` | ≥ 3 |
| 부서 수 | `frappe.db.count("Department", {"company": "노란봉투법 데모"})` | ≥ 7 |
| 출근 레코드 (3개월) | `frappe.db.count("Attendance", {"company": "노란봉투법 데모"})` | ≥ 400 |
| 연차 배분 | `frappe.db.count("Leave Allocation", {"company": "노란봉투법 데모"})` | ≥ 8 |

### 3. 브라우저 설정

- URL: `http://hrms.localhost:8000/app`
- 로그인: `demo.hr.manager@node.pe.kr` / `DemoHRMS!2026`
- 해상도: 1920×1080 권장 (미러링 시 폰트 크기 확대)
- 탭 사전 열기: 직원목록 / 근태대시보드 / 연차현황 / 급여대장 / 폐쇄체크리스트

---

## 시연 흐름 (30분)

| # | 화면 | 시간 | 핵심 메시지 |
|---|------|------|------------|
| 1 | 회사·사업장 설정 | 2분 | 한국 3개 사업장, 사업장 코드·사업자등록번호 연동 |
| 2 | 직원 목록 | 3분 | 10명, 다양한 고용형태·부서·직급 |
| 3 | 근태 대시보드 | 5분 | 80% 룰 트리거 케이스 시각화 |
| 4 | 연차 현황 | 5분 | 1년 미만 월차 / 5년차 17일 / 10년차 19일 |
| 5 | 급여 구성 & 명세서 | 5분 | 4대보험 자동계산, 비과세 식대 분리 |
| 6 | 급여 마감 체크리스트 | 4분 | 사업장별 블로커 → 해소 흐름 |
| 7 | 한국 연차 신청서 Print | 2분 | 한글 양식, 결재란 자동 |
| 8 | API 수출 데모 | 2분 | `export_employee_master` JSON 응답 |
| 9 | Q&A 버퍼 | 2분 | — |

---

## 화면 1: 회사·사업장 설정 (2분)

**경로:** `설정 > 회사 > 노란봉투법 데모`

**액션**
1. 회사 상세 페이지 열기
2. 사업자등록번호 필드 `123-45-67890` 확인
3. `Branch` 목록으로 이동 → "서울 본사 / 강남 매장 / 부산 지사" 3개 사업장 확인
4. 부산 지사 클릭 → `custom_business_registration_number` 필드 확인

**시연 메시지**
> "Frappe HRMS의 Branch 마스터가 한국 사업장 코드 체계와 연동됩니다.
>  각 사업장별로 독립적인 근태·급여 마감을 처리할 수 있습니다."

**예상 결과:** Branch 3개, 각각 사업장 코드 표시

---

## 화면 2: 직원 목록 (3분)

**경로:** `HR > 직원 목록`

**액션**
1. 필터: 회사 = "노란봉투법 데모" → 10명 표시 확인
2. 정렬: 사업장별 그룹 (`서울 본사 5명 / 강남 매장 3명 / 부산 지사 2명` — 기존 2명 포함)
3. 직원 "강지수" 클릭 → 입사일 2016-03-01, 10년차 확인
4. 직원 "임동우" 클릭 → 입사일 2026-02-01, 파트타임 확인

**시연 메시지**
> "고용형태별로 정규직·파트타임·계약직을 구분하고,
>  입사 연도에 따라 연차 자격이 자동으로 달라집니다."

**예상 결과:** 10명 목록, 다양한 부서·직급·사업장

---

## 화면 3: 근태 대시보드 (5분)

**경로:** `HR > Korea Attendance Dashboard`  
*또는 PWA: `/hrms/kr-attendance`*

**액션**
1. 기간 선택: 2026-03 ~ 2026-05 (3개월)
2. "임동우" 필터 → 출근률 75% 표시 확인
   - 이 직원은 **80% 룰 미달** → 경고 배지 활성
3. "강지수" 필터 → 출근률 95% — 정상
4. 전체 직원 집계 탭 → 출근률 분포 차트

**시연 메시지**
> "근로기준법 제60조 80% 출근 요건 미달 직원이 자동으로 표시됩니다.
>  연차 지급 여부 판단에 바로 활용할 수 있습니다."

**예상 결과:**
- 임동우: 빨간 경고 (80% 미달)
- 김민준, 한유진: 노란 주의 (88%)
- 나머지: 초록 정상

**Fallback:** Attendance 목록 뷰 (`HR > Attendance`) 에서 직접 필터로 직원 + 월 조합

---

## 화면 4: 연차 현황 (5분)

**경로:** `HR > Korea Annual Leave Dashboard`  
*또는 PWA: `/hrms/kr-annual-leave`*

**액션**
1. 전체 직원 연차 잔여 일수 리스트 확인
2. "강지수" 클릭 → 19일 배분 (10년차: 15+4)
3. "김수연" 클릭 → 17일 배분 (5년차: 15+2)
4. "임동우" 클릭 → 월차(3일) — 1년 미만 월별 발생
5. "김민준" 클릭 → 6일 — 입사 6개월, 월차 6회
6. Leave Application 탭 → 승인된 연차 이력 확인

**시연 메시지**
> "근로기준법에 따라 1년 미만은 월차 자동 계산,
>  5년차는 17일, 10년차는 19일로 연차 days가 분리됩니다.
>  연차 신청서도 한국 표준 양식으로 출력할 수 있습니다."

**예상 결과:** 연도별 누적 배분 + 사용/잔여 분리 표시

---

## 화면 5: 급여 구성 & 명세서 (5분)

**경로:** `급여 > Salary Structure > KR Demo Salary Structure`

**액션**
1. 구성요소 확인:
   - Earning: 기본급 2,800,000 / 식대 200,000 / 직책수당 300,000 / 연장수당
   - Deduction: 국민연금 / 건강보험 / 장기요양 / 고용보험 / 원천세
2. 직원 "강지수" Salary Slip 생성 (Draft) → 자동 계산 확인
3. 식대 200,000원 → 비과세 분리 표시 확인
4. 실지급액 계산 흐름: 총지급 → 공제 → 실수령

**시연 메시지**
> "식대는 월 20만원까지 비과세로 자동 분리되고,
>  4대보험 요율은 매년 고시 기준으로 업데이트됩니다."

**예상 결과:** Gross ~3,450,000 / 4대보험+세금 ~305,000 / Net ~3,145,000

---

## 화면 6: 급여 마감 체크리스트 (4분)

**경로:** `Korea > 급여 마감 체크리스트`  
*또는 API: `/api/method/hrms.regional.south_korea.payroll_closing_api.get_worklist`*

**액션**
1. 5월 서울 본사 행 클릭 → 상태 `blocked` 확인
2. 블로커 카드 확인:
   - `attendance_not_ready` — KR-DEMO-ATT-ABSENT-2026-05-15 미제출
   - `expense_settlement_not_ready` — KR-DEMO-EXP-UNSETTLED-2026-05 미정산
3. 부산 지사 5월 행 → `draft_pending_human_approval` 상태 확인
4. 강남 매장 4월 행 → 동일 흐름

**시연 메시지**
> "사업장별 급여 마감 전 체크리스트가 자동 생성됩니다.
>  미제출 출근 기록, 미정산 경비가 블로커로 표시되어
>  실무자가 놓치지 않도록 돕습니다."

**예상 결과:** 3개 Draft 행, 사업장별 blocker 색상 구분

**Fallback:** Korea Payroll Closing Draft 목록 뷰에서 상태 컬럼 직접 표시

---

## 화면 7: 한국 연차 신청서 Print (2분)

**경로:** `HR > Leave Application > 임의 건 선택 > Print > Korea Leave Application`

**액션**
1. 연차 신청서 하나 선택 (또는 신규 Draft 생성)
2. Print Format: "Korea Leave Application" 선택
3. PDF 미리보기 → 신청인/결재란/휴가종류 확인

**시연 메시지**
> "결재 3단 양식(신청인 / 결재자 / 인사 확인)이 자동 생성됩니다.
>  한글 서체·법적 고지 문구도 포함되어 있습니다."

**예상 결과:** A4 PDF, 한글 양식 완성

---

## 화면 8: API 수출 데모 (2분)

**URL:**
```
http://hrms.localhost:8000/api/method/hrms.api.korea_integration.export_employee_master
?company=노란봉투법+데모&page=1&page_size=5
```

**액션**
1. 브라우저에서 URL 호출 (또는 curl)
2. JSON 응답 확인:
   - `data` 배열: 직원 정보 (PII 필드 없음)
   - `meta.has_more`: 10명 → 두 페이지

**시연 메시지**
> "외부 급여 엔진·노무 시스템과 REST API로 연동됩니다.
>  주민번호 등 PII는 응답에 포함되지 않도록 필터링됩니다."

**예상 결과:**
```json
{
  "data": [{"employee_id": "HR-EMP-00001", "employee_name": "강지수", ...}],
  "meta": {"page": 1, "page_size": 5, "has_more": true}
}
```

---

## 실패 대응 (Fallback 시나리오)

### F-1: 사이트 접속 불가

```bash
bench --site hrms.localhost restart
# 또는
sudo supervisorctl restart all
```

임시 대응: 스크린샷/녹화 영상으로 진행

### F-2: 데이터 없음 (직원 10명 미표시)

```bash
bench --site hrms.localhost execute \
    hrms.regional.south_korea.demo_seed.seed_korea_demo
```

완료 후 브라우저 새로고침

### F-3: Attendance Dashboard 로딩 오류

- PWA 대신 `HR > Attendance` 목록 직접 이동
- 필터: Company = 노란봉투법 데모 / Date Between 2026-03-01 ~ 2026-05-31
- 직원 "임동우" 필터 → 결근(Absent) 레코드 다수 확인

### F-4: Leave Allocation 미표시

- `HR > Leave Allocation` 목록에서 필터:
  `Employee = 강지수`, `Leave Type = Annual Leave`
- 새 레코드 수동 생성 시연 → `New Leaves Allocated = 19`

### F-5: Print Format 없음

```bash
bench --site hrms.localhost import-doc \
    hrms/regional/south_korea/print_format/korea_leave_application/korea_leave_application.json
```

### F-6: API 인증 오류

```bash
curl -s -X GET \
  "http://hrms.localhost:8000/api/method/hrms.api.korea_integration.export_employee_master" \
  -H "Authorization: token <api_key>:<api_secret>" | python3 -m json.tool
```

---

## FAQ Cheat Sheet

**Q. 주민등록번호는 어떻게 관리하나요?**
> A. Frappe DB에는 저장하지 않습니다. `rrn_masked` 필드(예: `920315-2******`)만 저장하고, 
>    실 주민번호는 별도 Privacy Broker 시스템에서 일회성 API 조회만 허용합니다.

**Q. 4대보험 요율이 바뀌면 어떻게 업데이트하나요?**
> A. Korea Insurance Rates DocType에 `effective_from` 날짜를 지정해 등록합니다.
>    시스템이 자동으로 가장 최신 요율을 적용합니다.

**Q. 연차 일수가 법에서 정한 것과 다르면 어떻게 수정하나요?**
> A. Leave Allocation에서 직원별로 `new_leaves_allocated` 값을 수동 수정할 수 있습니다.
>    또는 Leave Policy를 사업장별로 별도 설정하는 것을 권장합니다.

**Q. 80% 미달 직원에게 자동으로 연차를 차감할 수 있나요?**
> A. 현재 대시보드에서 경고 표시는 자동, 차감은 HR 담당자가 직접 처리합니다.
>    Wave 5에서 자동 차감 옵션 추가 예정입니다.

**Q. 외부 급여 엔진(사외 시스템)과 연동은 어떻게 하나요?**
> A. `export_employee_master` / `export_time_and_leave` API로 데이터를 내보내고,
>    `import_payroll_result`로 계산 결과를 다시 받아옵니다.
>    상세 계약은 `docs/integration/engine-side-contract.md` 참조.

**Q. 일용직 직원은 어떻게 처리하나요?**
> A. Employment Type을 `일용직`으로 설정하고, 일급 기준 Salary Structure를 별도 구성합니다.
>    `docs/korea/08-daily-workers.md`에 상세 규칙이 있습니다.

**Q. 퇴직금 계산도 되나요?**
> A. Wave 5 로드맵에 포함되어 있습니다.
>    현재는 `docs/korea/05-severance.md` 사양과 API 계약이 완성된 상태입니다.

**Q. 연말정산은 어떻게 처리하나요?**
> A. `import_year_end_settlement_result` API로 외부 계산 결과를 받아 Salary Slip에 연결합니다.
>    상세 규칙은 `docs/korea/04-year-end-settlement.md` 참조.

---

## 시연 후 정리

```bash
# (선택) 시연 데이터 초기화가 필요한 경우 — 주의: 비가역적
# bench --site hrms.localhost execute \
#     hrms.regional.south_korea.demo_seed.reset_demo  # Wave 5 예정

# 로그 확인
bench --site hrms.localhost show-log error
```

---

*문서 버전: Wave 4 | 작성: 2026-05-17*
