# 한국 HRMS 백업 및 복구 운영 가이드

Wave 5-B-2 | 최종 업데이트: 2026-05-17

---

## 1. 개요

이 가이드는 노무법인 위너스 Frappe HRMS(한국화 버전)의 백업/복구 절차를 설명합니다.

**백업 방식:** Frappe 내장 `bench backup --with-files` 명령 사용  
- MariaDB 전체 덤프 (`.sql.gz`)  
- Frappe public/private 파일 (`-files.tar`, `-private-files.tar`)  
- site_config.json (암호화 키 포함)

---

## 2. 백업 주기 및 보관 정책

| 구분 | 주기 | 보관 기간 | 비고 |
|------|------|-----------|------|
| 일별 백업 | 매일 02:00 KST | 로컬 7일 | systemd timer 또는 cron |
| 원격 백업 | 매일 02:00 KST | S3 30일 | `--upload` 옵션 활성화 시 |
| 월간 스냅샷 | 매월 1일 | 1년 | S3 Lifecycle 규칙으로 자동 관리 |

**원격 보관 정책 (S3 Lifecycle):**  
로컬 스크립트가 아닌 S3 Lifecycle Policy로 관리합니다. 아래 S3 셋업 섹션 참조.

---

## 3. RTO / RPO 목표

| 지표 | 목표값 | 설명 |
|------|--------|------|
| **RPO** (복구 기점 목표) | 24시간 이내 | 일별 백업 기준 최대 데이터 손실 |
| **RTO** (복구 시간 목표) | 4시간 이내 | 백업 확인 → 복원 → 검증 완료 |

> 긴급 장애 시: 복원 담당자는 `restore_korea_hrms.sh` 실행 후 `bench doctor`로 상태 확인.

---

## 4. 재해 복구 시나리오

### 시나리오 A — 단순 데이터 오염 (실수로 레코드 삭제 등)

1. 해당 날짜 백업 디렉터리 확인: `/home/ubuntu/backups/hrms/`
2. 복구 스크립트 실행:
   ```bash
   ./scripts/restore_korea_hrms.sh \
       --backup-dir /home/ubuntu/backups/hrms/20260517_020000 \
       --site hrms.localhost
   ```
3. `bench --site hrms.localhost doctor` 로 상태 확인

### 시나리오 B — 서버 장애 (OS 재설치 필요)

1. 새 서버에 Frappe bench 및 HRMS 앱 설치 (docker/init.sh 참조)
2. S3에서 최신 백업 다운로드:
   ```bash
   aws s3 cp s3://your-bucket/hrms/20260517/ /home/ubuntu/backups/hrms/20260517/ \
       --recursive --endpoint-url https://s3.ap-northeast-2.amazonaws.com
   ```
3. 복구 스크립트 실행 (시나리오 A 동일)

### 시나리오 C — MariaDB 부분 손상

1. MariaDB를 `innodb_force_recovery=1`로 시작하여 덤프 추출 시도
2. 실패 시 S3 최신 백업으로 전체 복구 (시나리오 B)

---

## 5. 스크립트 사용법

### 5.1 백업 실행

```bash
# 기본 백업 (로컬 저장)
./scripts/backup_korea_hrms.sh

# S3/B2 업로드 포함
BACKUP_S3_BUCKET=s3://my-hrms-backups \
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE \
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY \
./scripts/backup_korea_hrms.sh --upload

# 사이트/경로 커스터마이즈
BENCH_PATH=/opt/frappe-bench \
SITE_NAME=mycompany.com \
./scripts/backup_korea_hrms.sh
```

### 5.2 복구 실행

```bash
# 가장 최근 백업으로 복구
./scripts/restore_korea_hrms.sh \
    --backup-dir /home/ubuntu/backups/hrms/20260517_020000

# 다른 사이트로 복구 (이전 사이트명 유지 불필요 시)
./scripts/restore_korea_hrms.sh \
    --backup-dir /home/ubuntu/backups/hrms/20260517_020000 \
    --site new-site.localhost
```

> **주의:** 복구 시 `YES` (대문자)를 직접 입력해야 진행됩니다. 자동화 환경에서는 `echo YES | ./scripts/restore_korea_hrms.sh ...` 형태를 사용하지 말고, 별도 워크플로를 구성하세요.

### 5.3 복구 드릴 실행

```bash
# 자동으로 최신 백업 사용
./scripts/backup_drill.sh

# 특정 백업으로 드릴
./scripts/backup_drill.sh \
    --backup-dir /home/ubuntu/backups/hrms/20260517_020000

# 드릴 결과 확인 후 테스트 사이트 유지
./scripts/backup_drill.sh --keep-test-site
```

---

## 6. 자동화 설정

### 6.1 systemd timer (권장)

```bash
# 설치
sudo cp scripts/systemd/hrms-backup.service /etc/systemd/system/
sudo cp scripts/systemd/hrms-backup.timer   /etc/systemd/system/

# service 파일에서 경로 및 환경변수 확인 후 활성화
sudo systemctl daemon-reload
sudo systemctl enable --now hrms-backup.timer

# 상태 확인
sudo systemctl status hrms-backup.timer
sudo journalctl -u hrms-backup.service -f
```

### 6.2 crontab (대안)

```bash
crontab -e
```

아래 항목 추가:

```cron
# 매일 02:00 KST — 한국 HRMS 백업 (로컬 저장)
0 2 * * * /bin/bash /home/ubuntu/workspaces/seojaehong-hrms-100h/scripts/backup_korea_hrms.sh >> /var/log/hrms-backup.log 2>&1

# 매일 02:00 KST — S3 업로드 포함
# 0 2 * * * BACKUP_S3_BUCKET=s3://my-bucket AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... /bin/bash /home/ubuntu/workspaces/seojaehong-hrms-100h/scripts/backup_korea_hrms.sh --upload >> /var/log/hrms-backup.log 2>&1
```

### 6.3 복구 드릴 자동화 (월 1회)

```cron
# 매월 1일 03:00 — 복구 드릴
0 3 1 * * /bin/bash /home/ubuntu/workspaces/seojaehong-hrms-100h/scripts/backup_drill.sh >> /var/log/hrms-drill.log 2>&1
```

---

## 7. S3 / Backblaze B2 셋업

### 7.1 필요 계정/권한 항목

| 항목 | AWS S3 | Backblaze B2 |
|------|--------|--------------|
| 버킷명 | `BACKUP_S3_BUCKET=s3://버킷명` | 동일 |
| 액세스 키 | `AWS_ACCESS_KEY_ID` | Application Key ID |
| 시크릿 키 | `AWS_SECRET_ACCESS_KEY` | Application Key |
| 리전 | `AWS_DEFAULT_REGION=ap-northeast-2` | (B2는 불필요) |
| 엔드포인트 | 불필요 | `BACKUP_S3_ENDPOINT=https://s3.us-west-004.backblazeb2.com` |

### 7.2 S3 IAM 최소 권한 정책

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/hrms/*"
      ]
    }
  ]
}
```

### 7.3 S3 Lifecycle 정책 (원격 보관 규칙)

AWS 콘솔 또는 CLI로 적용. 아래 정책은 두 가지 규칙을 포함합니다:

1. **30일 후 만료** — 일별 백업 삭제
2. **월별 스냅샷 1년 보존** — 매월 1일 업로드된 파일은 1년 후 삭제

```bash
# 예시: AWS CLI로 lifecycle 적용
aws s3api put-bucket-lifecycle-configuration \
    --bucket your-bucket-name \
    --lifecycle-configuration '{
      "Rules": [
        {
          "ID": "hrms-daily-expire-30d",
          "Status": "Enabled",
          "Filter": {"Prefix": "hrms/"},
          "Expiration": {"Days": 30}
        },
        {
          "ID": "hrms-monthly-expire-1y",
          "Status": "Enabled",
          "Filter": {"Prefix": "hrms/monthly/"},
          "Expiration": {"Days": 365}
        }
      ]
    }'
```

> 월별 스냅샷 경로 구분: 드릴 또는 수동 실행 시 `--monthly` 플래그(향후 구현 예정)를 사용하거나, cron에서 매월 1일 실행 시 `REMOTE_PREFIX`에 `monthly/` 경로를 수동 설정하세요.

---

## 8. 검증 드릴 실행 방법

### 정기 드릴 권장 주기

| 드릴 종류 | 주기 | 담당자 |
|-----------|------|--------|
| 자동 드릴 (backup_drill.sh) | 월 1회 (매월 1일 03:00) | 시스템 자동 |
| 수동 복원 검증 | 분기 1회 | 운영자 직접 확인 |
| 전체 재해 복구 훈련 | 연 1회 | 전체 팀 |

### 드릴 통과 기준

- `bench restore` 종료 코드 0
- `bench migrate` 종료 코드 0  
- `tabEmployee` 레코드 수 1건 이상
- 드릴 로그 `/tmp/hrms_drill_*.log` 에 `[PASS]` 확인

### 드릴 실패 시 대응

1. 드릴 로그 확인: `/tmp/hrms_drill_*.log`
2. 백업 파일 무결성 확인: `gzip -t *.sql.gz`
3. 백업 스크립트 재실행 후 새 백업으로 드릴 재시도
4. 반복 실패 시 Frappe 버전 호환성 및 MariaDB 설정 점검

---

## 9. 주의사항 및 알려진 제약

- `restore_korea_hrms.sh`는 `--admin-password` 기본값을 `admin`으로 설정합니다.  
  운영 복구 시 반드시 `ADMIN_PASSWORD` 환경변수로 실제 비밀번호를 지정하세요.
- `bench backup --with-files`는 bench가 설치된 서버에서만 실행 가능합니다.  
  Docker 환경에서는 컨테이너 내부에서 실행하거나 Frappe CLI를 직접 호출해야 합니다.
- S3 업로드 시 `BACKUP_S3_BUCKET`이 미설정이면 업로드를 건너뛰되 오류로 종료하지 않습니다 (`[WARN]`만 출력).
- 로컬 보관 7일 정책은 `mtime` 기준입니다. NFS 마운트 등 파일 시스템에서 `mtime`이 신뢰할 수 없는 경우 cron 기반 수동 삭제 스크립트를 추가 구성하세요.
