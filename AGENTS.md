# HRMS workspace guide for Hermes

Purpose
- This workspace is the authoritative server-side development copy of `frappe/hrms`.
- Primary use here: inspect app structure, do Sass/UI work, run frontend builds, and use Docker Bench runtime for integration checks.

Working rules
- Prefer small, reviewable, reversible edits.
- For UI/Sass work, inspect the relevant screen and source path before editing.
- Keep `develop` clean when possible; avoid broad unrelated refactors.
- Verify after edits with the smallest relevant command first, then broader checks.

Fast commands
- Full frontend build:
  - `cd /home/ubuntu/workspaces/frappe-hrms && yarn build`
- PWA dev server:
  - `cd /home/ubuntu/workspaces/frappe-hrms && yarn dev-pwa`
- Roster dev server:
  - `cd /home/ubuntu/workspaces/frappe-hrms && yarn dev-roster`
- Docker runtime up:
  - `docker compose -f /home/ubuntu/workspaces/frappe-hrms/docker/docker-compose.yml up -d`
- Docker runtime down:
  - `docker compose -f /home/ubuntu/workspaces/frappe-hrms/docker/docker-compose.yml down`
- Docker status:
  - `docker compose -f /home/ubuntu/workspaces/frappe-hrms/docker/docker-compose.yml ps`
- App logs:
  - `docker logs --tail 100 docker-frappe-1`

Key paths
- Main app hooks: `hrms/hooks.py`
- Main Sass bundle: `hrms/public/scss/hrms.bundle.scss`
- Sass partials:
  - `hrms/public/scss/feedback.scss`
  - `hrms/public/scss/circular_progress.scss`
  - `hrms/public/scss/hierarchy_chart.scss`
- Vue PWA app: `frontend/`
- Vue roster app: `roster/`

Validation order
1. Targeted file review
2. `yarn build`
3. If runtime-related, check Docker/Bench status
4. If UI-facing, validate served output when the site is up

## 한국 급여 작업 시 개인 스킬 활용

규칙 충돌 시 우선순위:
1. Published 온톨로지 노드 (`docs/korea_hrms/payroll-skills-bridge.md`)
2. 정합성 테스트 결과
3. 스킬 문서
4. 엔진 상수

불일치 발견 시 노무사에 확인. 정합성 테스트:
```
python3 hrms/tests/test_korea_skill_consistency.py
```

공개 레포(PUBLIC): 고객사명·개인정보·개인 경로 금지. 규칙과 공식만 기술.
