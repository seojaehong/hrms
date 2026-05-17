#!/usr/bin/env python3
"""
cloudflare_dns_add.py — safeclaw.kr 존에 테넌트 CNAME 레코드 추가

사용법:
    python scripts/provisioning/cloudflare_dns_add.py <tenant_id> <tunnel_id>

    tenant_id  : 테넌트 식별자. CNAME name = {tenant_id}.hrms.safeclaw.kr
    tunnel_id  : Cloudflare tunnel UUID. CNAME target = {tunnel_id}.cfargotunnel.com

환경변수:
    CLOUDFLARE_API_TOKEN  (필수) — Zone:DNS:Edit 권한, safeclaw.kr 스코프
    CLOUDFLARE_ZONE_NAME  (선택, 기본값: safeclaw.kr)

종료 코드:
    0 — 성공 (신규 생성 또는 레코드 이미 존재)
    1 — 오류 (환경변수 미설정, 존 조회 실패, API 오류)
"""

import json
import os
import sys
import urllib.error
import urllib.request


ZONE_NAME_DEFAULT = "safeclaw.kr"
CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"


def _cf_request(method: str, path: str, token: str, body: dict | None = None) -> dict:
    """Cloudflare API 요청 헬퍼. urllib만 사용 (외부 의존성 없음)."""
    url = f"{CLOUDFLARE_API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw.decode(errors="replace")}
        # 422 / 400 "record already exists" — treat as success
        if exc.code in (400, 422):
            errors = payload.get("errors", [])
            if any("already exists" in str(e) for e in errors):
                print(f"  [info] DNS 레코드 이미 존재 — 멱등 처리 (HTTP {exc.code})")
                return {"success": True, "idempotent": True}
        raise RuntimeError(
            f"Cloudflare API {method} {path} → HTTP {exc.code}: {payload}"
        ) from exc


def get_zone_id(token: str, zone_name: str) -> str:
    resp = _cf_request("GET", f"/zones?name={zone_name}&status=active", token)
    if not resp.get("success"):
        raise RuntimeError(f"존 조회 실패: {resp.get('errors')}")
    result = resp.get("result", [])
    if not result:
        raise RuntimeError(f"존을 찾을 수 없습니다: {zone_name}")
    return result[0]["id"]


def add_cname(token: str, zone_id: str, name: str, target: str) -> dict:
    """CNAME 레코드 생성. 이미 존재하면 멱등 성공 반환."""
    body = {
        "type": "CNAME",
        "name": name,
        "content": target,
        "ttl": 1,       # 1 = Auto (Cloudflare proxied TTL)
        "proxied": True,
    }
    return _cf_request("POST", f"/zones/{zone_id}/dns_records", token, body)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"사용법: {argv[0]} <tenant_id> <tunnel_id>", file=sys.stderr)
        return 1

    tenant_id = argv[1].strip().lower()
    tunnel_id = argv[2].strip()

    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not token:
        print("[오류] CLOUDFLARE_API_TOKEN 환경변수가 설정되어 있지 않습니다.", file=sys.stderr)
        return 1

    zone_name = os.environ.get("CLOUDFLARE_ZONE_NAME", ZONE_NAME_DEFAULT)

    cname_name = f"{tenant_id}.hrms.{zone_name}"
    cname_target = f"{tunnel_id}.cfargotunnel.com"

    print(f"[Cloudflare DNS] {cname_name} → {cname_target}")

    try:
        print(f"  존 조회 중: {zone_name}")
        zone_id = get_zone_id(token, zone_name)
        print(f"  zone_id: {zone_id}")

        print(f"  CNAME 레코드 추가 중...")
        result = add_cname(token, zone_id, cname_name, cname_target)

        if result.get("success"):
            if result.get("idempotent"):
                print(f"  [OK] 기존 레코드 확인 완료 (변경 없음)")
            else:
                record_id = result.get("result", {}).get("id", "unknown")
                print(f"  [OK] CNAME 생성 완료. record_id={record_id}")
            return 0
        else:
            print(f"  [오류] API 응답 실패: {result.get('errors')}", file=sys.stderr)
            return 1
    except RuntimeError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
