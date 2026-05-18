# Frappe HRMS Korea — Cron & 운영 서비스 현황

> **내부 운영 인수인계 문서 — 외부 공유 금지**

> 최종 업데이트: 2026-05-18 (Phase 7-B)
> 서버 TZ: UTC. KST = UTC+9

---

## 1. 현재 가동 중인 서비스

### 1-A. 모니터링 스택 (Docker)

| 컨테이너 | 이미지 | 포트 | 상태 |
|---|---|---|---|
| frappe_prometheus | prom/prometheus:v2.52.0 | 9090 | **Running** |
| frappe_grafana | grafana/grafana:11.1.0 | 3000 | **Running** |
| frappe_loki | grafana/loki:3.1.0 | 3100 | **Running** |
| frappe_alertmanager | prom/alertmanager:v0.27.0 | 9093 | **Running** |
| frappe_promtail | grafana/promtail:3.1.0 | — | **Running** (timestamp warn only) |
| frappe_exporter | python:3.11-slim | 9101 | **Running** |
| frappe_alert_webhook | python:3.11-slim | 5001 | **Running** |

**시작/정지 명령:**
```bash
# 시작
docker compose -f /home/ubuntu/workspaces/seojaehong-hrms-100h/docker/monitoring/docker-compose.yml \
  --env-file /home/ubuntu/workspaces/seojaehong-hrms-100h/docker/monitoring/.env up -d

# 정지
docker compose -f /home/ubuntu/workspaces/seojaehong-hrms-100h/docker/monitoring/docker-compose.yml down

# 로그
docker compose -f /home/ubuntu/workspaces/seojaehong-hrms-100h/docker/monitoring/docker-compose.yml logs -f

# 상태 확인
docker compose -f /home/ubuntu/workspaces/seojaehong-hrms-100h/docker/monitoring/docker-compose.yml ps
```

**Grafana 접속:** http://localhost:3000 (admin / 비밀번호는 안전 채널 확인)

---

### 1-B. HRMS 백업 cron (user-level crontab)

```
# 매일 02:00 KST (17:00 UTC) — 자동 백업
0 17 * * * /bin/bash /home/ubuntu/workspaces/seojaehong-hrms-100h/scripts/backup_korea_hrms.sh >> /home/ubuntu/backups/hrms/cron.log 2>&1
```

**백업 디렉터리:** `/home/ubuntu/backups/hrms/`
**보관 정책:** 최근 7일 자동 삭제 (스크립트 내장)
**백업 내용:**
- DB dump: `*.sql.gz` (~1.3 MiB)
- Files public: `*-files.tgz`
- Files private: `*-private-files.tgz`
- Site config: `*-site_config_backup.json`

**확인 방법:**
```bash
ls -la /home/ubuntu/backups/hrms/          # 백업 디렉터리 목록
cat /home/ubuntu/backups/hrms/cron.log     # cron 실행 로그
```

---

## 2. 알림 채널 (Telegram)

| 항목 | 값 |
|---|---|
| 봇 | Hermes 봇 (8711744272) |
| 수신 chat_id | 8699916672 (서재홍) |
| 연결 경로 | Alertmanager → alert-webhook:5001 → Telegram API |

**alert_webhook 설정 파일:**
`/home/ubuntu/workspaces/seojaehong-hrms-100h/docker/monitoring/.env`

---

## 3. 아키텍처 메모

### Bench 위치
Frappe bench는 호스트에 없고 **Docker 컨테이너 내부**에서 실행됨:
- 컨테이너명: `docker-frappe-1`
- 컨테이너 내 bench 경로: `/home/frappe/frappe-bench`

백업 스크립트는 `docker exec` + `docker cp` 방식으로 실행.

### Promtail 경고 (정상)
Promtail이 wordpress-blog 컨테이너의 오래된 로그(>7일)를 Loki에 전송 시도하면  
`timestamp too old` 오류가 발생하나, 이는 Loki 보존 정책 정상 동작임 (무시 가능).  
현재 시점 이후 신규 로그는 정상 수집됨.

---

## 4. Enable / Disable 방법

### 백업 cron 활성화 확인
```bash
crontab -l | grep "backup_korea_hrms"
```

### 백업 cron 일시 중지
```bash
# crontab -e 로 해당 줄 앞에 # 추가
crontab -e
```

### 모니터링 스택 재시작
```bash
docker compose -f /home/ubuntu/workspaces/seojaehong-hrms-100h/docker/monitoring/docker-compose.yml restart
```

### 모니터링 스택 자동 시작 (서버 재부팅 시)
모든 컨테이너는 `restart: unless-stopped` 정책이므로 서버 재부팅 후 Docker 데몬이 시작되면 자동 복구됨.

---

## 5. 사용자 액션 필요 사항

| 항목 | 상태 | 필요 작업 |
|---|---|---|
| systemd timer (hrms-backup) | 미등록 | `sudo cp scripts/systemd/hrms-backup.* /etc/systemd/system/ && sudo systemctl enable --now hrms-backup.timer` |
| S3/B2 원격 백업 | 미설정 | `.env`에 `BACKUP_S3_BUCKET`, `AWS_*` 설정 후 스크립트에 `--upload` 추가 |
| Telegram 실제 알림 테스트 | 미완 | `curl -X POST http://localhost:5001/ -d '{"alerts":[{"labels":{"alertname":"TestAlert"},"status":"firing","annotations":{}}],"status":"firing"}' -H 'Content-Type: application/json'` |
| Frappe API Key (exporter) | 미설정 | Frappe 관리자 > API Key 발급 후 `.env`에 `FRAPPE_API_KEY`, `FRAPPE_API_SECRET` 설정 |

---

## 6. 수동 백업 실행

```bash
# dry-run (파라미터 확인만)
bash /home/ubuntu/workspaces/seojaehong-hrms-100h/scripts/backup_korea_hrms.sh --dry-run

# 실제 백업
bash /home/ubuntu/workspaces/seojaehong-hrms-100h/scripts/backup_korea_hrms.sh

# 결과 확인
ls -lah /home/ubuntu/backups/hrms/
```
