"""Frappe whitelist API — 카카오 알림톡 발송 엔드포인트.

이 모듈은 Frappe RPC 레이어에 노출되는 함수들을 정의합니다.
내부 로직은 kakao_notification.py 에 위임합니다.
"""

from __future__ import annotations

from typing import Any

import frappe

from hrms.regional.south_korea.kakao_notification import (
	list_alimtalk_templates,
	preview_kakao_alimtalk,
	send_kakao_alimtalk,
)


@frappe.whitelist()
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
		frappe.throw("pf_id, template_id, to 는 필수입니다.")

	variables = _coerce_template_variables(template_variables)
	approved = _coerce_bool(human_approved)
	is_dry_run = _coerce_bool(dry_run)

	return send_kakao_alimtalk(
		pf_id=pf_id,
		template_id=template_id,
		to=to,
		template_variables=variables,
		human_approved=approved,
		dry_run=is_dry_run,
	)


@frappe.whitelist()
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
		frappe.throw("pf_id, template_id, to 는 필수입니다.")

	variables = _coerce_template_variables(template_variables)

	return preview_kakao_alimtalk(
		pf_id=pf_id,
		template_id=template_id,
		to=to,
		template_variables=variables,
	)


@frappe.whitelist()
def api_list_alimtalk_templates() -> list[dict[str, Any]]:
	"""등록된 알림톡 템플릿 카탈로그 조회 API (Frappe whitelist).

	Returns:
		템플릿 목록 (kakao_alimtalk_templates.json 기반)
	"""
	return list_alimtalk_templates()


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _coerce_template_variables(variables: Any) -> dict[str, str]:
	"""template_variables 를 dict 로 정규화 (JSON 문자열도 수용)."""
	import json  # noqa: PLC0415

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
