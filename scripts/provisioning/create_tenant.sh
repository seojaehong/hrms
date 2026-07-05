#!/bin/bash
# create_tenant.sh — 새 고객사 Frappe site 생성 + 자동 프로비저닝
#
# 사용법:
#   ./scripts/provisioning/create_tenant.sh <tenant_id> <admin_email> [옵션]
#
# 필수 인수:
#   tenant_id       : 테넌트 식별자 (영문 소문자·숫자·하이픈). 예: acme-corp
#   admin_email     : 초기 관리자 이메일
#
# 옵션:
#   --plan PLAN         : starter | professional | enterprise (기본값: starter)
#   --seed-demo         : 데모 데이터 시드 실행
#   --send-email        : 완료 후 admin에게 임시 비번 이메일 발송 (bench mail 필요)
#   --frappe-port PORT  : Frappe 웹서버 포트 (기본값: 8000)
#   --skip-dns          : Cloudflare DNS 추가 생략
#   --skip-cloudflared  : cloudflared ingress 추가 생략
#   --dry-run           : 실제 bench/API 호출 없이 단계만 출력
#
# 환경변수 (필수):
#   CLOUDFLARE_API_TOKEN    : Cloudflare API 토큰
#   CLOUDFLARED_TUNNEL_ID   : Cloudflare tunnel UUID
#   BENCH_PATH              : bench 루트 디렉터리 (기본값: ~/frappe-bench)
#   MARIADB_ROOT_PASSWORD   : MariaDB root 비번 (bench new-site에 필요)
#
# 환경변수 (선택):
#   BASE_DOMAIN             : 기본값 hrms.safeclaw.kr
#   CLOUDFLARE_ZONE_NAME    : 기본값 safeclaw.kr
#   CLOUDFLARED_CONFIG_PATH : 기본값 ~/.cloudflared/config.yml
#   ADMIN_PASSWORD          : site admin 임시 비번 (기본값: 자동 생성)
#
# 동작:
#   1. bench new-site {tenant_id}.hrms.safeclaw.kr
#   2. 한국 모듈 install (erpnext, hrms)
#   3. 데모 데이터 시드 (--seed-demo 시)
#   4. Cloudflare DNS CNAME 추가
#   5. cloudflared ingress 추가 + SIGHUP
#   6. Frappe site host_name 설정
#   7. config/multi_site.json 레지스트리 업데이트
#   8. 완료 요약 출력

set -euo pipefail

# ─── 상수 ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MULTI_SITE_JSON="${REPO_ROOT}/config/multi_site.json"
CF_DNS_SCRIPT="${SCRIPT_DIR}/cloudflare_dns_add.py"
CF_INGRESS_SCRIPT="${SCRIPT_DIR}/cloudflared_ingress_add.py"

BASE_DOMAIN="${BASE_DOMAIN:-safeclaw.kr}"
BENCH_PATH="${BENCH_PATH:-${HOME}/frappe-bench}"

# Docker 래핑 설정 — bench는 컨테이너 내부에만 설치됨
FRAPPE_CONTAINER="${FRAPPE_CONTAINER:-docker-frappe-1}"
BENCH_WORKDIR="${BENCH_WORKDIR:-/home/frappe/frappe-bench}"

# ─── 인수 파싱 ───────────────────────────────────────────────────────────────
if [[ $# -lt 2 ]]; then
    echo "사용법: $0 <tenant_id> <admin_email> [옵션]" >&2
    echo "       $0 --help 로 전체 도움말 확인" >&2
    exit 1
fi

TENANT_ID="${1}"
ADMIN_EMAIL="${2}"
shift 2

PLAN="starter"
SEED_DEMO=false
SEND_EMAIL=false
FRAPPE_PORT=8000
SKIP_DNS=false
SKIP_CLOUDFLARED=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --plan)          PLAN="$2";        shift 2 ;;
        --seed-demo)     SEED_DEMO=true;   shift   ;;
        --send-email)    SEND_EMAIL=true;  shift   ;;
        --frappe-port)   FRAPPE_PORT="$2"; shift 2 ;;
        --skip-dns)      SKIP_DNS=true;    shift   ;;
        --skip-cloudflared) SKIP_CLOUDFLARED=true; shift ;;
        --dry-run)       DRY_RUN=true;     shift   ;;
        --help)
            grep '^#' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "[오류] 알 수 없는 옵션: $1" >&2
            exit 1
            ;;
    esac
done

# ─── 입력 검증 ───────────────────────────────────────────────────────────────
_die() { echo "[오류] $*" >&2; exit 1; }

[[ "${TENANT_ID}" =~ ^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$|^[a-z0-9]$ ]] \
    || _die "tenant_id는 영문 소문자·숫자·하이픈만 허용됩니다: '${TENANT_ID}'"

[[ "${ADMIN_EMAIL}" =~ ^[^@]+@[^@]+\.[^@]+$ ]] \
    || _die "유효하지 않은 이메일: '${ADMIN_EMAIL}'"

[[ "${PLAN}" =~ ^(starter|professional|enterprise)$ ]] \
    || _die "plan은 starter|professional|enterprise 중 하나여야 합니다."

SITE_NAME="${TENANT_ID}.${BASE_DOMAIN}"

# ─── 환경변수 확인 ───────────────────────────────────────────────────────────
if [[ "${SKIP_DNS}" == false ]]; then
    [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]] \
        || _die "CLOUDFLARE_API_TOKEN 환경변수가 필요합니다."
    [[ -n "${CLOUDFLARED_TUNNEL_ID:-}" ]] \
        || _die "CLOUDFLARED_TUNNEL_ID 환경변수가 필요합니다."
fi

if [[ "${DRY_RUN}" == false ]]; then
    docker exec "${FRAPPE_CONTAINER}" which bench >/dev/null 2>&1 \
        || _die "컨테이너 '${FRAPPE_CONTAINER}' 내부에서 bench를 찾을 수 없습니다. FRAPPE_CONTAINER 또는 컨테이너 상태를 확인하세요."
    [[ -n "${MARIADB_ROOT_PASSWORD:-}" ]] \
        || _die "MARIADB_ROOT_PASSWORD 환경변수가 필요합니다."
fi

# ─── 헬퍼 ────────────────────────────────────────────────────────────────────
_step() { echo; echo "━━━ $* ━━━"; }
_run()  {
    if [[ "${DRY_RUN}" == true ]]; then
        echo "[dry-run] $*"
    else
        "$@"
    fi
}

# ─── 중복 site 확인 ─────────────────────────────────────────────────────────
_step "1/8  사전 확인"
if [[ "${DRY_RUN}" == false ]]; then
    if docker exec "${FRAPPE_CONTAINER}" test -d "${BENCH_WORKDIR}/sites/${SITE_NAME}" 2>/dev/null; then
        _die "site가 이미 존재합니다: ${SITE_NAME}. 기존 site를 삭제하려면 delete_tenant.sh를 사용하세요."
    fi
fi
echo "  tenant_id : ${TENANT_ID}"
echo "  site      : ${SITE_NAME}"
echo "  plan      : ${PLAN}"
echo "  email     : ${ADMIN_EMAIL}"

# ─── 임시 admin 비번 생성 ────────────────────────────────────────────────────
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*' < /dev/urandom | head -c 16 || true)}"

# ─── 1. bench new-site ───────────────────────────────────────────────────────
_step "2/8  bench new-site"
_run docker exec -w "${BENCH_WORKDIR}" "${FRAPPE_CONTAINER}" bench new-site "${SITE_NAME}" \
    --mariadb-root-password "${MARIADB_ROOT_PASSWORD}" \
    --admin-password "${ADMIN_PASSWORD}" \
    --no-mariadb-socket \
    --db-name "tenant_${TENANT_ID//-/_}"

# ─── 2. 한국 모듈 install ────────────────────────────────────────────────────
_step "3/8  한국 모듈 설치 (erpnext, hrms)"
_run docker exec -w "${BENCH_WORKDIR}" "${FRAPPE_CONTAINER}" bench --site "${SITE_NAME}" install-app erpnext
_run docker exec -w "${BENCH_WORKDIR}" "${FRAPPE_CONTAINER}" bench --site "${SITE_NAME}" install-app hrms

# ─── 2-1. 소셜 로그인 자동 설정 (env 있으면) ──────────────────────────────────
# GOOGLE_OAUTH_CLIENT_ID/SECRET, KAKAO_REST_API_KEY/KAKAO_CLIENT_SECRET
setup_social_login() {
    local provider="$1" cid="$2" secret="$3"
    _run docker exec -w "${BENCH_WORKDIR}" "${FRAPPE_CONTAINER}" bench --site "${SITE_NAME}" execute         hrms.regional.south_korea.social_login_api.setup_social_login         --kwargs "{'provider': '${provider}', 'client_id': '${cid}', 'client_secret': '${secret}'}"
}
if [[ -n "${GOOGLE_OAUTH_CLIENT_ID:-}" && -n "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ]]; then
    echo "  [info] 구글 로그인 설정 (리디렉션 URI를 Google 콘솔에 추가 필요: https://${SITE_NAME}/api/method/frappe.integrations.oauth2_logins.login_via_google)"
    setup_social_login google "${GOOGLE_OAUTH_CLIENT_ID}" "${GOOGLE_OAUTH_CLIENT_SECRET}"
fi
if [[ -n "${KAKAO_REST_API_KEY:-}" && -n "${KAKAO_CLIENT_SECRET:-}" ]]; then
    echo "  [info] 카카오 로그인 설정 (카카오 개발자 콘솔 Redirect URI: https://${SITE_NAME}/api/method/hrms.regional.south_korea.social_login_api.kakao_callback)"
    setup_social_login kakao "${KAKAO_REST_API_KEY}" "${KAKAO_CLIENT_SECRET}"
fi

# ─── 3. 데모 데이터 시드 ─────────────────────────────────────────────────────
if [[ "${SEED_DEMO}" == true ]]; then
    _step "4/8  데모 데이터 시드"
    _run docker exec -w "${BENCH_WORKDIR}" "${FRAPPE_CONTAINER}" bench --site "${SITE_NAME}" execute \
        hrms.regional.south_korea.demo_seed.seed_korea_demo \
        --args '{"company_name": "데모 회사 ('"${TENANT_ID}"')"}'
else
    echo "(--seed-demo 미설정 — 데모 시드 생략)"
fi

# ─── 4. Cloudflare DNS CNAME ─────────────────────────────────────────────────
_step "5/8  Cloudflare DNS CNAME 추가"
if [[ "${SKIP_DNS}" == false ]]; then
    _run python3 "${CF_DNS_SCRIPT}" "${TENANT_ID}" "${CLOUDFLARED_TUNNEL_ID}"
else
    echo "  (--skip-dns 설정됨 — 생략)"
fi

# ─── 5. cloudflared ingress ──────────────────────────────────────────────────
_step "6/8  cloudflared ingress 등록"
if [[ "${SKIP_CLOUDFLARED}" == false ]]; then
    _run python3 "${CF_INGRESS_SCRIPT}" "${TENANT_ID}" "${FRAPPE_PORT}"
else
    echo "  (--skip-cloudflared 설정됨 — 생략)"
fi

# ─── 6. Frappe host_name 설정 ────────────────────────────────────────────────
_step "7/8  Frappe site host_name 설정"
_run docker exec -w "${BENCH_WORKDIR}" "${FRAPPE_CONTAINER}" bench --site "${SITE_NAME}" set-config host_name "https://${SITE_NAME}"

# ─── 7. multi_site.json 레지스트리 업데이트 ──────────────────────────────────
_step "8/8  레지스트리 업데이트"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [[ "${DRY_RUN}" == false ]]; then
    # 보안(리뷰 C1): 셸 변수를 Python 소스에 보간하지 않는다 — 전부 env로 전달하고
    # os.environ으로 읽는다. (admin_email 등 외부 입력이 코드로 실행되던 RCE 차단)
    REG_PATH="${MULTI_SITE_JSON}" REG_TENANT_ID="${TENANT_ID}" REG_PLAN="${PLAN}" \
    REG_SITE="${SITE_NAME}" REG_EMAIL="${ADMIN_EMAIL}" REG_NOW="${NOW}" \
    python3 - <<'PYEOF'
import json, os, pathlib

registry_path = pathlib.Path(os.environ["REG_PATH"])
tenant_id = os.environ["REG_TENANT_ID"]
now = os.environ["REG_NOW"]
with registry_path.open("r", encoding="utf-8") as f:
    registry = json.load(f)

tenants = registry.setdefault("tenants", [])
existing = next((t for t in tenants if t.get("id") == tenant_id), None)
if existing:
    existing["status"] = "active"
    existing["updated_at"] = now
    print(f"  [info] 기존 테넌트 항목 업데이트: {tenant_id}")
else:
    tenants.append({
        "id":          tenant_id,
        "name":        tenant_id,
        "plan":        os.environ["REG_PLAN"],
        "status":      "active",
        "site":        os.environ["REG_SITE"],
        "admin_email": os.environ["REG_EMAIL"],
        "created_at":  now,
        "updated_at":  now,
    })
    print(f"  [info] 새 테넌트 등록: {tenant_id}")

with registry_path.open("w", encoding="utf-8") as f:
    json.dump(registry, f, ensure_ascii=False, indent=2)
print("  config/multi_site.json 업데이트 완료")
PYEOF
else
    echo "[dry-run] config/multi_site.json에 ${TENANT_ID} 추가"
fi

# ─── 완료 요약 ───────────────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════"
echo "  프로비저닝 완료"
echo "  site      : https://${SITE_NAME}"
echo "  admin     : ${ADMIN_EMAIL}"
if [[ "${DRY_RUN}" == false ]]; then
    echo "  임시 비번 : ${ADMIN_PASSWORD}"
    echo "  ※ 최초 로그인 후 반드시 비번을 변경하세요."
fi
echo "════════════════════════════════════════════"

# ─── (옵션) admin 이메일 발송 ────────────────────────────────────────────────
if [[ "${SEND_EMAIL}" == true ]]; then
    echo
    echo "  이메일 발송 중 → ${ADMIN_EMAIL}"
    _run docker exec -w "${BENCH_WORKDIR}" "${FRAPPE_CONTAINER}" bench --site "${SITE_NAME}" execute \
        frappe.utils.user.reset_password \
        --args "[\"${ADMIN_EMAIL}\"]" \
        && echo "  [OK] 비밀번호 재설정 이메일 발송 완료" \
        || echo "  [경고] 이메일 발송 실패. bench mail 설정을 확인하세요."
fi
