# -*- coding: utf-8 -*-
"""N4 스모크 — hourly_closing_prep 스킬을 실 LLM(Hermes gateway)로 1회 실행.

키는 환경변수 API_SERVER_KEY로 받는다(스크립트에 시크릿 없음).
"""
import importlib.util
import json
import os
import pathlib
import sys

REPO = pathlib.Path(os.environ.get("HRMS_REPO", "/home/ubuntu/workspaces/seojaehong-hrms-100h"))
SK = REPO / "hrms" / "regional" / "south_korea"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


api = _load("agent_harness_api", SK / "agent_harness_api.py")
tool_registry_mod = _load("tool_registry", SK / "agent_harness" / "tool_registry.py")
hermes_provider = _load("hermes_provider", SK / "agent_harness" / "hermes_provider.py")

SAMPLE_PROPOSALS = [
    {"employee": "김시급", "hours": 87.5, "hourly_rate": 10320, "gross": 903000, "flags": []},
    {"employee": "이파트", "hours": 42.0, "hourly_rate": 11000, "gross": 462000, "flags": ["주휴 미충족(주 14h)"]},
    {"employee": "박야간", "hours": 96.0, "hourly_rate": 10320, "gross": 1114560, "flags": ["야간 12h 포함"]},
]

reg = tool_registry_mod.ToolRegistry()
reg.register_tool(
    "list_hourly_payroll_proposals",
    lambda **kw: {"proposals": SAMPLE_PROPOSALS, "proposal_count": len(SAMPLE_PROPOSALS)},
    {"description": "이번 달 시급 급여 제안 목록 조회", "args": {}},
    read_only=True,
)

key = os.environ["API_SERVER_KEY"]
provider = hermes_provider.make_hermes_provider(
    base_url=os.environ.get("HERMES_GATEWAY_URL", "http://127.0.0.1:8130"),
    credentials={"status": "ok", "api_key": key, "model": os.environ.get("HERMES_MODEL", "gpt-5.5")},
)

result = api.run_agent_skill(
    "hourly_closing_prep",
    args={"month": "2026-07", "site": "smoke-tenant", "proposals_preview": SAMPLE_PROPOSALS},
    provider=provider,
    tool_registry=reg,
    max_steps=6,
)

out = {k: result.get(k) for k in ("status", "skill_name", "steps", "tool_calls")}
print(json.dumps(out, ensure_ascii=False, default=str)[:800])
print("--- final_text ---")
print((result.get("final_text") or result.get("error") or "")[:1200])
