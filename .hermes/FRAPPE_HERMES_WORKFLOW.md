# Frappe용 Hermes 작업 가이드

## 기본 원칙
- 이 프로필은 `/home/ubuntu/workspaces/frappe-hrms`를 기본 작업 디렉터리로 사용한다.
- 단순 질의보다 `수정 → 검증 → 요약` 루프로 시키는 것이 가장 효율적이다.
- bench CLI가 없는 현재 환경에서는 우선 `Python 코드 수정`, `JS/Vue 수정`, `ruff/빌드`, `docker compose 기반 실행 확인`을 기본 루프로 쓴다.

## 실행 방법
```bash
hermes-frappe
```

직접 명령형으로 시작하려면:
```bash
hermes-frappe chat -q "현재 워크스페이스 구조를 요약하고, 수정 전에 영향 파일부터 찾아줘"
```

## 추천 요청 패턴
### 1) Python/Frappe 서버 코드 수정
```text
이 이슈를 고쳐줘. 먼저 관련 doctype / server script / test 파일을 찾고,
수정 후 ruff 또는 가능한 테스트까지 돌려서 결과를 요약해줘.
```

### 2) Frontend(Vite/Vue) 수정
```text
이 화면을 수정해줘. 관련 Vue 컴포넌트와 build 경로를 먼저 찾고,
변경 후 frontend 또는 roster 빌드까지 확인해줘.
```

### 3) 원인분석 우선
```text
바로 수정하지 말고 원인 후보 3개와 가장 가능성 높은 지점을 찾은 뒤,
최소 수정안부터 적용해줘.
```

### 4) 대형 작업
```text
할 일을 todo로 쪼개고 병렬 가능한 건 병렬로 진행해.
각 단계마다 실제 검증 결과까지 남겨줘.
```

## 레포에서 자주 쓸 검증 포인트
### Python
- `pyproject.toml` 기준 Ruff 사용
- Frappe/ERPNext 의존성은 `>=17,<18`

### Frontend
- 루트 scripts
  - `yarn dev-pwa`
  - `yarn dev-roster`
  - `yarn build`
- 개별 앱
  - `frontend/package.json`
  - `roster/package.json`

### Docker 실행
```bash
cd docker
docker compose up
```
로그인 기본값(README 기준):
- Username: `Administrator`
- Password: `admin`

## 한국 런칭 모드(1개월)
- 핵심 기준 문서:
  - `.hermes/KOREA_LAUNCH_PLAN.md`
  - `.hermes/KOREA_GAP_AUDIT.md`
- 반복 점검:
```bash
python3 /home/ubuntu/workspaces/frappe-hrms/scripts/korea_launch_readiness.py
```
- 런칭 목표 기준 기본 요청:
```text
한국 런칭 기준으로 우선순위 높은 갭부터 찾아서,
작은 수정 단위로 반영하고 각 단계마다 실제 검증 결과를 남겨줘.
```

## 내가 Hermes에게 자주 시키면 좋은 방식
- "관련 파일 먼저 찾아서 영향도 설명 후 수정"
- "수정 후 빌드/린트/도커 확인까지"
- "애매하면 바로 묻지 말고 기본 가정으로 진행하고 가정을 적어줘"
- "큰 작업은 하위 에이전트 병렬로"

## 지금 환경의 한계
- 로컬 `bench` / `frappe` CLI는 아직 설치되어 있지 않다.
- 대신 이 레포는 `docker/docker-compose.yml` + `docker/init.sh`로 개발 부팅이 가능하다.
- bench 기반 로컬 개발이 꼭 필요해지면 별도 설치 단계를 추가한다.
