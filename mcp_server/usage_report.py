# 월간 테넌트 사용량·SLA 리포트 (S2 과금·SLA의 데이터 산출물).
#
# 입력: usage.jsonl(AI 호출 미터링), smoke-history.log(가용성), multi_site.json(플랜)
# 출력: 사이트별 호출 수·플랜·월정액(안)·SLA 가용률 — JSON + 사람이 읽는 표.
#
# 사용: python3 mcp_server/usage_report.py [YYYY-MM]  (기본: 이번 달)
# 크론(매월 1일 04:00): 지난달 리포트를 ~/.korea-hrms-mcp/reports/ 에 저장

from __future__ import annotations

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from plans import DEFAULT_PLAN, PLANS

USAGE_LOG = os.environ.get("KCHRMS_USAGE_LOG", "/home/ubuntu/.korea-hrms-mcp/usage.jsonl")
SMOKE_HISTORY = os.environ.get("KCHRMS_SMOKE_HISTORY", "/home/ubuntu/.korea-hrms-mcp/smoke-history.log")
REGISTRY = os.environ.get(
    "KCHRMS_REGISTRY",
    "/home/ubuntu/workspaces/seojaehong-hrms-100h/config/multi_site.json",
)


def month_of(ts: str) -> str:
    return ts[:7]


def load_plans_by_site() -> dict[str, str]:
    try:
        registry = json.loads(pathlib.Path(REGISTRY).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {t.get("site", ""): t.get("plan", DEFAULT_PLAN) for t in registry.get("tenants", [])}


def build_report(month: str) -> dict:
    calls_by_site: dict[str, int] = {}
    try:
        with open(USAGE_LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if month_of(row.get("ts", "")) != month:
                    continue
                site = row.get("site") or "(unbound)"
                calls_by_site[site] = calls_by_site.get(site, 0) + 1
    except FileNotFoundError:
        pass

    ok = fail = 0
    try:
        with open(SMOKE_HISTORY, encoding="utf-8") as f:
            for line in f:
                if not line.startswith(("OK", "FAIL")):
                    continue
                parts = line.split()
                if len(parts) >= 2 and month_of(parts[1]) == month:
                    if parts[0] == "OK":
                        ok += 1
                    else:
                        fail += 1
    except FileNotFoundError:
        pass
    availability = round(ok / (ok + fail) * 100, 3) if (ok + fail) else None

    plans_by_site = load_plans_by_site()
    tenants = []
    for site, calls in sorted(calls_by_site.items()):
        plan = plans_by_site.get(site, DEFAULT_PLAN)
        tenants.append(
            {
                "site": site,
                "plan": plan,
                "ai_calls": calls,
                "monthly_price_krw": PLANS.get(plan, PLANS[DEFAULT_PLAN])["monthly_price_krw"],
            }
        )
    return {
        "month": month,
        "tenants": tenants,
        "total_ai_calls": sum(calls_by_site.values()),
        "sla": {"checks_ok": ok, "checks_fail": fail, "availability_pct": availability},
    }


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    import datetime as dt

    month = sys.argv[1] if len(sys.argv) > 1 else dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    report = build_report(month)
    out_dir = pathlib.Path(os.environ.get("KCHRMS_REPORT_DIR", pathlib.Path.home() / ".korea-hrms-mcp" / "reports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"usage-{month}.json"
    out_path.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"# {month} 테넌트 사용량·SLA 리포트")
    for t in report["tenants"]:
        print(f"- {t['site']}: {t['ai_calls']}건 (plan={t['plan']}, 월정액 {t['monthly_price_krw']:,}원)")
    print(f"- 합계 AI 호출: {report['total_ai_calls']}건")
    sla = report["sla"]
    if sla["availability_pct"] is not None:
        print(f"- SLA 가용률: {sla['availability_pct']}% (OK {sla['checks_ok']} / FAIL {sla['checks_fail']})")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
