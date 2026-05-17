# 멀티 테넌트 운영 가이드

> Frappe HRMS — 고객사별 site 격리 + 자동 프로비저닝
> 대상: safeclaw.kr HRMS 서비스 운영자

---

## 아키텍처 개요

```
인터넷
  │
  ▼
Cloudflare (safeclaw.kr DNS + Proxy)
  │  CNAME: {tenant}.hrms.safeclaw.kr → {tunnel_id}.cfargotunnel.com
  ▼
cloudflared tunnel (서버에 상주)
  │  ingress 규칙: hostname → http://localhost:{port}
  ▼
Frappe bench (frappe-bench/)
  ├── sites/acme.hrms.safeclaw.kr/      ← 고객사 A (별도 DB)
  ├── sites/beta-co.hrms.safeclaw.kr/   ← 고객사 B (별도 DB)
  └── sites/...
```

### 데이터 격리

Frappe의 **site = 별도 MariaDB 데이터베이스** 구조를 그대로 활용합니다.

| 항목 | 격리 수준 |
|------|-----------|
| 데이터베이스 | 완전 격리 (site당 1 DB) |
| 파일 스토리지 | 완전 격리 (`sites/{name}/private/files/`) |
| 설정 | 완전 격리 (`sites/{name}/site_config.json`) |
| 앱 코드 | 공유 (모든 site가 동일 apps/ 사용) |
| 스케줄러 | 공유 프로세스 (site별 큐 분리) |

---

## 새 고객사 추가 Step-by-Step

### 1. 사전 준비

```bash
# 필수 환경변수 확인
echo $CLOUDFLARE_API_TOKEN      # Zone:DNS:Edit 권한, safeclaw.kr 스코프
echo $CLOUDFLARED_TUNNEL_ID     # cloudflare tunnel UUID
echo $MARIADB_ROOT_PASSWORD     # MariaDB root 비번
```

필요한 경우 `.env` 파일에 저장 후 `source .env` 로 로드합니다.
`.env`는 절대 git에 커밋하지 마세요.

### 2. 스크립트 실행

```bash
# 기본 프로비저닝
./scripts/provisioning/create_tenant.sh acme admin@acme.co.kr

# 데모 데이터 포함
./scripts/provisioning/create_tenant.sh acme admin@acme.co.kr --seed-demo

# 플랜 지정
./scripts/provisioning/create_tenant.sh acme admin@acme.co.kr --plan professional

# dry-run 먼저 확인
./scripts/provisioning/create_tenant.sh acme admin@acme.co.kr --dry-run
```

### 3. 내부 동작 순서

1. **bench new-site** — MariaDB DB 생성, Frappe site 초기화
2. **앱 설치** — erpnext, hrms 순서로 install
3. **데모 시드** — `--seed-demo` 지정 시 한국 데모 데이터 삽입
4. **Cloudflare DNS** — CNAME `{tenant}.hrms.safeclaw.kr` 추가 (proxied)
5. **cloudflared ingress** — `~/.cloudflared/config.yml`에 hostname 규칙 삽입 (catch-all 직전), SIGHUP 전송
6. **host_name 설정** — `bench set-config host_name`으로 Frappe가 올바른 URL 생성
7. **레지스트리 업데이트** — `config/multi_site.json`의 tenants 배열에 항목 추가

### 4. 완료 후 확인

```bash
# site 접근 테스트
curl -I https://acme.hrms.safeclaw.kr

# Frappe 상태 확인
bench --site acme.hrms.safeclaw.kr doctor

# 레지스트리 확인
cat config/multi_site.json | python3 -m json.tool
```

---

## 고객사 삭제

```bash
# 반드시 dry-run 먼저
./scripts/provisioning/delete_tenant.sh acme --dry-run

# 실제 삭제 (확인 프롬프트 포함)
./scripts/provisioning/delete_tenant.sh acme
```

### 삭제 절차

1. **확인 프롬프트** — tenant_id를 직접 타이핑해야 진행됩니다.
2. **백업** (필수, 생략 불가) — `bench --site backup --with-files`
   - 저장 위치: `~/frappe-bench-backups/{tenant}/{timestamp}/`
3. **bench drop-site** — DB 및 site 디렉터리 삭제
4. **레지스트리** — status를 `deleted`로 변경 (항목은 보존)

### 삭제 후 수동 정리

스크립트가 **자동 처리하지 않는** 항목:

```
1. Cloudflare DNS CNAME 수동 제거
   Cloudflare 대시보드 > safeclaw.kr > DNS
   → {tenant}.hrms.safeclaw.kr CNAME 삭제

2. cloudflared ingress 수동 제거
   ~/.cloudflared/config.yml 편집
   → hostname: {tenant}.hrms.safeclaw.kr 블록 삭제
   → cloudflared 재시작: sudo systemctl restart cloudflared
      또는: kill -HUP $(pgrep cloudflared)
```

---

## 백업

### 단일 site 백업

```bash
bench --site acme.hrms.safeclaw.kr backup \
    --with-files \
    --backup-path ~/backups/acme/$(date +%Y%m%d)/
```

### 전체 site 일괄 백업

```bash
# bench/sites/ 하위 모든 active site 백업
BACKUP_BASE=~/frappe-bench-backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

for site_dir in ~/frappe-bench/sites/*/; do
    site=$(basename "${site_dir}")
    # 시스템 site 제외
    [[ "${site}" == "assets" ]] && continue
    [[ "${site}" == "apps.txt" ]] && continue
    [[ ! -f "${site_dir}/site_config.json" ]] && continue

    echo "백업: ${site}"
    bench --site "${site}" backup \
        --with-files \
        --backup-path "${BACKUP_BASE}/${site}/${TIMESTAMP}/" \
        || echo "[경고] ${site} 백업 실패"
done
```

### 백업 보존 정책 (권고)

| 보존 기간 | 백업 종류 | 목적 |
|-----------|----------|------|
| 7일       | 일별 백업 | 단기 복구 |
| 4주       | 주별 백업 | 월별 감사 |
| 12개월    | 월별 백업 | 연간 감사 |

---

## 마이그레이션 (전 site 일괄)

Frappe HRMS 앱 업데이트 시:

```bash
# 1. 앱 코드 업데이트
cd ~/frappe-bench
bench update --pull --patch --build --restart-supervisor
```

이 명령은 모든 site에 마이그레이션을 자동 적용합니다.

특정 site만 마이그레이션:

```bash
bench --site acme.hrms.safeclaw.kr migrate
```

마이그레이션 전 반드시 백업:

```bash
bench --site acme.hrms.safeclaw.kr backup --with-files
bench --site acme.hrms.safeclaw.kr migrate
```

---

## 비용 구조 (per-site)

### MariaDB 용량 추정

| 직원 수 | 1년 데이터 | DB 크기 추정 |
|---------|-----------|-------------|
| ~ 20명  | 급여 12회 | ~50 MB |
| ~ 100명 | 급여 12회 | ~200 MB |
| ~ 500명 | 급여 12회 | ~1 GB |

### 플랜별 리소스 한도

`config/multi_site.json`의 `quotas` 섹션 참조:

| 플랜         | 최대 직원 | 저장소 | DB 연결 |
|--------------|----------|--------|---------|
| starter      | 20명     | 5 GB   | 10      |
| professional | 100명    | 20 GB  | 25      |
| enterprise   | 무제한   | 무제한 | 50      |

한도 초과 모니터링은 현재 수동입니다.
`bench --site {site} execute hrms.utils.check_quota` (향후 구현 예정).

---

## Cloudflare + cloudflared 관계

```
safeclaw.kr (Cloudflare zone)
  └── *.hrms.safeclaw.kr  →  CNAME  →  {tunnel_id}.cfargotunnel.com
                                              │
                                      cloudflared (서버 상주)
                                              │
                                      config.yml ingress:
                                        - hostname: acme.hrms.safeclaw.kr
                                          service: http://localhost:8000
                                        - hostname: beta.hrms.safeclaw.kr
                                          service: http://localhost:8000
                                        - service: http_status:404  ← catch-all (항상 마지막)
```

**주의**: `cloudflared_ingress_add.py`는 새 규칙을 catch-all 직전에 삽입합니다.
catch-all이 중간에 오면 이후 규칙이 무시됩니다.

---

## 트러블슈팅

### site 접속 안 됨

```bash
# 1. cloudflared 터널 상태
cloudflared tunnel info

# 2. cloudflared 로그
journalctl -u cloudflared -f

# 3. Frappe 프로세스 확인
bench status

# 4. site 설정 확인
bench --site acme.hrms.safeclaw.kr show-config
```

### DNS 전파 지연

Cloudflare DNS는 보통 1분 내 전파됩니다.
`dig acme.hrms.safeclaw.kr` 로 확인.

### 백업 실패

```bash
# 디스크 용량 확인
df -h ~/frappe-bench/

# 백업 디렉터리 권한 확인
ls -la ~/frappe-bench-backups/
```

### cloudflared SIGHUP 후에도 새 호스트 접근 안 됨

```bash
# 설정 재확인
cat ~/.cloudflared/config.yml | grep -A3 acme

# cloudflared 완전 재시작 (SIGHUP으로 충분하지 않을 때)
sudo systemctl restart cloudflared
```
