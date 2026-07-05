#!/bin/bash
# Korea HRMS 스모크 — 5분 크론. 실패 시 Alertmanager 웹훅(→텔레그램)으로 알림.
# 설치: crontab -e →  */5 * * * * /bin/bash <repo>/scripts/monitoring/hrms_smoke.sh >> /var/log/hrms-smoke.log 2>&1
set -u
WEBHOOK_URL="${HRMS_ALERT_WEBHOOK:-http://localhost:5001/}"
STATE_FILE="/tmp/hrms-smoke.state"
HISTORY_FILE="${HRMS_SMOKE_HISTORY:-/home/ubuntu/.korea-hrms-mcp/smoke-history.log}"

fails=()

check() {
    local name="$1" expect="$2"; shift 2
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$@")
    if [[ "$code" != "$expect" ]]; then
        fails+=("${name}: got ${code}, expected ${expect}")
    fi
}

check "web(hrms.localhost)"    200 -H "Host: hrms.localhost" http://localhost:8000
check "noho ping"              200 -H "Host: noho.safeclaw.kr" http://localhost:8000/api/method/frappe.ping
check "asset"                  200 -H "Host: hrms.localhost" http://localhost:8000/assets/hrms/frontend/index.html
check "public https"           200 https://hrms.safeclaw.kr
check "ai-plane auth gate"     401 -X POST http://127.0.0.1:8100/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" --data '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

now=$(date -Iseconds)
if [[ ${#fails[@]} -eq 0 ]]; then
    # 복구 알림: 직전 상태가 FAIL이었으면 회복 통지
    if [[ -f "$STATE_FILE" ]] && grep -q FAIL "$STATE_FILE"; then
        curl -s -m 10 -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" \
            -d "{\"status\":\"resolved\",\"alerts\":[{\"status\":\"resolved\",\"labels\":{\"alertname\":\"HRMSSmoke\",\"severity\":\"info\"},\"annotations\":{\"summary\":\"HRMS smoke 회복 (${now})\"}}]}" > /dev/null
    fi
    echo "OK ${now}" > "$STATE_FILE"
    echo "OK ${now}" >> "$HISTORY_FILE"
    exit 0
fi

echo "FAIL ${now} ${fails[*]}" > "$STATE_FILE"
echo "FAIL ${now}" >> "$HISTORY_FILE"
summary=$(printf '%s; ' "${fails[@]}")
curl -s -m 10 -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" \
    -d "{\"status\":\"firing\",\"alerts\":[{\"status\":\"firing\",\"labels\":{\"alertname\":\"HRMSSmoke\",\"severity\":\"critical\"},\"annotations\":{\"summary\":\"HRMS smoke 실패: ${summary}\"}}]}" > /dev/null
echo "ALERT sent: ${summary}"
exit 1
