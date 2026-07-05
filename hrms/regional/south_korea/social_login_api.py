"""Frappe whitelist API — 소셜 로그인 설정·카카오 콜백.

내부 로직은 social_login.py(순수 코어)에 위임한다.
테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import한다.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

try:
	import frappe as _frappe  # noqa: PLC0415

	_FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
	_frappe = None  # type: ignore[assignment]
	_FRAPPE_AVAILABLE = False


def _whitelist(fn=None, **kwargs):
	if _FRAPPE_AVAILABLE and _frappe is not None:
		decorator = _frappe.whitelist(**kwargs)
		return decorator(fn) if fn else decorator
	if fn:
		return fn
	return lambda f: f


import importlib.util as _ilu
import pathlib as _pl

_CORE_PATH = _pl.Path(__file__).resolve().parent / "social_login.py"
_spec = _ilu.spec_from_file_location("korea_social_login_core", _CORE_PATH)
_core = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_core)


def setup_social_login(provider: str, client_id: str, client_secret: str) -> dict[str, Any]:
	"""사이트에 Social Login Key 생성/갱신. bench execute 로 호출 (프로비저닝 자동화).

	사용: bench --site <site> execute \
	  hrms.regional.south_korea.social_login_api.setup_social_login \
	  --kwargs "{'provider': 'kakao', 'client_id': '...', 'client_secret': '...'}"
	"""
	payload = _core.build_social_login_key_payload(provider, client_id, client_secret)
	if not (_FRAPPE_AVAILABLE and _frappe is not None):
		return {"status": "dry-run", "payload_keys": sorted(payload)}

	name = "google" if provider == "google" else "kakao"
	if _frappe.db.exists("Social Login Key", name):
		doc = _frappe.get_doc("Social Login Key", name)
		doc.update(payload)
	else:
		doc = _frappe.get_doc(payload)
	doc.save(ignore_permissions=True)
	_frappe.db.commit()
	return {"status": "ok", "provider": provider, "name": doc.name}


def _exchange_kakao_token(code: str, client_id: str, client_secret: str, redirect_uri: str) -> str:
	body = urllib.parse.urlencode(
		{
			"grant_type": "authorization_code",
			"client_id": client_id,
			"client_secret": client_secret,
			"redirect_uri": redirect_uri,
			"code": code,
		}
	).encode()
	request = urllib.request.Request(
		_core.KAKAO_TOKEN_URL,
		data=body,
		headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
	)
	with urllib.request.urlopen(request, timeout=15) as response:
		token = json.load(response)
	access_token = token.get("access_token")
	if not access_token:
		raise ValueError(f"kakao token exchange failed: {token.get('error_description') or token}")
	return access_token


def _fetch_kakao_userinfo(access_token: str) -> dict[str, Any]:
	request = urllib.request.Request(
		_core.KAKAO_USERINFO_URL,
		headers={"Authorization": f"Bearer {access_token}"},
	)
	with urllib.request.urlopen(request, timeout=15) as response:
		return json.load(response)


@_whitelist(allow_guest=True)
def kakao_callback(code: str | None = None, state: str | None = None, **_ignored) -> None:
	"""카카오 OAuth 콜백 — 토큰 교환 → 사용자정보 평탄화 → Frappe 소셜 로그인.

	Frappe 기본 custom 핸들러는 이메일 중첩(kakao_account.email)을 못 읽으므로
	이 전용 콜백이 normalize_kakao_userinfo 로 평탄화한 뒤 login_oauth_user 에 넘긴다.
	"""
	if not (_FRAPPE_AVAILABLE and _frappe is not None):
		raise RuntimeError("kakao_callback requires a running Frappe site")
	if not code:
		_frappe.throw("missing authorization code")

	from frappe.utils.oauth import login_oauth_user  # noqa: PLC0415

	key = _frappe.get_doc("Social Login Key", "kakao")
	redirect_uri = _frappe.utils.get_url(_core.KAKAO_CALLBACK_PATH)
	access_token = _exchange_kakao_token(
		code, key.client_id, key.get_password("client_secret"), redirect_uri
	)
	info = _core.normalize_kakao_userinfo(_fetch_kakao_userinfo(access_token))
	login_oauth_user(info, provider="kakao", state=state)
