# NOHO 베타 도입 SOP
> Frappe HRMS 한국화 Wave 5-C-1  |  최종 수정: 2026-05-17
> 베타 URL: https://noho.hrms.safeclaw.kr

---

## 0. 사전 준비 (재홍님 액션)

| # | 항목 | 담당 | 상태 |
|---|------|------|------|
| 0-1 | 노호 측 의사결정자 confirm (대표 or HR 담당자 이름·연락처 확보) | **재홍님** | ☐ |
| 0-2 | 베타 기간·무료 약정 서면 확인 (예: 3개월 무료 → 정식 전환 시 요금제 고지) | **재홍님** | ☐ |
| 0-3 | 데이터 마이그레이션 범위 확정 (직원 수 N, 기존 근태·급여 기록 이관 여부) | **재홍님** | ☐ |
| 0-4 | 슬랙 채널 생성: `#hrms-beta-noho` (thenoho workspace) + 클로/제우스 초대 | **재홍님** | ☐ |
| 0-5 | 노호 측 담당자 슬랙 초대 | **재홍님** | ☐ |
| 0-6 | 환경변수 확인: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARED_TUNNEL_ID`, `MARIADB_ROOT_PASSWORD` | 클로 | ☐ |

---

## 1. 멀티 사이트 프로비저닝 (클로/제우스 실행)

```bash
# 서버2(Execution Plane)에서 실행
./scripts/provisioning/create_tenant.sh noho admin@noho.kr --plan starter --send-email
```

자동 처리 항목:
1. `bench new-site noho.hrms.safeclaw.kr` (MariaDB 격리 DB 생성)
2. `erpnext` + `hrms` 앱 install
3. Cloudflare DNS CNAME (`noho.hrms.safeclaw.kr` → tunnel)
4. cloudflared ingress 등록 + SIGHUP
5. `host_name` = `https://noho.hrms.safeclaw.kr` 설정
6. `config/multi_site.json` 레지스트리 등록
7. admin 임시 비번 생성 후 `admin@noho.kr`로 이메일 발송

> **재홍님 확인 필요**: 완료 후 터미널 출력의 임시 비번을 슬랙 DM으로 노호 담당자에게 전달. 최초 로그인 즉시 변경 요청.

---

## 2. 초기 데이터 셋업 (운영자)

### 2-1. 회사 기본 정보
- [ ] Company 도큐먼트: 회사명, 사업자번호, 대표자명, 주소, 대표 이메일, 회계연도(1월~12월)
- [ ] Default Currency: KRW
- [ ] Country: South Korea

### 2-2. 한국 사업장 프로필 (Korea Workplace Profile)
```
bench --site noho.hrms.safeclaw.kr frappe desk
→ Korea Workplace Profile → New
```
- [ ] 사업장명, 사업장 주소, 사업장 관리번호
- [ ] 5인 이상 여부 (Y/N) — 근로기준법 적용 범위 결정
- [ ] 업종 코드 (한국표준산업분류, 예: F&B = 56*)
- [ ] 산재보험 요율 (업종별 상이)

### 2-3. 부서/직급 등록
- [ ] 부서 (예: 주방, 홀, 관리) — 기본 템플릿 또는 수동 입력
- [ ] 직급 (예: 점장, 주임, 스태프, 아르바이트)

### 2-4. 직원 등록

**CSV Import 방식 (권장)**:
```
HR > 직원 > Import > 파일 업로드
템플릿: docs/clients/noho_employee_import_template.csv
```

**수동 등록 방식**: HR > 직원 > New (직원 수 10명 미만인 경우)

- [ ] 기본 정보 (사번, 이름, 이메일, 생년월일, 입사일)
- [ ] 소속 (부서, 직급, 사업장)
- [ ] 연락처 (휴대폰, 주소)

### 2-5. 한국 고용 프로필 (직원별)
```
직원 도큐먼트 > Korea Employment Profile 섹션
```
- [ ] 주민등록번호 (암호화 저장)
- [ ] 4대보험 가입 여부 (국민연금/건강보험/고용보험/산재보험)
- [ ] 외국인 여부 (Y → 외국인 등록번호, 체류 자격)
- [ ] 소득세 공제 방식 (간이세액표 vs 연말정산 선택)

---

## 3. 한국 모듈 데이터 셋업

### 3-1. 공휴일 시드
```bash
bench --site noho.hrms.safeclaw.kr execute \
  hrms.regional.south_korea.holiday_seed.seed_korea_holiday_list \
  --kwargs '{"year": 2026, "human_approved": true}'
```
- [ ] 2026년 공휴일 시드 완료 확인

### 3-2. 급여 항목 (Salary Component)

| 항목 | 유형 | 비고 |
|------|------|------|
| 기본급 | Earning | 필수 |
| 식대 | Earning | 월 20만원까지 비과세 |
| 연장근로수당 | Earning | 통상임금 × 1.5 |
| 야간근로수당 | Earning | 22시~06시, × 0.5 |
| 국민연금 (직원부담) | Deduction | 기준소득월액 × 4.5% |
| 건강보험 (직원부담) | Deduction | 보수월액 × 3.545% |
| 장기요양보험 | Deduction | 건강보험료 × 12.95% |
| 고용보험 (직원부담) | Deduction | 보수월액 × 0.9% |
| 갑근세 (소득세) | Deduction | 간이세액표 적용 |
| 지방소득세 | Deduction | 소득세 × 10% |

- [ ] Salary Component 전체 등록 완료

### 3-3. 급여 구조 (Salary Structure)
- [ ] 정규직 표준 구조 (기본급 + 식대 + 4대보험 + 소득세)
- [ ] 시급제 구조 (시간급여 + 주휴수당 + 4대보험 일할계산)
- [ ] 일용직 구조 (일 단위 지급, 일용직 원천세율 2.7%)

### 3-4. Salary Structure Assignment
- [ ] 직원별 적절한 구조 배정 완료

---

## 4. 카카오 알림톡 셋업 (선택 — 노호 확정 시)

> **재홍님 액션**: 아래 1~3단계는 노호 측에서 직접 진행해야 합니다.

- [ ] **[노호 담당자]** 카카오 비즈니스 채널 가입 (카카오톡 채널 개설)
- [ ] **[노호 담당자]** 알림톡 채널 연동 신청 (심사 7~14일 소요)
- [ ] **[노호 담당자 + 재홍님]** Solapi 계정 가입 → API 키 발급
- [ ] 알림톡 템플릿 7개 등록 (파일: `hrms/regional/south_korea/data/kakao_alimtalk_templates.json`)

| 템플릿 | scenario | 설명 |
|--------|----------|------|
| `korea_wage_statement` | salary_slip_submit | 임금명세서 발행 |
| `korea_leave_approved` | leave_application_approve | 휴가 승인 |
| `korea_leave_rejected` | leave_application_reject | 휴가 반려 |
| `korea_payroll_closing` | payroll_closing_reminder | 급여 마감 안내 |
| `korea_compliance_alert` | compliance_alert | 컴플라이언스 알림 |
| `korea_contract_renewal` | contract_renewal_reminder | 계약 갱신 안내 |
| `korea_attendance_correction` | attendance_correction_complete | 근태 수정 완료 |

- [ ] HRMS site config에 API 키 등록:
```bash
bench --site noho.hrms.safeclaw.kr set-config SOLAPI_API_KEY "..."
bench --site noho.hrms.safeclaw.kr set-config SOLAPI_API_SECRET "..."
bench --site noho.hrms.safeclaw.kr set-config KAKAO_CHANNEL_ID "..."
```

---

## 5. 운영 단계별 일정 (W1~W4)

### Week 1 — 소프트 런칭
| 일자 | 항목 | 담당 |
|------|------|------|
| D+0 | URL + 임시 비번 노호 담당자에게 전달 | **재홍님** |
| D+1 | 담당자 1인 시범 사용 (로그인 → 출근체크 → 휴가신청) | 노호 담당자 |
| D+2 | 명세서 조회 흐름 확인, 오류 수집 | 클로 |
| D+3~7 | 발견 버그 즉시 패치, 슬랙 #hrms-beta-noho 피드백 수집 | 클로/제우스 |

### Week 2~3 — 전체 시작
| 항목 | 담당 |
|------|------|
| 전 직원 계정 활성화 + 앱 안내 | **재홍님** + 노호 담당자 |
| 출근 데이터 실데이터 입력 시작 | 노호 담당자 |
| 첫 월 급여 마감 실행 (6월분) | **재홍님 검수** 후 실행 |
| 임금명세서 발송 (카카오 or 이메일) | 클로 |

### Week 4 — 검토 및 전환 결정
| 항목 | 담당 |
|------|------|
| 베타 피드백 리포트 작성 | 클로 |
| 개선 요청 우선순위 정리 (MoSCoW) | **재홍님** |
| 베타 → 정식 전환 or 연장 결정 | **재홍님 + 노호 의사결정자** |
| 정식 계약 및 요금제 안내 | **재홍님** |

---

## 6. 지원 채널

| 채널 | 용도 | SLA |
|------|------|-----|
| 슬랙 `#hrms-beta-noho` | 일반 문의, 기능 요청 | 평일 4h 내 |
| 이메일 `abc@winhr.co.kr` | 공식 요청, 문서 전달 | 평일 24h 내 |
| 텔레그램 (재홍님) | 긴급 장애, 데이터 이슈 | P1: 4h / P2: 24h |

---

## 7. SLA (베타 기간)

| 구분 | 기준 | 목표 |
|------|------|------|
| 응답 | 평일 9~18시 | 4h 내 |
| 응답 | 주말/공휴일 | 24h 내 |
| P1 장애 복구 | 서비스 전체 중단 | 4h |
| P2 장애 복구 | 기능 일부 오류 | 24h |
| 백업 | 매일 02:00 KST | 자동 (7일 보관) |
| 업데이트 공지 | 사전 1영업일 | 슬랙 채널 공지 |

---

## 8. 데이터 보안

- **DB 격리**: 노호 site는 `tenant_noho` 전용 MariaDB 데이터베이스 (타 고객사 완전 분리)
- **접근 제한**: `admin@noho.kr` + 재홍님만 site 관리자 접근 가능
- **PII 암호화**: 주민등록번호 등 민감정보는 Frappe 필드 암호화 저장
- **백업 암호화**: 백업 파일은 AES-256 암호화 후 보관 (S3 또는 로컬 안전 경로)
- **데이터 삭제**: 노호 측 요청 시 재홍님 승인 후 진행 (자동 삭제 없음)
- **퇴장 처리**: 계약 종료 시 60일 데이터 보관 후 안전 삭제, 마지막 백업 파일 노호에 제공

---

## 9. 체크리스트 요약

> 모든 단계 완료 후 아래 항목을 최종 확인합니다.

- [ ] https://noho.hrms.safeclaw.kr 접속 정상
- [ ] admin@noho.kr 로그인 성공
- [ ] 직원 N명 등록 완료
- [ ] 급여 구조 배정 완료
- [ ] 한국 공휴일 2026년 시드 완료
- [ ] 테스트 임금명세서 1건 생성 및 확인
- [ ] 슬랙 #hrms-beta-noho 채널 활성화
- [ ] 카카오 알림톡 테스트 발송 (선택)
- [ ] 베타 종료 기준일 공유 (재홍님 + 노호 담당자)
