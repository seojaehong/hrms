# Korea HRMS AI HR 담당자 — 텔레그램 커넥터 (scale-architecture Plane 2-③).
#
# 봇 계정 1개가 멀티테넌트를 서빙한다(불변식 3): chat_id ↔ 테넌트 바인딩 파일로
# 라우팅하고, 바인딩 없는 채팅은 응답하지 않는다(fail-closed).
# 응답 로직은 channel_core(5채널 공용)에 위임한다.
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
import channel_core

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BINDINGS_FILE = os.environ.get("KCHRMS_TG_BINDINGS", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def tg(method: str, **params) -> dict:
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"{API}/{method}", data=data, timeout=35) as response:
        return json.load(response)


def load_bindings() -> dict:
    try:
        return json.loads(pathlib.Path(BINDINGS_FILE).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main() -> None:
    if not BOT_TOKEN or not BINDINGS_FILE:
        raise SystemExit("TELEGRAM_BOT_TOKEN / KCHRMS_TG_BINDINGS required")
    offset = 0
    print("telegram connector started", flush=True)
    while True:
        try:
            updates = tg("getUpdates", offset=offset, timeout=30)
        except Exception as error:  # 네트워크 일시 오류 — 재시도
            print(f"getUpdates error: {type(error).__name__}", flush=True)  # 토큰이 URL에 있어 error 전문 로깅 금지
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
            reply = channel_core.handle_message(text, binding)
            try:
                tg("sendMessage", chat_id=chat_id, text=reply[:4000])
            except Exception as error:
                print(f"sendMessage error: {type(error).__name__}", flush=True)


if __name__ == "__main__":
    main()
