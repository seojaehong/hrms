# Korea HRMS AI HR 담당자 — 텔레그램 커넥터 v0 (scale-architecture Plane 2-③).
#
# 봇 계정 1개가 멀티테넌트를 서빙한다(불변식 3): chat_id ↔ AI 플레인 토큰 바인딩 파일로
# 라우팅하고, 바인딩 없는 채팅은 응답하지 않는다(fail-closed).
# v0 능력: 노동법 Q&A(hr_chat, retrieval 기반 — LLM 불필요) + 연차/퇴직금 계산 명령.
# 확정 행위는 하지 않는다 — 답변 말미에 관련 화면 딥링크만 안내.
#
# 실행(systemd): TELEGRAM_BOT_TOKEN=... KCHRMS_TG_BINDINGS=~/.korea-hrms-mcp/tg-bindings.json \
#   python3 mcp_server/telegram_connector.py
# 바인딩 파일: {"<chat_id>": {"site": "noho.safeclaw.kr", "label": "사장님"}}

from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import server as calc_server

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BINDINGS_FILE = os.environ.get("KCHRMS_TG_BINDINGS", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

HELP_TEXT = (
    "안녕하세요, AI HR 담당자입니다.\n"
    "· 노동법/HR 질문을 그대로 입력하세요 (예: 연차는 며칠 발생하나요?)\n"
    "· /연차 입사일 기준일 — 연차 산정 (예: /연차 2024-03-02 2026-07-05)\n"
    "· /퇴직금 입사일 퇴직일 일평균임금 — 퇴직금 계산\n"
    "※ 답변은 AI 보조이며, 확정 판단은 담당자·노무사 검토가 필요합니다."
)


def tg(method: str, **params) -> dict:
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"{API}/{method}", data=data, timeout=35) as response:
        return json.load(response)


def load_bindings() -> dict:
    try:
        return json.loads(pathlib.Path(BINDINGS_FILE).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def answer_command(text: str) -> str | None:
    parts = text.split()
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
    r = calc_server.hr_chat(text, user_role="manager", session_id=f"tg-{binding.get('site', 'unknown')}")
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


def main() -> None:
    if not BOT_TOKEN or not BINDINGS_FILE:
        raise SystemExit("TELEGRAM_BOT_TOKEN / KCHRMS_TG_BINDINGS required")
    offset = 0
    print("telegram connector started", flush=True)
    while True:
        try:
            updates = tg("getUpdates", offset=offset, timeout=30)
        except Exception as error:  # 네트워크 일시 오류 — 재시도
            print(f"getUpdates error: {error}", flush=True)
            time.sleep(5)
            continue
        for update in updates.get("result", []):
            offset = update["update_id"] + 1
            message = update.get("message") or {}
            chat_id = str((message.get("chat") or {}).get("id", ""))
            text = (message.get("text") or "").strip()
            if not chat_id or not text:
                continue
            binding = load_bindings().get(chat_id)
            if not binding:
                continue  # 미바인딩 채팅은 무응답 (fail-closed)
            if text in ("/start", "/help", "help"):
                reply = HELP_TEXT
            else:
                reply = answer_command(text) or answer_question(text, binding)
            try:
                tg("sendMessage", chat_id=chat_id, text=reply[:4000])
            except Exception as error:
                print(f"sendMessage error: {error}", flush=True)


if __name__ == "__main__":
    main()
