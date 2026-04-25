# Frappe Korea Week1 Prototype Harness Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 1주 내 한국형 HRMS 시제품 출시가 가능하도록, 오늘 안에 실행 가능한 하네스(오케스트레이션 문서, 역할 프롬프트, 상태 수집 러너, 첫 실행 사이클)를 워크스페이스에 고정한다.

**Architecture:** 코어 HRMS 포크를 크게 흔들지 않고 `.hermes` 아래에 운영 하네스를 두고, `scripts/`에는 실행 가능한 상태 수집/보드 생성 러너를 둔다. 병렬 가능한 일은 감사/분석에만 쓰고, 실제 코드 수정은 단일 흐름으로 수렴한다.

**Tech Stack:** Hermes, Python 3, Docker Compose, Frappe/HRMS repo metadata, markdown/yaml artifacts.

---

### Task 1: 출시 범위와 오늘의 작업축 고정
**Objective:** 1주 시제품 기준과 Day 0 산출물을 문서로 명확히 고정한다.

**Files:**
- Create: `.hermes/harness/README.md`
- Create: `.hermes/harness/launch-week.yaml`

**Step 1:** 1주 시제품 범위를 MVP/제외범위/검증기준으로 정리한다.
**Step 2:** 오늘 완료해야 할 Day 0 산출물(하네스, 스냅샷, 실행보드)을 문서화한다.
**Step 3:** 하네스 역할(오케스트레이터/구현/QA)과 책임분리를 적는다.
**Step 4:** 파일 저장 후 내용 검토.

### Task 2: 역할별 에이전트 프롬프트 고정
**Objective:** 같은 품질 기준으로 반복 실행 가능한 역할 프롬프트를 만든다.

**Files:**
- Create: `.hermes/harness/prompts/pm-orchestrator.md`
- Create: `.hermes/harness/prompts/backend-regional.md`
- Create: `.hermes/harness/prompts/qa-runtime.md`

**Step 1:** PM 프롬프트에 범위 통제/우선순위/리스크 관리 규칙을 적는다.
**Step 2:** 구현 프롬프트에 Frappe/HRMS 한국화 우선순위와 검증 규칙을 적는다.
**Step 3:** QA 프롬프트에 docker/readiness/UI 핵심동선 검증 규칙을 적는다.
**Step 4:** 공통적으로 작은 수정, 근거 제시, pass/fail 보고 규칙을 넣는다.

### Task 3: 실행 하네스 러너 추가
**Objective:** 현재 상태를 기계적으로 모으고 실행 보드를 생성하는 스크립트를 추가한다.

**Files:**
- Create: `scripts/korea_launch_harness.py`
- Create: `.hermes/harness/runs/.gitkeep`

**Step 1:** git 상태, branch, docker ps, readiness, 핵심 파일 존재를 수집한다.
**Step 2:** timestamped JSON 리포트를 `.hermes/harness/runs/`에 쓴다.
**Step 3:** 같은 내용으로 markdown 실행보드를 생성한다.
**Step 4:** `python3 scripts/korea_launch_harness.py`로 검증한다.

### Task 4: 첫 실행 사이클 산출물 생성
**Objective:** 실제로 하네스를 1회 돌려 Day 0 실행보드를 만든다.

**Files:**
- Create: `.hermes/harness/runs/<timestamp>-snapshot.json`
- Create: `.hermes/harness/runs/<timestamp>-board.md`

**Step 1:** 러너 실행.
**Step 2:** 출력 파일 생성 여부 확인.
**Step 3:** 실행보드 내용이 오늘의 우선순위를 제대로 요약하는지 검토.

### Task 5: 후속 작업 진입점 확인
**Objective:** 오늘 이후 바로 이어서 사용할 명령/검증 진입점을 문서에 남긴다.

**Files:**
- Modify: `.hermes/harness/README.md`

**Step 1:** 러너 명령, readiness 명령, docker 상태 확인 명령, 다음 실행 순서를 추가.
**Step 2:** 결과를 `git diff --stat`와 실제 파일 읽기로 검토한다.

## Likely files to change
- `/home/ubuntu/workspaces/frappe-hrms/.hermes/harness/README.md`
- `/home/ubuntu/workspaces/frappe-hrms/.hermes/harness/launch-week.yaml`
- `/home/ubuntu/workspaces/frappe-hrms/.hermes/harness/prompts/pm-orchestrator.md`
- `/home/ubuntu/workspaces/frappe-hrms/.hermes/harness/prompts/backend-regional.md`
- `/home/ubuntu/workspaces/frappe-hrms/.hermes/harness/prompts/qa-runtime.md`
- `/home/ubuntu/workspaces/frappe-hrms/scripts/korea_launch_harness.py`

## Validation
- `python3 /home/ubuntu/workspaces/frappe-hrms/scripts/korea_launch_harness.py`
- `python3 /home/ubuntu/workspaces/frappe-hrms/scripts/korea_launch_readiness.py`
- `git -C /home/ubuntu/workspaces/frappe-hrms diff --stat`

## Risks
- 여러 에이전트가 같은 파일을 동시에 수정하면 충돌 위험이 있다.
- 현재 bench CLI 없이 Docker/스크립트 중심 검증만 가능하다.
- 실제 UI 시연 검증은 브라우저 E2E를 추가해야 완결된다.

## Recommendation
Day 0는 하네스와 스냅샷을 고정하고, Day 1부터는 이 보드를 기준으로 Company/Employee/Leave/Shift/Payroll 샘플 데이터를 순차 반영한다.
