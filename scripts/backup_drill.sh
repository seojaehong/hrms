#!/bin/bash
# 한국 HRMS 복구 검증 드릴 (Drill)
#
# 사용법:
#   ./scripts/backup_drill.sh [--backup-dir <경로>] [--test-site <사이트명>]
#
# 설명:
#   1. 최신 백업(또는 지정 백업)을 테스트 사이트에 복원합니다.
#   2. 핵심 데이터(직원 수 > 0)를 SQL로 검증합니다.
#   3. 테스트 사이트를 삭제하고 결과를 리포트합니다.
#
#   운영 사이트(SITE_NAME)와 테스트 사이트(TEST_SITE_NAME)가 동일하면
#   즉시 오류를 발생시켜 중단합니다.
#
# 필수 환경변수:
#   SITE_NAME        운영 사이트명 (기본: hrms.localhost)
#   BENCH_PATH       bench 경로    (기본: /home/frappe/frappe-bench)
#   BACKUP_DIR       로컬 백업 루트 (기본: /home/ubuntu/backups/hrms)
#
# 선택 인자:
#   --backup-dir <경로>     특정 백업 디렉터리 사용 (기본: 가장 최근 백업)
#   --test-site <사이트명>  드릴 전용 사이트명 (기본: hrms-drill.localhost)
#   --keep-test-site        드릴 완료 후 테스트 사이트 유지 (검사 용도)

set -euo pipefail
LC_ALL=C
export LC_ALL

# ── 기본값 ─────────────────────────────────────────────
BENCH_PATH="${BENCH_PATH:-/home/frappe/frappe-bench}"
SITE_NAME="${SITE_NAME:-hrms.localhost}"
BACKUP_DIR="${BACKUP_DIR:-/home/ubuntu/backups/hrms}"
TEST_SITE_NAME="${TEST_SITE_NAME:-hrms-drill.localhost}"
BACKUP_DIR_ARG=""
KEEP_TEST_SITE=false
DRILL_LOG="/tmp/hrms_drill_$(date +%Y%m%d_%H%M%S).log"

# ── 인자 파싱 ───────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --backup-dir)
            BACKUP_DIR_ARG="$2"
            shift 2
            ;;
        --test-site)
            TEST_SITE_NAME="$2"
            shift 2
            ;;
        --keep-test-site)
            KEEP_TEST_SITE=true
            shift
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

# ── 안전장치: 운영 사이트 == 테스트 사이트 차단 ──────
if [[ "$SITE_NAME" == "$TEST_SITE_NAME" ]]; then
    echo "[ERROR] 운영 사이트와 테스트 사이트가 동일합니다!" >&2
    echo "        SITE_NAME=$SITE_NAME, TEST_SITE_NAME=$TEST_SITE_NAME" >&2
    echo "        --test-site 옵션으로 별도 사이트명을 지정하세요." >&2
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

# ── 백업 디렉터리 결정 ─────────────────────────────────
if [[ -n "$BACKUP_DIR_ARG" ]]; then
    TARGET_BACKUP="$BACKUP_DIR_ARG"
else
    # 가장 최근 백업 디렉터리 자동 탐색
    TARGET_BACKUP=$(find "$BACKUP_DIR" -maxdepth 1 -mindepth 1 -type d | sort -r | head -1)
    if [[ -z "$TARGET_BACKUP" ]]; then
        echo "[ERROR] 백업을 찾을 수 없습니다: $BACKUP_DIR" >&2
        echo "        먼저 backup_korea_hrms.sh를 실행하세요." >&2
        exit 1
    fi
fi

if [[ ! -d "$TARGET_BACKUP" ]]; then
    echo "[ERROR] 백업 디렉터리가 존재하지 않습니다: $TARGET_BACKUP" >&2
    exit 1
fi

SQL_FILE=$(find "$TARGET_BACKUP" -maxdepth 1 -name "*.sql.gz" | sort | head -1)
if [[ -z "$SQL_FILE" ]]; then
    echo "[ERROR] SQL 파일을 찾을 수 없습니다: $TARGET_BACKUP" >&2
    exit 1
fi

# "*-private-files.tar" 을 먼저 제외하여 public files tar 과 혼동하지 않도록 함
FILES_BACKUP=$(find "$TARGET_BACKUP" -maxdepth 1 -name "*-files.tar" ! -name "*-private-files.tar" | sort | head -1 || true)
PRIVATE_BACKUP=$(find "$TARGET_BACKUP" -maxdepth 1 -name "*-private-files.tar" | sort | head -1 || true)

# ── 드릴 시작 ──────────────────────────────────────────
DRILL_START=$(date +%s)

{
echo "======================================================"
echo "한국 HRMS 복구 드릴 시작: $(date '+%Y-%m-%d %H:%M:%S')"
echo "백업 소스: $TARGET_BACKUP"
echo "SQL 파일: $SQL_FILE"
echo "테스트 사이트: $TEST_SITE_NAME"
echo "======================================================"
} | tee "$DRILL_LOG"

# 드릴 결과 추적
DRILL_PASS=true
DRILL_FAILURES=()

# ── STEP 1: 테스트 사이트 생성 ─────────────────────────
echo "[STEP 1] 테스트 사이트 생성: $TEST_SITE_NAME" | tee -a "$DRILL_LOG"
cd "$BENCH_PATH"

# 기존 드릴 사이트가 있으면 제거
if [[ -d "$BENCH_PATH/sites/$TEST_SITE_NAME" ]]; then
    echo "[INFO] 기존 테스트 사이트 제거 중..." | tee -a "$DRILL_LOG"
    $BENCH_CMD drop-site "$TEST_SITE_NAME" \
        --root-password "${MARIADB_ROOT_PASSWORD:-}" \
        --no-backup 2>&1 | tee -a "$DRILL_LOG" || true
fi

$BENCH_CMD new-site "$TEST_SITE_NAME" \
    --admin-password admin \
    --mariadb-root-password "${MARIADB_ROOT_PASSWORD:-}" \
    --no-mariadb-socket 2>&1 | tee -a "$DRILL_LOG" || {
    echo "[ERROR] 테스트 사이트 생성 실패" | tee -a "$DRILL_LOG" >&2
    DRILL_PASS=false
    DRILL_FAILURES+=("STEP1: 테스트 사이트 생성 실패")
}

# ── STEP 2: 백업 복원 ──────────────────────────────────
echo "[STEP 2] 백업 복원 중..." | tee -a "$DRILL_LOG"
if [[ "$DRILL_PASS" == "true" ]]; then
    RESTORE_EXTRA_OPTS=""
    if [[ -n "$FILES_BACKUP" ]]; then
        RESTORE_EXTRA_OPTS="$RESTORE_EXTRA_OPTS --with-public-files $FILES_BACKUP"
    fi
    if [[ -n "$PRIVATE_BACKUP" ]]; then
        RESTORE_EXTRA_OPTS="$RESTORE_EXTRA_OPTS --with-private-files $PRIVATE_BACKUP"
    fi

    # shellcheck disable=SC2086
    # bench restore: DB + files 복원 (BENCH_CMD = bench 바이너리 경로)
    $BENCH_CMD --site "$TEST_SITE_NAME" restore "$SQL_FILE" \
        --admin-password admin \
        $RESTORE_EXTRA_OPTS \
        2>&1 | tee -a "$DRILL_LOG" || {
        echo "[ERROR] 복원 실패" | tee -a "$DRILL_LOG" >&2
        DRILL_PASS=false
        DRILL_FAILURES+=("STEP2: 복원 실패")
    }
fi

# ── STEP 3: migrate 실행 ───────────────────────────────
echo "[STEP 3] bench migrate 실행 중..." | tee -a "$DRILL_LOG"
if [[ "$DRILL_PASS" == "true" ]]; then
    $BENCH_CMD --site "$TEST_SITE_NAME" migrate 2>&1 | tee -a "$DRILL_LOG" || {
        echo "[ERROR] migrate 실패" | tee -a "$DRILL_LOG" >&2
        DRILL_PASS=false
        DRILL_FAILURES+=("STEP3: migrate 실패")
    }
fi

# ── STEP 4: 핵심 데이터 검증 ───────────────────────────
echo "[STEP 4] 핵심 데이터 검증..." | tee -a "$DRILL_LOG"
if [[ "$DRILL_PASS" == "true" ]]; then
    # DB명 추출: Frappe site_config.json에서 db_name 읽기
    SITE_CONFIG="$BENCH_PATH/sites/$TEST_SITE_NAME/site_config.json"
    DB_NAME=$(python3 -c "import json; d=json.load(open('$SITE_CONFIG')); print(d.get('db_name',''))" 2>/dev/null || true)

    if [[ -z "$DB_NAME" ]]; then
        echo "[WARN] DB명을 확인할 수 없습니다. 데이터 검증을 건너뜁니다." | tee -a "$DRILL_LOG"
    else
        echo "[INFO] 검증 DB: $DB_NAME" | tee -a "$DRILL_LOG"

        # Employee 레코드 수 확인
        EMP_COUNT=$(mysql -u root --password="${MARIADB_ROOT_PASSWORD:-}" \
            -e "SELECT COUNT(*) FROM \`$DB_NAME\`.\`tabEmployee\`;" \
            --skip-column-names 2>/dev/null || echo "-1")

        echo "[INFO] Employee 레코드 수: $EMP_COUNT" | tee -a "$DRILL_LOG"

        if [[ "$EMP_COUNT" == "-1" ]]; then
            echo "[WARN] DB 연결 실패 — MySQL 자격증명을 확인하세요 (MARIADB_ROOT_PASSWORD)." | tee -a "$DRILL_LOG"
            DRILL_FAILURES+=("STEP4: DB 연결 실패 (경고)")
        elif [[ "$EMP_COUNT" -lt 1 ]]; then
            echo "[ERROR] Employee 레코드가 없습니다. 복원이 올바르지 않습니다." | tee -a "$DRILL_LOG" >&2
            DRILL_PASS=false
            DRILL_FAILURES+=("STEP4: Employee 레코드 없음 (복원 실패)")
        else
            echo "[OK] Employee 레코드 확인: $EMP_COUNT 건" | tee -a "$DRILL_LOG"
        fi
    fi
fi

# ── STEP 5: 테스트 사이트 정리 ─────────────────────────
if [[ "$KEEP_TEST_SITE" == "false" ]]; then
    echo "[STEP 5] 테스트 사이트 삭제: $TEST_SITE_NAME" | tee -a "$DRILL_LOG"
    $BENCH_CMD drop-site "$TEST_SITE_NAME" \
        --root-password "${MARIADB_ROOT_PASSWORD:-}" \
        --no-backup 2>&1 | tee -a "$DRILL_LOG" || \
        echo "[WARN] 테스트 사이트 삭제 실패 (수동 정리 필요)" | tee -a "$DRILL_LOG"
else
    echo "[INFO] --keep-test-site: 테스트 사이트를 유지합니다: $TEST_SITE_NAME" | tee -a "$DRILL_LOG"
fi

# ── 드릴 결과 리포트 ───────────────────────────────────
DRILL_END=$(date +%s)
DRILL_DURATION=$((DRILL_END - DRILL_START))

{
echo ""
echo "======================================================"
echo "복구 드릴 결과 리포트"
echo "소요 시간: ${DRILL_DURATION}초"
echo "로그 파일: $DRILL_LOG"
echo "------------------------------------------------------"
} | tee -a "$DRILL_LOG"

if [[ "$DRILL_PASS" == "true" ]]; then
    echo "[PASS] 복구 드릴 성공!" | tee -a "$DRILL_LOG"
    EXIT_CODE=0
else
    echo "[FAIL] 복구 드릴 실패!" | tee -a "$DRILL_LOG"
    for failure in "${DRILL_FAILURES[@]}"; do
        echo "  - $failure" | tee -a "$DRILL_LOG"
    done
    EXIT_CODE=1
fi

echo "======================================================" | tee -a "$DRILL_LOG"
exit $EXIT_CODE
