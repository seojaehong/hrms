"""Frappe whitelist API — 카카오 알림톡 발송 엔드포인트.

이 모듈은 Frappe RPC 레이어에 노출되는 함수들을 정의합니다.
내부 로직은 kakao_notification.py 에 위임합니다.

테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import합니다.
"""

from __future__ import annotations

import copy
import json
from typing import Any

# ---------------------------------------------------------------------------
# Frappe 조건부 import — framework-free 테스트 환경에서 안전하게 로드
# ---------------------------------------------------------------------------
try:
	import frappe as _frappe  # noqa: PLC0415

	_FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
	_frappe = None  # type: ignore[assignment]
	_FRAPPE_AVAILABLE = False


def _whitelist(fn):
	"""@frappe.whitelist() 데코레이터 — Frappe 없으면 no-op."""
	if _FRAPPE_AVAILABLE and _frappe is not None:
		return _frappe.whitelist()(fn)
	return fn


# ---------------------------------------------------------------------------
# kakao_notification 모듈 동적 로드 (importlib으로 frappe 패키지 경로 우회)
# ---------------------------------------------------------------------------
import importlib.util as _ilu
import pathlib as _pl

_MODULE_DIR = _pl.Path(__file__).resolve().parent
_KAKAO_CORE = _MODULE_DIR / "kakao_notification.py"

_spec = _ilu.spec_from_file_location("_kakao_notification_core", _KAKAO_CORE)
_core = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_core)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 기존 Frappe whitelist API (하위 호환)
# ---------------------------------------------------------------------------


@_whitelist
def api_send_kakao_alimtalk(
	pf_id: str,
	template_id: str,
	to: str,
	template_variables: dict[str, str] | str | None = None,
	human_approved: bool | str = False,
	dry_run: bool | str = False,
) -> dict[str, Any]:
	"""카카오 알림톡 발송 API (Frappe whitelist).

	Args:
		pf_id: 발신 프로필 ID (카카오 비즈니스 채널)
		template_id: 알림톡 템플릿 ID (사전 등록 필수)
		to: 수신자 휴대폰 번호
		template_variables: 템플릿 변수 딕셔너리 또는 JSON 문자열
		human_approved: True 일 때만 실제 발송. 기본 False (fail-closed)
		dry_run: True 이면 preview만 반환, 발송 X

	Returns:
		send_kakao_alimtalk() 반환값 참조
	"""
	if not pf_id or not template_id or not to:
		if _FRAPPE_AVAILABLE and _frappe is not None:
			_frappe.throw("pf_id, template_id, to 는 필수입니다.")
		else:
			raise ValueError("pf_id, template_id, to 는 필수입니다.")

	variables = _coerce_template_variables(template_variables)
	approved = _coerce_bool(human_approved)
	is_dry_run = _coerce_bool(dry_run)

	return _core.send_kakao_alimtalk(
		pf_id=pf_id,
		template_id=template_id,
		to=to,
		template_variables=variables,
		human_approved=approved,
		dry_run=is_dry_run,
	)


@_whitelist
def api_preview_kakao_alimtalk(
	pf_id: str,
	template_id: str,
	to: str,
	template_variables: dict[str, str] | str | None = None,
) -> dict[str, Any]:
	"""카카오 알림톡 발송 전 preview API (Frappe whitelist).

	실제 발송 없이 템플릿 변수 치환 결과를 반환합니다.

	Returns:
		preview_kakao_alimtalk() 반환값 참조
	"""
	if not pf_id or not template_id or not to:
		if _FRAPPE_AVAILABLE and _frappe is not None:
			_frappe.throw("pf_id, template_id, to 는 필수입니다.")
		else:
			raise ValueError("pf_id, template_id, to 는 필수입니다.")

	variables = _coerce_template_variables(template_variables)

	return _core.preview_kakao_alimtalk(
		pf_id=pf_id,
		template_id=template_id,
		to=to,
		template_variables=variables,
	)


@_whitelist
def api_list_alimtalk_templates() -> list[dict[str, Any]]:
	"""등록된 알림톡 템플릿 카탈로그 조회 API (Frappe whitelist)."""
	return _core.list_alimtalk_templates()


# ---------------------------------------------------------------------------
# Phase 2-A Preview API — framework-free, 실제 발송 없음
# ---------------------------------------------------------------------------


@_whitelist
def preview_korea_kakao_template_registry_entry(
	*,
	template_code: str,
	template_name: str,
	template_body: str,
	required_variables: list[str] | str,
	consent_purpose: str,
	provider_template_keys: dict[str, str] | str | None = None,
	active: bool | str = True,
) -> dict[str, Any]:
	"""템플릿 레지스트리 엔트리 미리보기 — 실제 등록 없음.

	required_variables 와 active 는 JSON 문자열로 전달해도 됩니다.
	"""
	# Coerce required_variables from JSON string
	if isinstance(required_variables, str):
		try:
			required_variables = json.loads(required_variables)
		except (json.JSONDecodeError, TypeError) as exc:
			raise ValueError("required_variables must be a list") from exc
	if not isinstance(required_variables, list):
		raise ValueError("required_variables must be a list")

	# Coerce active from string
	if isinstance(active, str):
		low = active.strip().lower()
		if low in ("true", "1", "yes"):
			active = True
		elif low in ("false", "0", "no"):
			active = False
		else:
			raise ValueError("active must be a bool")

	# Coerce provider_template_keys from JSON string
	if isinstance(provider_template_keys, str):
		try:
			provider_template_keys = json.loads(provider_template_keys)
		except (json.JSONDecodeError, TypeError):
			provider_template_keys = None

	entry = _core.build_kakao_template_registry_entry(
		template_code=template_code,
		template_name=template_name,
		template_body=template_body,
		required_variables=required_variables,
		consent_purpose=consent_purpose,
		provider_template_keys=copy.deepcopy(provider_template_keys) if provider_template_keys else None,
		active=active,
	)

	return {
		"contract_type": "korea_kakao_template_registry_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_send": False,
		"registry_entry": copy.deepcopy(entry),
	}


@_whitelist
def preview_korea_kakao_registered_queue_item(
	*,
	recipient_phone: str,
	template_registry_entry: dict[str, Any] | str,
	variables: dict[str, str] | str,
	recipient_consent: bool = True,
	opted_out: bool = False,
	scheduled_at: str | None = None,
	provider_key: str = "solapi",
	max_attempts: int | str = 3,
) -> dict[str, Any]:
	"""등록된 템플릿 레지스트리 엔트리를 이용해 큐 아이템 미리보기 — 실제 발송 없음."""
	# Coerce template_registry_entry from JSON string
	if isinstance(template_registry_entry, str):
		try:
			template_registry_entry = json.loads(template_registry_entry)
		except (json.JSONDecodeError, TypeError) as exc:
			raise ValueError("JSON payload is invalid") from exc
	if not isinstance(template_registry_entry, dict):
		raise ValueError("template_registry_entry must be a dict or JSON object")

	# Coerce variables from JSON string
	if isinstance(variables, str):
		try:
			variables = json.loads(variables)
		except (json.JSONDecodeError, TypeError) as exc:
			raise ValueError("variables must be a dict or JSON object") from exc
	if not isinstance(variables, dict):
		raise ValueError("variables must be a dict or JSON object")

	# Coerce max_attempts to strict int
	if isinstance(max_attempts, str):
		try:
			max_attempts = int(max_attempts)
		except ValueError as exc:
			raise ValueError("max_attempts must be an integer") from exc
	if not isinstance(max_attempts, int) or isinstance(max_attempts, bool):
		raise ValueError("max_attempts must be an integer")

	# Build registered template payload
	payload = _core.build_registered_kakao_template_payload(
		recipient_phone=recipient_phone,
		template_registry_entry=template_registry_entry,
		variables=variables,
	)

	# Build queue item
	queue_item = _core.build_kakao_send_queue_item(
		payload=payload,
		recipient_consent=recipient_consent,
		opted_out=opted_out,
		scheduled_at=scheduled_at,
		provider_key=provider_key,
		max_attempts=max_attempts,
	)

	return {
		"contract_type": "korea_kakao_queue_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_send": True,
		"payload": copy.deepcopy(payload),
		"queue_item": copy.deepcopy(queue_item),
	}


@_whitelist
def preview_korea_kakao_provider_dispatch(
	*,
	queue_item: dict[str, Any] | str,
	provider: dict[str, Any] | str,
	requested_at: str,
) -> dict[str, Any]:
	"""Provider dispatch request 미리보기 — 실제 발송 없음."""
	# Coerce queue_item from JSON string
	if isinstance(queue_item, str):
		try:
			queue_item = json.loads(queue_item)
		except (json.JSONDecodeError, TypeError) as exc:
			raise ValueError("JSON payload is invalid") from exc
	if not isinstance(queue_item, dict):
		raise ValueError("queue_item must be a dict or JSON object")

	# Coerce provider from JSON string
	if isinstance(provider, str):
		try:
			provider = json.loads(provider)
		except (json.JSONDecodeError, TypeError) as exc:
			raise ValueError("JSON payload is invalid") from exc

	queue_item_copy = copy.deepcopy(queue_item)

	dispatch_request = _core.build_kakao_provider_dispatch_request(
		queue_item=queue_item_copy,
		provider=provider,
		requested_at=requested_at,
	)

	return {
		"contract_type": "korea_kakao_dispatch_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_send": False,
		"dispatch_request": dispatch_request,
	}


@_whitelist
def preview_korea_kakao_delivery_audit_event(
	*,
	queue_item: dict[str, Any] | str,
	attempted_at: str,
	provider_status: str,
	provider_message_id: str | None = None,
	error_code: str | None = None,
	base_retry_delay_seconds: int | str = 60,
	max_retry_delay_seconds: int | str = 3600,
) -> dict[str, Any]:
	"""Delivery audit event 미리보기 — 실제 발송 없음."""
	# Coerce queue_item from JSON string
	if isinstance(queue_item, str):
		try:
			queue_item = json.loads(queue_item)
		except (json.JSONDecodeError, TypeError) as exc:
			raise ValueError("JSON payload is invalid") from exc
	if not isinstance(queue_item, dict):
		raise ValueError("queue_item must be a dict or JSON object")

	# Coerce retry delay seconds from string
	if isinstance(base_retry_delay_seconds, str):
		try:
			base_retry_delay_seconds = int(base_retry_delay_seconds)
		except ValueError as exc:
			raise ValueError("base_retry_delay_seconds must be an integer") from exc
	if isinstance(max_retry_delay_seconds, str):
		try:
			max_retry_delay_seconds = int(max_retry_delay_seconds)
		except ValueError as exc:
			raise ValueError("max_retry_delay_seconds must be an integer") from exc

	queue_item_copy = copy.deepcopy(queue_item)

	audit_event = _core.build_kakao_delivery_audit_event(
		queue_item=queue_item_copy,
		attempted_at=attempted_at,
		provider_status=provider_status,
		provider_message_id=provider_message_id,
		error_code=error_code,
		base_retry_delay_seconds=base_retry_delay_seconds,
		max_retry_delay_seconds=max_retry_delay_seconds,
	)

	return {
		"contract_type": "korea_kakao_delivery_audit_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_send": True,
		"audit_event": audit_event,
	}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _coerce_template_variables(variables: Any) -> dict[str, str]:
	"""template_variables 를 dict 로 정규화 (JSON 문자열도 수용)."""
	if variables is None:
		return {}
	if isinstance(variables, dict):
		return {str(k): str(v) for k, v in variables.items()}
	if isinstance(variables, str):
		try:
			parsed = json.loads(variables)
			if isinstance(parsed, dict):
				return {str(k): str(v) for k, v in parsed.items()}
		except (json.JSONDecodeError, TypeError):
			pass
	return {}


def _coerce_bool(value: Any) -> bool:
	"""Frappe form dict 에서 넘어오는 문자열 bool 처리."""
	if isinstance(value, bool):
		return value
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "y"}
	return bool(value)
