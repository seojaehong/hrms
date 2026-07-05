"""소셜 로그인(구글·카카오) 순수 코어 — framework-free.

Social Login Key 문서 페이로드 생성과 카카오 사용자정보 정규화만 담당한다.
HTTP 호출·Frappe 접근은 social_login_api.py 가 수행한다.

카카오 유의점:
  - 이메일은 kakao_account.email 에 중첩돼 있어 Frappe 기본 custom provider
    핸들러(email 최상위 기대)로는 로그인 불가 → normalize_kakao_userinfo 로 평탄화.
  - 이메일 동의항목(account_email)이 꺼져 있으면 email 이 안 온다 — 명시 오류로 안내.
"""

from __future__ import annotations

from typing import Any

KAKAO_AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"
KAKAO_CALLBACK_PATH = "/api/method/hrms.regional.south_korea.social_login_api.kakao_callback"
GOOGLE_CALLBACK_PATH = "/api/method/frappe.integrations.oauth2_logins.login_via_google"

SUPPORTED_PROVIDERS = ("google", "kakao")


def _require_text(value: Any, fieldname: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{fieldname} is required")
	return value.strip()


def build_social_login_key_payload(provider: str, client_id: str, client_secret: str) -> dict[str, Any]:
	"""Social Login Key 문서 페이로드. provider: google | kakao."""
	if provider not in SUPPORTED_PROVIDERS:
		raise ValueError(f"unsupported provider: {provider!r} (supported: {', '.join(SUPPORTED_PROVIDERS)})")
	client_id = _require_text(client_id, "client_id")
	client_secret = _require_text(client_secret, "client_secret")

	if provider == "google":
		return {
			"doctype": "Social Login Key",
			"enable_social_login": 1,
			"social_login_provider": "Google",
			"client_id": client_id,
			"client_secret": client_secret,
		}

	return {
		"doctype": "Social Login Key",
		"enable_social_login": 1,
		"social_login_provider": "Custom",
		"provider_name": "kakao",
		"client_id": client_id,
		"client_secret": client_secret,
		"icon": "https://developers.kakao.com/favicon.ico",
		"base_url": "https://kauth.kakao.com",
		"authorize_url": KAKAO_AUTHORIZE_URL,
		"access_token_url": KAKAO_TOKEN_URL,
		"redirect_url": KAKAO_CALLBACK_PATH,
		"api_endpoint": KAKAO_USERINFO_URL,
		"auth_url_data": '{"response_type": "code", "scope": "account_email profile_nickname"}',
		"user_id_property": "id",
	}


def normalize_kakao_userinfo(payload: dict[str, Any]) -> dict[str, Any]:
	"""카카오 /v2/user/me 응답 → Frappe login_oauth_user 가 기대하는 평탄 구조.

	이메일 미제공(동의항목 꺼짐/미동의)은 명시 오류 — 침묵 실패 금지.
	"""
	if not isinstance(payload, dict):
		raise ValueError("kakao userinfo payload must be a dict")
	kakao_id = payload.get("id")
	if kakao_id in (None, ""):
		raise ValueError("kakao userinfo is missing id")

	account = payload.get("kakao_account") or {}
	if not isinstance(account, dict):
		raise ValueError("kakao_account must be a dict")
	email = account.get("email")
	if not isinstance(email, str) or not email.strip():
		raise ValueError(
			"kakao account did not return an email — 카카오 앱의 동의항목에서 "
			"카카오계정(이메일)을 필수 동의로 설정했는지 확인하세요"
		)

	profile = account.get("profile") or {}
	nickname = profile.get("nickname") if isinstance(profile, dict) else None
	picture = profile.get("profile_image_url") if isinstance(profile, dict) else None

	info: dict[str, Any] = {
		"id": str(kakao_id),
		"email": email.strip(),
		"first_name": nickname or email.split("@", 1)[0],
	}
	if picture:
		info["picture"] = picture
	return info
