# -*- coding: utf-8 -*-
"""스킬+Hermes 급여 작업 셀프테스트.

1) 엔진(afcf31a3a)으로 실계산: 주휴수당·일용직 원천징수(국세청 정렬 로직)·통상시급
2) 하네스(run_agent_skill)+HermesProvider(gpt-5.5)로 급여 검토 요약 생성
3) LLM 출력에 엔진 수치가 정확히 인용됐는지 프로그램 대조 → PASS/FAIL

키는 env API_SERVER_KEY (스크립트에 시크릿 없음).
"""
import importlib.util
import json
import os
import pathlib
import re
import sys

REPO = pathlib.Path(os.environ.get("HRMS_REPO", "/home/ubuntu/workspaces/seojaehong-hrms-100h"))
SK = REPO / "hrms" / "regional" / "south_korea"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hourly = _load("hourly_wage", SK / "hourly_wage.py")
daily = _load("daily_worker", SK / "daily_worker.py")
api = _load("agent_harness_api", SK / "agent_harness_api.py")
tool_registry_mod = _load("tool_registry", SK / "agent_harness" / "tool_registry.py")
skill_registry_mod = _load("skill_registry", SK / "agent_harness" / "skill_registry.py")
hermes_provider = _load("hermes_provider", SK / "agent_harness" / "hermes_provider.py")

# ── 1) 엔진 실계산 ─────────────────────────────────────────────
weekly_allow = hourly.weekly_holiday_allowance(
    contracted_weekly_hours=20, hourly_rate=10320, perfect_attendance=True
)  # 기대 41,280
dwp = daily.calculate_daily_worker_payroll(daily_wage=160_000, days_worked=4)
ohw = float(hourly.ordinary_hourly_wage(2_156_880))  # 기대 10,320

engine = {
    "주휴수당_주20h_개근_시급10320": weekly_allow,
    "일용직_160000x4일_소득세": dwp["income_tax_total"],
    "일용직_160000x4일_지방소득세": dwp["local_income_tax_total"],
    "일용직_160000x4일_고용보험": dwp["employment_insurance_employee"],
    "일용직_160000x4일_실지급": dwp["net_pay"],
    "통상시급_기본급2156880": ohw,
}
print("[engine]", json.dumps(engine, ensure_ascii=False))

# ── 2) 하네스 스킬 정의 + 실 LLM 실행 ─────────────────────────
reg = tool_registry_mod.ToolRegistry()
reg.register_tool(
    "get_payroll_calculations",
    lambda **kw: {"calculations": engine, "note": "엔진(statutory 2026 정렬) 확정값 — 이 수치를 그대로 인용할 것"},
    {"description": "이번 달 급여 엔진 계산 확정값 조회 (주휴·일용 원천징수·통상시급)", "args": {}},
    read_only=True,
)

key = os.environ["API_SERVER_KEY"]
provider = hermes_provider.make_hermes_provider(
    base_url=os.environ.get("HERMES_GATEWAY_URL", "http://127.0.0.1:8130"),
    credentials={"status": "ok", "api_key": key, "model": os.environ.get("HERMES_MODEL", "gpt-5.5")},
    tool_specs={"get_payroll_calculations": {"description": "이번 달 급여 엔진 계산 확정값 조회 (주휴·일용 원천징수·통상시급)", "args": {}}},
)

result = api.run_agent_skill(
    "hr_freeform_qa",
    args={
        "요청": "이번 달 급여 3건을 검토 요약하라. 반드시 도구로 엔진 확정값을 조회해 그 수치를 그대로 인용할 것(직접 계산 금지): "
        "①시급 10,320원·주 20시간·개근 알바의 1주 주휴수당 ②일급 160,000원 4일 일괄지급 일용직의 소득세·지방소득세·고용보험·실지급액 "
        "③기본급 2,156,880원의 통상시급(÷209). 각 항목에 법적 근거 조항 명시.",
    },
    provider=provider,
    tool_registry=reg,
    max_steps=6,
)

text = result.get("final_text") or ""
print("[harness]", json.dumps({k: result.get(k) for k in ("status", "steps", "tool_calls")}, ensure_ascii=False, default=str))
print("--- LLM 출력 ---")
print(text[:1600])

# ── 3) 자동 대조 ───────────────────────────────────────────────
def _found(amount):
    a = int(amount)
    pats = [f"{a:,}", str(a)]
    return any(p in text.replace(" ", "") or p in text for p in pats)

checks = {name: _found(v) for name, v in engine.items()}
passed = sum(checks.values())
print("--- 대조 결과 ---")
for name, ok in checks.items():
    print(("PASS " if ok else "FAIL "), name, "=", engine[name])
tc = result.get("tool_calls") or []
print(f"[verdict] {passed}/{len(checks)} 일치, tool_calls={len(tc)}, harness status={result.get('status')}")
sys.exit(0 if (passed == len(checks) and result.get("status") == "completed" and len(tc) >= 1) else 1)
