# Korea HRMS AI 플레인 v0 — streamable HTTP MCP 게이트웨이 (scale-architecture §1 Plane 2-①).
#
# stdio 서버(server.py)의 계산 도구 7종을 재사용하고, 테넌트 데이터 브리지 도구를 추가한다.
# 확장 불변식:
#   - 무상태: 토큰 파일 외 상태 없음. 워커를 몇 개 띄워도 동일.
#   - 테넌트 격리: Bearer 토큰(sha256 저장) → {site, api_key, api_secret} 바인딩.
#     브리지 도구는 그 사이트의 Frappe REST로만 접근. 크로스 테넌트 구조적 불가.
#   - 브리지는 읽기 전용 + DocType 화이트리스트 (쓰기·확정 행위는 사람이 Frappe에서).
#
# 실행: KCHRMS_MCP_TOKENS_FILE=/path/tokens.json uvicorn http_server:app --host 127.0.0.1 --port 8100
# 토큰 발급: python3 mcp_server/issue_token.py <site> <label> (tokens.json에 해시 저장)

from __future__ import annotations

import contextvars
import hashlib
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import server as calc_server  # 계산 도구 7종이 등록된 FastMCP 인스턴스

TOKENS_FILE = os.environ.get("KCHRMS_MCP_TOKENS_FILE", "/etc/korea-hrms-mcp/tokens.json")
FRAPPE_BASE_URL = os.environ.get("KCHRMS_FRAPPE_URL", "http://localhost:8000")
# 테넌트별 사용량 미터링(JSONL append) — S2 과금·쿼터의 데이터 기반 (불변식: 무상태, 로그는 파일)
USAGE_LOG = os.environ.get("KCHRMS_USAGE_LOG", "")
# 셀프서브 가입 큐 — process_signup_queue.sh 가 소비해 무인 프로비저닝
SIGNUP_QUEUE = os.environ.get("KCHRMS_SIGNUP_QUEUE", "")

# 브리지 허용 DocType (읽기 전용). PII 최소화: 필드도 화이트리스트.
BRIDGE_DOCTYPES: dict[str, list[str]] = {
    "Employee": ["name", "employee_name", "company", "date_of_joining", "relieving_date", "status", "department", "designation"],
    "Attendance": ["name", "employee", "attendance_date", "status", "working_hours"],
    "Leave Application": ["name", "employee", "leave_type", "from_date", "to_date", "status"],
    "Holiday List": ["name", "from_date", "to_date", "total_holidays"],
    "Company": ["name", "company_name", "default_currency"],
}

_auth_context: contextvars.ContextVar[dict | None] = contextvars.ContextVar("kchrms_auth", default=None)


def _hash(token: str) -> str:
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def load_tokens() -> dict[str, Any]:
    try:
        return json.loads(pathlib.Path(TOKENS_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def resolve_token(bearer: str | None) -> dict | None:
    """Bearer → {site, api_key, api_secret, label} 또는 None."""
    if not bearer:
        return None
    entry = load_tokens().get(_hash(bearer))
    if not entry or entry.get("disabled"):
        return None
    return entry


def frappe_get_list(site_ctx: dict, doctype: str, filters: dict | None, limit: int) -> list[dict]:
    if doctype not in BRIDGE_DOCTYPES:
        raise ValueError(f"doctype not allowed: {doctype} (allowed: {', '.join(BRIDGE_DOCTYPES)})")
    limit = max(1, min(int(limit), 100))
    fields = BRIDGE_DOCTYPES[doctype]
    params = {
        "fields": json.dumps(fields),
        "limit_page_length": str(limit),
    }
    if filters:
        params["filters"] = json.dumps(filters)
    # 샤딩 준비: 토큰 바인딩에 frappe_url이 있으면 그 bench 호스트로 (S3 다중 호스트 = 데이터 변경만)
    base_url = site_ctx.get("frappe_url") or FRAPPE_BASE_URL
    url = f"{base_url}/api/resource/{urllib.parse.quote(doctype)}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"token {site_ctx['api_key']}:{site_ctx['api_secret']}",
            "Host": site_ctx["site"],
            "X-Frappe-Site-Name": site_ctx["site"],
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response).get("data", [])


mcp = calc_server.mcp  # 계산 도구 7종 재사용


@mcp.tool()
def get_tenant_records(doctype: str, filters: dict | None = None, limit: int = 20) -> dict:
    """인증된 테넌트(사업장) 사이트의 실데이터 조회 (읽기 전용).
    doctype: Employee | Attendance | Leave Application | Holiday List | Company.
    반환 필드는 서버 화이트리스트로 제한된다. 급여 금액 등 민감 수치는 이 도구로 노출하지 않는다."""
    ctx = _auth_context.get()
    if not ctx:
        raise ValueError("no tenant binding for this token")
    rows = frappe_get_list(ctx, doctype, filters, limit)
    return {"site": ctx["site"], "doctype": doctype, "count": len(rows), "rows": rows}


@mcp.tool()
def prepare_insurance_filing(filing_type: str, year: int, month: int) -> dict:
    """4대보험 신고 대상자 추출 (acquisition=취득/입사자, loss=상실/퇴사자).
    인증된 테넌트의 직원 실데이터에서 귀속월 대상자를 뽑아 명단 컨트랙트를 반환한다.
    반환된 명단은 반드시 담당자 확인 후에만 신고서로 만든다 (자동 제출 금지)."""
    ctx = _auth_context.get()
    if not ctx:
        raise ValueError("no tenant binding for this token")
    employees = frappe_get_list(ctx, "Employee", None, 100)
    insurance = calc_server._load_core("insurance_filing")
    contract = insurance.build_filing_contract(
        filing_type=filing_type, year=int(year), month=int(month), employees=employees
    )
    contract["site"] = ctx["site"]
    return contract


@mcp.tool()
def whoami() -> dict:
    """현재 토큰의 테넌트 바인딩 확인 (사이트·라벨)."""
    ctx = _auth_context.get()
    if not ctx:
        return {"authenticated": False}
    return {"authenticated": True, "site": ctx["site"], "label": ctx.get("label", "")}


DEFAULT_DAILY_LIMIT = int(os.environ.get("KCHRMS_DEFAULT_DAILY_LIMIT", "500"))
QUOTA_FILE = os.environ.get("KCHRMS_QUOTA_FILE", "")


def check_and_count_quota(token_hash: str, daily_limit: int) -> bool:
    """토큰별 일일 쿼터 카운트(파일 기반, 날짜 바뀌면 리셋). 초과면 False.

    플랜별 한도는 tokens.json 엔트리의 daily_limit — S2 과금의 강제 지점.
    """
    if not QUOTA_FILE:
        return True
    import datetime as _dt

    today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    path = pathlib.Path(QUOTA_FILE)
    data: dict = {"date": today, "counts": {}}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if loaded.get("date") == today:
            data = loaded
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    count = int(data["counts"].get(token_hash, 0))
    if count >= daily_limit:
        return False
    data["counts"][token_hash] = count + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)  # 원자적 교체 (부분쓰기·경합 완화 — 완전 방지는 아니나 찢긴 JSON 방지)
    return True


def record_usage(entry: dict, path: str) -> None:
    if not USAGE_LOG:
        return
    try:
        import datetime as _dt

        line = json.dumps(
            {
                "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                "site": entry.get("site"),
                "label": entry.get("label"),
                "path": path,
            },
            ensure_ascii=False,
        )
        with open(USAGE_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass  # 미터링 실패가 요청을 막으면 안 된다


TENANT_ID_RE = __import__("re").compile(r"^[a-z][a-z0-9-]{1,30}$")
EMAIL_RE = __import__("re").compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def validate_signup(payload: dict) -> dict:
    """가입 요청 검증(순수). 반환: 큐 엔트리."""
    tenant_id = str(payload.get("tenant_id", "")).strip().lower()
    admin_email = str(payload.get("admin_email", "")).strip()
    company_name = str(payload.get("company_name", "")).strip()
    if not TENANT_ID_RE.match(tenant_id):
        raise ValueError("tenant_id는 영문 소문자로 시작, 소문자·숫자·하이픈 2~31자")
    if tenant_id in {"www", "hrms", "ai", "api", "admin", "noho"}:
        raise ValueError("사용할 수 없는 tenant_id 입니다")
    if not EMAIL_RE.match(admin_email):
        raise ValueError("admin_email 형식이 올바르지 않습니다")
    if not company_name:
        raise ValueError("company_name은 필수입니다")
    return {"tenant_id": tenant_id, "admin_email": admin_email, "company_name": company_name, "status": "pending"}


MAX_BODY_BYTES = 256 * 1024  # 비인증 엔드포인트 본문 상한 (DoS 완화)


async def _read_body(receive) -> bytes:
    chunks = []
    total = 0
    while True:
        message = await receive()
        chunk = message.get("body", b"")
        total += len(chunk)
        if total > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        chunks.append(chunk)
        if not message.get("more_body"):
            return b"".join(chunks)


async def _json_response(send, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": body})


async def handle_signup(scope, receive, send) -> None:
    """POST /signup — 셀프서브 가입 접수. 큐에 적재하면 워커가 무인 프로비저닝한다."""
    if scope["method"] != "POST":
        await _json_response(send, 405, {"error": "method_not_allowed"})
        return
    if not SIGNUP_QUEUE:
        await _json_response(send, 503, {"error": "signup_disabled"})
        return
    try:
        body = await _read_body(receive)
        payload = json.loads(body or b"{}")
        entry = validate_signup(payload)
    except ValueError as error:
        await _json_response(send, 400, {"error": str(error)})
        return
    except json.JSONDecodeError:
        await _json_response(send, 400, {"error": "invalid_json"})
        return
    # 중복 방지: 큐 + 레지스트리에 같은 tenant_id가 있으면 거절
    queue_path = pathlib.Path(SIGNUP_QUEUE)
    existing = ""
    if queue_path.exists():
        if queue_path.stat().st_size > 256 * 1024:  # 큐 폭주 방어 (H2)
            await _json_response(send, 429, {"error": "signup_queue_full",
                                             "message": "잠시 후 다시 시도해 주세요."})
            return
        existing = queue_path.read_text(encoding="utf-8")
    if f'"tenant_id": "{entry["tenant_id"]}"' in existing:
        await _json_response(send, 409, {"error": "이미 접수된 tenant_id 입니다"})
        return
    import datetime as _dt

    entry["requested_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with open(queue_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    await _json_response(send, 202, {
        "status": "accepted",
        "tenant_id": entry["tenant_id"],
        "site": f'{entry["tenant_id"]}.safeclaw.kr',
        "message": "프로비저닝이 예약되었습니다. 완료까지 약 20~30분 소요됩니다.",
    })


# ── 슬랙·디스코드 채널 엔드포인트 (env-gated — 키 없으면 503) ─────────────────
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_BINDINGS = os.environ.get("KCHRMS_SLACK_BINDINGS", "")
DISCORD_PUBLIC_KEY = os.environ.get("DISCORD_PUBLIC_KEY", "")
DISCORD_BINDINGS = os.environ.get("KCHRMS_DISCORD_BINDINGS", "")
GOOGLECHAT_PROJECT_NUMBER = os.environ.get("GOOGLECHAT_PROJECT_NUMBER", "")
GOOGLECHAT_BINDINGS = os.environ.get("KCHRMS_GOOGLECHAT_BINDINGS", "")


def _load_channel_bindings(path: str) -> dict:
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def verify_slack_signature(body: bytes, timestamp: str, signature: str, secret: str) -> bool:
    """Slack v0 서명 검증(순수). 5분 이상 지난 타임스탬프 거절."""
    import hmac
    import time as _time

    try:
        if abs(_time.time() - float(timestamp)) > 300:
            return False
    except ValueError:
        return False
    base = f"v0:{timestamp}:".encode() + body
    expected = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def _channel_reply(text: str, binding: dict) -> str:
    import channel_core  # 지연 import — 계산 코어 로드 비용

    return channel_core.handle_message(text, binding)


async def handle_slack(scope, receive, send) -> None:
    """Slack Events API — url_verification + message 이벤트. 바인딩: 채널ID→테넌트."""
    if not (SLACK_SIGNING_SECRET and SLACK_BOT_TOKEN and SLACK_BINDINGS):
        await _json_response(send, 503, {"error": "slack_disabled"})
        return
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    body = await _read_body(receive)
    if not verify_slack_signature(
        body, headers.get("x-slack-request-timestamp", ""), headers.get("x-slack-signature", ""), SLACK_SIGNING_SECRET
    ):
        await _json_response(send, 401, {"error": "bad_signature"})
        return
    payload = json.loads(body or b"{}")
    if payload.get("type") == "url_verification":
        await _json_response(send, 200, {"challenge": payload.get("challenge", "")})
        return
    event = payload.get("event") or {}
    await _json_response(send, 200, {"ok": True})  # 3초 규칙 — 먼저 ACK
    if event.get("type") != "message" or event.get("bot_id") or event.get("subtype"):
        return
    binding = _load_channel_bindings(SLACK_BINDINGS).get(str(event.get("channel", "")))
    if not binding:
        return  # fail-closed
    reply = _channel_reply(event.get("text", ""), binding)
    request = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps({"channel": event["channel"], "text": reply[:3800]}).encode(),
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(request, timeout=15)
    except OSError:
        pass


async def handle_discord(scope, receive, send) -> None:
    """Discord Interactions — PING/PONG + /hr 슬래시 커맨드. 바인딩: 채널ID→테넌트."""
    if not (DISCORD_PUBLIC_KEY and DISCORD_BINDINGS):
        await _json_response(send, 503, {"error": "discord_disabled"})
        return
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    body = await _read_body(receive)
    try:
        from nacl.exceptions import BadSignatureError
        from nacl.signing import VerifyKey

        VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY)).verify(
            (headers.get("x-signature-timestamp", "")).encode() + body,
            bytes.fromhex(headers.get("x-signature-ed25519", "")),
        )
    except (BadSignatureError, ValueError, ImportError):
        await _json_response(send, 401, {"error": "bad_signature"})
        return
    payload = json.loads(body or b"{}")
    if payload.get("type") == 1:  # PING
        await _json_response(send, 200, {"type": 1})
        return
    if payload.get("type") == 2:  # 슬래시 커맨드
        binding = _load_channel_bindings(DISCORD_BINDINGS).get(str(payload.get("channel_id", "")))
        if not binding:
            await _json_response(send, 200, {"type": 4, "data": {"content": "이 채널은 아직 연결되지 않았습니다.", "flags": 64}})
            return
        options = (payload.get("data") or {}).get("options") or []
        text = str(options[0].get("value", "")) if options else "/help"
        reply = _channel_reply(text, binding)
        await _json_response(send, 200, {"type": 4, "data": {"content": reply[:1900]}})
        return
    await _json_response(send, 200, {"type": 1})


# ── 구글챗(Google Chat) 채널 엔드포인트 (env-gated — 키 없으면 503) ──────────
# 구글챗 HTTP 봇은 요청마다 Authorization: Bearer <JWT>를 보낸다.
#   issuer  = chat@system.gserviceaccount.com
#   audience= 프로젝트 번호(GOOGLECHAT_PROJECT_NUMBER)
#   서명    = RS256, 공개 x509 인증서는 아래 URL(주기적 로테이션)에서 제공.
# 동기 응답: 200 + {"text": ...} 를 반환하면 봇 메시지로 게시된다.
_GC_CERTS_URL = (
    "https://www.googleapis.com/service_accounts/v1/metadata/x509/chat@system.gserviceaccount.com"
)
_GC_ISSUER = "chat@system.gserviceaccount.com"
_gc_cert_cache: dict[str, Any] = {"certs": {}, "fetched_at": 0.0}


def _gc_public_certs() -> dict:
    """구글 x509 인증서 {kid: PEM} 조회. 1시간 캐시(로테이션 대비)."""
    import time as _time

    now = _time.time()
    if now - _gc_cert_cache["fetched_at"] > 3600 or not _gc_cert_cache["certs"]:
        with urllib.request.urlopen(_GC_CERTS_URL, timeout=10) as response:
            _gc_cert_cache["certs"] = json.load(response)
            _gc_cert_cache["fetched_at"] = now
    return _gc_cert_cache["certs"]


def verify_googlechat_jwt(token: str, project_number: str) -> bool:
    """구글챗 JWT 검증(RS256). 라이브러리·인증서 없거나 실패 시 False(fail-closed)."""
    if not token:
        return False
    try:
        import jwt  # PyJWT
        from cryptography.x509 import load_pem_x509_certificate

        certs = _gc_public_certs()
        kid = jwt.get_unverified_header(token).get("kid", "")
        pem = certs.get(kid)
        if not pem:
            claims = jwt.decode(token, options={"verify_signature": False})
            print(f"googlechat kid-miss: kid={kid[:12]} iss={claims.get('iss')} aud={claims.get('aud')}", flush=True)
            return False
        public_key = load_pem_x509_certificate(pem.encode()).public_key()
        jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=str(project_number),
            issuer=_GC_ISSUER,
        )
        return True
    except Exception as error:  # ImportError·서명불일치·만료·aud/iss 불일치 모두 거절
        # 토큰 원문은 절대 로깅하지 않는다 — 예외 유형·메시지만 (디버깅용)
        print(f"googlechat jwt reject: {type(error).__name__}: {error}", flush=True)
        return False


async def handle_googlechat(scope, receive, send) -> None:
    """Google Chat 이벤트 — ADDED_TO_SPACE 인사 + MESSAGE 응답. 바인딩: space.name→테넌트."""
    if not (GOOGLECHAT_PROJECT_NUMBER and GOOGLECHAT_BINDINGS):
        await _json_response(send, 503, {"error": "googlechat_disabled"})
        return
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    body = await _read_body(receive)
    auth = headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not bearer:
        # 디버깅: 헤더 '이름'만 로깅 (값 비로깅 — 토큰·쿠키 보호)
        print(f"googlechat no-bearer, header names: {sorted(headers.keys())}", flush=True)
    if not verify_googlechat_jwt(bearer, GOOGLECHAT_PROJECT_NUMBER):
        await _json_response(send, 401, {"error": "bad_signature"})
        return
    payload = json.loads(body or b"{}")
    event_type = payload.get("type")
    if event_type == "ADDED_TO_SPACE":
        await _json_response(send, 200, {"text": "안녕하세요, AI HR 담당자입니다. 노동법·HR 질문을 그대로 입력하세요. (/help 로 도움말)"})
        return
    if event_type != "MESSAGE":
        await _json_response(send, 200, {})
        return
    space = str((payload.get("space") or {}).get("name", ""))  # 예: spaces/AAAA
    binding = _load_channel_bindings(GOOGLECHAT_BINDINGS).get(space)
    if not binding:
        # 온보딩용: 미바인딩 스페이스 식별자를 로그에 남겨 바인딩 등록을 돕는다 (PII 없음)
        sender = str(((payload.get("message") or {}).get("sender") or {}).get("displayName", ""))
        print(f"googlechat unbound space: {space} (sender: {sender})", flush=True)
        await _json_response(send, 200, {"text": "이 대화는 아직 연결되지 않았습니다."})  # fail-closed
        return
    text = (payload.get("message") or {}).get("text", "")
    reply = _channel_reply(text, binding)
    await _json_response(send, 200, {"text": reply[:4000]})


# ── ASGI: Bearer 인증 미들웨어로 FastMCP streamable HTTP 앱을 감싼다 ──────────
_inner_app = mcp.streamable_http_app()


async def app(scope, receive, send):
    if scope["type"] != "http":
        await _inner_app(scope, receive, send)
        return
    path = scope.get("path", "")
    if "googlechat" in path:
        print(f"app() saw path={path!r} method={scope.get('method')}", flush=True)
    if path == "/signup":
        await handle_signup(scope, receive, send)
        return
    if path == "/slack/events":
        await handle_slack(scope, receive, send)
        return
    if path == "/discord/interactions":
        await handle_discord(scope, receive, send)
        return
    if path == "/googlechat/events":
        await handle_googlechat(scope, receive, send)
        return
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    auth = headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else None
    entry = resolve_token(bearer)
    if entry is None:
        body = json.dumps({"error": "invalid_token"}).encode()
        await send({"type": "http.response.start", "status": 401,
                    "headers": [(b"content-type", b"application/json"),
                                (b"www-authenticate", b"Bearer")]})
        await send({"type": "http.response.body", "body": body})
        return
    if not check_and_count_quota(_hash(bearer), int(entry.get("daily_limit", DEFAULT_DAILY_LIMIT))):
        await _json_response(send, 429, {"error": "daily_quota_exceeded",
                                         "message": "오늘의 사용 한도를 초과했습니다. 플랜을 확인하세요."})
        return
    record_usage(entry, scope.get("path", ""))
    token_ctx = _auth_context.set(entry)
    try:
        await _inner_app(scope, receive, send)
    finally:
        _auth_context.reset(token_ctx)
