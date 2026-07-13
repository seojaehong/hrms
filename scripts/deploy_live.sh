#!/usr/bin/env bash
# SafeClaw HR 라이브 배포 — 로컬(git bash)에서 실행. origin/develop 기준.
#   bash scripts/deploy_live.sh            # 앱 + 랜딩
#   bash scripts/deploy_live.sh --restart  # hooks.py 등 파이썬 훅 변경 시 (노호 ~10초 순단)
# 안전장치: 로컬=origin 동기 확인 → ff-only 머지 → 컨테이너 HEAD 검증 → 배포 후 스모크.
set -euo pipefail

HOST=claudebot-2
WS='~/workspaces/seojaehong-hrms-100h'
DX='docker exec -w /home/frappe/frappe-bench docker-frappe-1'
RESTART=${1:-}

cd "$(dirname "$0")/.."

LOCAL_HEAD=$(git rev-parse develop)
REMOTE_HEAD=$(git ls-remote origin refs/heads/develop | cut -f1)
if [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  echo "ABORT: 로컬 develop($LOCAL_HEAD)이 origin과 다릅니다. 먼저 push하세요." >&2
  exit 1
fi

echo "== 호스트 워크스페이스 갱신 =="
ssh "$HOST" "cd $WS && git fetch origin && git merge --ff-only origin/develop"

echo "== 컨테이너 코드 갱신 =="
ssh "$HOST" "docker exec -w /home/frappe/frappe-bench/apps/hrms docker-frappe-1 bash -c 'git fetch upstream develop && git reset --hard FETCH_HEAD'"
CONTAINER_HEAD=$(ssh "$HOST" "docker exec -w /home/frappe/frappe-bench/apps/hrms docker-frappe-1 git rev-parse HEAD")
if [ "$CONTAINER_HEAD" != "$LOCAL_HEAD" ]; then
  echo "ABORT: 컨테이너 HEAD($CONTAINER_HEAD) != 로컬($LOCAL_HEAD)" >&2
  exit 1
fi

echo "== bench build =="
ssh "$HOST" "$DX bench build --app hrms"
ssh "$HOST" "$DX bench --site noho.safeclaw.kr clear-cache && $DX bench --site hrms.localhost clear-cache"

if [ "$RESTART" = "--restart" ]; then
  echo "== 컨테이너 재시작 (hooks 반영) =="
  ssh "$HOST" "docker restart docker-frappe-1"
fi

echo "== 랜딩 반영 =="
scp -q scripts/landing/safeclaw-hr.html "$HOST":/tmp/
ssh "$HOST" "docker cp /tmp/safeclaw-hr.html docker-frappe-1:/home/frappe/frappe-bench/sites/safeclaw-hr.html"

echo "== 스모크 =="
for u in https://noho.safeclaw.kr/api/method/ping https://hr.safeclaw.kr/; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 --retry 8 --retry-delay 5 --retry-all-errors "$u")
  echo "  $u -> $code"
  [ "$code" = "200" ] || { echo "ABORT: 스모크 실패 $u" >&2; exit 1; }
done

echo "DEPLOY OK: $LOCAL_HEAD"
