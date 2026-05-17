#!/bin/bash
# 한국 HRMS 자동 백업
#
# 사용법:
#   ./scripts/backup_korea_hrms.sh [--upload]
#
# 백업 대상 (bench backup --with-files 사용):
#   - MariaDB dump (site DB, bench 내장 암호화 키 처리)
#   - Frappe files (private / public)
#   - site config (site_config.json)
#
# 저장 위치:
#   - 로컬: /home/ubuntu/backups/hrms/{YYYYMMDD_HHMMSS}/
#   - --upload 옵션: S3/B2 (환경변수 BACKUP_S3_BUCKET 필요)
#
# 보관 정책:
#   - 로컬: 최근 7일 자동 삭제
#   - 원격: S3 Lifecycle 정책으로 30일 + 월 1회 1년 관리
#         (docs/operations/backup_recovery.md 참조)
#
# 필수 환경변수:
#   BENCH_PATH   bench 디렉터리 경로 (기본: /home/frappe/frappe-bench)
#   SITE_NAME    Frappe 사이트명    (기본: hrms.localhost)
#   BACKUP_DIR   로컬 백업 루트     (기본: /home/ubuntu/backups/hrms)
#
# --upload 시 추가 환경변수:
#   BACKUP_S3_BUCKET      S3/B2 버킷명  (예: s3://my-hrms-backups)
#   AWS_ACCESS_KEY_ID     AWS 또는 B2 액세스 키
#   AWS_SECRET_ACCESS_KEY AWS 또는 B2 시크릿 키
#   AWS_DEFAULT_REGION    AWS 리전 (기본: ap-northeast-2)
#   BACKUP_S3_ENDPOINT    B2 등 커스텀 엔드포인트 (선택)

set -euo pipefail
LC_ALL=C
export LC_ALL

# ── 기본값 ─────────────────────────────────────────────
BENCH_PATH="${BENCH_PATH:-/home/frappe/frappe-bench}"
SITE_NAME="${SITE_NAME:-hrms.localhost}"
BACKUP_DIR="${BACKUP_DIR:-/home/ubuntu/backups/hrms}"
LOCAL_RETAIN_DAYS=7
UPLOAD=false

# ── 인자 파싱 ───────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --upload) UPLOAD=true ;;
        --help|-h)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "[ERROR] 알 수 없는 옵션: $arg" >&2
            exit 1
            ;;
    esac
done

# ── 사전 검사 ───────────────────────────────────────────
if [[ ! -d "$BENCH_PATH" ]]; then
    echo "[ERROR] bench 디렉터리를 찾을 수 없습니다: $BENCH_PATH" >&2
    echo "        BENCH_PATH 환경변수를 확인하세요." >&2
    exit 1
fi

if ! command -v bench &>/dev/null && [[ ! -x "$BENCH_PATH/env/bin/bench" ]]; then
    echo "[ERROR] bench 명령을 찾을 수 없습니다." >&2
    exit 1
fi

# bench 경로 우선 사용
BENCH_CMD="bench"
if [[ -x "$BENCH_PATH/env/bin/bench" ]]; then
    BENCH_CMD="$BENCH_PATH/env/bin/bench"
fi

# ── 타임스탬프 및 디렉터리 생성 ───────────────────────
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DEST="$BACKUP_DIR/$TIMESTAMP"
mkdir -p "$DEST"

echo "[INFO] ======================================================"
echo "[INFO] 한국 HRMS 백업 시작: $TIMESTAMP"
echo "[INFO] 사이트: $SITE_NAME"
echo "[INFO] 저장 위치: $DEST"
echo "[INFO] ======================================================"

# ── bench backup 실행 ──────────────────────────────────
# bench backup은 sites/{site}/private/backups/ 에 파일을 생성합니다.
# --with-files: public/private 파일 포함
# --compress: gzip 압축
echo "[INFO] bench backup 실행 중..."
cd "$BENCH_PATH"
$BENCH_CMD --site "$SITE_NAME" backup --with-files --compress 2>&1 | tee "$DEST/backup.log"

# ── 생성된 백업 파일 수집 ──────────────────────────────
BENCH_BACKUP_DIR="$BENCH_PATH/sites/$SITE_NAME/private/backups"
if [[ ! -d "$BENCH_BACKUP_DIR" ]]; then
    echo "[ERROR] bench 백업 디렉터리를 찾을 수 없습니다: $BENCH_BACKUP_DIR" >&2
    exit 1
fi

# 가장 최근에 생성된 백업 파일들을 대상 디렉터리로 복사
# (최근 5분 이내 생성된 파일)
find "$BENCH_BACKUP_DIR" -maxdepth 1 -type f \
    \( -name "*.sql.gz" -o -name "*.tar" -o -name "*.json.gz" \) \
    -newer "$DEST/backup.log" \
    -exec cp -v {} "$DEST/" \; 2>/dev/null || true

# backup.log 생성 직후라 find 기준 시간이 같을 수 있으므로
# 30초 이내 파일도 추가로 확인
find "$BENCH_BACKUP_DIR" -maxdepth 1 -type f \
    \( -name "*.sql.gz" -o -name "*.tar" -o -name "*.json.gz" \) \
    -mmin -1 \
    -exec cp -v {} "$DEST/" \; 2>/dev/null || true

BACKUP_FILE_COUNT=$(find "$DEST" -maxdepth 1 -type f ! -name "backup.log" | wc -l)
if [[ "$BACKUP_FILE_COUNT" -eq 0 ]]; then
    echo "[ERROR] bench backup이 파일을 생성하지 않았습니다. backup.log를 확인하세요: $DEST/backup.log" >&2
    exit 1
fi

echo "[INFO] 수집된 백업 파일 수: $BACKUP_FILE_COUNT"
ls -lh "$DEST/"

# ── 메타데이터 기록 ────────────────────────────────────
cat > "$DEST/backup_meta.json" <<EOF
{
  "timestamp": "$TIMESTAMP",
  "site_name": "$SITE_NAME",
  "bench_path": "$BENCH_PATH",
  "backup_files": $(find "$DEST" -maxdepth 1 -type f ! -name "backup_meta.json" | sort | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin]))"),
  "hostname": "$(hostname -f 2>/dev/null || hostname)",
  "script_version": "5-B-2"
}
EOF

echo "[INFO] 메타데이터 저장: $DEST/backup_meta.json"

# ── S3/B2 업로드 (--upload 옵션) ──────────────────────
if [[ "$UPLOAD" == "true" ]]; then
    if [[ -z "${BACKUP_S3_BUCKET:-}" ]]; then
        echo "[WARN] BACKUP_S3_BUCKET이 설정되지 않았습니다. 업로드를 건너뜁니다." >&2
    else
        if ! command -v aws &>/dev/null; then
            echo "[WARN] aws CLI를 찾을 수 없습니다. 업로드를 건너뜁니다." >&2
        else
            echo "[INFO] S3/B2 업로드 시작: $BACKUP_S3_BUCKET"

            S3_OPTS=""
            if [[ -n "${BACKUP_S3_ENDPOINT:-}" ]]; then
                S3_OPTS="--endpoint-url $BACKUP_S3_ENDPOINT"
            fi

            # 원격 경로: bucket/hrms/{YYYYMMDD}/
            REMOTE_DATE=$(date +"%Y%m%d")
            REMOTE_PREFIX="$BACKUP_S3_BUCKET/hrms/$REMOTE_DATE/$TIMESTAMP/"

            # shellcheck disable=SC2086
            aws s3 cp "$DEST/" "$REMOTE_PREFIX" \
                --recursive \
                $S3_OPTS \
                --storage-class STANDARD_IA 2>&1 | tee -a "$DEST/backup.log"

            echo "[INFO] 업로드 완료: $REMOTE_PREFIX"
            echo "[NOTE] 원격 보관 정책(30일/월 1회 1년)은 S3 Lifecycle 설정으로 관리합니다."
            echo "[NOTE] docs/operations/backup_recovery.md > S3 셋업 섹션을 참조하세요."
        fi
    fi
fi

# ── 로컬 보관 정책: 7일 이상 된 백업 삭제 ─────────────
echo "[INFO] 로컬 보관 정책 적용 중 (${LOCAL_RETAIN_DAYS}일 초과 삭제)..."
if [[ -d "$BACKUP_DIR" ]]; then
    find "$BACKUP_DIR" -maxdepth 1 -mindepth 1 -type d \
        -mtime +${LOCAL_RETAIN_DAYS} \
        -exec rm -rf {} \; 2>/dev/null && \
        echo "[INFO] 오래된 백업 정리 완료" || \
        echo "[WARN] 오래된 백업 정리 중 일부 오류 발생 (계속 진행)"
fi

# ── 완료 ───────────────────────────────────────────────
echo "[INFO] ======================================================"
echo "[INFO] 백업 완료: $DEST"
echo "[INFO] ======================================================"
