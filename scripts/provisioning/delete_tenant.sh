#!/bin/bash
# delete_tenant.sh — 고객사 site 삭제 (백업 강제)
#
# 사용법:
#   ./scripts/provisioning/delete_tenant.sh <tenant_id>
#
# 필수 인수:
#   tenant_id : 삭제할 테넌트 식별자
#
# 옵션:
#   --dry-run : 실제 삭제 없이 단계만 출력
#
# 환경변수:
#   BENCH_PATH              : bench 루트 디렉터리 (기본값: ~/frappe-bench)
#   BASE_DOMAIN             : 기본값 hrms.safeclaw.kr
#   BACKUP_DIR              : 백업 저장 디렉터리 (기본값: ~/frappe-bench-backups)
#   MARIADB_ROOT_PASSWORD   : MariaDB root 비번 (bench drop-site에 필요)
#
# 안전 규칙:
#   - 백업은 무조건 실행됩니다. 백업 생략 옵션은 존재하지 않습니다.
#   - 삭제 확인을 위해 tenant_id를 직접 입력해야 합니다.
#   - 레지스트리에서 status를 'deleted'로 업데이트합니다 (항목 유지).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MULTI_SITE_JSON="${REPO_ROOT}/config/multi_site.json"

BASE_DOMAIN="${BASE_DOMAIN:-hrms.safeclaw.kr}"
BENCH_PATH="${BENCH_PATH:-${HOME}/frappe-bench}"
BACKUP_DIR="${BACKUP_DIR:-${HOME}/frappe-bench-backups}"

# ─── 인수 파싱 ───────────────────────────────────────────────────────────────
_die() { echo "[오류] $*" >&2; exit 1; }

if [[ $# -lt 1 ]]; then
    echo "사용법: $0 <tenant_id> [--dry-run]" >&2
    exit 1
fi

TENANT_ID="${1}"
shift

DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        *) _die "알 수 없는 옵션: $1" ;;
    esac
done

SITE_NAME="${TENANT_ID}.${BASE_DOMAIN}"

# ─── 헬퍼 ────────────────────────────────────────────────────────────────────
_step() { echo; echo "━━━ $* ━━━"; }
_run()  {
    if [[ "${DRY_RUN}" == true ]]; then
        echo "[dry-run] $*"
    else
        "$@"
    fi
}

# ─── 사전 확인 ───────────────────────────────────────────────────────────────
_step "1/5  사전 확인"

[[ "${TENANT_ID}" =~ ^[a-z0-9][a-z0-9-]*$ ]] \
    || _die "tenant_id 형식이 올바르지 않습니다: '${TENANT_ID}'"

if [[ "${DRY_RUN}" == false ]]; then
    command -v bench >/dev/null 2>&1 \
        || _die "bench 명령어를 찾을 수 없습니다."

    [[ -n "${MARIADB_ROOT_PASSWORD:-}" ]] \
        || _die "MARIADB_ROOT_PASSWORD 환경변수가 필요합니다."

    if [[ ! -d "${BENCH_PATH}/sites/${SITE_NAME}" ]]; then
        _die "site를 찾을 수 없습니다: ${SITE_NAME}"
    fi
fi

echo "  삭제 대상 site: ${SITE_NAME}"
echo "  bench 경로    : ${BENCH_PATH}"
echo "  백업 저장 위치: ${BACKUP_DIR}"

# ─── 확인 프롬프트 ───────────────────────────────────────────────────────────
_step "2/5  삭제 확인"
echo
echo "  ⚠️  경고: 이 작업은 site '${SITE_NAME}' 과 모든 데이터를 삭제합니다."
echo "  삭제를 확인하려면 tenant_id '${TENANT_ID}' 를 정확히 입력하세요:"
echo

if [[ "${DRY_RUN}" == false ]]; then
    read -r -p "  tenant_id 입력: " CONFIRM_ID
    if [[ "${CONFIRM_ID}" != "${TENANT_ID}" ]]; then
        echo "[중단] 입력값이 일치하지 않습니다. 삭제를 취소합니다."
        exit 1
    fi
else
    echo "[dry-run] 확인 프롬프트 건너뜀"
fi

# ─── 백업 (무조건 실행) ──────────────────────────────────────────────────────
_step "3/5  백업 (필수)"
NOW="$(date +%Y%m%d_%H%M%S)"
BACKUP_TARGET="${BACKUP_DIR}/${TENANT_ID}/${NOW}"

if [[ "${DRY_RUN}" == false ]]; then
    mkdir -p "${BACKUP_TARGET}"
    echo "  bench --site 백업 실행 중..."
    bench --site "${SITE_NAME}" backup \
        --with-files \
        --backup-path "${BACKUP_TARGET}" \
        || _die "백업 실패. 삭제를 중단합니다. 백업 경로를 확인하세요: ${BACKUP_TARGET}"
    echo "  [OK] 백업 완료: ${BACKUP_TARGET}"
else
    echo "[dry-run] bench --site ${SITE_NAME} backup --with-files --backup-path ${BACKUP_TARGET}"
fi

# ─── site 삭제 ───────────────────────────────────────────────────────────────
_step "4/5  site 삭제"
# --force: 별도 확인 프롬프트 생략 (이 스크립트에서 이미 확인함)
# bench이 자체 백업을 추가로 수행할 수 있으나 위 3단계 백업이 주 백업임
_run bench drop-site "${SITE_NAME}" \
    --mariadb-root-password "${MARIADB_ROOT_PASSWORD}" \
    --force

# ─── 레지스트리 업데이트 ─────────────────────────────────────────────────────
_step "5/5  레지스트리 업데이트"
NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ "${DRY_RUN}" == false ]]; then
    python3 - <<PYEOF
import json, pathlib, sys

registry_path = pathlib.Path("${MULTI_SITE_JSON}")
with registry_path.open("r", encoding="utf-8") as f:
    registry = json.load(f)

tenants = registry.get("tenants", [])
target = next((t for t in tenants if t["id"] == "${TENANT_ID}"), None)

if target is None:
    print("  [경고] 레지스트리에서 테넌트를 찾지 못했습니다: ${TENANT_ID}")
else:
    target["status"] = "deleted"
    target["updated_at"] = "${NOW_ISO}"
    print(f"  [info] 테넌트 status → deleted: ${TENANT_ID}")

with registry_path.open("w", encoding="utf-8") as f:
    json.dump(registry, f, ensure_ascii=False, indent=2)
print("  config/multi_site.json 업데이트 완료")
PYEOF
else
    echo "[dry-run] config/multi_site.json에서 ${TENANT_ID} status → deleted"
fi

# ─── 완료 ────────────────────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════"
echo "  삭제 완료"
echo "  tenant : ${TENANT_ID}"
echo "  site   : ${SITE_NAME}"
if [[ "${DRY_RUN}" == false ]]; then
    echo "  백업   : ${BACKUP_TARGET}"
fi
echo "  ※ Cloudflare DNS CNAME은 수동으로 제거하세요."
echo "    (Cloudflare 대시보드 > safeclaw.kr > DNS)"
echo "  ※ cloudflared config.yml에서 해당 hostname ingress를"
echo "    수동으로 제거 후 cloudflared 재시작 또는 SIGHUP 하세요."
echo "════════════════════════════════════════════"
