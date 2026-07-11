# 급여 개인 스킬 ↔ Korea HRMS 엔진 브리지

개인 워크플로우(Claude Code 스킬, `~/.claude/skills/`)에 굳어진 한국 급여 실무 규칙과
`hrms/regional/south_korea/` 엔진 모듈의 계산 로직을 한 문서에서 대조한다.

**범위·주의**: 이 저장소는 public repo다. 아래 표에는 고객 사업장명·개인정보를 쓰지 않는다.
개인 스킬 경로는 항상 `~/.claude/skills/<스킬명>` 형태로만 표기하며, 원문 인용도 규칙·공식
부분만 옮긴다. 스킬 파일 자체는 읽기 전용이며 이 브리지 작업으로 수정하지 않는다.

## 1. 규칙 매핑 표

| 스킬 | 규칙(공식 원문) | HRMS 엔진 대응(파일:함수) | 정합 상태 |
|---|---|---|---|
| `~/.claude/skills/일용직세금` | 신고근무일 = MIN(실근무일, 7) — 7일 캡 후 일급 역산(`총지급액 ÷ 신고근무일`) | `daily_worker.py:reporting_basis` | **일치 (2026-07-11 엔진 구현)** — `reporting_basis(total_payment, actual_days)`가 캡·역산을 수행. `calculate_daily_worker_payroll`은 여전히 일급을 직접 받으므로 신고 플로우에서 이 함수로 선처리. |
| `~/.claude/skills/일용직세금` | 과세표준 = MAX(일급 − 150,000, 0) | `daily_worker.py:_calc_daily_income_tax` (`taxable_base = daily_wage - DAILY_WORKING_DEDUCTION_AMOUNT`, `DAILY_WORKING_DEDUCTION_AMOUNT = 150_000`) | **일치** |
| `~/.claude/skills/일용직세금` | 결정세액 = 과세표준 × 2.7% (분리과세 6% × (1−55%)) | `daily_worker.py:_calc_daily_income_tax` (`_EFFECTIVE_TAX_RATE = 0.06 * (1-0.55) = 0.027`) | **일치** (요율·절사 순서 — 2026-07-11 정정 완료) |
| `~/.claude/skills/일용직세금` | 절사 순서: 일별 결정세액은 **1원 단위**로만 truncate 후 신고근무일만큼 합산, **최종 납부세액을 10원 단위 절사**(`ROUNDDOWN(합계, -1)`) | `daily_worker.py:_calc_daily_income_tax`(1원 절사) → `calculate_daily_worker_payroll`(합산 후 `_floor10`) | **일치 (2026-07-11 엔진 정정)** — 근거: 국고금관리법 §47①(10원 절사는 납부 단계 총액) + 국세청 계산례(매일 세액 합산 후 납부 시 절사). 실측 고정: 일급 215,000×4일 = 7,020원 (`test_korea_skill_consistency.py::test_일급_215000원_4일_절사순서_납부시_10원절사`). 정정 전 엔진은 일별 선(先)절사로 7,000원(20원 차이)이었음. |
| `~/.claude/skills/일용직세금` | 소액부징수: 원천징수세액(신고근무일 합산) < 1,000원 → 소득세 0 | `daily_worker.py:calculate_daily_worker_payroll` (지급분 합산 세액 < `SMALL_AMOUNT_WITHHOLDING_THRESHOLD`(1,000) → 0) | **일치 (2026-07-11 엔진 정정)** — 근거: 소득세법 §86(원천징수**세액** 1천원 미만) + 행정해석(일괄 지급 시 일별 징수세액 **합계** 기준). 일급 187,000원 이하라도 다일 일괄지급 합산 ≥ 1,000원이면 과세 (예: 160,000×4일 = 1,080원 과세, ×3일 = 810원 부징수). 정정 전 엔진은 일급≤187,000 무조건 0이었음. |
| `~/.claude/skills/일용직세금` | 고용보험 = ROUNDDOWN(보수총액 × 0.9%, -1) | `daily_worker.py:calculate_daily_worker_payroll` (`employment_insurance_employee` 필드) | **일치 (2026-07-11 엔진 구현)** — 보수(비과세 수당 제외분)×0.9% 10원 내림. 실지급액도 고용보험 공제 반영(`net_pay = 총지급 − 소득세 − 지방세 − 고용보험`, 스킬 Step 6과 동일). |
| `~/.claude/skills/일용직세금` | 지방소득세 = ROUNDDOWN(소득세 × 10%, -1) | `daily_worker.py:calculate_daily_worker_payroll` (`local_income_tax_total = _floor10(income_tax_total * _LOCAL_INCOME_TAX_RATE)`) | **일치** (요율·10원 절사 방식 동일) |
| `~/.claude/skills/급여관리`, `~/.claude/skills/급여검증` | 주휴수당 = 주 15h 이상 + 개근 시 `min(주소정근로시간, 40) ÷ 40 × 8` | `hourly_wage.py:weekly_holiday_allowance`, `hourly_wage.py:weekly_holiday_hours` | **일치** |
| `~/.claude/skills/퇴직정산` | 퇴직금 = max(평균임금, 통상임금) × 30 × (재직일수 / 365), 평균임금 = 3개월 임금총액 ÷ 3개월 총일수 | `severance_pay.py:calculate_severance_pay`, `severance_pay.py:calculate_average_wage` | **일치** |
| `~/.claude/skills/퇴직정산` | 통상시급 = 기본급 ÷ 209 (포괄임금 실무 규칙, 계약임금 아님) | `hourly_wage.py:ordinary_hourly_wage` (`MONTHLY_ORDINARY_HOURS = 209`) | **일치 (2026-07-11 엔진 구현)** — Decimal 원값 반환, 원 단위 확정은 호출자. `severance_pay.py`의 `ordinary_wage_per_day` 계산에 이 함수 × 8h 사용 가능. |
| `~/.claude/skills/퇴직정산` | 미사용연차수당 = 기본급 ÷ 209 × 8 × 미사용일수 (통상일급 × 일수) | `hourly_wage.py:unused_leave_allowance` | **일치 (2026-07-11 엔진 구현)** — 부여 일수는 기존 `annual_leave.py`, 금액 환산은 이 함수. |
| `~/.claude/skills/4대보험신고`, `~/.claude/skills/급여검증`(검증17/18) | 4대보험 요율(2026): 국민연금 4.75%, 건강보험 3.595%, 장기요양 13.14%(건강보험료 대비), 고용보험 0.9%, 만60세↑ 국민연금 면제 | `statutory_2026.py:calculate_pension`/`calculate_health_insurance`/`calculate_employment_insurance`, `PENSION_RATE_EMPLOYEE`/`HEALTH_RATE_EMPLOYEE`/`LONGTERM_CARE_RATE`/`EMPLOYMENT_INSURANCE_RATE_EMPLOYEE` | **일치** — 요율 값이 스킬 기술과 동일. 장기요양은 엔진이 `0.009448/0.0719 ≈ 13.1405%`로 계산(스킬 표기 13.14%와 반올림 차이만, 실질 동일). 이 상수들은 이미 `hrms/tests/test_korea_rate_single_source.py`가 `foreign_worker.py`·`leave_of_absence.py`와 어긋나지 않도록 단일소스 가드를 걸어 회귀를 방지한다. |
| `~/.claude/skills/급여관리`, `~/.claude/skills/퇴직정산` | 연차 산정: 1년 미만 매월 개근 1일(최대 11일), 1년 이상 15일, 3년 이상부터 2년마다 1일 가산(최대 25일) | `annual_leave.py:calculate_annual_leave_entitlement`, `first_year_monthly_accrual`, `anniversary_annual_entitlement` | **일치** |
| `~/.claude/skills/명세서생성` | 포괄임금 설계: 총액을 통상시급 기준 기본급(÷209)·고정연장(×1.5)·고정야간(×0.5 가산분)·고정휴일(×1.5)로 분해(산정내역 구성항목 표시용) | `inclusive_wage.py:design_inclusive_wage` | **일치 (2026-07-11 엔진 신규 구현)** — `t = total ÷ (209 + 1.5×H_ot + 0.5×H_night + 1.5×H_hol)`, 끝수는 기본급이 흡수(검산 항등 `base+ot+night+holiday == 입력총액` 보장). 명세서생성 스킬의 산정내역 분해는 이 함수의 출력 매핑을 참조만 한다(스킬 파일 자체는 미수정, 읽기 전용). |
| `~/.claude/skills/명세서생성` | 포괄임금 역산 감사: 기존 계약 기재액(기본급+고정수당)이 통상시급(기본급÷209) 기준 적정 최소지급액을 충족하는지 검증, 부족분·최저임금·주12h 한도 초과는 경고(확정 아님) | `inclusive_wage.py:audit_inclusive_wage` | **일치 (2026-07-11 엔진 신규 구현)** — 경고는 raise가 아닌 `warnings` 리스트로 반환(판단은 노무사). 최저임금 값은 하드코딩 없이 인자로 주입(`ontology/statutory_ontology.get_minimum_hourly_wage`). |
| `~/.claude/skills/취업규칙검토` | 근기법 §93 필수기재 14호(9의2 포함) 있음/불충분/누락 판정 (`references/근기법-93조-체크리스트.md`) | `work_rules.py:WORK_RULES_REQUIRED_ITEMS`, `check_required_items` | **역할분리** — 엔진은 키워드 candidate 판정(있음/누락 2단만, "불충분" 세분 없음)만 반환. 조문 단위 대조·HWP 변경지시 생성은 스킬 Step 0~7 전담. |
| `~/.claude/skills/취업규칙검토` | 상시 10명 이상 → 취업규칙 작성·신고 의무 (근기법 §93) | `work_rules.py:filing_obligation` | **일치** — 엔진이 임계값(10명) 판정만 반환, 신고서 작성·제출은 `~/.claude/skills/4대보험신고` 등 별개 흐름. |
| `~/.claude/skills/취업규칙검토`, `~/.claude/skills/취업규칙의견서` | 작성·변경 절차: 과반수 노조(없으면 근로자 과반수) 의견청취, 불이익변경 시 **동의**, 신고 시 의견서 첨부(근기법 §94), 게시(§14) | `work_rules.py:amendment_procedure` | **일치** — 절차 단계 리스트·주체 판정만 엔진 담당. 불이익변경 **해당 여부 자체**는 여전히 사람(노무사) 판단(스킬 diff-engine-규칙.md §5, 엔진도 입력값으로만 받고 단정하지 않음). |
| `~/.claude/skills/취업규칙검토` | 불이익변경 후보 판정: 수치형 항목(임금·휴가일수 등)은 방향 비교로 플래그, 단정 금지 | `work_rules.py:classify_amendment` | **역할분리** — 엔진은 `candidate` 라벨(favorable/unfavorable/neutral/indeterminate) + `requires_labor_attorney_review=True` 고정 반환. 최종 불이익변경 확정·`변경지시.json`의 `disadvantage_risk` 필드 작성은 스킬(사람) 몫. |
| `~/.claude/skills/취업규칙개정` | HWP 원본에 변경지시(before/after) 적용, 한글 COM ReplaceAll | (엔진 대응 없음 — HWP 렌더링은 스킬 전담) | **역할분리(엔진 미개입)** — `work_rules.py`는 판정 로직만 제공하고 실제 HWP 개정·문서 렌더는 다루지 않는다. |
| `~/.claude/skills/급여관리`, `~/.claude/skills/퇴직정산` | §61 연차 사용촉진: 일반은 소멸 6개월 전 기준 10일 내 1차 서면촉구 → 미통보 시 2개월 전까지 2차 서면통보. 1년 미만자(§60②)는 3개월 전 기준 10일 촉구(단서: 촉구 후 발생분은 1개월 전 기준 5일) → 1개월 전까지 2차 통보(단서분은 10일 전까지). 촉진 조치를 모두 이행하면 미사용 휴가 보상 의무 면제 | `annual_leave_promotion.py:promotion_schedule`, `promotion_notice_draft`, `settle_unused_leave` | **일치 (2026-07-11 엔진 신설)** — 1차 근거는 published 온톨로지 노드 `wiki/ontology/급여규칙/연차_사용촉진.md`(노무사 승인, 근거 근로기준법 제61조). 기한 판정은 `annual_leave.py`의 `add_years`/`add_months`/`completed_years`를 재사용하고, 수당 금액은 `hourly_wage.unused_leave_allowance`를 재사용해 원 단위로 반올림한다. 에이전트 도구 `calc_annual_leave_promotion`(read_only)로도 노출됨(`agent_harness_api.py`). |
| `~/.claude/skills/명세서생성` | 임금 구성항목(기본급/주휴/연장/야간/연차/휴일)을 실지급액에서 분해하되, 각 항목에 검산 가능한 계산방법 문자열("209h × 10,320원", "{h}h(×1.5배) × {통상}원")을 필수 표기(§48②) | `payslip_breakdown.py:build_payslip_breakdown`, `render_payslip_markdown` | **일치 (2026-07-11 엔진 구현)** — hourly_wage.py(주휴·통상시급)·overtime_premium.py(가산배수 DI 재정의)·statutory_2026.py(공제)를 그대로 재사용하는 신규 조립 모듈. 계산방법 누락 항목은 `compliance.missing_basis_labels`로 검출(지급 차단은 아님). 사업장별 구성비 설계·PDF 디자인은 스킬 쪽 커스텀 영역으로 이식 범위 제외. |

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
- 취업규칙 필수기재·신고의무·절차(의견청취/동의)를 에이전트가 즉시 candidate 판정하고 싶을 때
  → `hrms/regional/south_korea/work_rules.py` (도구: `check_work_rules_required_items`,
  `work_rules_amendment_procedure`). **실제 조문 대조·HWP 변경지시·개정본 렌더링은 여전히**
  `~/.claude/skills/취업규칙검토` → `~/.claude/skills/취업규칙개정` → `~/.claude/skills/취업규칙의견서`
  순서의 개인 스킬이 담당한다 — 엔진은 판정 보조일 뿐 생성 파이프라인을 대체하지 않는다.

## 3. 정합성 게이트

스킬 문서(위 규칙 원문)와 엔진 코드(`hrms/regional/south_korea/*.py`) 중 **어느 한쪽이라도 규칙이
바뀌면** 아래 테스트가 깨지도록 설계된다(Task 2 산출물):

```bash
python3 hrms/tests/test_korea_skill_consistency.py
```

이 테스트는 위 표의 "일치" 항목을 각각 assert하는 회귀 테스트이며, "불일치(기록)" 항목은
`Global Constraints`에 따라 두 값(엔진값 vs 스킬값)을 모두 명시한 채 **현재 엔진값을 assert**하고
주석으로 스킬값을 병기하는 방식으로 표현한다(`expectedFailure`나 조용한 skip이 아니다).

일용직 절사 순서·소액부징수 판단 단위는 **2026-07-11 국세청 기준으로 엔진을 정정해 일치로 전환**되었다(테스트가 정답을 직접 assert). 잔여 "불일치 기록 테스트"(엔진값 assert + 스킬값 주석 병기) 항목:

  (일급 215,000원 × 4일: 스킬 7,020원 vs 엔진 7,000원, 20원 차이)
  (일급 160,000원 × 4일: 스킬 1,080원 vs 엔진 0원)
- (해소) 고용보험 금액·7일 캡·통상시급÷209·미사용연차수당 — 2026-07-11 엔진 구현으로 전부 "일치" 전환, 테스트가 직접 대조
  (존재성만 기록: bool 필드만 있고 금액 필드 없음)

(2026-07-11 기준 "엔진 미구현" 항목 없음 — 전 규칙 일치)
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
