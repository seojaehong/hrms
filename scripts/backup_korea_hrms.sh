#!/bin/bash
# 한국 HRMS 자동 백업
#
# 사용법:
#   ./scripts/backup_korea_hrms.sh [--upload] [--dry-run]
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
#   BENCH_CONTAINER  Docker 컨테이너명 (기본: docker-frappe-1)
#                    Frappe bench가 컨테이너 내부에서 실행됩니다.
#   BENCH_PATH       bench 디렉터리 경로 — 컨테이너 내부 기준
#                    (기본: /home/frappe/frappe-bench)
#   SITE_NAME        Frappe 사이트명 (기본: hrms.localhost)
#   BACKUP_DIR       로컬 백업 루트  (기본: /home/ubuntu/backups/hrms)
#
# --upload 시 추가 환경변수:
#   BACKUP_S3_BUCKET      S3/B2 버킷명  (예: s3://my-hrms-backups)
#   AWS_ACCESS_KEY_ID     AWS 또는 B2 액세스 키
#   AWS_SECRET_ACCESS_KEY AWS 또는 B2 시크릿 키
#   AWS_DEFAULT_REGION    AWS 리전 (기본: ap-northeast-2)
#   BACKUP_S3_ENDPOINT    B2 등 커스텀 엔드포인트 (선택)
#
# Phase 7-B-1: Frappe bench는 docker-frappe-1 컨테이너 내부에서 실행됨.
#   bench backup은 docker exec 로 실행하고, 결과물은 docker cp 로 호스트로 수집.

set -euo pipefail
LC_ALL=C
export LC_ALL

# ── 기본값 ─────────────────────────────────────────────
BENCH_CONTAINER="${BENCH_CONTAINER:-docker-frappe-1}"
BENCH_PATH="${BENCH_PATH:-/home/frappe/frappe-bench}"
SITE_NAME="${SITE_NAME:-hrms.localhost}"
BACKUP_DIR="${BACKUP_DIR:-/home/ubuntu/backups/hrms}"
LOCAL_RETAIN_DAYS=7
UPLOAD=false
DRY_RUN=false

# ── 인자 파싱 ───────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --upload) UPLOAD=true ;;
        --dry-run) DRY_RUN=true ;;
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

# ── dry-run 모드 ────────────────────────────────────────
if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY-RUN] 백업 파라미터 확인:"
    echo "  BENCH_CONTAINER : $BENCH_CONTAINER"
    echo "  BENCH_PATH      : $BENCH_PATH (컨테이너 내부)"
    echo "  SITE_NAME       : $SITE_NAME"
    echo "  BACKUP_DIR      : $BACKUP_DIR"
    echo "  UPLOAD          : $UPLOAD"
    echo "[DRY-RUN] 컨테이너 상태:"
    DRY_STATUS=$(docker inspect --format '{{.State.Status}}' "$BENCH_CONTAINER" 2>/dev/null || echo "not_found")
    if [ "$DRY_STATUS" = "running" ]; then
        echo "[DRY-RUN] 컨테이너 $BENCH_CONTAINER 가동 중 — OK"
    else
        echo "[DRY-RUN][WARN] 컨테이너 $BENCH_CONTAINER 상태=$DRY_STATUS — 정지 또는 없음 (실제 백업 불가)"
    fi
    echo "[DRY-RUN] bench --version:"
    docker exec "$BENCH_CONTAINER" bench --version 2>&1 || true
    echo "[DRY-RUN] 완료. 실제 백업을 실행하려면 --dry-run 없이 실행하세요."
    exit 0
fi

# ── 사전 검사 ───────────────────────────────────────────
if ! docker inspect --format '{{.State.Status}}' "$BENCH_CONTAINER" 2>/dev/null | grep -q "running"; then
    echo "[ERROR] Frappe 컨테이너가 실행 중이지 않습니다: $BENCH_CONTAINER" >&2
    echo "        BENCH_CONTAINER 환경변수 또는 컨테이너 상태를 확인하세요." >&2
    exit 1
fi

if ! docker exec "$BENCH_CONTAINER" bench --version &>/dev/null; then
    echo "[ERROR] 컨테이너 내에서 bench 명령을 찾을 수 없습니다." >&2
    exit 1
fi

# ── 임시 디렉터리 생성 + 종료 시 자동 정리 ──────────
TMP_COPY_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_COPY_DIR"' EXIT

# ── 타임스탬프 및 디렉터리 생성 ───────────────────────
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DEST="$BACKUP_DIR/$TIMESTAMP"
mkdir -p "$DEST"

echo "[INFO] ======================================================"
echo "[INFO] 한국 HRMS 백업 시작: $TIMESTAMP"
echo "[INFO] 컨테이너: $BENCH_CONTAINER"
echo "[INFO] 사이트: $SITE_NAME"
echo "[INFO] 저장 위치: $DEST"
echo "[INFO] ======================================================"

# ── bench backup 실행 (컨테이너 내부) ─────────────────
# bench backup은 sites/{site}/private/backups/ 에 파일을 생성합니다.
# --with-files: public/private 파일 포함
# --compress: gzip 압축
echo "[INFO] bench backup 실행 중 (docker exec)..."

# 컨테이너 내부에 타임스탬프 마커 생성 (backup 시작 시점 기록)
CONTAINER_MARKER="/tmp/backup_started_marker_$TIMESTAMP"
docker exec "$BENCH_CONTAINER" touch "$CONTAINER_MARKER"

docker exec -w "$BENCH_PATH" "$BENCH_CONTAINER" \
    bench --site "$SITE_NAME" backup --with-files --compress \
    2>&1 | tee "$DEST/backup.log"

# ── 신규 생성 파일만 개별 docker cp ──────────────────
CONTAINER_BACKUP_DIR="$BENCH_PATH/sites/$SITE_NAME/private/backups"

echo "[INFO] 컨테이너에서 신규 백업 파일 수집 중 (docker cp)..."
NEW_FILES=$(docker exec "$BENCH_CONTAINER" find "$CONTAINER_BACKUP_DIR" \
    -newer "$CONTAINER_MARKER" -type f 2>/dev/null)
docker exec "$BENCH_CONTAINER" rm -f "$CONTAINER_MARKER"

for f in $NEW_FILES; do
    docker cp "$BENCH_CONTAINER:$f" "$TMP_COPY_DIR/"
done

find "$TMP_COPY_DIR" -maxdepth 1 -type f \
    \( -name "*.sql.gz" -o -name "*.tgz" -o -name "*.tar" -o -name "*.json" \) \
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
  "bench_container": "$BENCH_CONTAINER",
  "bench_path": "$BENCH_PATH",
  "backup_files": $(find "$DEST" -maxdepth 1 -type f ! -name "backup_meta.json" | sort | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin]))"),
  "hostname": "$(hostname -f 2>/dev/null || hostname)",
  "script_version": "7-B-1"
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
