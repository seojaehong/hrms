# 4대보험 고지 대사 실무 가이드

> 매월 공단(국민연금·건강보험·고용보험) EDI 고지내역을 우리 엔진 계산값과 **1원 단위로 대사**하는 절차.
> 계산·조회 전용 — 어떤 데이터도 저장하지 않는다. 차이·누락·매칭실패를 절대 숨기지 않는다.
>
> 관련 코드
> - 파서: `hrms/regional/south_korea/insurance_notice_parser.py`
> - 대사 API: `hrms/regional/south_korea/insurance_reconciliation_api.py`
> - 대사 코어: `hrms/regional/south_korea/insurance_reconciliation.py`

---

## 왜 필요한가 — 쿠우쿠우 사례

신규 입사자의 국민연금은 공단이 **소득월액 × 4.5%(근로자부담)** 로 고지하는데, 입사월 취득 시점·소득월액 산정 기준이 우리 계산과 어긋나면 몇천~몇만 원 차이가 생긴다.

실제로 쿠우쿠우 한 지점에서 **신규입사자 국민연금을 4.75%로 역산**해 공제하는 바람에 **21,230원이 과다공제**된 적이 있다. 당시엔 사람이 급여대장을 눈으로 훑다가 **뒤늦게** 발견했다.

→ 자동 대사(`reconcile_period_from_notice_file`)를 돌렸다면, 그 달 마감 직후 `diffs`에 해당 직원의 국민연금 `delta`가 **즉시** 떴을 것이다. 사람의 눈이 아니라 규칙이 잡는다.

---

## 전체 흐름

```
공단 EDI 고지내역 xlsx 다운로드
        │
        ▼
column_map 작성 (엑셀 컬럼 레터 → 표준 필드)
        │
        ▼
reconcile_period_from_notice_file(year, month, file_path, column_map, company, tolerance)
   ├─ parse_notice_xlsx        : xlsx → 고지 표준행 + 파싱 errors
   ├─ Employee 조회 + 매칭       : match_notice_to_employees (주민번호→이름 순)
   └─ reconcile_period_contributions : 그 달 제출 급여 슬립 공제 vs 고지 대사
        │
        ▼
결과 해석: summary_ko / diffs / unmatched / ambiguous / parse_errors
```

---

## 1단계 — 공단 EDI에서 고지내역 xlsx 다운로드

각 공단 EDI(4대사회보험 정보연계센터 또는 개별 공단)에서 해당 귀속월의 **고지내역/부과내역**을 엑셀(xlsx)로 내려받는다. 보통 직원별로 국민연금·건강보험·장기요양·고용보험 부과액이 열로 나열된다.

> ⚠️ 이 기능은 **실제 공단 서식을 절대 가정하지 않는다.** 공단·EDI·다운로드 시점마다 컬럼 순서가 다르므로, 컬럼 위치는 다음 단계의 `column_map`으로 전부 주입한다.

---

## 2단계 — column_map 작성

### 컬럼 레터 확인법

1. 내려받은 xlsx를 엑셀로 연다.
2. 맨 위 **열 머리글(A, B, C, …)** 을 본다. 필요한 값이 어느 열에 있는지 레터를 적는다.
   - 예: 이름이 B열, 국민연금이 E열, 건강보험이 F열, 장기요양이 G열, 고용보험이 H열.
3. 데이터가 시작하기 직전의 **헤더 행 번호**를 확인한다(보통 1행이 헤더면 데이터는 2행부터). 헤더가 여러 줄이면 마지막 헤더 행 번호를 `header_row`로 준다.

### column_map JSON 예시

```json
{
  "match_key": "B",
  "national_pension": "E",
  "health_insurance": "F",
  "long_term_care_insurance": "G",
  "employment_insurance": "H"
}
```

- **`match_key`** (필수): 직원을 식별할 값의 컬럼. **주민번호**(하이픈 포함/미포함 13자리) 또는 **이름** 문자열이 있는 열.
- 금액 키는 **반드시 표준 필드명**을 쓴다(대사 코어 `CONTRIBUTION_FIELDS`와 맞아야 함):
  - `national_pension` (국민연금)
  - `health_insurance` (건강보험)
  - `long_term_care_insurance` (장기요양보험) — `long_term_care` 아님, `_insurance` 접미사 주의
  - `employment_insurance` (고용보험)
- 고지 xlsx에 없는 보험 컬럼은 `column_map`에서 빼면 된다(있는 것만 대사).

> 금액 셀은 `"1,234,560 원"`처럼 콤마·공백·'원' 표기가 있어도 자동으로 `1234560` 정수로 정리된다. 소수부가 있거나 숫자가 아닌 셀은 숨기지 않고 `parse_errors`로 노출된다.

---

## 3단계 — 원커맨드 대사 (bench console)

`bench --site <사이트> console` 에서:

```python
from hrms.regional.south_korea.insurance_reconciliation_api import (
    reconcile_period_from_notice_file,
)

result = reconcile_period_from_notice_file(
    year=2026,
    month=6,
    file_path="/home/frappe/files/공단고지_202606.xlsx",
    column_map={
        "match_key": "B",
        "national_pension": "E",
        "health_insurance": "F",
        "long_term_care_insurance": "G",
        "employment_insurance": "H",
    },
    company="쿠우쿠우 강남점",   # 선택 — Employee·Salary Slip 필터
    tolerance=0,                  # 기본 0 = 1원 단위 규칙
)

# 사람이 읽는 1줄 요약
print(result["summary_ko"])

# 차이 상세
for d in result["reconciliation"]["diffs"]:
    print(d["employee"], d["label"], "계산", d["computed"], "고지", d["notified"], "차이", d["delta"])

# 매칭·파싱 이슈 (숨기지 않음)
print("파싱오류:", result["parse_errors"])
print("미매칭:", result["unmatched"])
print("동명이인 모호:", result["ambiguous"])
```

`column_map`은 JSON **문자열**로 줘도 된다(내부에서 `json.loads`). `frappe` 환경(급여 슬립·직원 조회)에서만 동작한다.

---

## 4단계 — 결과 해석

`result` 구조:

```python
{
  "period": "2026-06",
  "employee_count": 42,                # 그 달 제출된 급여 슬립 수
  "reconciliation": {
    "ok": False,                       # 차이·누락 하나라도 있으면 False
    "diffs": [
      {"employee": "HR-EMP-0007", "field": "national_pension",
       "label": "국민연금", "computed": 135000, "notified": 156230,
       "delta": -21230},              # delta = 계산 - 고지 (음수 = 고지가 더 큼)
      ...
    ],
    "missing_in_notified": ["HR-EMP-0031"],   # 우리에겐 있는데 고지에 없음
    "missing_in_computed": ["HR-EMP-0044"],   # 고지에 있는데 우리 계산에 없음
    "totals": {"national_pension": {"computed": ..., "notified": ..., "delta": ...}, ...}
  },
  "summary_ko": "고지 대사 불일치 — 차이 3건(과다 1·과소 2, 합계 -18,400원)",
  "unmapped_deductions": [...],        # 4대보험 아닌 공제 항목(정보)
  "parse_errors": [                    # 금액 파싱 불가 셀
    {"row": 5, "column": "E", "value": "미상", "reason": "금액이 숫자가 아닙니다: '미상'"}
  ],
  "unmatched": [ {"match_key": "...", ...} ],   # 어떤 직원과도 매칭 안 된 고지행
  "ambiguous": [ {"row": {...}, "candidates": [ {...}, {...} ]} ]  # 동명이인
}
```

해석 가이드:

| 항목 | 의미 | 조치 |
|------|------|------|
| `summary_ko` | 사람이 읽는 1줄 요약 | 먼저 이걸 본다 |
| `diffs[].delta` | `계산 - 고지`. **양수** = 우리가 더 걷음(과다공제 의심), **음수** = 고지가 더 큼 | 절대값 큰 순으로 정렬돼 있음 — 위에서부터 확인 |
| `missing_in_notified` | 우리 급여엔 공제 있는데 공단 고지에 없음 | 취득신고 누락/지연 여부 확인 |
| `missing_in_computed` | 공단 고지엔 있는데 우리 계산에 없음 | 급여 슬립 미제출/퇴사자 여부 확인 |
| `parse_errors` | 고지 xlsx 셀이 숫자로 안 읽힘 | column_map 컬럼 레터·헤더행 재확인 |
| `unmatched` | `match_key`로 직원을 못 찾음 | 이름 표기 차이 / rrn_masked 미등록 확인 |
| `ambiguous` | 이름 동명이인 2명 이상 | **자동 배정 안 함** — 주민번호로 구분하거나 수동 확인 |

### 매칭 규칙 (참고)

`match_notice_to_employees`의 우선순위:
1. `match_key`가 **주민번호 형태**(13자리)면 → Employee의 `rrn_masked` 앞 7자리(`YYMMDD-G`)와 대조.
2. 주민번호로 못 찾으면 → **이름 정확 일치**(양쪽 공백 전부 제거 후 비교).
3. 이름이 2명 이상이면 `ambiguous`, 아무도 없으면 `unmatched`. **추측 배정은 하지 않는다.**

> 정확도를 높이려면 고지 xlsx의 `match_key`를 **주민번호 열**로 잡는 것이 가장 안전하다(동명이인 문제 회피).

---

## CODEF 연동 시 달라지는 것

지금은 공단 EDI에서 xlsx를 **수동 다운로드**하고 `column_map`으로 컬럼을 맞춰준다. 향후 **CODEF(금융/공공 API)** 연동이 붙으면:

| 지금 (xlsx 수동) | CODEF 연동 후 |
|------------------|----------------|
| EDI에서 xlsx 직접 다운로드 | API로 고지내역 **자동 수집** |
| `column_map` 작성 필수 | `column_map` **불필요** (응답 필드가 고정 스키마) |
| `parse_notice_xlsx`로 파싱 | API 응답에서 `notified` 표준행 **직접 구성** |
| `reconcile_period_from_notice_file` | `reconcile_period_contributions`에 `notified`를 바로 주입 |

즉 대사 **코어**(`reconcile_period_contributions` / `summarize_reconciliation_ko`)는 그대로 재사용하고, 앞단의 "고지내역을 표준행으로 만드는 부분"만 xlsx 파서 → API 수집기로 교체된다.

---

## 회귀·검증

기능 자체의 테스트(참고):

```bash
python3 hrms/tests/test_korea_insurance_notice_parser.py
python3 hrms/tests/test_korea_insurance_reconciliation_api.py
python3 hrms/tests/test_korea_insurance_reconciliation.py
```
