#!/usr/bin/env python3
"""디자인 규율 감사기 — DESIGN.md v2 「장부(Ledger)」 정합 정적 스캔.

frontend/src/views/**/*.vue 를 스캔해 규칙 위반을 리포트한다.

규칙 (스펙: docs/design/2026-07-12-design-revision-v2-sweep.md §Phase 0):
  R1  데이터 화면 pill(rounded-full) 금지 — 내러티브 화이트리스트 제외
  R2  데이터 화면 검정(bg-black) 버튼 금지
  R3  금액 표기에 k-amount/k-display/k-settled 의무 (error — 2026-07-12 승격)
  R4  하드코딩 색 금지 (text-gray-*/bg-gray-*/임의 #hex — var(--k-*) 토큰 제외)
  R5  파스텔 차터 — 데이터 화면 k-block--* 금지 (cream은 결과 히어로 관례로 예외)
  R6  ledger-navy 유용 금지 — 버튼 배경에 --k-ledger-navy 직접 사용 금지

사용:
  python3 scripts/design_audit.py            # 리포트 출력, error>0이면 exit 1
  python3 scripts/design_audit.py --baseline N  # 기존 위반 N건까지 허용(점진 감축)
"""

from __future__ import annotations

import pathlib
import re
import sys

# 내러티브 화면(파스텔·pill 허용) — 스펙 §Phase 0 화이트리스트
NARRATIVE_VIEWS = {
    "Home.vue",
    "KoreaOnboardingRequest.vue",  # 온보딩 요청(내러티브 톤 허용)
    "InvalidEmployee.vue",
    "Login.vue",
    "KoreaLanding.vue",  # 마케팅 (Linear 다크 — 별도 문법)
    "KoreaAIChat.vue",  # 대화형 챗 — 내러티브 분류(장부 데이터 없음, navy 히어로 유지)
}

_BUTTON_TAG = re.compile(r"<button\b[^>]*>", re.IGNORECASE)
_ROUTER_BTN = re.compile(r"<(?:router-link|a)\b[^>]*class=\"[^\"]*\bbtn\b", re.IGNORECASE)
_AMOUNT_BIND = re.compile(r"\{\{\s*formatKRW\(")
_AMOUNT_OK_CLASSES = ("k-amount", "k-display", "k-settled", "linear")
_HEX_IN_CLASS = re.compile(r"class=\"[^\"]*\[#(?:[0-9a-fA-F]{3,8})\]")
_GRAY_UTIL = re.compile(r"\b(?:text|bg|border)-gray-\d+")
_PASTEL = re.compile(r"k-block--(\w+)")
_NAVY_BTN = re.compile(r"<button\b[^>]*(?:bg-\[var\(--k-ledger-navy\)\]|background:\s*var\(--k-ledger-navy\))")


_BUTTON_OPEN = re.compile(r"<button\b[^>]*>", re.IGNORECASE | re.DOTALL)


def audit_source(source: str, filename: str, *, narrative: bool = False) -> list[dict]:
    """단일 뷰 소스 감사. 위반 리스트 [{rule, level, line, detail}] 반환."""
    violations: list[dict] = []
    lines = source.split("\n")

    # ── 버튼 태그 단위 검사 (Vue 관례상 속성이 여러 줄로 갈라짐 — 태그 전체를 본다)
    if not narrative:
        for m in _BUTTON_OPEN.finditer(source):
            tag = m.group(0)
            line_no = source.count("\n", 0, m.start()) + 1
            if "rounded-full" in tag:
                violations.append({
                    "rule": "R1", "level": "error", "line": line_no,
                    "detail": "데이터 화면 pill 버튼 — radius 8px(.k-btn-*)로 교체",
                })
            if re.search(r"\bbg-black\b", tag):
                violations.append({
                    "rule": "R2", "level": "error", "line": line_no,
                    "detail": "데이터 화면 검정 버튼 — tenant-accent(.k-btn-primary)로 교체",
                })
            if re.search(r"bg-\[var\(--k-ledger-navy\)\]", tag):
                violations.append({
                    "rule": "R6", "level": "error", "line": line_no,
                    "detail": "ledger-navy는 돈의 색 — 버튼은 --t-accent 사용",
                })

    for idx, line in enumerate(lines, start=1):
        # R3 — 금액 잉크 (warn 휴리스틱). 멀티라인 요소는 클래스가 윗줄에 올 수 있어
        # 바인딩 줄에 class 속성이 없으면 직전 2줄까지 함께 본다.
        context = line
        if 'class="' not in line and _AMOUNT_BIND.search(line):
            context = "\n".join(lines[max(0, idx - 3):idx])
        if _AMOUNT_BIND.search(line) and not any(c in context for c in _AMOUNT_OK_CLASSES):
            violations.append({
                "rule": "R3", "level": "error", "line": idx,
                "detail": "금액 바인딩에 k-amount/k-display/k-settled 미적용",
            })

        # R4 — 하드코딩 색
        if _GRAY_UTIL.search(line) or _HEX_IN_CLASS.search(line):
            violations.append({
                "rule": "R4", "level": "error", "line": idx,
                "detail": "하드코딩 색 — 토큰(var(--k-*))으로 교체",
            })

        # R5 — 파스텔 차터 (데이터 화면, cream 예외)
        if not narrative:
            for m in _PASTEL.finditer(line):
                if m.group(1) != "cream":
                    violations.append({
                        "rule": "R5", "level": "error", "line": idx,
                        "detail": f"데이터 화면 파스텔 블록(k-block--{m.group(1)}) 금지",
                    })

    return violations


def audit_repo(repo_root) -> dict:
    root = pathlib.Path(repo_root)
    views_dir = root / "frontend" / "src" / "views"
    results: dict[str, list[dict]] = {}
    files = sorted(views_dir.rglob("*.vue"))
    for path in files:
        name = path.name
        source = path.read_text(encoding="utf-8", errors="replace")
        found = audit_source(source, name, narrative=name in NARRATIVE_VIEWS)
        if found:
            results[str(path.relative_to(root)).replace("\\", "/")] = found

    error_count = sum(1 for vs in results.values() for v in vs if v["level"] == "error")
    warn_count = sum(1 for vs in results.values() for v in vs if v["level"] == "warn")
    return {
        "files_scanned": len(files),
        "violations": results,
        "error_count": error_count,
        "warn_count": warn_count,
    }


def main(argv: list[str]) -> int:
    baseline = 0
    if "--baseline" in argv:
        baseline = int(argv[argv.index("--baseline") + 1])

    repo = pathlib.Path(__file__).resolve().parents[1]
    report = audit_repo(repo)

    by_rule: dict[str, int] = {}
    for vs in report["violations"].values():
        for v in vs:
            by_rule[v["rule"]] = by_rule.get(v["rule"], 0) + 1

    print(f"design_audit — files={report['files_scanned']} "
          f"errors={report['error_count']} warns={report['warn_count']} "
          f"by_rule={dict(sorted(by_rule.items()))}")
    for fname, vs in report["violations"].items():
        for v in vs:
            print(f"  [{v['level']}] {v['rule']} {fname}:{v['line']} — {v['detail']}")

    if report["error_count"] > baseline:
        print(f"FAIL: errors {report['error_count']} > baseline {baseline}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
