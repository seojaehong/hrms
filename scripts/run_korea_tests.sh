#!/bin/bash
# Korea framework-free 테스트 전체 러너 — 머지 게이트/회귀 베이스라인용.
# 사용: bash scripts/run_korea_tests.sh [필터패턴]
#   예: bash scripts/run_korea_tests.sh            # 전체
#       bash scripts/run_korea_tests.sh insurance  # 파일명 필터
# 종료코드: 실패 파일 있으면 1. 출력: 파일별 ✓/✗ + 총계.
set -u
cd "$(dirname "$0")/.."

FILTER="${1:-}"
PASS=0; FAIL=0; TOTAL_CASES=0
FAILED_FILES=()

# spec_from_file_location 사용 = frappe 불필요 직접실행 테스트
FILES=$(grep -rl "spec_from_file_location" hrms/tests/test_korea_*.py 2>/dev/null | sort)
[ -n "$FILTER" ] && FILES=$(echo "$FILES" | grep -i "$FILTER")

for t in $FILES; do
  OUT=$(python3 "$t" 2>&1)
  RC=$?
  N=$(echo "$OUT" | grep -oE "Ran [0-9]+ tests" | grep -oE "[0-9]+" | head -1)
  N=${N:-0}
  if [ $RC -eq 0 ]; then
    PASS=$((PASS+1)); TOTAL_CASES=$((TOTAL_CASES+N))
    echo "  ✓ $(basename "$t") ($N)"
  else
    FAIL=$((FAIL+1)); FAILED_FILES+=("$t")
    echo "  ✗ $(basename "$t")"
    echo "$OUT" | tail -5 | sed 's/^/      /'
  fi
done

echo ""
echo "════ 결과: 파일 PASS $PASS / FAIL $FAIL · 케이스 $TOTAL_CASES ════"
if [ $FAIL -gt 0 ]; then
  printf '실패: %s\n' "${FAILED_FILES[@]}"
  exit 1
fi
