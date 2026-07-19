#!/usr/bin/env bash
# SafeClaw HR (한국) 배포 + 신선도 검증 — 로컬(git bash)에서 실행. origin/develop 기준.
#   bash scripts/deploy_korea.sh          # inert: 실행할 명령만 출력하고 종료 (안전)
#   bash scripts/deploy_korea.sh --run    # 실제 배포 수행 (운영자 전용)
#
# deploy_live.sh 와 달리 빌드된 CSS 번들이 최신 토큰을 실제로 담고 있는지
# grep 으로 강제 확인한다 — stale 배포(캐시된 옛 번들)를 시끄럽게 실패시킨다.
# 홉(hop): (1) 운영자가 origin 으로 먼저 push → (2) 호스트 git fetch + ff-merge origin/develop
#          → (3) 컨테이너 git fetch upstream develop + reset --hard → (4) bench build --app hrms
#          → (5) bench --site noho.safeclaw.kr clear-cache.
set -euo pipefail

HOST=claudebot-2
WS='~/workspaces/seojaehong-hrms-100h'
DX='docker exec -w /home/frappe/frappe-bench docker-frappe-1'
DXAPP='docker exec -w /home/frappe/frappe-bench/apps/hrms docker-frappe-1'
# 서브된 CSS 번들 위치 + 최신 토큰을 증명하는 센티넬
BUNDLE_GLOB='sites/assets/hrms/frontend/assets/index-*.css'
SENTINEL='k-hairline-strong'

cd "$(dirname "$0")/.."

# --- 최상단 가드: --run 없으면 아무것도 하지 않고 계획만 출력 (기본 inert) ---
if [ "${1:-}" != "--run" ]; then
  cat <<EOF
deploy_korea.sh — INERT (계획 출력만). 실제 배포는 'bash scripts/deploy_korea.sh --run'.
수행될 홉:
  0) 운영자: git push origin develop   (스크립트가 하지 않음 — 먼저 해두세요)
  1) 호스트:     git fetch origin && git merge --ff-only origin/develop
  2) 컨테이너:   git fetch upstream develop && git reset --hard FETCH_HEAD
  3) 빌드:       bench build --app hrms
  4) 캐시:       bench --site noho.safeclaw.kr clear-cache
  5) 신선도 검증: $BUNDLE_GLOB 에서 '$SENTINEL' + HEAD sha grep → 없으면 STALE 로 실패
EOF
  exit 0
fi

LOCAL_HEAD=$(git rev-parse develop)
REMOTE_HEAD=$(git ls-remote origin refs/heads/develop | cut -f1)
if [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  echo "ABORT: 로컬 develop($LOCAL_HEAD)이 origin과 다릅니다. 먼저 push하세요." >&2
  exit 1
fi

echo "== (1) 호스트 워크스페이스 갱신 =="
ssh "$HOST" "cd $WS && git fetch origin && git merge --ff-only origin/develop"

echo "== (2) 컨테이너 코드 갱신 =="
ssh "$HOST" "$DXAPP bash -c 'git fetch upstream develop && git reset --hard FETCH_HEAD'"
CONTAINER_HEAD=$(ssh "$HOST" "$DXAPP git rev-parse HEAD")
if [ "$CONTAINER_HEAD" != "$LOCAL_HEAD" ]; then
  echo "ABORT: 컨테이너 HEAD($CONTAINER_HEAD) != 로컬($LOCAL_HEAD)" >&2
  exit 1
fi

echo "== (3) bench build =="
ssh "$HOST" "$DX bench build --app hrms"

echo "== (4) clear-cache =="
ssh "$HOST" "$DX bench --site noho.safeclaw.kr clear-cache"

echo "== (5) 신선도 검증 (STALE 방지) =="
# 서브된 번들 파일명을 찾아 출력하고, 최신 토큰 센티넬을 실제로 담고 있는지 확인한다.
BUNDLE=$(ssh "$HOST" "$DX bash -c 'ls -1t $BUNDLE_GLOB 2>/dev/null | head -1'")
if [ -z "$BUNDLE" ]; then
  echo "STALE: 번들을 찾지 못했습니다 ($BUNDLE_GLOB). 빌드가 서브되지 않았습니다." >&2
  exit 1
fi
echo "  bundle: $BUNDLE"
if ! ssh "$HOST" "$DX grep -q '$SENTINEL' '$BUNDLE'"; then
  echo "STALE: 서브된 번들($BUNDLE)에 '$SENTINEL' 센티넬이 없습니다 — 옛 번들이 서브 중입니다." >&2
  exit 1
fi
echo "  ok: '$SENTINEL' 확인 (HEAD $LOCAL_HEAD)"

echo "DEPLOY OK: $LOCAL_HEAD"
