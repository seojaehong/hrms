# 한국형 HRMS 사용자 검증 가이드 — 30분 read-only

목표: 검증 담당 사용자 1명이 이 문서만 들고 30분 안에 “접속 가능 / 데이터 있음 / 숫자·사업장 경계가 깨지지 않음 / 위험 버튼을 누르지 않음”을 확인한다.

## 0. 작성자 사전 확인 결과

- 검증 기준 시각: 2026-05-17 KST
- 서버 작업경로: `/home/ubuntu/workspaces/seojaehong-hrms-100h`
- GitHub remote: `https://github.com/seojaehong/hrms.git`
- 서버 HEAD: `4498f467c969` 기준
- GitHub remote HEAD: `4498f467c969` 기준
- 비브라우저 read-only 런타임 소스 일치: 통과
  - Docker Compose의 `frappe`, `mariadb`, `redis` 서비스가 실행 중이다.
  - `source_matches_mounted_workspace=True`
  - `positive_runtime_rows_verified=True`
  - `runtime_verified=True`
  - `runtime_blockers=[]`
- 자동 브라우저 검증 상태: 아직 미완료
  - `FRAPPE_BROWSER_PASSWORD`가 현재 cron 런타임에 없어서 credential apply는 시도되지 않았다.
  - 자동 credential apply와 authenticated browser proof는 운영자 제공 비밀번호와 명시적 human approval이 모두 있어야만 진행된다.
  - 따라서 이 문서는 사람 검증자가 운영자에게 별도 전달받은 데모 비밀번호로 read-only 확인하는 절차다.
- 회사 데이터: `노란봉투법 데모` 존재
- 사업장 기준: 표준 HRMS의 `Branch`를 사용자 검증 축으로 사용
  - `Branch`: `서울 본사`, `강남 매장` 존재
  - `Korea Workplace Profile` DocType은 존재하지만 런타임 row는 0건이므로, 사용자 검증에서는 “사업장 프로필”이 아니라 “Branch/사업장 표시”로 확인한다.
- 급여마감 기준: 커스텀 `Korea Payroll Closing Draft` 사용
  - draft row 1건 존재: 회사 `노란봉투법 데모`, 사업장 `서울 본사`, 기간 `2026-05-01` ~ `2026-05-31`, 상태 `draft_pending_human_approval`
  - 표준 `Payroll Entry` row는 현재 0건이므로 사용자 검증 항목에서 Payroll Entry 존재를 필수로 두지 않는다.
- 데모 직원: 2명 존재
  - `민지 김`: 회사 `노란봉투법 데모`, Branch `서울 본사`
  - `현우 박`: 회사 `노란봉투법 데모`, Branch `강남 매장`

## 1. 접속 정보

### 서버 안에서 직접 브라우저를 여는 경우

- URL: `http://hrms.localhost:8000`
- 계정: `demo.hr.manager@node.pe.kr`
- 비밀번호: 운영자가 별도 전달한 데모 비밀번호 사용

### Windows/외부 PC에서 여는 경우

1. SSH 터널을 먼저 연다.
   - 예시: `ssh -L 8000:127.0.0.1:8000 ubuntu@<서버주소>`
2. 브라우저에서 접속한다.
   - URL: `http://hrms.localhost:8000`
3. 접속이 안 되면 `http://127.0.0.1:8000`도 확인하되, 사이트 라우팅이 `hrms.localhost` 기준이면 로그인/리다이렉트가 깨질 수 있다.

## 2. 절대 안전선

- 저장, 제출, 승인, 마감 실행, 급여 생성, 메일 발송, 외부 전송, provider/외부기관 호출 버튼은 누르지 않는다.
- 허용되는 동작은 조회, 필터 변경, 목록 열기, 상세 열기, export/download 시도, 브라우저 뒤로가기뿐이다.
- 버튼 문구가 다음 중 하나면 누르지 않는다: `Save`, `Submit`, `Approve`, `Cancel`, `Create`, `Generate`, `Process Payroll`, `Close`, `Send`, `Email`, `Delete`, `Import`, `Bulk Update`, `New`, `Duplicate`, `Amend`, `Provider`, `마감`, `승인`, `제출`, `생성`, `저장`, `삭제`, `가져오기`, `일괄 수정`, `신규`, `복제`, `수정`, `외부전송`.
- 캡처할 때 이름, 주민번호, 계좌번호, 이메일, 전화번호는 마스킹한다. 데모 이름도 외부 공유 시 마스킹한다.
- 실수로 위험 버튼을 눌렀다면 즉시 중지하고 다음 4가지를 기록한다: 시간, 화면 URL, 누른 버튼명, 화면 캡처. 이후 운영자가 데모 시드/DB 상태를 복구한다.

## 3. 30분 체크리스트

### 0단계 — 접속 가능 여부 / 5분

- [ ] `http://hrms.localhost:8000` 접속 성공
- [ ] `demo.hr.manager@node.pe.kr` 로그인 성공
- [ ] Desk 또는 HRMS 메뉴가 보임
- [ ] 가능한 경우 DevTools Console에 빨간 오류가 반복되지 않음
- [ ] 가능한 경우 DevTools Network에 4xx/5xx가 반복되지 않음

기록:
- 브라우저/버전:
- 접속 URL:
- 콘솔/네트워크 오류:

### 1단계 — 직원 1명 1개월 워크플로 통검증 / 8분

검증 직원은 먼저 `민지 김 / 서울 본사`로 시작한다.

- [ ] Employee 목록에서 `민지 김` 상세 진입 가능
- [ ] 회사가 `노란봉투법 데모`로 표시됨
- [ ] Branch 또는 사업장 표시가 `서울 본사`로 유지됨
- [ ] 근태/Attendance 관련 화면 또는 요약 진입 가능
- [ ] 연차/Leave 관련 화면 또는 요약 진입 가능
- [ ] 급여마감 또는 `Korea Payroll Closing Draft` 관련 목록/상세 진입 가능
- [ ] `2026-05-01` ~ `2026-05-31` 기간의 draft 또는 마감 후보 row가 보임
- [ ] 명세서/급여 관련 화면으로 이동 가능하되, 생성·제출·발송 버튼은 누르지 않음

PASS 기준: 화면을 이동해도 회사=`노란봉투법 데모`, 사업장/Branch=`서울 본사` 문맥이 끊기지 않는다.

### 2단계 — 숫자/표기 스팟체크 3건 / 7분

아래 3건만 확인한다. 계산을 새로 만들지 말고 화면 간 “같은 숫자가 같은 숫자로 보이는지”를 본다.

- [ ] 직원 A: 목록 숫자와 상세 숫자가 일치
- [ ] 직원 B: 목록 숫자와 상세 숫자가 일치
- [ ] 전체 합계와 Branch별 합계가 어긋나지 않음

표기 체크:
- [ ] 원 단위 `원` 또는 KRW 표기가 깨지지 않음
- [ ] 천단위 구분자가 과도하게 섞이지 않음
- [ ] `0`, 빈 셀, `None`, `NaN`이 의미 없이 섞이지 않음
- [ ] 날짜가 `YYYY-MM-DD` 또는 `YYYY.MM.DD` 중 한 방식으로 일관됨
- [ ] 한글 줄바꿈/폰트 깨짐 없음
- [ ] 한글 입력 IME가 필터/검색창에서 동작함

### 3단계 — 사업장 경계 / 3분

- [ ] Branch/사업장 필터에서 `서울 본사` 선택 시 `강남 매장` 직원이 섞이지 않음
- [ ] Branch/사업장 필터에서 `강남 매장` 선택 시 `서울 본사` 직원이 섞이지 않음
- [ ] 전체 보기로 돌아오면 두 사업장 데이터가 모두 보임

주의: 현재 런타임에서 `Korea Workplace Profile` row는 0건이다. 사용자는 “사업장 프로필” 메뉴가 아니라 Employee/급여마감 화면의 Branch 또는 workplace 필드를 기준으로 본다.

### 4단계 — CSV/Excel 다운로드 / 4분

- [ ] Employee 또는 급여마감 목록에서 Export/Download 메뉴가 보임
- [ ] 다운로드를 실행해도 저장/제출/승인 상태가 바뀌지 않음
- [ ] 파일명 또는 컬럼명이 한글에서 깨지지 않음
- [ ] 내려받은 파일에 회사/Branch/기간 컬럼이 포함됨

PII 주의: 다운로드 파일은 외부 메일/메신저에 원본으로 보내지 않는다. 필요 시 이름·이메일·번호 컬럼을 삭제하거나 마스킹한다. 검증 종료 후 로컬 다운로드 파일도 삭제한다.

### 5단계 — 보조 화면 / 3분

- [ ] 승인함/ToDo/Workflow 관련 화면 진입 가능
- [ ] Leave/Attendance 보조 화면 진입 가능
- [ ] 필터 변경 후 화면이 빈 화면으로 죽지 않음
- [ ] 모바일은 이번 30분 검증의 필수 범위가 아니다. 최소 확인만 할 경우 390px와 1440px 두 폭만 본다.

## 4. 결과 기록

- 최종 판정: PASS / FAIL
- FAIL 사유:
- 재현 경로:
- 콘솔/네트워크 오류:
- 캡처 파일명:
- 숫자 불일치 항목:
- 사업장 경계 누수 여부:
- 위험 버튼 클릭 여부:

## 5. 작성자/운영자 부록

### 사전 검증 커맨드

```bash
cd /home/ubuntu/workspaces/seojaehong-hrms-100h
python3 scripts/verify_korea_payroll_closing_runtime.py \
  --include-bench \
  --site hrms.localhost \
  --company '노란봉투법 데모' \
  --report-file /tmp/korea-runtime-guide-review.json
```

### 런타임 row 확인 요약

```sql
SELECT name FROM `tabCompany`;
SELECT name FROM `tabBranch`;
SELECT name, employee_name, company, branch, status FROM `tabEmployee`;
SELECT name, company, workplace, period_start, period_end, status FROM `tabKorea Payroll Closing Draft`;
```

### 데모 시드 재적용

위험 버튼 클릭 등으로 데모 상태가 흔들렸으면 사용자는 멈추고 운영자가 처리한다. 현재 repo에는 idempotent demo seed가 있다.

```bash
cd /home/ubuntu/workspaces/seojaehong-hrms-100h
docker compose -f docker/docker-compose.yml exec -T frappe \
  bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost execute hrms.regional.south_korea.demo_seed.main'
```

이 명령은 데모 시드 재적용용이다. 운영자가 실행 전 DB 상태와 최근 변경 로그를 먼저 확인한다.
