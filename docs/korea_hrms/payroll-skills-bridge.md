# 급여 개인 스킬 ↔ Korea HRMS 엔진 브리지

개인 워크플로우(Claude Code 스킬, `~/.claude/skills/`)에 굳어진 한국 급여 실무 규칙과
`hrms/regional/south_korea/` 엔진 모듈의 계산 로직을 한 문서에서 대조한다.

**범위·주의**: 이 저장소는 public repo다. 아래 표에는 고객 사업장명·개인정보를 쓰지 않는다.
개인 스킬 경로는 항상 `~/.claude/skills/<스킬명>` 형태로만 표기하며, 원문 인용도 규칙·공식
부분만 옮긴다. 스킬 파일 자체는 읽기 전용이며 이 브리지 작업으로 수정하지 않는다.

## 1. 규칙 매핑 표

| 스킬 | 규칙(공식 원문) | HRMS 엔진 대응(파일:함수) | 정합 상태 |
|---|---|---|---|
| `~/.claude/skills/일용직세금` | 신고근무일 = MIN(실근무일, 7) — 7일 캡 후 일급 역산(`총지급액 ÷ 신고근무일`) | `daily_worker.py:calculate_daily_worker_payroll` | **엔진 미구현** — 함수는 `daily_wage`(일급)를 인자로 직접 받는다. "실근무일→7일 캡→역산"은 호출자 책임이며 엔진 내부에 캡·역산 로직이 없다. |
| `~/.claude/skills/일용직세금` | 과세표준 = MAX(일급 − 150,000, 0) | `daily_worker.py:_calc_daily_income_tax` (`taxable_base = daily_wage - DAILY_WORKING_DEDUCTION_AMOUNT`, `DAILY_WORKING_DEDUCTION_AMOUNT = 150_000`) | **일치** |
| `~/.claude/skills/일용직세금` | 결정세액 = 과세표준 × 2.7% (분리과세 6% × (1−55%)) | `daily_worker.py:_calc_daily_income_tax` (`_EFFECTIVE_TAX_RATE = 0.06 * (1-0.55) = 0.027`) | **일치** (요율) / **불일치**(절사 순서, 아래 참조) |
| `~/.claude/skills/일용직세금` | 절사 순서: 일별 결정세액은 **1원 단위**로만 truncate 후 신고근무일만큼 합산, **최종 납부세액을 10원 단위 절사**(`ROUNDDOWN(합계, -1)`) | `daily_worker.py:_calc_daily_income_tax` → `_floor10`, `calculate_daily_worker_payroll`(`income_tax_total = income_tax_per_day * days_worked`) | **불일치(기록, 테스트로 확정)** — 엔진은 **일별 세액을 먼저 10원 단위로 절사**(`_floor10`)한 뒤 일수를 곱해 합계를 낸다. 스킬은 일별 세액을 1원 단위로 남겨 여러 날을 합산한 다음 총액만 10원 절사한다. 실측 예(`hrms/tests/test_korea_skill_consistency.py::TestDailyWorkerDecidedTax::test_일급_215000원_4일_절사순서_불일치기록`로 값 고정): 일급 215,000원 — 과세표준 65,000 × 2.7% = 1,755원/일(정수, 부동소수점 오차 없음) × 4일. 스킬 방식: 1,755×4=7,020 → 최종 10원 절사 7,020원(이미 10원 배수). 엔진 방식: `_floor10(1,755.0)`은 `round(1755.0)=1755` → 10원 절사 1,750원(일별) × 4일 = 7,000원. **실제로 20원 차이**(스킬 7,020원 vs 엔진 7,000원). 절사가 갈리는 조건은 일별 세액(원단위)의 1의 자리가 5 이상일 때(예: 1,755 → 엔진은 1,750으로 내림) 발생하며, 여러 날 누적 시 최종 합계 차이가 배가된다. 참고로 일급 173,900원 × 4일은 173,900 ≤ 187,000 소액부징수 경계 이하라 양쪽 모두 0원으로 우연히 일치해 이 쟁점을 드러내지 못한다(테스트도 경계 위 일급으로 대체해 값을 확정). 어느 쪽이 맞는지는 노무사 판단 사항. |
| `~/.claude/skills/일용직세금` | 소액부징수: 원천징수세액(신고근무일 합산) < 1,000원 → 소득세 0 | `daily_worker.py:_calc_daily_income_tax` (`if daily_wage <= DAILY_TAX_EXEMPT_LIMIT(187_000): return 0.0`) | **불일치(기록)** — 엔진은 **일급 단위**로 187,000원 이하면 그 날의 세액을 무조건 0으로 처리한다. 스킬 규칙은 "여러 날 지급을 **합산**했을 때 1,000원 미만이면 0"이라, 일급이 160,000~186,999원인 날이 여러 날(예: 4일 이상) 누적되어 합계가 1,000원을 넘는 경우를 엔진은 포착하지 못한다(스킬: 4일째부터 과세 vs 엔진: 항상 0). |
| `~/.claude/skills/일용직세금` | 고용보험 = ROUNDDOWN(총지급액 × 0.9%, -1) | `daily_worker.py:calculate_daily_worker_payroll` (`applies_employment_insurance: bool`) | **엔진 미구현** — 엔진은 고용보험 **적용 여부(bool)**만 반환하고 보험료 금액 계산이 없다. 요율 0.9%는 `statutory_2026.py:EMPLOYMENT_INSURANCE_RATE_EMPLOYEE`에 별도로 존재(월급제 공용 상수)하나 `daily_worker.py`가 이를 호출하지 않는다. |
| `~/.claude/skills/일용직세금` | 지방소득세 = ROUNDDOWN(소득세 × 10%, -1) | `daily_worker.py:calculate_daily_worker_payroll` (`local_income_tax_total = _floor10(income_tax_total * _LOCAL_INCOME_TAX_RATE)`) | **일치** (요율·10원 절사 방식 동일; 단 `income_tax_total` 자체가 위 절사 순서 불일치의 영향을 받음) |
| `~/.claude/skills/급여관리`, `~/.claude/skills/급여검증` | 주휴수당 = 주 15h 이상 + 개근 시 `min(주소정근로시간, 40) ÷ 40 × 8` | `hourly_wage.py:weekly_holiday_allowance`, `hourly_wage.py:weekly_holiday_hours` | **일치** |
| `~/.claude/skills/퇴직정산` | 퇴직금 = max(평균임금, 통상임금) × 30 × (재직일수 / 365), 평균임금 = 3개월 임금총액 ÷ 3개월 총일수 | `severance_pay.py:calculate_severance_pay`, `severance_pay.py:calculate_average_wage` | **일치** |
| `~/.claude/skills/퇴직정산` | 통상시급 = 기본급 ÷ 209 (포괄임금 실무 규칙, 계약임금 아님) | 대응 함수 없음 | **엔진 미구현** — `hourly_wage.py`는 `hourly_rate`를 항상 외부 인자로 주입받으며, "기본급 ÷ 209"로 통상시급을 역산하는 로직이 south_korea 모듈 전체(`daily_worker.py`, `hourly_wage.py`, `severance_pay.py`, `statutory_2026.py`, `annual_leave.py`)에 없다(`grep 209` 결과 데이터 카탈로그 JSON만 매칭, 계산 코드 매칭 0건). `severance_pay.py:calculate_severance_pay`는 `ordinary_wage_per_day`를 호출자가 이미 계산해서 넘기는 구조라, 209 나눗셈 자체는 여전히 호출자(사업장별 스킬/운영) 책임으로 남는다. |
| `~/.claude/skills/퇴직정산` | 미사용연차수당 = 기본급 ÷ 209 × 8 × 미사용일수 (통상일급 × 일수) | 대응 함수 없음 (연차 **부여일수** 계산만 존재) | **엔진 미구현** — `annual_leave.py:calculate_annual_leave_entitlement`는 부여 연차 **일수**(entitlement days)만 계산하고, 미사용 연차를 금액으로 환산하는 로직(통상일급 곱셈)은 없다. |
| `~/.claude/skills/4대보험신고`, `~/.claude/skills/급여검증`(검증17/18) | 4대보험 요율(2026): 국민연금 4.75%, 건강보험 3.595%, 장기요양 13.14%(건강보험료 대비), 고용보험 0.9%, 만60세↑ 국민연금 면제 | `statutory_2026.py:calculate_pension`/`calculate_health_insurance`/`calculate_employment_insurance`, `PENSION_RATE_EMPLOYEE`/`HEALTH_RATE_EMPLOYEE`/`LONGTERM_CARE_RATE`/`EMPLOYMENT_INSURANCE_RATE_EMPLOYEE` | **일치** — 요율 값이 스킬 기술과 동일. 장기요양은 엔진이 `0.009448/0.0719 ≈ 13.1405%`로 계산(스킬 표기 13.14%와 반올림 차이만, 실질 동일). 이 상수들은 이미 `hrms/tests/test_korea_rate_single_source.py`가 `foreign_worker.py`·`leave_of_absence.py`와 어긋나지 않도록 단일소스 가드를 걸어 회귀를 방지한다. |
| `~/.claude/skills/급여관리`, `~/.claude/skills/퇴직정산` | 연차 산정: 1년 미만 매월 개근 1일(최대 11일), 1년 이상 15일, 3년 이상부터 2년마다 1일 가산(최대 25일) | `annual_leave.py:calculate_annual_leave_entitlement`, `first_year_monthly_accrual`, `anniversary_annual_entitlement` | **일치** |

## 2. 활용 가이드

HRMS로 급여 작업을 하다가 아래 상황이면 해당 개인 스킬을 참고한다(개인 스킬은 읽기 전용 참고 자료이며, HRMS 엔진 실행을 대체하지 않는다).

- 일용직 세액을 손으로 검산하고 싶을 때 → `~/.claude/skills/일용직세금`
- 월급여 처리 전체 흐름(근태→임금대장→검증)을 오케스트레이션하고 싶을 때 → `~/.claude/skills/급여관리`
- 만든 급여 파일이 헤더·인원·금액·수식오류·4대보험 요율까지 맞는지 종합 점검하고 싶을 때 → `~/.claude/skills/급여검증`
- 퇴사자의 퇴직금·퇴직소득세·중도퇴사 연말정산을 처리할 때 → `~/.claude/skills/퇴직정산`
- 퇴사월/연말 건강보험 보수총액 정산이 필요할 때 → `~/.claude/skills/건보정산`
- 근로기준법 제48조제2항 요건(구성항목·계산방법 명시)을 갖춘 임금명세서를 만들 때 → `~/.claude/skills/명세서생성`
- 4대보험 취득/상실/근로내용확인 신고서를 생성할 때 → `~/.claude/skills/4대보험신고`
- 급여대장을 세무대장으로 변환해 세무사에게 전달할 때 → `~/.claude/skills/세무변환`

## 3. 정합성 게이트

스킬 문서(위 규칙 원문)와 엔진 코드(`hrms/regional/south_korea/*.py`) 중 **어느 한쪽이라도 규칙이
바뀌면** 아래 테스트가 깨지도록 설계된다(Task 2 산출물):

```bash
python3 hrms/tests/test_korea_skill_consistency.py
```

이 테스트는 위 표의 "일치" 항목을 각각 assert하는 회귀 테스트이며, "불일치(기록)" 항목은
`Global Constraints`에 따라 두 값(엔진값 vs 스킬값)을 모두 명시한 채 **현재 엔진값을 assert**하고
주석으로 스킬값을 병기하는 방식으로 표현한다(`expectedFailure`나 조용한 skip이 아니다).

실제로 "불일치 기록 테스트"(엔진값 assert + 스킬값 주석 병기)가 있는 항목은 다음 3건뿐이다:

- 절사 순서 불일치 — `TestDailyWorkerDecidedTax::test_일급_215000원_4일_절사순서_불일치기록`
  (일급 215,000원 × 4일: 스킬 7,020원 vs 엔진 7,000원, 20원 차이)
- 소액부징수 판단 단위 불일치 — `TestDailyWorkerDecidedTax::test_일급_160000원_4일_합산_스킬규칙이면_과세_엔진은_0원_불일치기록`
  (일급 160,000원 × 4일: 스킬 1,080원 vs 엔진 0원)
- 고용보험 금액 계산 엔진 미구현 — `TestDailyWorkerLocalTaxRounding::test_고용보험_금액계산_엔진미구현_bool만_반환`
  (존재성만 기록: bool 필드만 있고 금액 필드 없음)

위 표의 나머지 "엔진 미구현" 항목 — **신고근무일 7일 캡 후 일급 역산**, **미사용연차수당(통상일급 환산)**
— 은 대응하는 기록 테스트가 없다(**기록 테스트 없음 — 표만**). 이 두 항목은 엔진에 대응 함수 자체가
없어 "엔진값 assert"가 성립하지 않으므로, 위 규칙 매핑 표에만 서술로 남기고 테스트로는 고정하지 않았다.
(단, "통상시급=기본급÷209 엔진 미구현"은 예외로 `TestOrdinaryHourlyWageReference`가 순수 참조
구현 + "대응 함수 없음" 확인 테스트를 갖고 있다.)

따라서:

- 엔진 계산 로직이 바뀌면 → assert가 깨져 "엔진이 스킬 규칙에서 이탈했다"는 신호가 된다.
- 개인 스킬(운영 규칙)이 바뀌면 → 사람이 이 문서·테스트의 주석을 갱신해야 계약이 다시 맞는다.

머지 게이트에 포함하려면:

```bash
bash scripts/run_korea_tests.sh
```

를 실행해 전체 그린을 확인한다(이 러너는 `hrms/tests/test_korea_*.py` 중
`importlib.util.spec_from_file_location` 패턴을 쓰는 framework-free 테스트를 전부 수집·실행하고,
온톨로지 그래프 검증까지 포함한다).
