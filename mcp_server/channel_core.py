# AI HR 담당자 채널 공용 코어 — 텔레그램·슬랙·디스코드·메일·구글챗 5채널이 공유 (불변식 3).
#
# 채널 커넥터는 (사용자ID→테넌트 바인딩, 텍스트 in/out)만 담당하고,
# 명령 해석·계산·Q&A는 전부 이 모듈이 처리한다. 채널이 늘어도 여기는 불변.

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import server as calc_server

HELP_TEXT = (
    "안녕하세요, AI HR 담당자입니다.\n"
    "· 노동법/HR 질문을 그대로 입력하세요 (예: 연차는 며칠 발생하나요?)\n"
    "· /연차 입사일 기준일 — 연차 산정 (예: /연차 2024-03-02 2026-07-05)\n"
    "· /퇴직금 입사일 퇴직일 일평균임금 — 퇴직금 계산\n"
    "※ 답변은 AI 보조이며, 확정 판단은 담당자·노무사 검토가 필요합니다."
)


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


def handle_message(text: str, binding: dict) -> str:
    """채널 공용 진입점: help → 명령 → Q&A."""
    text = (text or "").strip()
    if text in ("/start", "/help", "help", "도움말"):
        return HELP_TEXT
    return answer_command(text) or answer_question(text, binding)
