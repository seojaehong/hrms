# Korea HRMS AI 플레인 토큰 발급 — 평문은 stdout 1회, 파일에는 sha256만.
#
# 사용: python3 mcp_server/issue_token.py <site> <label> [--api-key K --api-secret S]
#   api key/secret 은 해당 사이트의 Frappe API 자격 (브리지 도구용).
#   생략하면 계산 도구 전용 토큰(테넌트 데이터 접근 불가)이 된다.
# 파일 경로: env KCHRMS_MCP_TOKENS_FILE (기본 /etc/korea-hrms-mcp/tokens.json)

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import secrets
import sys

parser = argparse.ArgumentParser()
parser.add_argument("site")
parser.add_argument("label")
parser.add_argument("--api-key", default=None)
parser.add_argument("--api-secret", default=None)
parser.add_argument("--plan", default=None, help="starter|professional|enterprise — 일일 쿼터 자동 설정")
parser.add_argument("--frappe-url", default=None, help="사이트가 있는 bench 호스트 (샤딩용, 기본 로컬)")
args = parser.parse_args()

tokens_file = pathlib.Path(os.environ.get("KCHRMS_MCP_TOKENS_FILE", "/etc/korea-hrms-mcp/tokens.json"))
tokens: dict = {}
if tokens_file.exists():
    tokens = json.loads(tokens_file.read_text(encoding="utf-8"))

token = f"khrms_{secrets.token_urlsafe(32)}"
entry = {"site": args.site, "label": args.label, "disabled": False}
if args.api_key and args.api_secret:
    entry["api_key"] = args.api_key
    entry["api_secret"] = args.api_secret
if args.plan:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from plans import plan_daily_limit

    entry["plan"] = args.plan
    entry["daily_limit"] = plan_daily_limit(args.plan)
if args.frappe_url:
    entry["frappe_url"] = args.frappe_url
tokens[hashlib.sha256(token.encode()).hexdigest()] = entry

tokens_file.parent.mkdir(parents=True, exist_ok=True)
tokens_file.write_text(json.dumps(tokens, indent=1, ensure_ascii=False), encoding="utf-8")
os.chmod(tokens_file, 0o600)

print(f"Issued token for site={args.site} label={args.label}", file=sys.stderr)
print("Plaintext token below — copy now, NOT recoverable:", file=sys.stderr)
print(token)
