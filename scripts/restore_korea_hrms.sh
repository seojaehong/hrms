#!/bin/bash
# 한국 HRMS 복구 스크립트
#
# 사용법:
#   ./scripts/restore_korea_hrms.sh --backup-dir <백업_디렉터리> [--site <사이트명>]
#
# 설명:
#   backup_korea_hrms.sh 가 생성한 백업 디렉터리에서 Frappe 사이트를 복원합니다.
#   bench restore 명령을 사용합니다.
#
# 필수 인자:
#   --backup-dir <경로>   백업 디렉터리 (backup_meta.json 이 있는 디렉터리)
#
# 선택 인자:
#   --site <사이트명>     복원 대상 사이트 (기본: 백업과 동일 사이트명)
#   --bench-path <경로>   bench 디렉터리 (기본: /home/frappe/frappe-bench)
#
# !! 주의 !!
#   이 스크립트는 대상 사이트의 데이터를 완전히 덮어씁니다.
#   반드시 운영 전에 테스트 사이트에서 먼저 확인하십시오.

set -euo pipefail
LC_ALL=C
export LC_ALL

# ── 기본값 ─────────────────────────────────────────────
BENCH_PATH="${BENCH_PATH:-/home/frappe/frappe-bench}"
BACKUP_DIR_ARG=""
SITE_NAME_ARG=""

# ── 인자 파싱 ───────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --backup-dir)
            BACKUP_DIR_ARG="$2"
            shift 2
            ;;
        --site)
            SITE_NAME_ARG="$2"
            shift 2
            ;;
        --bench-path)
            BENCH_PATH="$2"
            shift 2
            ;;
        --help|-h)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "[ERROR] 알 수 없는 옵션: $1" >&2
            exit 1
            ;;
    esac
done

# ── 필수 인자 검사 ─────────────────────────────────────
if [[ -z "$BACKUP_DIR_ARG" ]]; then
    echo "[ERROR] --backup-dir 옵션이 필요합니다." >&2
    echo "사용법: $0 --backup-dir <백업_디렉터리> [--site <사이트명>]" >&2
    exit 1
fi

if [[ ! -d "$BACKUP_DIR_ARG" ]]; then
    echo "[ERROR] 백업 디렉터리가 존재하지 않습니다: $BACKUP_DIR_ARG" >&2
    exit 1
fi

# ── 메타데이터에서 사이트명 읽기 ──────────────────────
META_FILE="$BACKUP_DIR_ARG/backup_meta.json"
if [[ -f "$META_FILE" ]]; then
    BACKUP_SITE=$(python3 -c "import json,sys; d=json.load(open('$META_FILE')); print(d.get('site_name',''))" 2>/dev/null || true)
    BACKUP_TIMESTAMP=$(python3 -c "import json,sys; d=json.load(open('$META_FILE')); print(d.get('timestamp',''))" 2>/dev/null || true)
else
    echo "[WARN] backup_meta.json을 찾을 수 없습니다. 백업 파일에서 직접 사이트명을 추론합니다." >&2
    BACKUP_SITE=""
    BACKUP_TIMESTAMP="unknown"
fi

SITE_NAME="${SITE_NAME_ARG:-$BACKUP_SITE}"
if [[ -z "$SITE_NAME" ]]; then
    echo "[ERROR] 사이트명을 확인할 수 없습니다. --site 옵션을 명시적으로 지정하세요." >&2
    exit 1
fi

# ── bench 명령 확인 ────────────────────────────────────
if [[ ! -d "$BENCH_PATH" ]]; then
    echo "[ERROR] bench 디렉터리를 찾을 수 없습니다: $BENCH_PATH" >&2
    exit 1
fi

BENCH_CMD="bench"
if [[ -x "$BENCH_PATH/env/bin/bench" ]]; then
    BENCH_CMD="$BENCH_PATH/env/bin/bench"
fi

# ── 백업 파일 검색 ─────────────────────────────────────
SQL_FILE=$(find "$BACKUP_DIR_ARG" -maxdepth 1 -name "*.sql.gz" | sort | head -1)
# "*-private-files.tar" 을 먼저 제외하여 public files tar 과 혼동하지 않도록 함
FILES_BACKUP=$(find "$BACKUP_DIR_ARG" -maxdepth 1 -name "*-files.tar" ! -name "*-private-files.tar" | sort | head -1)
PRIVATE_BACKUP=$(find "$BACKUP_DIR_ARG" -maxdepth 1 -name "*-private-files.tar" | sort | head -1)

if [[ -z "$SQL_FILE" ]]; then
    echo "[ERROR] SQL 덤프 파일(*.sql.gz)을 찾을 수 없습니다: $BACKUP_DIR_ARG" >&2
    exit 1
fi

echo "[INFO] ======================================================"
echo "[INFO] 한국 HRMS 복구 준비"
echo "[INFO] 백업 타임스탬프: $BACKUP_TIMESTAMP"
echo "[INFO] 백업 디렉터리: $BACKUP_DIR_ARG"
echo "[INFO] SQL 파일: $SQL_FILE"
echo "[INFO] 파일 백업: ${FILES_BACKUP:-없음}"
echo "[INFO] Private 파일 백업: ${PRIVATE_BACKUP:-없음}"
echo "[INFO] 복원 대상 사이트: $SITE_NAME"
echo "[INFO] bench 경로: $BENCH_PATH"
echo "[INFO] ======================================================"
echo ""
echo "[!! 경고 !!]"
echo "  이 작업은 사이트 '$SITE_NAME'의 데이터를 완전히 덮어씁니다."
echo "  운영 데이터가 있는 사이트에서 실행하기 전에"
echo "  반드시 현재 상태를 별도 백업하십시오."
echo ""
read -rp "정말 복구할까요? 계속하려면 YES (대문자)를 입력하세요: " CONFIRM

if [[ "$CONFIRM" != "YES" ]]; then
    echo "[INFO] 복구를 취소했습니다."
    exit 0
fi

echo ""
echo "[INFO] 복구를 시작합니다..."

# ── 현재 사이트 사전 백업 (안전망) ────────────────────
echo "[INFO] 복구 전 현재 사이트 백업 중 (안전망)..."
cd "$BENCH_PATH"
PRE_RESTORE_TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
$BENCH_CMD --site "$SITE_NAME" backup --compress 2>&1 || \
    echo "[WARN] 사전 백업 실패. 복구는 계속 진행됩니다." >&2

# ── bench restore 실행 ─────────────────────────────────
echo "[INFO] bench restore 실행 중..."

# 파일 백업이 있을 때만 --with-*-files 옵션 추가 (없으면 /dev/null 전달 시 오류 발생)
RESTORE_FILE_OPTS=""
if [[ -n "$FILES_BACKUP" ]]; then
    RESTORE_FILE_OPTS="$RESTORE_FILE_OPTS --with-public-files $FILES_BACKUP"
fi
if [[ -n "$PRIVATE_BACKUP" ]]; then
    RESTORE_FILE_OPTS="$RESTORE_FILE_OPTS --with-private-files $PRIVATE_BACKUP"
fi

# SQL 복원 (shellcheck disable=SC2086: RESTORE_FILE_OPTS는 의도적으로 단어 분리)
# shellcheck disable=SC2086
$BENCH_CMD --site "$SITE_NAME" restore "$SQL_FILE" \
    --admin-password "${ADMIN_PASSWORD:-admin}" \
    $RESTORE_FILE_OPTS \
    2>&1 | tee /tmp/restore_korea_hrms_$PRE_RESTORE_TIMESTAMP.log || {
    echo "[ERROR] bench restore 실패. 로그: /tmp/restore_korea_hrms_$PRE_RESTORE_TIMESTAMP.log" >&2
    exit 1
}

# ── 마이그레이션 실행 ──────────────────────────────────
echo "[INFO] bench migrate 실행 중 (스키마 동기화)..."
$BENCH_CMD --site "$SITE_NAME" migrate 2>&1 | tee -a /tmp/restore_korea_hrms_$PRE_RESTORE_TIMESTAMP.log

# ── 캐시 초기화 ───────────────────────────────────────
echo "[INFO] 캐시 초기화..."
$BENCH_CMD --site "$SITE_NAME" clear-cache 2>&1

# ── 완료 ───────────────────────────────────────────────
echo ""
echo "[INFO] ======================================================"
echo "[INFO] 복구 완료!"
echo "[INFO] 사이트: $SITE_NAME"
echo "[INFO] 소스 백업: $BACKUP_TIMESTAMP"
echo "[INFO] 복구 로그: /tmp/restore_korea_hrms_$PRE_RESTORE_TIMESTAMP.log"
echo "[INFO] ======================================================"
echo ""
echo "[INFO] 복구 후 확인 권장 사항:"
echo "  1. bench --site $SITE_NAME doctor  (시스템 상태 확인)"
echo "  2. 직원(Employee) 목록 및 급여 데이터 샘플 검증"
echo "  3. 스케줄러 재활성화: bench --site $SITE_NAME enable-scheduler"
