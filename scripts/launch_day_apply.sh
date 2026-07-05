#!/bin/bash
# 출시일 원커맨드 적용 — 외부 자격증명이 준비되면 이 스크립트 하나로 전부 반영한다.
# 서버(claudebot-2)에서 실행. 값이 없는 항목은 건너뛴다(부분 적용 가능).
#
# 사용:
#   GOOGLE_OAUTH_CLIENT_ID=... GOOGLE_OAUTH_CLIENT_SECRET=... \
#   KAKAO_REST_API_KEY=... KAKAO_CLIENT_SECRET=... \
#   BACKUP_S3_BUCKET=s3://... AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
#   ./scripts/launch_day_apply.sh noho.safeclaw.kr
set -euo pipefail

SITE="${1:-noho.safeclaw.kr}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRAPPE_CONTAINER="${FRAPPE_CONTAINER:-docker-frappe-1}"
BENCH_WORKDIR="/home/frappe/frappe-bench"

setup_login() {
    local provider="$1" cid="$2" secret="$3"
    docker exec -w "$BENCH_WORKDIR" "$FRAPPE_CONTAINER" bench --site "$SITE" execute \
        hrms.regional.south_korea.social_login_api.setup_social_login \
        --kwargs "{'provider': '${provider}', 'client_id': '${cid}', 'client_secret': '${secret}'}"
    echo "[OK] ${provider} 로그인 활성화: $SITE"
}

if [[ -n "${GOOGLE_OAUTH_CLIENT_ID:-}" && -n "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ]]; then
    setup_login google "$GOOGLE_OAUTH_CLIENT_ID" "$GOOGLE_OAUTH_CLIENT_SECRET"
else
    echo "[SKIP] 구글 키 없음"
fi

if [[ -n "${KAKAO_REST_API_KEY:-}" && -n "${KAKAO_CLIENT_SECRET:-}" ]]; then
    setup_login kakao "$KAKAO_REST_API_KEY" "$KAKAO_CLIENT_SECRET"
else
    echo "[SKIP] 카카오 키 없음"
fi

if [[ -n "${BACKUP_S3_BUCKET:-}" && -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
    ENV_FILE="/home/ubuntu/.korea-hrms-mcp/backup-upload.env"
    printf 'BACKUP_S3_BUCKET=%s\nAWS_ACCESS_KEY_ID=%s\nAWS_SECRET_ACCESS_KEY=%s\nAWS_ENDPOINT_URL=%s\n' \
        "$BACKUP_S3_BUCKET" "$AWS_ACCESS_KEY_ID" "${AWS_SECRET_ACCESS_KEY:-}" "${AWS_ENDPOINT_URL:-}" > "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    (crontab -l 2>/dev/null | grep -v backup_korea_hrms; \
     echo "0 2 * * * . ${ENV_FILE} && /bin/bash ${REPO_ROOT}/scripts/backup_korea_hrms.sh --upload >> /tmp/hrms-backup.log 2>&1") | crontab -
    echo "[OK] 오프사이트 백업 크론 전환 (--upload). 즉시 1회 검증 실행:"
    . "$ENV_FILE" && bash "${REPO_ROOT}/scripts/backup_korea_hrms.sh" --upload | tail -3
else
    echo "[SKIP] 백업 스토리지 키 없음 (로컬 백업은 계속 가동 중)"
fi

echo
echo "=== 확인 ==="
curl -s -o /dev/null -w "https://${SITE} : %{http_code}\n" "https://${SITE}" --max-time 15 || true
echo "직원 CSV가 준비되면: docs/clients/noho_beta_onboarding.md §3 (템플릿 docs/clients/noho_employee_import_template.csv)"
