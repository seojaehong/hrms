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
	recipient_phone은 숫자만 남겨서 정규화합니다.
	"""
	# Normalize phone to digits-only and validate
	normalized_phone = "".join(ch for ch in str(recipient_phone) if ch.isdigit())
	if not _validate_phone(normalized_phone):
		raise ValueError(f"invalid recipient phone: {recipient_phone!r}")
	return {
		"recipient_phone": normalized_phone,
		"template_code": template_code,
		"variables": dict(variables),
		"channel": "kakao_alimtalk",
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
	to = (payload or {}).get("recipient_phone", "") or (payload or {}).get("to", "")
	if not _validate_phone(to):
		raise ValueError(f"invalid recipient phone: {to}")
	if not recipient_consent:
		raise ValueError("recipient_consent is required")
	if opted_out:
		raise ValueError("recipient has opted out")
	# Strict integer validation for max_attempts
	if not isinstance(max_attempts, int) or isinstance(max_attempts, bool):
		raise ValueError("max_attempts must be an integer")
	# Validate provider_key does not contain phone numbers (PII guard)
	if _key_contains_phone_number(provider_key):
		raise ValueError(f"provider_key must not contain phone numbers: {provider_key!r}")
	# Validate scheduled_at has timezone info if provided
	if scheduled_at is not None and isinstance(scheduled_at, str):
		if "+" not in scheduled_at and "Z" not in scheduled_at and "-" not in scheduled_at[10:]:
			raise ValueError(f"scheduled_at must include timezone: {scheduled_at!r}")
	# dedupe key: kakao:<uuid> — must NOT expose template code or phone (PII guard)
	dedupe_key = f"kakao:{uuid.uuid4().hex[:16]}"
	return {
		"queue_type": "korea_kakao_send_queue_v1",
		"contract_type": "korea_kakao_send_queue_item_v1",
		"runtime_action": "kakao_send_queue_enqueue",
		"status": "queued",
		"attempt_count": 0,
		"dedupe_key": dedupe_key,
		"next_attempt_at": scheduled_at,
		"payload": dict(payload),
		"recipient_consent": True,
		"opted_out": False,
		"scheduled_at": scheduled_at,
		"provider_key": provider_key,
		"max_attempts": max_attempts,
	}


def render_kakao_preview(template_str: str, variables: dict[str, str]) -> str:
	"""템플릿 문자열의 변수를 치환하여 미리보기 반환. 변수 누락 시 ValueError."""
	import re as _re
	_VAR_PAT = _re.compile(r"\{\{(\w+)\}\}")
	required = set(_VAR_PAT.findall(template_str))
	missing = required - set(variables.keys())
	if missing:
		raise ValueError(f"missing template variables: {sorted(missing)}")
	result = template_str
	for k, v in variables.items():
		result = result.replace(f"{{{{{k}}}}}", str(v))
	return result


def build_kakao_template_registry_entry(
	*,
	template_code: str,
	template_name: str,
	template_body: str,
	required_variables: list[str],
	consent_purpose: str,
	provider_template_keys: dict[str, str] | None = None,
	active: bool = True,
) -> dict[str, Any]:
	"""Phase 2-A 카카오 템플릿 레지스트리 엔트리 빌더."""
	import re as _re
	if not isinstance(active, bool):
		raise TypeError("active must be a bool")
	if not template_body or not template_body.strip():
		raise ValueError("template_body is required")
	# Validate body variables match required_variables
	_VAR_PAT = _re.compile(r"\{\{(\w+)\}\}")
	body_vars = set(_VAR_PAT.findall(template_body))
	required_set = set(required_variables)
	if body_vars != required_set:
		raise ValueError("required_variables must match body variables")
	# Validate provider_template_keys don't contain phone numbers
	if provider_template_keys:
		for k, v in provider_template_keys.items():
			k_digits = "".join(ch for ch in str(k) if ch.isdigit())
			v_digits = "".join(ch for ch in str(v) if ch.isdigit())
			if len(k_digits) >= 9 or len(v_digits) >= 9:
				raise ValueError("provider_template_keys must not contain phone numbers")
	return {
		"registry_type": "korea_kakao_template_registry_v1",
		"channel": "kakao_alimtalk",
		"template_code": template_code,
		"template_name": template_name,
		"template_body": template_body.strip(),
		"required_variables": sorted(required_variables),
		"consent_purpose": consent_purpose,
		"provider_template_keys": dict(provider_template_keys) if provider_template_keys else {},
		"active": active,
		"requires_runtime_send": False,
	}


def build_registered_kakao_template_payload(
	*,
	recipient_phone: str,
	template_registry_entry: dict[str, Any],
	variables: dict[str, str],
) -> dict[str, Any]:
	"""Phase 2-A 등록된 템플릿 레지스트리 엔트리를 이용해 payload 빌더.

	- active 플래그 검사
	- required_variables 만 추출 (extra variables 무시)
	- preview_text 렌더링
	"""
	import re as _re
	# Validate active flag type
	active = template_registry_entry.get("active")
	if not isinstance(active, bool):
		raise TypeError("template_registry_entry.active must be a bool")
	if not active:
		raise ValueError("template registry entry is inactive")
	# Normalize phone
	normalized_phone = "".join(ch for ch in str(recipient_phone) if ch.isdigit())
	if not _validate_phone(normalized_phone):
		raise ValueError(f"invalid recipient phone: {recipient_phone!r}")
	required_variables = template_registry_entry.get("required_variables", [])
	# Check all required variables are provided
	missing = [v for v in required_variables if v not in variables]
	if missing:
		raise ValueError(f"missing template variables: {', '.join(sorted(missing))}")
	# Extract only required variables (ignore extras)
	filtered_vars = {k: variables[k] for k in required_variables}
	# Render preview text
	template_body = template_registry_entry.get("template_body", "")
	_VAR_PAT = _re.compile(r"\{\{(\w+)\}\}")
	preview_text = _VAR_PAT.sub(lambda m: str(filtered_vars.get(m.group(1), f"{{{{{m.group(1)}}}}}")), template_body)
	return {
		"recipient_phone": normalized_phone,
		"template_code": template_registry_entry.get("template_code", ""),
		"variables": filtered_vars,
		"channel": "kakao_alimtalk",
		"consent_purpose": template_registry_entry.get("consent_purpose", ""),
		"preview_text": preview_text,
	}


def build_kakao_provider_dispatch_request(
	*,
	queue_item: dict[str, Any],
	provider: dict[str, Any],
	requested_at: str,
) -> dict[str, Any]:
	"""Phase 2-A 카카오 provider dispatch request 빌더 (실제 발송 없음)."""
	import copy as _copy
	ALLOWED_PROVIDER_TYPES = ("partner_api", "direct_api", "aggregator_api")
	# Strict integer validation for queue_item counters
	for field in ("attempt_count", "max_attempts"):
		val = queue_item.get(field)
		if val is not None and (not isinstance(val, int) or isinstance(val, bool)):
			raise ValueError(f"queue_item.{field} must be an integer")
	provider_key = provider.get("provider_key", "")
	if _key_contains_phone_number(provider_key):
		raise ValueError(f"provider.provider_key must not contain phone numbers: {provider_key!r}")
	provider_type = provider.get("provider_type", "")
	if provider_type not in ALLOWED_PROVIDER_TYPES:
		raise ValueError(f"provider_type must be one of {ALLOWED_PROVIDER_TYPES}: {provider_type!r}")
	queue_provider = queue_item.get("provider_key", "")
	if provider_key and queue_provider and provider_key != queue_provider:
		raise ValueError(f"provider.provider_key must match queue_item.provider_key: {provider_key!r} != {queue_provider!r}")
	endpoint_key = provider.get("endpoint_key", "")
	if _key_contains_phone_number(endpoint_key):
		raise ValueError(f"provider.endpoint_key must not contain phone numbers: {endpoint_key!r}")
	payload = queue_item.get("payload", {})
	if not isinstance(payload, dict):
		raise TypeError("queue_item.payload must be a dict")
	dispatch_id = f"kakao-dispatch:{uuid.uuid4().hex[:16]}"
	return {
		"request_type": "korea_kakao_provider_dispatch_v1",
		"runtime_action": "send_via_provider",
		"requires_runtime_send": True,
		"provider_key": provider_key,
		"provider_type": provider_type,
		"endpoint_key": endpoint_key,
		"attempt_number": queue_item.get("attempt_count", 0) + 1,
		"payload": _copy.deepcopy(payload),
		"dispatch_request_id": dispatch_id,
		"requested_at": requested_at,
	}


def build_kakao_delivery_audit_event(
	*,
	queue_item: dict[str, Any],
	attempted_at: str,
	provider_status: str,
	provider_message_id: str | None = None,
	error_code: str | None = None,
	base_retry_delay_seconds: int = 60,
	max_retry_delay_seconds: int = 3600,
) -> dict[str, Any]:
	"""Phase 2-A 카카오 delivery audit event 빌더 (실제 발송 없음).

	provider_status: "delivered" | "retryable_error" | "permanent_error"
	"""
	import re as _re
	import copy as _copy
	# Strict integer validation for retry controls
	for field, val in (("base_retry_delay_seconds", base_retry_delay_seconds), ("max_retry_delay_seconds", max_retry_delay_seconds)):
		if not isinstance(val, int) or isinstance(val, bool):
			raise ValueError(f"{field} must be an integer")
	# Strict integer validation for queue_item counters
	for field in ("attempt_count", "max_attempts"):
		val = queue_item.get(field)
		if val is not None and (not isinstance(val, int) or isinstance(val, bool)):
			raise ValueError(f"queue_item.{field} must be an integer")
	# Timezone validation
	has_tz = "+" in attempted_at or "Z" in attempted_at or bool(_re.search(r"T\d\d:\d\d:\d\d-\d\d", attempted_at))
	if not has_tz:
		raise ValueError("attempted_at must include timezone")
	# Validate phone not in provider_key
	provider_key = queue_item.get("provider_key", "")
	if _key_contains_phone_number(provider_key):
		raise ValueError(f"queue_item.provider_key must not contain phone numbers: {provider_key!r}")
	attempt_count = queue_item.get("attempt_count", 0)
	# Compute next_retry_at for retryable statuses (exponential backoff)
	RETRYABLE_STATUSES = ("retryable_error", "timeout")
	next_retry_at = None
	if provider_status in RETRYABLE_STATUSES:
		# Exponential backoff: min(base * 2^attempt_count, max)
		try:
			import datetime as _dt
			delay = min(base_retry_delay_seconds * (2 ** attempt_count), max_retry_delay_seconds)
			# Parse ISO8601 with tz - handle +HH:MM format
			_tz_match = _re.search(r"([+-]\d\d:\d\d)$", attempted_at)
			if _tz_match:
				tz_str = _tz_match.group(1)
				dt_str = attempted_at[:_tz_match.start()]
				base_dt = _dt.datetime.fromisoformat(dt_str)
				tz_sign = 1 if tz_str[0] == "+" else -1
				tz_h, tz_m = int(tz_str[1:3]), int(tz_str[4:6])
				tz = _dt.timezone(_dt.timedelta(hours=tz_sign * tz_h, minutes=tz_sign * tz_m))
				base_dt = base_dt.replace(tzinfo=tz)
				retry_dt = base_dt + _dt.timedelta(seconds=delay)
				next_retry_at = retry_dt.isoformat()
		except Exception:
			pass
	return {
		"event_type": "korea_kakao_delivery_audit_v1",
		"dedupe_key": queue_item.get("dedupe_key", ""),
		"provider_key": provider_key,
		"attempt_number": attempt_count + 1,
		"attempted_at": attempted_at,
		"provider_status": provider_status,
		"provider_message_id": provider_message_id,
		"error_code": error_code,
		"next_retry_at": next_retry_at,
	}


def _validate_phone(phone: str) -> bool:
	"""휴대폰 번호 유효성 검사 — 010/011/016/017/018/019 시작 번호만 허용.

	유선번호(02, 031 등) 또는 잘못된 형식은 False 반환.
	"""
	if not phone:
		return False
	digits = "".join(ch for ch in str(phone) if ch.isdigit())
	if not (10 <= len(digits) <= 11):
		return False
	# 한국 휴대폰 번호 앞자리: 010, 011, 016, 017, 018, 019
	mobile_prefixes = ("010", "011", "016", "017", "018", "019")
	return digits.startswith(mobile_prefixes)


def _key_contains_phone_number(key: str) -> bool:
	"""키 문자열에 한국 휴대폰 번호가 포함됐는지 검사.

	Date-like identifiers (e.g. "provider-20260101123456") are allowed.
	Rejected patterns (checked against all digits concatenated from key):
	  - 10-11 digit total starting with Korean mobile prefix (010/011/016/017/018/019)
	  - 12-13 digit total starting with Korean country code prefix (8210/8211/8216/...)

	Examples:
	  "partner-010-1234-5678" → digits "01012345678" (11, starts 010) → True
	  "+82-10-1234-5678"      → digits "821012345678" (12, starts 8210) → True
	  "provider-20260101123456" → digits "20260101123456" (14) → False (allowed)
	"""
	mobile_prefixes = ("010", "011", "016", "017", "018", "019")
	intl_prefixes = ("8210", "8211", "8216", "8217", "8218", "8219")
	digits = "".join(ch for ch in str(key) if ch.isdigit())
	n = len(digits)
	# Domestic mobile: 10-11 digits starting with Korean mobile prefix
	if 10 <= n <= 11 and digits.startswith(mobile_prefixes):
		return True
	# International mobile: 12-13 digits starting with Korean country code + mobile prefix
	if 12 <= n <= 13 and digits.startswith(intl_prefixes):
		return True
	return False


# ── PII 마스킹 헬퍼 (audit log / external system 노출 시 사용) ──

def mask_phone_number(phone: str) -> str:
	"""휴대폰 번호 마스킹: 01012345678 → 010-****-5678."""
	if not phone:
		return ""
	digits = "".join(ch for ch in str(phone) if ch.isdigit())
	if len(digits) == 11 and digits.startswith("01"):
		return f"{digits[:3]}-****-{digits[7:]}"
	if len(digits) == 10 and digits.startswith("01"):
		return f"{digits[:3]}-***-{digits[6:]}"
	return "***-****-" + (digits[-4:] if len(digits) >= 4 else "****")


def mask_korean_name(name: str) -> str:
	"""한국 이름 마스킹: 홍길동 → 홍*동, 김민지 → 김*지, 박세재홍 → 박**홍."""
	if not name:
		return ""
	if len(name) == 1:
		return "*"
	if len(name) == 2:
		return name[0] + "*"
	return name[0] + "*" * (len(name) - 2) + name[-1]


def mask_email(email: str) -> str:
	"""이메일 마스킹: abc@winhr.co.kr → a**@winhr.co.kr."""
	if not email or "@" not in email:
		return "***"
	local, _, domain = email.partition("@")
	if len(local) <= 1:
		return "*@" + domain
	return local[0] + "*" * (len(local) - 1) + "@" + domain


def mask_rrn(rrn: str) -> str:
	"""주민번호 마스킹: 940312-1234567 → 940312-1******."""
	if not rrn:
		return ""
	if "-" in rrn:
		front, _, back = rrn.partition("-")
		return f"{front}-{back[0] if back else '*'}{'*' * 6}"
	if len(rrn) >= 7:
		return rrn[:7] + "*" * (len(rrn) - 7)
	return "*" * len(rrn)
