# Korea HRMS AI HR 담당자 — 메일 커넥터 (Plane 2-③, 4채널 중 메일).
#
# IMAP 미확인 메일을 폴링해 발신자 주소 ↔ 테넌트 바인딩으로 라우팅하고,
# channel_core 답변을 SMTP로 회신한다. 미바인딩 발신자는 무응답(fail-closed).
#
# 실행(systemd): EnvironmentFile에 아래 값을 넣고 enable.
#   MAIL_IMAP_HOST / MAIL_SMTP_HOST / MAIL_USER / MAIL_PASSWORD
#   KCHRMS_MAIL_BINDINGS=~/.korea-hrms-mcp/mail-bindings.json
#     예: {"boss@noho.kr": {"site": "noho.safeclaw.kr", "label": "사장님"}}

from __future__ import annotations

import email
import email.header
import email.mime.text
import imaplib
import json
import os
import pathlib
import smtplib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import channel_core

IMAP_HOST = os.environ.get("MAIL_IMAP_HOST", "")
SMTP_HOST = os.environ.get("MAIL_SMTP_HOST", "")
USER = os.environ.get("MAIL_USER", "")
PASSWORD = os.environ.get("MAIL_PASSWORD", "")
BINDINGS_FILE = os.environ.get("KCHRMS_MAIL_BINDINGS", "")
POLL_SECONDS = int(os.environ.get("MAIL_POLL_SECONDS", "60"))


def load_bindings() -> dict:
    try:
        return json.loads(pathlib.Path(BINDINGS_FILE).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def decode_header_text(value: str | None) -> str:
    if not value:
        return ""
    parts = email.header.decode_header(value)
    out = []
    for text, charset in parts:
        if isinstance(text, bytes):
            out.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def extract_sender(message: email.message.Message) -> str:
    """From 헤더에서 주소만 소문자로. (순수 — 테스트 대상)"""
    raw = message.get("From", "")
    _, addr = email.utils.parseaddr(raw)
    return addr.lower()


def extract_body(message: email.message.Message) -> str:
    """text/plain 파트 우선 추출. (순수 — 테스트 대상)"""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace").strip()
        return ""
    payload = message.get_payload(decode=True) or b""
    return payload.decode(message.get_content_charset() or "utf-8", errors="replace").strip()


def send_reply(to_addr: str, subject: str, body: str) -> None:
    reply = email.mime.text.MIMEText(body, _charset="utf-8")
    reply["From"] = USER
    reply["To"] = to_addr
    reply["Subject"] = f"Re: {subject}" if subject and not subject.lower().startswith("re:") else (subject or "AI HR 담당자")
    with smtplib.SMTP_SSL(SMTP_HOST, 465, timeout=20) as smtp:
        smtp.login(USER, PASSWORD)
        smtp.sendmail(USER, [to_addr], reply.as_string())


def poll_once() -> int:
    handled = 0
    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(USER, PASSWORD)
        imap.select("INBOX")
        _, data = imap.search(None, "UNSEEN")
        for num in (data[0] or b"").split():
            _, msg_data = imap.fetch(num, "(RFC822)")
            message = email.message_from_bytes(msg_data[0][1])
            sender = extract_sender(message)
            binding = load_bindings().get(sender)
            imap.store(num, "+FLAGS", "\\Seen")
            if not binding:
                continue  # 미바인딩 발신자 무응답 (fail-closed)
            text = extract_body(message)
            if not text:
                continue
            reply = channel_core.handle_message(text.splitlines()[0].strip() or text, binding)
            send_reply(sender, decode_header_text(message.get("Subject")), reply)
            handled += 1
    return handled


def main() -> None:
    if not all([IMAP_HOST, SMTP_HOST, USER, PASSWORD, BINDINGS_FILE]):
        raise SystemExit("MAIL_IMAP_HOST/MAIL_SMTP_HOST/MAIL_USER/MAIL_PASSWORD/KCHRMS_MAIL_BINDINGS required")
    print("mail connector started", flush=True)
    while True:
        try:
            poll_once()
        except Exception as error:
            print(f"poll error: {error}", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
