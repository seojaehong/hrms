# NOHO 프로비저닝 Dry-Run 보고서
> Phase 7-D | 실행일: 2026-05-18 | 상태: dry-run 완료 — 실제 실행은 재홍님 승인 필요

---

## 0. 실행 차단 사항 (Blocker — 실제 실행 전 필수 수정)

### [BLOCKER] bench 명령어 host에 없음

**심각도**: 실제 실행 차단 (Blocker)

**현황**:
- `bench`는 컨테이너 내부에만 설치됨
- host 머신 PATH에 bench 없음
- `create_tenant.sh` 내 `bench` 관련 호출 7곳 모두 host 실행 전제로 작성됨

**해결 방법 3가지** (재홍님 선택):

| 방법 | 공수 | 권장도 |
|------|------|--------|
| A. 스크립트 내 bench 호출을 `docker exec <컨테이너> bench ...`로 래핑 | 30분 | ★★★ 권장 |
| B. 컨테이너 내부에서 스크립트 실행 (`docker exec -it <컨테이너> bash -c "..."`) | 즉시 가능, 환경변수 주입 필요 | ★★ |
| C. host에 bench 직접 설치 | 2~3시간, 충돌 위험 | ★ |

> **Blocker 해소 전까지 실제 실행 불가.** 재홍님 승인 후 방법 A 적용 권장.

---

## 1. Dry-Run 실행 결과

### 실행 명령

```bash
export CLOUDFLARE_API_TOKEN="<redacted-cloudflare-token>"
export CLOUDFLARED_TUNNEL_ID="<redacted-tunnel-id>"
export MARIADB_ROOT_PASSWORD="<redacted-mariadb-root-password>"

bash scripts/provisioning/create_tenant.sh noho admin@noho.kr \
    --plan starter --dry-run 2>&1
```

### 출력 전문

```
━━━ 1/8  사전 확인 ━━━
  tenant_id : noho
  site      : noho.hrms.safeclaw.kr
  plan      : starter
  email     : admin@noho.kr

━━━ 2/8  bench new-site ━━━
[dry-run] bench new-site noho.hrms.safeclaw.kr \
  --mariadb-root-password <redacted> \
  --admin-password <generated-redacted> \
  --no-mariadb-socket \
  --db-name tenant_noho

━━━ 3/8  한국 모듈 설치 (erpnext, hrms) ━━━
[dry-run] bench --site noho.hrms.safeclaw.kr install-app erpnext
[dry-run] bench --site noho.hrms.safeclaw.kr install-app hrms
(--seed-demo 미설정 — 데모 시드 생략)

━━━ 5/8  Cloudflare DNS CNAME 추가 ━━━
[dry-run] python3 .../cloudflare_dns_add.py noho <redacted-tunnel-id>

━━━ 6/8  cloudflared ingress 등록 ━━━
[dry-run] python3 .../cloudflared_ingress_add.py noho 8000

━━━ 7/8  Frappe site host_name 설정 ━━━
[dry-run] bench --site noho.hrms.safeclaw.kr set-config host_name https://noho.hrms.safeclaw.kr

━━━ 8/8  레지스트리 업데이트 ━━━
[dry-run] config/multi_site.json에 noho 추가

════════════════════════════════════════════
  프로비저닝 완료
  site      : https://noho.hrms.safeclaw.kr
  admin     : admin@noho.kr
════════════════════════════════════════════
```

**결론**: 8단계 입력값 검증 + 명령 계획 통과 (실제 실행은 Blocker 1개로 차단됨 — Section 0 참조). 입력 유효성 검증(tenant_id 형식, 이메일, plan) 모두 통과.

---

## 2. 발견된 이슈

### [BLOCKER] Issue 1 — bench 명령어 host에 없음

**심각도**: 실제 실행 차단 (Blocker)

**현황**:
- `bench`는 `docker-frappe-1` 컨테이너 내부(`/home/frappe/.local/bin/bench`)에만 설치됨
- host 머신 PATH에 bench 없음
- `create_tenant.sh` 내 `bench` 관련 호출 7곳 모두 host 실행 전제로 작성됨

```bash
# 현재 스크립트 (실패)
bench new-site noho.hrms.safeclaw.kr ...
bench --site noho.hrms.safeclaw.kr install-app erpnext

# 필요한 수정 방향 (예시)
docker exec -it docker-frappe-1 bench new-site noho.hrms.safeclaw.kr ...
docker exec -it docker-frappe-1 bench --site noho.hrms.safeclaw.kr install-app erpnext
```

**해결 방법 3가지** (재홍님 선택):

| 방법 | 공수 | 권장도 |
|------|------|--------|
| A. 스크립트 내 bench 호출을 `docker exec docker-frappe-1 bench ...`로 래핑 | 30분 | ★★★ 권장 |
| B. 컨테이너 내부에서 스크립트 실행 (`docker exec -it docker-frappe-1 bash -c "..."`) | 즉시 가능, 환경변수 주입 필요 | ★★ |
| C. host에 bench 직접 설치 | 2~3시간, 충돌 위험 | ★ |

---

### [BUG] Issue 2 — 데모 시드 모듈 경로 불일치

**심각도**: `--seed-demo` 사용 시 실행 오류 (NOHO는 해당 없음 — 미사용)

**현황**: 스크립트(line 164)가 호출하는 모듈 경로 vs 실제 파일 경로가 불일치

```python
# 스크립트에서 호출하는 경로 (존재하지 않음)
hrms.regional.south_korea.demo.seed_demo_data

# 실제 파일 경로 및 함수명
hrms/regional/south_korea/demo_seed.py → def seed_korea_demo()
```

**수정 필요** (`--seed-demo` 기능 활성화 전 필수):

```bash
# 수정 전
bench --site "${SITE_NAME}" execute \
    hrms.regional.south_korea.demo.seed_demo_data \
    --args '{"company_name": "..."}'

# 수정 후
bench --site "${SITE_NAME}" execute \
    hrms.regional.south_korea.demo_seed.seed_korea_demo \
    --args '{"company_name": "..."}'
```

---

### [WARNING] Issue 3 — Host Header 멀티사이트 라우팅 미검증

**심각도**: 경고 (실제 실행 후 확인 필요)

**현황**:
- 현재 운영 사이트 디렉터리: `frappe-bench/sites/hrms.localhost/`
- `common_site_config.json`의 `default_site`: `hrms.localhost`, `serve_default_site: true`
- Frappe는 Host header 값으로 `sites/<hostname>/` 디렉터리를 찾아 라우팅
- `noho.hrms.safeclaw.kr` → `sites/noho.hrms.safeclaw.kr/` 디렉터리로 라우팅 예상

**검증 미완료** — 실제 site 생성 후 다음 명령으로 확인 필요:

```bash
# site 생성 후 실행 (mutation 아님 — 읽기 전용 확인)
curl -s -o /dev/null -w "%{http_code}" \
    -H "Host: noho.hrms.safeclaw.kr" \
    http://localhost:8000/
# 200 또는 302이면 정상 라우팅
# 404 이면 default_site fallback 발생 → 추가 설정 필요
```

**현재 cloudflared 설정 상태** (문제 없음):
```yaml
ingress:
  - hostname: hrms.safeclaw.kr
    service: http://localhost:8000
  - service: http_status:404  # catch-all
```
새 tenant 추가 시 `cloudflared_ingress_add.py`가 catch-all 직전에 삽입 → 구조 정상.
모든 tenant는 동일 포트(8000)로 라우팅되며, Frappe 내부에서 Host header 기반으로 분리.

---

### [INFO] Issue 4 — MARIADB_ROOT_PASSWORD 평문 노출

**심각도**: 정보 (개발 환경 수준)

- `docker-compose.yml`에 `MYSQL_ROOT_PASSWORD: <redacted>` 형태의 placeholder만 문서화
- 운영 투입 전 환경변수 또는 Docker Secret으로 변경 권장

---

## 3. 단계별 실행 명령 분석

| 단계 | 실행 내용 | 실패 위험 | 비고 |
|------|-----------|-----------|------|
| 1/8 사전 확인 | 입력 유효성 검증, 중복 site 체크 | 낮음 | dry-run 정상 통과 |
| 2/8 bench new-site | MariaDB에 격리 DB 생성, site 초기화 | **높음** | bench 호스트 없음(Issue 1) |
| 3/8 한국 모듈 설치 | erpnext, hrms app install | **높음** | bench 호스트 없음(Issue 1). 10~20분 소요 예상 |
| 4/8 데모 시드 | `--seed-demo` 시에만 실행 | **높음** | 모듈 경로 오류(Issue 2). NOHO는 미사용 |
| 5/8 Cloudflare DNS | `cloudflare_dns_add.py` → CF API CNAME 생성 | 낮음 | API 토큰 권한 확인 필요 |
| 6/8 cloudflared ingress | `config.yml` 수정 + SIGHUP | 낮음 | PyYAML 설치 확인됨, cloudflared 실행 중 |
| 7/8 host_name 설정 | bench set-config | **높음** | bench 호스트 없음(Issue 1) |
| 8/8 레지스트리 업데이트 | `config/multi_site.json` 수정 | 낮음 | Python3 직접 실행, 의존성 없음 |

---

## 4. 실제 실행 체크리스트

재홍님 승인 후 실행 시 필요한 액션:

### 사전 액션 (1회성)
- [ ] **[필수]** `create_tenant.sh` 내 bench 호출을 `docker exec docker-frappe-1 bench ...`로 수정 (Issue 1 해소)
- [ ] `MARIADB_ROOT_PASSWORD` 환경변수 안전하게 관리 (`.env` 파일 + `.gitignore`)
- [ ] Cloudflare API 토큰의 Zone:DNS:Edit 권한 확인 (safeclaw.kr 스코프)

### 실행 시 액션
```bash
export CLOUDFLARE_API_TOKEN="<redacted-cloudflare-token>"
export CLOUDFLARED_TUNNEL_ID="<redacted-tunnel-id>"
export MARIADB_ROOT_PASSWORD="<redacted-mariadb-root-password>"  # 운영 전 안전한 secret으로 주입

bash scripts/provisioning/create_tenant.sh noho admin@noho.kr \
    --plan starter --send-email
```

### 실행 후 검증
- [ ] `curl -H "Host: noho.hrms.safeclaw.kr" http://localhost:8000/` → 200/302 확인
- [ ] `https://noho.hrms.safeclaw.kr` 브라우저 접속 확인
- [ ] `admin@noho.kr` 임시 비번 이메일 수신 확인 (또는 터미널 출력 확인)
- [ ] Frappe 로그인 → 회사 기본 정보 입력 (Korea Workplace Profile)

---

## 5. 예상 실행 시간

| 단계 | 예상 시간 |
|------|-----------|
| bench new-site + DB 생성 | 2~3분 |
| erpnext install-app | 5~10분 |
| hrms install-app | 5~10분 |
| Cloudflare DNS + ingress | 1분 |
| DNS 전파 | 최대 5분 (Cloudflare proxy 즉시 적용) |
| **전체** | **약 15~25분** |

---

## 6. 요약

| 항목 | 상태 |
|------|------|
| Dry-run 실행 | 정상 완료 |
| Issue 1 (bench 호스트 없음) | **실제 실행 전 수정 필수** |
| Issue 2 (seed 경로 오류) | NOHO 미사용, 추후 수정 |
| Issue 3 (host header 라우팅) | 실행 후 curl 검증 필요 |
| Issue 4 (MariaDB 비번) | 운영 전 교체 권장 |
| cloudflared 라우팅 구조 | 정상 (catch-all 패턴 확인) |
| config/multi_site.json | 정상 (tenants: [] 초기 상태) |
| 실제 site 생성 | **재홍님 명시 승인 필요** |

---

*작성: Claude (Clo) | Phase 7-D dry-run | 실제 mutation 없음 확인*
