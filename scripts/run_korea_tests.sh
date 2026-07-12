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

# ── 온톨로지 그래프 검증 단계 ──
# 깨진 그래프(고아 엣지/중복 node_id/무출처 published)가 머지되지 않게 게이트.
# draft 포함 전체 로드. wiki/ontology 부재/빈 경우도 통과(신규 클론 무해).
# FILTER 없거나 "ontology" 계열이면 실행.
GRAPH_FAIL=0
if [ -z "$FILTER" ] || echo "ontology" | grep -qi "$FILTER"; then
  GOUT=$(python3 - <<'PY'
import importlib.util, pathlib, sys
try:
	sys.stdout.reconfigure(encoding="utf-8")
except Exception:
	pass
ROOT = pathlib.Path.cwd()  # 러너가 repo 루트로 cd 후 호출
ONT = ROOT / "hrms" / "regional" / "south_korea" / "ontology"
WIKI = ROOT / "wiki" / "ontology"


def _load(name, path):
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


loader = _load("korea_ontology_loader", ONT / "loader.py")
validate = _load("korea_ontology_validate", ONT / "validate.py")
nodes, errors = loader.load_nodes(WIKI, review_state=None)
problems = ["frontmatter %s: %s" % (e.get("path"), e.get("error")) for e in errors]
problems += list(validate.validate_graph(nodes))
if problems:
	for p in problems:
		print(p)
	sys.exit(1)
print("nodes=%d graph OK" % len(nodes))
sys.exit(0)
PY
)
  GRC=$?
  if [ $GRC -eq 0 ]; then
    echo "  ✓ ontology graph ($GOUT)"
  else
    GRAPH_FAIL=1
    echo "  ✗ ontology graph"
    echo "$GOUT" | tail -10 | sed 's/^/      /'
  fi
fi

# ── 디자인 규율 감사 (DESIGN.md v2) — 베이스라인 래칫: 위반이 늘면 실패
DESIGN_AUDIT_BASELINE=0
DAOUT=$(PYTHONIOENCODING=utf-8 python3 scripts/design_audit.py --baseline $DESIGN_AUDIT_BASELINE 2>&1 | head -1)
DARC=$?
DESIGN_FAIL=0
if [ $DARC -eq 0 ]; then
  echo "  ✓ design audit ($DAOUT · baseline $DESIGN_AUDIT_BASELINE)"
else
  DESIGN_FAIL=1
  echo "  ✗ design audit — $DAOUT (baseline $DESIGN_AUDIT_BASELINE 초과)"
fi

echo ""
echo "════ 결과: 파일 PASS $PASS / FAIL $FAIL · 케이스 $TOTAL_CASES ════"
if [ $FAIL -gt 0 ] || [ $GRAPH_FAIL -gt 0 ] || [ $DESIGN_FAIL -gt 0 ]; then
  [ $FAIL -gt 0 ] && printf '실패: %s\n' "${FAILED_FILES[@]}"
  [ $GRAPH_FAIL -gt 0 ] && echo "실패: ontology graph validation"
  [ $DESIGN_FAIL -gt 0 ] && echo "실패: design audit (scripts/design_audit.py)"
  exit 1
fi
