#!/bin/bash
# 셀프서브 가입 큐 소비 워커 — 5분 크론. AI 플레인 /signup 이 적재한 pending 항목을
# create_tenant.sh 로 무인 프로비저닝한다 (scale-architecture 불변식 4).
#
# 설치: crontab →  */5 * * * * /bin/bash <repo>/scripts/provisioning/process_signup_queue.sh >> /tmp/hrms-signup.log 2>&1
# 환경: docker/.env 의 MARIADB_ROOT_PASSWORD 사용. 한 실행에 1건만 처리(직렬화·부하 보호).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
QUEUE="${KCHRMS_SIGNUP_QUEUE:-/home/ubuntu/.korea-hrms-mcp/signup-queue.jsonl}"
LOCK="/tmp/hrms-signup.lock"
RESULT_LOG="${QUEUE%.jsonl}-processed.jsonl"

[[ -f "$QUEUE" ]] || exit 0
exec 9>"$LOCK"
flock -n 9 || exit 0  # 이전 프로비저닝 진행 중이면 건너뜀

ENTRY=$(head -n 1 "$QUEUE" 2>/dev/null || true)
[[ -n "$ENTRY" ]] || exit 0

TENANT_ID=$(echo "$ENTRY" | python3 -c "import sys,json;print(json.load(sys.stdin)['tenant_id'])")
ADMIN_EMAIL=$(echo "$ENTRY" | python3 -c "import sys,json;print(json.load(sys.stdin)['admin_email'])")

echo "[INFO] $(date -Iseconds) 프로비저닝 시작: ${TENANT_ID} (${ADMIN_EMAIL})"

export MARIADB_ROOT_PASSWORD
MARIADB_ROOT_PASSWORD=$(cut -d= -f2 "${REPO_ROOT}/docker/.env")
export CLOUDFLARE_API_TOKEN=skip CLOUDFLARED_TUNNEL_ID=skip

STATUS=ok
if ! "${REPO_ROOT}/scripts/provisioning/create_tenant.sh" "$TENANT_ID" "$ADMIN_EMAIL" \
        --skip-dns --skip-cloudflared >> "/tmp/hrms-provision-${TENANT_ID}.log" 2>&1; then
    STATUS=failed
fi

# 큐에서 제거하고 결과 기록 (append-only)
tail -n +2 "$QUEUE" > "${QUEUE}.tmp" && mv "${QUEUE}.tmp" "$QUEUE"
echo "$ENTRY" | python3 -c "
import sys, json, datetime
e = json.load(sys.stdin)
e['status'] = '${STATUS}'
e['processed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
print(json.dumps(e, ensure_ascii=False))" >> "$RESULT_LOG"

echo "[INFO] $(date -Iseconds) 완료: ${TENANT_ID} status=${STATUS} (상세: /tmp/hrms-provision-${TENANT_ID}.log)"
[[ "$STATUS" == "ok" ]]
