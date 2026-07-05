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
    "Employee": ["name", "employee_name", "company", "date_of_joining", "status", "department", "designation"],
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
    url = f"{FRAPPE_BASE_URL}/api/resource/{urllib.parse.quote(doctype)}?{urllib.parse.urlencode(params)}"
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
def whoami() -> dict:
    """현재 토큰의 테넌트 바인딩 확인 (사이트·라벨)."""
    ctx = _auth_context.get()
    if not ctx:
        return {"authenticated": False}
    return {"authenticated": True, "site": ctx["site"], "label": ctx.get("label", "")}


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
EMAIL_RE = __import__("re").compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


async def _read_body(receive) -> bytes:
    chunks = []
    while True:
        message = await receive()
        chunks.append(message.get("body", b""))
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
        payload = json.loads((await _read_body(receive)) or b"{}")
        entry = validate_signup(payload)
    except (ValueError, json.JSONDecodeError) as error:
        await _json_response(send, 400, {"error": str(error)})
        return
    # 중복 방지: 큐 + 레지스트리에 같은 tenant_id가 있으면 거절
    queue_path = pathlib.Path(SIGNUP_QUEUE)
    existing = ""
    if queue_path.exists():
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


# ── ASGI: Bearer 인증 미들웨어로 FastMCP streamable HTTP 앱을 감싼다 ──────────
_inner_app = mcp.streamable_http_app()


async def app(scope, receive, send):
    if scope["type"] != "http":
        await _inner_app(scope, receive, send)
        return
    if scope.get("path", "") == "/signup":
        await handle_signup(scope, receive, send)
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
    record_usage(entry, scope.get("path", ""))
    token_ctx = _auth_context.set(entry)
    try:
        await _inner_app(scope, receive, send)
    finally:
        _auth_context.reset(token_ctx)
