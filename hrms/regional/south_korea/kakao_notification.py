"""Side-effect-free Kakao Alimtalk notification adapter helpers."""

from __future__ import annotations

import re
from typing import Any

VARIABLE_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def build_kakao_template_payload(
	*,
	recipient_phone: str,
	template_code: str,
	variables: dict[str, Any],
) -> dict[str, Any]:
	"""Build a validated Kakao template payload without sending it."""

	phone = _normalize_phone(recipient_phone)
	if not template_code:
		raise ValueError("template_code is required")
	return {
		"channel": "kakao_alimtalk",
		"recipient_phone": phone,
		"template_code": template_code,
		"variables": {str(key): str(value) for key, value in sorted((variables or {}).items())},
	}


def render_kakao_preview(template: str, variables: dict[str, Any]) -> str:
	"""Render a local preview and reject unresolved template variables."""

	variables = {str(key): str(value) for key, value in (variables or {}).items()}
	missing = sorted({match.group(1) for match in VARIABLE_RE.finditer(template)} - set(variables))
	if missing:
		raise ValueError(f"missing template variables: {', '.join(missing)}")
	return VARIABLE_RE.sub(lambda match: variables[match.group(1)], template)


def _normalize_phone(value: str) -> str:
	digits = "".join(ch for ch in str(value or "") if ch.isdigit())
	if not (10 <= len(digits) <= 11) or not digits.startswith("01"):
		raise ValueError("recipient_phone must be a valid Korean mobile number")
	return digits


__all__ = ["build_kakao_template_payload", "render_kakao_preview"]
