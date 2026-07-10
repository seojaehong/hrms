# AI HR 담당자 채널 공용 코어 — 텔레그램·슬랙·디스코드·메일·구글챗 5채널이 공유 (불변식 3).
#
# 채널 커넥터는 (사용자ID→테넌트 바인딩, 텍스트 in/out)만 담당하고,
# 명령 해석·계산·Q&A는 전부 이 모듈이 처리한다. 채널이 늘어도 여기는 불변.

from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import server as calc_server

HELP_TEXT = (
    "안녕하세요, AI HR 담당자입니다.\n"
    "· 노동법/HR 질문을 그대로 입력하세요 (예: 연차는 며칠 발생하나요?)\n"
    "· /연차 입사일 기준일 — 연차 산정 (예: /연차 2024-03-02 2026-07-05)\n"
    "· /퇴직금 입사일 퇴직일 일평균임금 — 퇴직금 계산\n"
    "· /마감준비 YYYY-MM — 시급 마감 준비 (예: /마감준비 2026-07)\n"
    "· /스킬 스킬명 {json인자} — AI 에이전트 스킬 실행\n"
    "※ 답변은 AI 보조이며, 확정 판단은 담당자·노무사 검토가 필요합니다."
)

AGENT_NOT_CONFIGURED = (
    "AI 에이전트가 아직 설정되지 않았습니다. 담당자에게 문의해 주세요."
)
_AGENT_SKILL_METHOD = "hrms.regional.south_korea.agent_harness_api.run_agent_skill"
_YYYY_MM = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def answer_command(text: str) -> str | None:
    """계산 명령(/연차, /퇴직금) 처리. 명령이 아니면 None."""
    parts = text.split()
    if not parts:
        return None
    try:
        if parts[0] in ("/연차", "/annual"):
            r = calc_server.calculate_annual_leave(parts[1], parts[2])
            return (
                f"연차 산정 결과 (기준 {r['as_of_date']})\n"
                f"· 근속: {r['service_years']}년\n"
                f"· 월차 적치: {r['monthly_accrual_days']}일 / 연차: {r['annual_entitlement_days']}일\n"
                f"· 합계: {r['total_entitlement_days']}일\n"
                f"(산정기간 {r['period_start']}~{r['period_end']}, 기준: {r['basis']})"
            )
        if parts[0] in ("/퇴직금", "/severance"):
            r = calc_server.calculate_severance(parts[1], parts[2], float(parts[3]))
            if not r.get("qualified_for_severance"):
                return "재직 1년 미만으로 퇴직금 지급 대상이 아닙니다."
            return (
                f"퇴직금 계산 결과\n"
                f"· 재직일수: {r['continuous_service_days']}일\n"
                f"· 퇴직금: {int(r['severance_pay_amount']):,}원\n"
                f"(근로자퇴직급여 보장법 제8조 — 확정 전 담당자 검토 필수)"
            )
    except (IndexError, ValueError) as error:
        return f"입력 형식 오류: {error}\n\n{HELP_TEXT}"
    return None


def answer_question(text: str, binding: dict) -> str:
    """노동법 Q&A — retrieval 기반(hr_chat), 조문 인용 + 딥링크."""
    r = calc_server.hr_chat(text, user_role="manager", session_id=f"ch-{binding.get('site', 'unknown')}")
    lines = [r["answer"].strip()]
    citations = r.get("citations") or []
    if citations:
        lines.append("\n근거:")
        for c in citations[:3]:
            lines.append(f"· {c.get('ref', '')}")
    actions = r.get("suggested_actions") or []
    if actions:
        site = binding.get("site", "")
        lines.append("\n바로가기:")
        for a in actions[:3]:
            lines.append(f"· {a.get('label', '')}: https://{site}{a.get('url', '')}")
    lines.append("\n※ AI 보조 답변입니다. 확정 판단은 담당자·노무사 검토 필수.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AI 에이전트 스킬 명령 — /스킬, /마감준비
#   파싱→payload 구성→응답 정형은 순수 함수(네트워크 분리),
#   frappe HTTP 전송은 주입식(callable)이라 직접실행 테스트가 가능하다.
# ---------------------------------------------------------------------------


def parse_agent_command(text: str) -> dict | None:
    """스킬 명령 파싱. 스킬 명령이 아니면 None.
    성공: {"skill_name": str, "args": dict}. 오형식: {"error": <안내문>}."""
    parts = (text or "").split()
    if not parts:
        return None
    head = parts[0]
    if head in ("/스킬", "/skill"):
        if len(parts) < 2:
            return {"error": "사용법: /스킬 스킬명 {json인자}\n예: /스킬 hr_freeform_qa {\"question\": \"연차 며칠?\"}"}
        skill_name = parts[1]
        rest = text.split(None, 2)
        raw = rest[2].strip() if len(rest) > 2 else ""
        if not raw:
            args: dict = {}
        else:
            try:
                args = json.loads(raw)
            except (ValueError, json.JSONDecodeError):
                return {"error": "인자는 JSON 형식이어야 합니다.\n예: /스킬 hr_freeform_qa {\"question\": \"연차 며칠?\"}"}
            if not isinstance(args, dict):
                return {"error": "인자는 JSON 객체({...})여야 합니다."}
        return {"skill_name": skill_name, "args": args}
    if head in ("/마감준비", "/closing"):
        if len(parts) < 2 or not _YYYY_MM.match(parts[1]):
            return {"error": "사용법: /마감준비 YYYY-MM\n예: /마감준비 2026-07"}
        return {"skill_name": "hourly_closing_prep", "args": {"period": parts[1]}}
    return None


def format_agent_result(result: dict) -> str:
    """run_agent_skill 반환 dict → 회신 텍스트."""
    status = (result or {}).get("status")
    if status == "completed":
        text = (result.get("final_text") or "").strip()
        body = text or "(응답 내용이 비어 있습니다.)"
        return f"{body}\n\n※ AI 에이전트 실행 결과입니다. 확정 판단은 담당자·노무사 검토 필수."
    if status == "not_configured":
        return AGENT_NOT_CONFIGURED
    reason = result.get("reason") or result.get("error") or ""
    label = {
        "unknown_skill": "등록되지 않은 스킬입니다.",
        "no_tools": "실행 가능한 도구가 없습니다.",
        "max_steps_exceeded": "단계 한도를 초과해 완료하지 못했습니다.",
        "provider_error": "AI 게이트웨이 처리 중 오류가 발생했습니다.",
    }.get(status, f"스킬을 실행하지 못했습니다 (status={status}).")
    return f"{label}{(' — ' + reason) if reason else ''}"


def _post_run_agent_skill(binding: dict, payload: dict) -> dict:
    """frappe run_agent_skill 화이트리스트 메서드 호출 (http_server.frappe_get_list 컨벤션 재사용)."""
    base_url = binding["frappe_url"].rstrip("/")
    url = f"{base_url}/api/method/{_AGENT_SKILL_METHOD}"
    data = urllib.parse.urlencode(
        {"skill_name": payload["skill_name"], "args": json.dumps(payload["args"])}
    ).encode()
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"token {binding['api_key']}:{binding['api_secret']}",
            "Host": binding["site"],
            "X-Frappe-Site-Name": binding["site"],
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(request, timeout=35) as response:
        return json.load(response).get("message", {})


def handle_agent_command(text: str, binding: dict, send=None) -> str | None:
    """스킬 명령이면 실행해 회신 텍스트를 반환, 아니면 None(기존 경로로 넘김).
    send: (binding, payload)->dict 주입식 전송자(기본 frappe HTTP)."""
    parsed = parse_agent_command(text)
    if parsed is None:
        return None
    if "error" in parsed:
        return parsed["error"]
    if not (binding.get("api_key") and binding.get("api_secret") and binding.get("frappe_url")):
        return AGENT_NOT_CONFIGURED
    send = send or _post_run_agent_skill
    try:
        result = send(binding, parsed)
    except Exception:  # 네트워크/게이트웨이 장애 — traceback 비노출
        return "AI 에이전트 요청 처리 중 일시적 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    return format_agent_result(result if isinstance(result, dict) else {})


def handle_message(text: str, binding: dict) -> str:
    """채널 공용 진입점: help → 스킬 명령 → 계산 명령 → Q&A."""
    text = (text or "").strip()
    if text in ("/start", "/help", "help", "도움말"):
        return HELP_TEXT
    agent_reply = handle_agent_command(text, binding)
    if agent_reply is not None:
        return agent_reply
    return answer_command(text) or answer_question(text, binding)
