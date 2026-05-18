"""Korea HRMS demo seed runner + post-seed verification.

Usage (bench execute — preferred, runs inside Frappe context):
    bench --site hrms.localhost execute hrms.regional.south_korea.demo_seed.seed_korea_demo

Standalone CLI helper (shells out to bench, no direct Frappe context needed):
    python scripts/seed_korea_demo_full.py --help
    python scripts/seed_korea_demo_full.py --site hrms.localhost
    python scripts/seed_korea_demo_full.py --site hrms.localhost --verify-only
    python scripts/seed_korea_demo_full.py --reset    # future: tears down demo data

NOTE: `scripts/` is NOT on bench's Python import path, so
    bench --site ... execute scripts.seed_korea_demo_full.run
will raise ModuleNotFoundError.  Use the hrms.regional.south_korea.demo_seed
module path above for direct bench execute, or use this file as a CLI helper.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Bench-execute entry point (runs inside frappe context)
# ---------------------------------------------------------------------------

def run():
    """Bench-execute entry: seed + verify in one shot.

    NOTE: This function cannot be called via bench execute because scripts/ is
    not on bench's Python import path.  Use the CLI wrapper instead:

        python scripts/seed_korea_demo_full.py --site hrms.localhost

    Or call the seed directly:
        bench --site hrms.localhost execute hrms.regional.south_korea.demo_seed.seed_korea_demo
    """
    import frappe  # available inside bench execute context

    print("[seed] Running Korea demo seed (Wave 4)...")
    from hrms.regional.south_korea.demo_seed import seed_korea_demo  # noqa: PLC0415

    summary = seed_korea_demo()
    print("[seed] Seed complete. Running verification...")
    result = _verify_in_frappe(frappe, summary)
    _print_verification_report(result)
    if not result["ok"]:
        raise SystemExit("[seed] Verification FAILED — see report above")
    print("[seed] All checks passed.")
    return result


# ---------------------------------------------------------------------------
# In-frappe verification (called from run())
# ---------------------------------------------------------------------------

def _verify_in_frappe(frappe, seed_summary: dict) -> dict:
    """Run count assertions after the seed."""
    company = "노란봉투법 데모"
    checks: list[dict[str, Any]] = []

    def chk(label: str, actual: Any, expected: Any, op: str = "eq") -> bool:
        if op == "eq":
            ok = actual == expected
        elif op == "gte":
            ok = actual >= expected
        else:
            ok = bool(actual)
        checks.append({"label": label, "actual": actual, "expected": expected, "op": op, "ok": ok})
        return ok

    # Employee count
    emp_count = frappe.db.count("Employee", {"company": company, "status": "Active"})
    chk("Active employees", emp_count, 10, "gte")

    # Branch count
    branch_count = frappe.db.count("Branch")
    chk("Branches (total)", branch_count, 3, "gte")

    # Department count
    dept_count = frappe.db.count("Department", {"company": company})
    chk("Departments", dept_count, 7, "gte")

    # Attendance records (3 months, 8 extended employees)
    att_count = frappe.db.count("Attendance", {"company": company})
    chk("Attendance records", att_count, 200, "gte")

    # Leave allocations
    alloc_count = frappe.db.count("Leave Allocation", {"company": company})
    chk("Leave allocations", alloc_count, 8, "gte")

    # Korea Payroll Closing Drafts
    draft_count = frappe.db.count(
        "Korea Payroll Closing Draft",
        {"company": company, "status": "draft_pending_human_approval", "docstatus": 0},
    )
    chk("Payroll closing drafts", draft_count, 3, "gte")

    # Salary structure
    ss_exists = frappe.db.exists("Salary Structure", "KR Demo Salary Structure")
    chk("Salary structure exists", bool(ss_exists), True)

    all_ok = all(c["ok"] for c in checks)
    return {"ok": all_ok, "company": company, "checks": checks}


# ---------------------------------------------------------------------------
# CLI / standalone helpers
# ---------------------------------------------------------------------------

def _print_verification_report(result: dict) -> None:
    print("\n=== Korea HRMS Demo Seed — Verification Report ===")
    print(f"Company: {result['company']}")
    max_label = max(len(c['label']) for c in result['checks'])
    for c in result['checks']:
        status = "OK" if c["ok"] else "FAIL"
        label = c["label"].ljust(max_label)
        print(f"  [{status}] {label}  actual={c['actual']}  expected({c['op']})={c['expected']}")
    overall = "PASS" if result["ok"] else "FAIL"
    print(f"\nOverall: {overall}")
    print("=" * 51)


def _bench_execute(site: str, method: str) -> dict:
    """Run bench execute and return parsed JSON output."""
    cmd = ["bench", "--site", site, "execute", method]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[ERR] bench execute failed:\n{proc.stderr}", file=sys.stderr)
        raise SystemExit(1)
    # bench execute prints JSON (from our seed's print()) after frappe log lines
    # Find the last '{' line start
    lines = proc.stdout.splitlines()
    json_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("{"):
            json_start = i
            break
    if json_start is not None:
        raw = "\n".join(lines[json_start:])
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return {"raw_output": proc.stdout}


def _cli_seed(site: str) -> None:
    print(f"[cli] Seeding demo data on site '{site}'...")
    result = _bench_execute(site, "hrms.regional.south_korea.demo_seed.seed_korea_demo")
    print("[cli] Seed output:")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def _cli_verify(site: str) -> None:
    """Run verification via bench execute (wraps run() in verify-only mode)."""
    print(f"[cli] Verifying demo data on site '{site}'...")
    result = _bench_execute(site, "scripts.seed_korea_demo_full._cli_verify_inplace")
    _print_verification_report(result)
    if not result.get("ok"):
        raise SystemExit(1)


def _cli_verify_inplace():
    """Called from bench execute for --verify-only."""
    import frappe  # noqa: PLC0415
    result = _verify_in_frappe(frappe, {})
    _print_verification_report(result)
    print(json.dumps(result, ensure_ascii=False, default=str))
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Korea HRMS demo seed runner + verifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed + verify (most common):
  python scripts/seed_korea_demo_full.py --site hrms.localhost

  # Verify only (after seed already run):
  python scripts/seed_korea_demo_full.py --site hrms.localhost --verify-only

  # Via bench execute (inside frappe context):
  bench --site hrms.localhost execute scripts.seed_korea_demo_full.run
        """,
    )
    parser.add_argument("--site", default="hrms.localhost", help="Frappe site name (default: hrms.localhost)")
    parser.add_argument("--verify-only", action="store_true", help="Skip seeding, only run verification")
    args = parser.parse_args(argv)

    if args.verify_only:
        _cli_verify(args.site)
    else:
        _cli_seed(args.site)
        _cli_verify(args.site)


if __name__ == "__main__":
    main()
