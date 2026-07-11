# 근로감독(점검) 대비 에이전트 — 설계서

작성: 2026-07-12. 성격: **설계 트랙** — 코드 산출물은 체크리스트 JSON 로더뿐이고, 이 문서가 본 산출물이다.
관련 브리프: [`docs/superpowers/plans/brief.md`](../superpowers/plans/brief.md) (feature/labor-inspection)
관련 데이터: [`hrms/regional/south_korea/data/labor_inspection_checklist.json`](../../hrms/regional/south_korea/data/labor_inspection_checklist.json) (15개 항목)
관련 코드: [`hrms/regional/south_korea/labor_inspection_checklist.py`](../../hrms/regional/south_korea/labor_inspection_checklist.py)

## 무엇인가 (한 줄)

고용노동부 정기·수시 근로감독(자율점검표·근로감독관 집무규정 기준)에 대비해, 사업장이 보유한 서류(근로계약서·임금대장·명세서·취업규칙 등)를 업로드하면 **문서 파싱 → 체크리스트 대조 → 위험요인 리포트 → 개선안 생성**까지 자동화하되, 최종 판단은 항상 사람(노무사) 검토를 거치는 read-only 진단 에이전트.

## ⚠️ Global Constraints 재확인

- public repo — 고객 사업장명·사건 정보 절대 미포함. 부평·강동 등 실제 점검 사례는 §5 "후속 훅"에서 **사용자 로컬 자료로 보강하는 절차**로만 언급하고, 구체 내용은 이 저장소에 두지 않는다.
- 체크리스트의 legal_basis/risk는 법제처 원문(`mcp__korean-law__get_law_text`)으로 확인한 항목만 "확인"으로 표기했고, 원문 재확인이 필요하거나 2차 자료에 의존한 항목은 "미확인"을 명시했다(§1 표 참조, 추측 금지).

## ① 리서치 — 점검 항목·근거조항·과태료 (요약, 전체는 JSON 참조)

고용노동부는 2026년 사업장 감독 물량을 전년 대비 73% 확대(5.2만→9만 개소)하고 "적발 시 즉시 제재"(시정기회 없는 사법처리·행정처분)를 예고했다. 정기감독은 감독점검표에 따라 근로자 명부·임금대장(최근 1년, 특별한 경우 3개년) 등을 전반적으로 확인하며, 근로조건 자율진단표(자율점검표)를 사업주가 자유롭게 활용·재배포하도록 공개하고 있다.

| id | category | item | legal_basis | risk | automated_check |
|----|----------|------|-------------|------|------------------|
| LI-001 | 근로계약 | 근로계약서 서면 작성·교부 | 근기법 §17, §19 | 벌금 500만원 이하(§114①) | employment_contract |
| LI-002 | 임금 | 임금명세서 교부(구성항목·계산방법·공제내역) | 근기법 §48② | 과태료 500만원 이하(§116②2) | payslip_breakdown |
| LI-003 | 임금 | 임금대장 작성 | 근기법 §48① | 과태료 500만원 이하(§116②2) | payslip_breakdown |
| LI-004 | 임금 | 최저임금 이상 지급 | 최저임금법 §6 | 3년 이하 징역/2천만원 이하 벌금(§28①) | hourly_wage |
| LI-005 | 근로시간 | 연장근로 한도(주 12h, 합계 52h) | 근기법 §53 | 2년 이하 징역/2천만원 이하 벌금(§110①) | 미확인(근태 연동 모듈 부재) |
| LI-006 | 임금 | 연장·야간·휴일 가산수당(통상임금 50%+) | 근기법 §56 | 3년 이하 징역/3천만원 이하 벌금(§109①) | hourly_wage |
| LI-007 | 휴가 | 연차 발생·부여 | 근기법 §60 | 2년 이하 징역/2천만원 이하 벌금(§110①) | annual_leave |
| LI-008 | 휴가 | 연차 사용촉진 | 근기법 §61 | 벌칙조항 아님(촉진요건 미충족 시 미사용수당 지급의무 존속) | annual_leave |
| LI-009 | 취업규칙 | 취업규칙 작성·신고(상시 10인+) | 근기법 §93 | 과태료 500만원 이하(§116②2) | work_rules |
| LI-010 | 취업규칙 | 취업규칙 게시·비치 | 근기법 §14 | 과태료 500만원 이하(§116②2) | work_rules |
| LI-011 | 성희롱예방 | 예방교육 연 1회 + 게시 | 남녀고용평등법 §13 | 과태료 500만원 이하(§39③1의2·1의3) | 미확인(교육이력 모듈 부재) |
| LI-012 | 직장내괴롭힘 | 금지 및 발생 시 조사·조치 | 근기법 §76의2, §76의3 | 1천만원 이하(§76의2, §116①) / 500만원 이하(§76의3 관련, §116②2) | 미확인(사전점검 자동화 부재) |
| LI-013 | 서류보존 | 근로자명부·근로계약 서류 3년 보존 | 근기법 §42 | 과태료 500만원 이하(§116②2) | employment_contract |
| LI-014 | 4대보험 | 4대보험 자격취득 신고 기한 | 국민연금법§3·88, 건강보험법§69, 고용보험법§13, 산재보험법§6 | 고용·산재 지연신고 시 근로자당 과태료(2차자료, moel.go.kr 원문 미확인) | 4대보험신고 |
| LI-015 | 해고·금품청산 | 퇴직 시 금품 14일 이내 청산 | 근기법 §36 | 3년 이하 징역/3천만원 이하 벌금(§109①) | 퇴직정산 |

전체 15개 항목·evidence_needed·risk 원문 인용은 JSON 참조. 원문 조회 출처: 법제처 국가법령정보센터(법령ID 001872 근로기준법 MST 265959 시행 2025-10-23분 / 000129 최저임금법 MST 218303 / 000130 남녀고용평등법 MST 276851 시행 2025-10-01분).

Sources:
- [고용노동부 2026년 사업장 근로감독 대폭 강화](https://www.lawtimes.co.kr/LawFirm-NewsLetter/215331)
- [고용노동부 정기 근로감독 대응 및 점검 포인트 - IMHR](https://www.imhr.work/brand/labor-supervision-check-point/)
- [근로감독관집무규정 - 국가법령정보센터](https://www.law.go.kr/행정규칙/근로감독관집무규정)
- [취업규칙(신고서, 변경신고서) - 고용노동부 노동포털](https://labor.moel.go.kr/minwonApply/minwonFormat.do?searchVal=SN004)
- 근로기준법·최저임금법·남녀고용평등법 원문: 법제처 국가법령정보센터 Open API(mcp__korean-law) 직접 조회

## ② 체크리스트 데이터 스키마

```json
{
  "id": "LI-002",
  "category": "임금",
  "item": "임금명세서 서면(전자문서 포함) 교부 — 구성항목·계산방법·공제내역 기재",
  "legal_basis": "근기법 제48조제2항(임금대장 및 임금명세서)",
  "evidence_needed": ["임금명세서 발급 이력", "임금대장"],
  "risk": {"type": "과태료", "amount": "500만원 이하", "note": "근기법 제116조제2항제2호(제48조 위반) — 확인: 원문 조회 완료"},
  "automated_check": "payslip_breakdown"
}
```

- `automated_check`은 **기존 엔진 모듈명**(하단 §3 매핑표의 좌측 컬럼)과 1:1 매칭되거나, 아직 대응 모듈이 없으면 `"미확인(사유)"`로 명시한다. UI/에이전트는 이 접두어로 "자동 점검 가능 항목"과 "사람이 봐야 하는 항목"을 분기한다.
- 로더: `load_labor_inspection_checklist(path=None)` — JSON 로드 + 구조 검증(필수 필드 7종, `id` 유일성, `evidence_needed` 비어있지 않음, `risk.type` 존재)을 통과해야 반환. `filter_by_category`, `filter_automatable` 헬퍼 제공.
- 테스트: `hrms/tests/test_korea_labor_inspection_checklist.py` — 9 케이스(로드·유일성·경로주입·파일없음·검증실패 3종·카테고리필터·자동화필터). TDD RED(모듈 부재 FileNotFoundError) 확인 후 구현, GREEN 전환 완료.

## ③ 플로우 설계 — 문서 업로드 → OCR/파싱 → 대조 → 리포트 → 개선안

```
┌──────────────┐   ┌───────────────────┐   ┌────────────────────┐   ┌──────────────────┐   ┌───────────────────┐
│ 문서 업로드    │──▶│ OCR/파싱 레이어     │──▶│ 체크리스트 대조      │──▶│ 위험요인 리포트     │──▶│ 개선안 생성(승인게이트)│
│ 근로계약서     │   │ (신규 모듈 필요)     │   │ labor_inspection_   │   │ compliance_        │   │ 기존 스킬/도구 재사용  │
│ 임금대장/명세서 │   │ 텍스트층 有 PDF→    │   │ checklist.py        │   │ diagnosis 패턴 재사용│   │ (자동 실행 금지)      │
│ 취업규칙 등    │   │ pdfplumber 직독     │   │ ×  evidence 매핑    │   │ severity 산정        │   │                    │
└──────────────┘   │ 텍스트층 無(캡처)→   │   └────────────────────┘   └──────────────────┘   └───────────────────┘
                    │ 비전 OCR 필수 함정   │
                    └───────────────────┘
```

1. **문서 업로드**: 근로계약서/임금대장/명세서/취업규칙/성희롱예방교육 이력/연차관리대장 등. PII(주민번호 등)는 업로드 즉시 마스킹 원칙 — 기존 `employment_contract.py`의 `mask_rrn()` 패턴을 재사용한다.
2. **OCR/파싱**: 이 저장소에는 아직 문서 파싱 모듈이 없다(신규 개발 필요, 미확인 항목). 설계 원칙은 **개인 스킬 `extract_evidence_images.py`의 사상**을 그대로 계승한다 — "카톡·문자 캡처는 텍스트층이 0이라 일반 텍스트 추출이 실패하고, 반드시 이미지 렌더 후 비전 모델(또는 외부 OCR API)로 판독해야 한다"는 함정을 임금대장·명세서 스캔본에도 동일하게 적용한다(엑셀/워드 원본은 텍스트층 有 → 직독, 스캔·사진은 텍스트층 無 → 비전 경로로 분기). 이 함정을 놓치면 "서류 없음"으로 오판해 실제로는 존재하는 증빙을 위반으로 오분류하는 리스크가 크다.
3. **체크리스트 대조**: 파싱 결과(문서 종류·발급이력·게시이력 등)를 `evidence_needed`와 매칭해 항목별 `evidence_status`(attached/missing)를 산정. `compliance_diagnosis.py`의 계약 패턴(`severity: ok/warning/critical`, `requires_human_review`)을 그대로 재사용해 **AI 확신도 점수·자동 승인 없이** 사람이 검토할 항목만 표시한다.
4. **위험요인 리포트**: 항목별 `risk`(과태료/형사처벌 여부·금액)와 `evidence_status`를 결합해 severity를 산정하고, `automated_check`가 확정 모듈이면 해당 모듈의 계산 결과(예: `hourly_wage.is_below_minimum_wage`)를 근거로 첨부한다. `automated_check`가 "미확인"이면 "자동 점검 불가 — 서류 직접 확인 필요"로 표시(추측 금지).
5. **개선안 생성**: `search_labor_knowledge`(시맨틱 검색, 행정해석·판례·판정례·FAQ)로 근거를 인용한 개선 문구를 초안 생성하되, **문서 실제 수정·발송은 사람 승인 게이트를 거쳐야 한다**(`agent_harness`의 `read_only=False + human_approved` 계약 그대로 적용). 실제 개정 실행은 기존 `/취업규칙개정`, `/명세서생성` 등 스킬에 위임하고 이 에이전트는 "무엇을 고쳐야 하는지"만 리포트한다.

## ④ 기존 자산 매핑

| 체크리스트 automated_check | 기존/병렬 개발 모듈 | 상태 | 결합점 |
|---|---|---|---|
| `employment_contract` | `hrms/regional/south_korea/employment_contract.py`, `employment_contract_api.py` | develop 존재, `feature/employment-contract` 브랜치에서 계속 개발 중 | 계약서 필수기재사항 검증(`_check_required_fields`) 재사용, 교부 이력 로그 필요(미확인 — 신규) |
| `payslip_breakdown` | `hrms/regional/south_korea/payslip.py` (`build_payslip_snapshot`, `build_korea_wage_statement_preview`) | develop 존재, `feature/payslip-breakdown` 브랜치에서 구성항목 분해 진행 중 | 임금명세서 §48②항 구성항목·공제내역 필드가 그대로 evidence 매핑 대상 |
| `hourly_wage` | `hrms/regional/south_korea/hourly_wage.py` (`is_below_minimum_wage`, `weekly_holiday_allowance` 등) | develop 존재, 안정 | 최저임금·가산수당 자동 점검을 위한 계산 엔진으로 바로 재사용 가능 |
| `annual_leave` | `hrms/regional/south_korea/annual_leave.py`, `annual_leave_attendance_ratio.py` | develop 존재, `feature/annual-leave-mgmt` 브랜치에서 확장 중 | 연차 발생일수·촉진 요건(제61조 10일/2개월 서면기한)을 코드 상수와 대조 가능 |
| `work_rules` | 없음 — `feature/work-rules` 브랜치가 있으나 아직 커밋 없음(리서치 시점 기준 develop 대비 diff 无, 신규 착수 전) | 미착수 | 취업규칙 신고·게시(§93, §14) 점검은 이 모듈이 생기면 신고필증 유무·게시이력 필드를 그대로 흡수 |
| `compliance_checklist` / `compliance_diagnosis` | `hrms/regional/south_korea/compliance_checklist.py`, `compliance_diagnosis_api.py` | develop 존재, payroll-close/payslip-issue 등 4종 기본 체크만 커버 | **이 근로감독 체크리스트가 카테고리를 확장하는 자매 데이터**로 봐야 함 — 동일한 `severity/requires_human_review` 계약을 재사용해 진단 API를 확장하는 것이 다음 단계(§5) |
| `search_labor_knowledge` | `hrms/regional/south_korea/agent_harness_api.py`(`_register_calc_tools` 내) | develop 존재, env 게이트(시맨틱 retriever 미설정 시 fail-closed) | 개선안 문구의 법령 근거 인용(판례·행정해석·판정례·FAQ)에 직접 재사용 |
| `4대보험신고` | `/4대보험신고` 스킬(openpyxl 기반, 이 저장소 외부) | 별도 실행계층 | 자격취득 신고 이력 자동 대조는 이 저장소 엔진이 아니라 스킬 실행 로그로 매핑(미확인 — 로그 표준화 필요) |
| `퇴직정산` | `/퇴직정산` 스킬(별도 실행계층) | 별도 실행계층 | 금품청산 14일 기한 자동 점검은 퇴직정산 스킬의 지급일자 필드 재사용 |

## ⑤ 경쟁 분석 — 급여 SaaS(페이엔진 등)의 점검 대응 기능

WebSearch로 페이엔진(payengine)·에듀서베이 등 국내 급여 SaaS의 "근로감독 대응" 마케팅 기능을 조사했다. 각 벤더의 상세 기능 스펙 페이지는 대부분 로그인 후 열람 가능한 세일즈 자료라 원문 조회가 제한적이었고, 확인된 범위는 다음과 같다(미확인 항목은 표기).

| 축 | 급여 SaaS 일반(페이엔진 등) | 이 저장소(korea_hrms) 지향 |
|---|---|---|
| 체크리스트 제공 | 대부분 "임금명세서 자동 생성" 등 개별 기능 단위 마케팅, 근로감독 전용 통합 체크리스트 노출은 미확인 | 법령 조문·과태료·증빙서류를 1:1 매핑한 구조화 JSON(본 산출물) — 감사 가능한 데이터 |
| 법령 근거 인용 | 대부분 "법 준수"라고만 홍보, 조문 원문 인용 여부 미확인 | 법제처 원문 직접 조회 후 인용(§1), "미확인"은 추측하지 않고 명시 |
| 계산 신뢰성 | 미확인(벤더별 상이) — 자체 검증 방식 비공개 | 노무사 검증 + 국세청/고용보험 정렬 계산 엔진(hourly_wage 등)을 사업장 실데이터로 교차검증하는 운영 관행(사용자 CLAUDE.md 원칙과 동일) |
| 자동 개선안 | 미확인 — 알림/리마인더 수준이 일반적으로 보임(2차 자료 기준) | 에이전트가 위반 항목별 근거 인용 개선안 초안을 생성하되, 실행은 사람 승인 게이트 통과 필수(자동 확정 없음) |
| 사후 대응(조사보고서 등) | 미확인 — 급여 SaaS는 대개 사전 컴플라이언스 영역에 집중, 괴롭힘 조사보고서 등 사후 대응 도구는 별도 카테고리 | 이미 `/괴롭힘보고서`, `/문답서생성`, `labor-commission-report` 등 사후 대응 스킬 보유 — 사전 점검(이 설계)과 결합 시 "예방→대응" 풀사이클 제공이 차별점 |

**차별화 결론**: 페이엔진류의 강점은 UX·확산력(마케팅 노출)이며, 상세 계산·법령 검증 방식은 비공개라 정량 비교가 어렵다(미확인). 우리 차별화는 ① 법령 조문 원문 인용을 코드/데이터 레벨에서 강제(추측 시 "미확인" 표기하는 문화), ② 노무사 실무 검증을 거친 계산 엔진(1원 단위 검증 관행)을 근로감독 자동점검에도 그대로 적용, ③ 사전 점검(이 설계)과 사후 대응(괴롭힘보고서·문답서·노동위 조사보고서 등 기존 스킬)을 하나의 에이전트 생태계로 묶는다는 점이다.

Sources:
- [고용노동부 2026년 사업장 근로감독 대폭 강화](https://www.lawtimes.co.kr/LawFirm-NewsLetter/215331)
- [고용노동부 정기 근로감독 대응 및 점검 포인트 - IMHR](https://www.imhr.work/brand/labor-supervision-check-point/)

## ⑥ 후속 훅 — 사용자 로컬 실점검 자료로 체크리스트 보강

이 저장소는 public repo이므로 실제 점검 사례(부평·강동 등)의 사업장명·위반 사실·금액은 절대 커밋하지 않는다. 대신 다음 절차로 **패턴만 로컬에서 추출해 이 JSON을 보강**한다.

1. 사용자가 로컬(OneDrive `payroll/`, 개인 메모리 등)에서 실제 점검 지적사항을 정리 — 사업장 식별정보는 그대로 로컬에 남긴다.
2. 지적사항에서 "어떤 조문 위반이 실무에서 자주 나오는지 / 어떤 서류가 자주 누락되는지"만 일반화해 `labor_inspection_checklist.json`에 새 `id`(LI-016~)로 추가하거나 기존 항목의 `evidence_needed`를 보강하는 PR을 별도로 올린다.
3. PR 본문·커밋 메시지에도 사업장 고유정보(상호명·주소·대표자명·사건번호)를 쓰지 않는다 — "실사례 기반 보강"이라고만 기록한다.
4. `automated_check`가 "미확인"인 항목(근태 연동·교육이력·괴롭힘 사전점검)은 실사례에서 반복적으로 지적되면 우선순위를 올려 신규 모듈 개발 백로그(`docs/korea_hrms/feature-proposals-2026h2.md`)에 등록한다.

## ⑦ 검증

- 코드 게이트: `bash scripts/run_korea_tests.sh labor_inspection` — 신규 로더 테스트 9건 GREEN. 전체 스위트(`bash scripts/run_korea_tests.sh`)로 회귀 확인.
- 데이터 게이트: JSON 파싱 성공 + 로더의 `validate_labor_inspection_checklist` 통과(필수 필드 7종·유일 id·evidence 비어있지 않음·risk.type 존재) — 15개 항목 전부 통과.
- 온톨로지 게이트: `bash scripts/run_korea_tests.sh ontology` — 이 태스크는 `wiki/ontology` 노드를 추가하지 않았으므로 무해(브리프 §Global Constraints 4항).
