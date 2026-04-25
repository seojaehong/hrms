# Korea HRMS Launch Harness

## 목적
1주 내 한국형 HRMS 시제품 출시를 목표로, 오늘부터 바로 반복 실행 가능한 에이전트 하네스를 고정한다.

이 하네스는 네 가지를 남긴다.
1. 범위 통제
2. 역할 분리
3. 상태 스냅샷
4. 다음 실행 우선순위

## 1주 시제품 범위
### 포함
- 한국어 핵심 UI 동선
- Company / Employee 한국 필드 확인 및 보강
- Holiday List / Leave Policy / Shift Type 템플릿
- Salary Component / Salary Structure 한국 기본 세트
- 급여 자동계산 대신 기준값 저장 + 수동검증 보조
- 샘플 데이터 기반 데모 시나리오

### 제외
- 4대보험/세금 완전자동 계산 엔진
- 정부기관 직접 연동
- 고난도 퇴직금/평균임금 예외 자동화
- 광범위한 코어 리팩터링

## Day 0 산출물
- 실행 계획 문서: `.hermes/plans/2026-04-25_032900-frappe-korea-week1-prototype-harness.md`
- 역할 프롬프트 3종
- 상태 수집 러너: `scripts/korea_launch_harness.py`
- 실행 스냅샷/보드: `.hermes/harness/runs/`

## 역할 구조
### 1) PM Orchestrator
- 범위, 우선순위, 리스크를 통제한다.
- 병렬 가능한 분석 작업만 분기한다.
- 실제 코드 수정은 단일 흐름으로 수렴시킨다.

### 2) Backend / Regional Builder
- 한국 regional setup, custom field, 템플릿/fixture, 문서 반영을 담당한다.
- 수정 후 최소 검증(ruff/build/readiness)을 반드시 남긴다.

### 3) QA / Runtime Verifier
- docker 상태, readiness, 로그인 진입, 핵심 동선 노출 여부를 검증한다.
- pass/fail과 남은 리스크를 구분해 기록한다.

## 운영 규칙
- 작은 수정, 즉시 검증, 가시적 산출물 남기기
- 사실/해석/권고 구분
- 법률 계산은 자동판정처럼 보이지 않게 구성
- 민감정보 최소수집 원칙 유지
- 병렬은 조사/정리에만 쓰고, 같은 파일 동시수정 금지

## 실행 명령
```bash
python3 /home/ubuntu/workspaces/frappe-hrms/scripts/korea_launch_harness.py
python3 /home/ubuntu/workspaces/frappe-hrms/scripts/korea_launch_readiness.py
sudo docker compose -f /home/ubuntu/workspaces/frappe-hrms/docker/docker-compose.yml ps
```

## 다음 실행 순서
1. harness 러너로 최신 스냅샷 생성
2. 보드 기준으로 오늘 1순위 작업 선택
3. 단일 구현 흐름으로 수정
4. readiness / build / UI 확인
5. 실행보드 업데이트
