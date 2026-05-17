"""카카오 알림톡 발송 path — solapi HTTP 또는 dry-run.

환경변수:
  SOLAPI_API_KEY    — Solapi API Key
  SOLAPI_API_SECRET — Solapi API Secret

키가 없으면 자동으로 dry-run 모드(로그만).
human_approved=False 이면 발송 없이 fail-closed 반환.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
	pass

SOLAPI_BASE_URL = "https://api.solapi.com"
SOLAPI_SEND_PATH = "/messages/v4/send"
KAKAO_API_KEY_ENV = "SOLAPI_API_KEY"
KAKAO_API_SECRET_ENV = "SOLAPI_API_SECRET"

TEMPLATE_VAR_PATTERN = re.compile(r"#\{(\w+)\}")

CONTRACT_TYPE = "korea_kakao_alimtalk_send_v1"
RUNTIME_ACTION = "kakao_alimtalk_send"


# ---------------------------------------------------------------------------
# 자격증명
# ---------------------------------------------------------------------------


def get_kakao_credentials() -> dict[str, str] | None:
	"""환경변수 또는 Frappe site config에서 Solapi 자격증명 조회.

	Returns:
		{"api_key": str, "api_secret": str} 또는 None
	"""
	api_key = os.environ.get(KAKAO_API_KEY_ENV, "").strip()
	api_secret = os.environ.get(KAKAO_API_SECRET_ENV, "").strip()

	if api_key and api_secret:
		return {"api_key": api_key, "api_secret": api_secret}

	# Frappe site config fallback (frappe 없는 환경에서는 건너뜀)
	try:
		import frappe  # noqa: PLC0415

		site_api_key = (getattr(frappe.conf, "solapi_api_key", None) or "").strip()
		site_api_secret = (getattr(frappe.conf, "solapi_api_secret", None) or "").strip()
		if site_api_key and site_api_secret:
			return {"api_key": site_api_key, "api_secret": site_api_secret}
	except Exception:
		pass

	return None


# ---------------------------------------------------------------------------
# 핵심 발송 함수
# ---------------------------------------------------------------------------


def send_kakao_alimtalk(
	*,
	pf_id: str,
	template_id: str,
	to: str,
	template_variables: dict[str, str],
	human_approved: bool,
	dry_run: bool = False,
	_transport: Callable[[str, dict, bytes], dict] | None = None,
) -> dict[str, Any]:
	"""카카오 알림톡 발송.

	human_approved=False → fail-closed (발송 없이 즉시 반환)
	credentials 없으면 dry_run=True 자동 적용
	실제 발송 시 Solapi POST 호출

	Args:
		pf_id: 발신 프로필 ID (카카오 비즈니스 채널)
		template_id: 알림톡 템플릿 ID (사전 등록 필수)
		to: 수신자 휴대폰 번호 (예: "01012345678")
		template_variables: 템플릿 변수 딕셔너리 {"employee_name": "홍길동", ...}
		human_approved: True 일 때만 실제 발송. False → fail-closed
		dry_run: True 이면 실제 발송 없이 preview만 반환
		_transport: 테스트용 HTTP transport 주입. None 이면 실제 urllib 사용

	Returns:
		{
			"contract_type": "korea_kakao_alimtalk_send_v1",
			"runtime_action": "kakao_alimtalk_send",
			"sent": bool,
			"dry_run": bool,
			"message_id": str | None,
			"to": str,
			"template_id": str,
			"human_approval_verified": bool,
			"reason": str | None,
		}
	"""
	base_result: dict[str, Any] = {
		"contract_type": CONTRACT_TYPE,
		"runtime_action": RUNTIME_ACTION,
		"sent": False,
		"dry_run": dry_run,
		"message_id": None,
		"to": to,
		"template_id": template_id,
		"human_approval_verified": human_approved,
		"reason": None,
	}

	# fail-closed: human_approved 미충족
	if not human_approved:
		base_result["reason"] = "human_approval_required"
		_log_info(
			f"[KakaoAlimtalk] fail-closed: human_approved=False, template={template_id}, to={to}"
		)
		return base_result

	# credentials 확인 → 없으면 dry_run 자동
	credentials = get_kakao_credentials()
	if not credentials:
		dry_run = True
		base_result["dry_run"] = True
		base_result["reason"] = "no_credentials_dry_run"
		_log_info(
			f"[KakaoAlimtalk] dry-run (no credentials): template={template_id}, to={to}"
		)

	if dry_run:
		# 템플릿 변수 치환 검증만 수행 (발송 X)
		rendered = _render_template_content(template_id, template_variables)
		base_result["sent"] = False
		base_result["dry_run"] = True
		if base_result["reason"] is None:
			base_result["reason"] = "dry_run_requested"
		_log_info(
			f"[KakaoAlimtalk] dry-run preview: template={template_id}, rendered_length={len(rendered)}"
		)
		return base_result

	# 실제 발송
	try:
		response = _call_solapi_send(
			api_key=credentials["api_key"],
			api_secret=credentials["api_secret"],
			pf_id=pf_id,
			template_id=template_id,
			to=to,
			template_variables=template_variables,
			transport=_transport,
		)
		message_id = _extract_message_id(response)
		base_result["sent"] = True
		base_result["message_id"] = message_id
		_log_info(
			f"[KakaoAlimtalk] sent: template={template_id}, to={to}, message_id={message_id}"
		)
	except Exception as exc:
		base_result["sent"] = False
		base_result["reason"] = f"send_error: {exc}"
		_log_error(f"[KakaoAlimtalk] send failed: template={template_id}, to={to}, error={exc}")

	return base_result


# ---------------------------------------------------------------------------
# Preview 함수
# ---------------------------------------------------------------------------


def preview_kakao_alimtalk(
	*,
	pf_id: str,
	template_id: str,
	to: str,
	template_variables: dict[str, str],
) -> dict[str, Any]:
	"""발송 전 preview. 실제 발송 없이 템플릿 변수 치환 결과만 반환.

	Returns:
		{
			"contract_type": "korea_kakao_alimtalk_send_v1",
			"runtime_action": "kakao_alimtalk_preview",
			"pf_id": str,
			"template_id": str,
			"to": str,
			"rendered_content": str,
			"missing_variables": list[str],
			"template_variables": dict,
		}
	"""
	rendered = _render_template_content(template_id, template_variables)
	missing = _find_missing_variables(rendered, template_variables)

	return {
		"contract_type": CONTRACT_TYPE,
		"runtime_action": "kakao_alimtalk_preview",
		"pf_id": pf_id,
		"template_id": template_id,
		"to": to,
		"rendered_content": rendered,
		"missing_variables": missing,
		"template_variables": template_variables,
	}


# ---------------------------------------------------------------------------
# 템플릿 목록 조회
# ---------------------------------------------------------------------------


def list_alimtalk_templates() -> list[dict[str, Any]]:
	"""등록된 표준 템플릿 카탈로그 반환.

	credentials 있을 때 Solapi 실제 조회를 시도하지만,
	없거나 실패 시에는 로컬 카탈로그(kakao_alimtalk_templates.json)를 반환.
	"""
	import pathlib  # noqa: PLC0415

	catalog_path = pathlib.Path(__file__).parent / "data" / "kakao_alimtalk_templates.json"
	try:
		with open(catalog_path, encoding="utf-8") as f:
			return json.load(f)
	except Exception as exc:
		_log_error(f"[KakaoAlimtalk] Failed to load template catalog: {exc}")
		return []


# ---------------------------------------------------------------------------
# 내부 헬퍼 — Solapi HTTP
# ---------------------------------------------------------------------------


def _build_solapi_auth_header(api_key: str, api_secret: str) -> str:
	"""Solapi HMAC-SHA256 인증 헤더 생성."""
	date_str = _iso_now()
	salt = uuid.uuid4().hex
	signature_text = f"{date_str}{salt}"
	signature = hmac.new(
		api_secret.encode("utf-8"),
		signature_text.encode("utf-8"),
		hashlib.sha256,
	).hexdigest()
	return f'HMAC-SHA256 apiKey={api_key}, date={date_str}, salt={salt}, signature={signature}'


def _iso_now() -> str:
	"""현재 시각 ISO-8601 문자열 (UTC)."""
	t = time.gmtime()
	return (
		f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}T"
		f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}Z"
	)


def _build_solapi_payload(
	pf_id: str,
	template_id: str,
	to: str,
	template_variables: dict[str, str],
) -> bytes:
	"""Solapi /messages/v4/send 요청 바디 생성."""
	body = {
		"message": {
			"to": to,
			"from": pf_id,
			"kakaoOptions": {
				"pfId": pf_id,
				"templateId": template_id,
				"variables": template_variables,
			},
		}
	}
	return json.dumps(body, ensure_ascii=False).encode("utf-8")


def _call_solapi_send(
	*,
	api_key: str,
	api_secret: str,
	pf_id: str,
	template_id: str,
	to: str,
	template_variables: dict[str, str],
	transport: Callable[[str, dict, bytes], dict] | None = None,
) -> dict[str, Any]:
	"""Solapi POST 실행 또는 주입된 transport 사용."""
	url = f"{SOLAPI_BASE_URL}{SOLAPI_SEND_PATH}"
	auth_header = _build_solapi_auth_header(api_key, api_secret)
	headers = {
		"Authorization": auth_header,
		"Content-Type": "application/json; charset=utf-8",
	}
	body = _build_solapi_payload(pf_id, template_id, to, template_variables)

	if transport is not None:
		return transport(url, headers, body)

	return _default_http_transport(url, headers, body)


def _default_http_transport(url: str, headers: dict[str, str], body: bytes) -> dict[str, Any]:
	"""실제 urllib HTTP POST."""
	req = urllib.request.Request(url, data=body, headers=headers, method="POST")
	try:
		with urllib.request.urlopen(req, timeout=10) as resp:
			raw = resp.read()
			return json.loads(raw.decode("utf-8"))
	except urllib.error.HTTPError as exc:
		raw = exc.read()
		try:
			data = json.loads(raw.decode("utf-8"))
		except Exception:
			data = {"raw": raw.decode("utf-8", errors="replace")}
		raise RuntimeError(f"Solapi HTTP {exc.code}: {data}") from exc


def _extract_message_id(response: dict[str, Any]) -> str | None:
	"""Solapi 응답에서 messageId 추출."""
	# Solapi v4 응답 구조: {"messageId": "...", ...} 또는 {"result": [{"messageId": "..."}]}
	if isinstance(response, dict):
		if "messageId" in response:
			return str(response["messageId"])
		result_list = response.get("result") or []
		if result_list and isinstance(result_list, list):
			first = result_list[0]
			if isinstance(first, dict) and "messageId" in first:
				return str(first["messageId"])
	return None


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 템플릿 처리
# ---------------------------------------------------------------------------


def _render_template_content(template_id: str, variables: dict[str, str]) -> str:
	"""카탈로그에서 템플릿 본문을 찾아 #{var} 치환."""
	templates = list_alimtalk_templates()
	content = ""
	for tmpl in templates:
		if tmpl.get("template_id") == template_id:
			content = tmpl.get("content", "")
			break

	if not content:
		# 템플릿을 찾지 못하면 변수 딕셔너리를 직렬화해 반환 (디버그용)
		content = f"[template:{template_id}] " + " ".join(f"#{{{k}}}={v}" for k, v in variables.items())

	def replace_var(match: re.Match) -> str:
		key = match.group(1)
		return str(variables.get(key, f"#{{{key}}}"))

	return TEMPLATE_VAR_PATTERN.sub(replace_var, content)


def _find_missing_variables(rendered: str, variables: dict[str, str]) -> list[str]:
	"""치환 후에도 남아 있는 #{...} 패턴 = 미입력 변수 목록."""
	remaining = TEMPLATE_VAR_PATTERN.findall(rendered)
	return [v for v in remaining if v not in variables]


# ---------------------------------------------------------------------------
# 로깅 헬퍼 (frappe 없어도 동작)
# ---------------------------------------------------------------------------


def _log_info(message: str) -> None:
	try:
		import frappe  # noqa: PLC0415

		frappe.logger("kakao_alimtalk").info(message)
	except Exception:
		pass


def _log_error(message: str) -> None:
	try:
		import frappe  # noqa: PLC0415

		frappe.log_error(message, "KakaoAlimtalk")
	except Exception:
		pass


def build_kakao_template_payload(
	*,
	recipient_phone: str,
	template_code: str,
	variables: dict[str, str],
) -> dict[str, Any]:
	"""Phase 2-A wage_statement_kakao 호환 — 표준 payload dict 빌더.

	실제 발송 X, payload 형식만 준비. send_kakao_alimtalk()의 입력으로 사용 가능.
	"""
	return {
		"to": recipient_phone,
		"template_id": template_code,
		"template_variables": dict(variables),
	}


def build_kakao_send_queue_item(
	*,
	payload: dict[str, Any],
	recipient_consent: bool,
	opted_out: bool = False,
	scheduled_at: str | None = None,
	provider_key: str = "solapi",
	max_attempts: int = 3,
) -> dict[str, Any]:
	"""Phase 2-A wage_statement_kakao 호환 — 발송 큐 아이템 빌더.

	실제 dispatch X. 큐에 넣을 dict만 준비.
	"""
	to = (payload or {}).get("to", "")
	if not _validate_phone(to):
		raise ValueError(f"invalid recipient phone: {to}")
	if not recipient_consent:
		raise ValueError("recipient consent required")
	if opted_out:
		raise ValueError("recipient opted out")
	return {
		"contract_type": "korea_kakao_send_queue_item_v1",
		"runtime_action": "kakao_send_queue_enqueue",
		"payload": dict(payload),
		"recipient_consent": True,
		"opted_out": False,
		"scheduled_at": scheduled_at,
		"provider_key": provider_key,
		"max_attempts": int(max_attempts),
	}


def _validate_phone(phone: str) -> bool:
	if not phone:
		return False
	digits = "".join(ch for ch in str(phone) if ch.isdigit())
	return 9 <= len(digits) <= 11
