# NOHO 프로비저닝 상태 — Blocker 해소 후

> 업데이트: 2026-05-18 | PR: fix/create-tenant-docker-exec-wrap
> 이전 보고서: [noho_provisioning_dryrun_report.md](noho_provisioning_dryrun_report.md)

---

## 1. Blocker 해소 결과

### [RESOLVED] Issue 1 — bench docker-exec 래핑 (7곳)

`bench`는 host에 없고 `docker-frappe-1` 컨테이너 내부에만 설치됨.
`create_tenant.sh`의 모든 bench 관련 호출 7곳을 `docker exec` 래핑으로 수정.

상수 블록에 두 변수 추가:
```bash
FRAPPE_CONTAINER="${FRAPPE_CONTAINER:-docker-frappe-1}"
BENCH_WORKDIR="${BENCH_WORKDIR:-/home/frappe/frappe-bench}"
```

수정된 7곳:

| # | 위치 | 수정 내용 |
|---|------|-----------|
| 1 | `command -v bench` 사전 확인 | `docker exec "${FRAPPE_CONTAINER}" which bench` 로 교체 |
| 2 | 중복 site 확인 (`-d "${BENCH_PATH}/sites/...`) | `docker exec … test -d "${BENCH_WORKDIR}/sites/…"` 로 교체 |
| 3 | `bench new-site` | `docker exec -w "${BENCH_WORKDIR}" "${FRAPPE_CONTAINER}" bench new-site …` |
| 4 | `bench --site … install-app erpnext` | 동일 래핑 |
| 5 | `bench --site … install-app hrms` | 동일 래핑 |
| 6 | `bench --site … set-config host_name` | 동일 래핑 |
| 7 | `bench --site … execute frappe.utils.user.reset_password` | 동일 래핑 |

### [RESOLVED] Issue 2 — 데모 시드 모듈 경로 수정

```diff
- hrms.regional.south_korea.demo.seed_demo_data
+ hrms.regional.south_korea.demo_seed.seed_korea_demo
```

실제 파일: `hrms/regional/south_korea/demo_seed.py`, 함수: `def seed_korea_demo()`

---

## 2. NOHO Dry-Run 출력 (수정 후)

**실행 명령:**
```bash
export CLOUDFLARE_API_TOKEN=$(cat /home/ubuntu/.config/safeclaw/cf_token)
export CLOUDFLARED_TUNNEL_ID="a04b8f7a-8b04-49f7-8c73-3fc1c07519fb"
export MARIADB_ROOT_PASSWORD="123"

bash scripts/provisioning/create_tenant.sh noho-test admin@noho.kr \
    --plan starter --dry-run
```

**출력 전문:**
```
━━━ 1/8  사전 확인 ━━━
  tenant_id : noho-test
  site      : noho-test.hrms.safeclaw.kr
  plan      : starter
  email     : admin@noho.kr

━━━ 2/8  bench new-site ━━━
[dry-run] docker exec -w /home/frappe/frappe-bench docker-frappe-1 bench new-site noho-test.hrms.safeclaw.kr \
  --mariadb-root-password 123 \
  --admin-password <자동생성> \
  --no-mariadb-socket \
  --db-name tenant_noho_test

━━━ 3/8  한국 모듈 설치 (erpnext, hrms) ━━━
[dry-run] docker exec -w /home/frappe/frappe-bench docker-frappe-1 bench --site noho-test.hrms.safeclaw.kr install-app erpnext
[dry-run] docker exec -w /home/frappe/frappe-bench docker-frappe-1 bench --site noho-test.hrms.safeclaw.kr install-app hrms
(--seed-demo 미설정 — 데모 시드 생략)

━━━ 5/8  Cloudflare DNS CNAME 추가 ━━━
[dry-run] python3 …/cloudflare_dns_add.py noho-test a04b8f7a-8b04-49f7-8c73-3fc1c07519fb

━━━ 6/8  cloudflared ingress 등록 ━━━
[dry-run] python3 …/cloudflared_ingress_add.py noho-test 8000

━━━ 7/8  Frappe site host_name 설정 ━━━
[dry-run] docker exec -w /home/frappe/frappe-bench docker-frappe-1 bench --site noho-test.hrms.safeclaw.kr set-config host_name https://noho-test.hrms.safeclaw.kr

━━━ 8/8  레지스트리 업데이트 ━━━
[dry-run] config/multi_site.json에 noho-test 추가

════════════════════════════════════════════
  프로비저닝 완료
  site      : https://noho-test.hrms.safeclaw.kr
  admin     : admin@noho.kr
════════════════════════════════════════════
```

**결론**: 8단계 모두 정상 출력. docker-exec 래핑 확인 완료.

---

## 3. Fix 3 — Host Header 라우팅 검증 (실제 site 생성 후)

실제 site 생성 후 아래 명령으로 확인:

```bash
curl -s -o /dev/null -w "%{http_code}" \
    -H "Host: noho-test.hrms.safeclaw.kr" \
    http://localhost:8000/
# 200 또는 302 → 정상
# 404 → default_site fallback 발생 → common_site_config.json 확인 필요
```

현재 `sites/` 내 사이트: `hrms.localhost` (기존 운영 사이트)
Frappe는 Host header 값으로 `sites/<hostname>/` 디렉터리를 찾아 라우팅하므로,
`noho-test.hrms.safeclaw.kr` site 디렉터리 생성 후 자동 라우팅 예상.

---

## 4. 실제 실행 단계 (재홍님 명시 승인 필요)

```bash
export CLOUDFLARE_API_TOKEN=$(cat /home/ubuntu/.config/safeclaw/cf_token)
export CLOUDFLARED_TUNNEL_ID="a04b8f7a-8b04-49f7-8c73-3fc1c07519fb"
export MARIADB_ROOT_PASSWORD="123"   # 운영 전 교체 권장

bash scripts/provisioning/create_tenant.sh noho admin@noho.kr \
    --plan starter
```

실행 후 검증:
- [ ] `curl -H "Host: noho.hrms.safeclaw.kr" http://localhost:8000/` → 200/302 확인
- [ ] `https://noho.hrms.safeclaw.kr` 브라우저 접속
- [ ] 관리자 비번 메모 (터미널 출력의 `임시 비번` 값)
- [ ] Frappe 첫 로그인 → 회사 기본 정보 (Korea Workplace Profile) 설정

---

## 5. 예상 소요 시간

| 단계 | 예상 시간 |
|------|-----------|
| bench new-site + DB 생성 | 2~3분 |
| erpnext install-app | 5~10분 |
| hrms install-app | 5~10분 |
| Cloudflare DNS + ingress | 1분 |
| DNS 전파 | 최대 5분 (Cloudflare proxy 즉시 적용) |
| **전체** | **약 15~25분** |

---

## 6. 잔여 이슈

| 항목 | 상태 |
|------|------|
| bench 7곳 docker-exec 래핑 | **해소 완료** |
| 데모 시드 모듈 경로 | **해소 완료** |
| Host Header 라우팅 검증 | 실제 site 생성 후 curl 확인 필요 (deferred) |
| MariaDB root 비번 평문 | 운영 투입 전 교체 권장 (개발 환경 수준) |
| Frappe site 실제 생성 | **재홍님 명시 승인 필요** |

---

*작성: Claude (Clo) | fix/create-tenant-docker-exec-wrap | mutation 없음*
