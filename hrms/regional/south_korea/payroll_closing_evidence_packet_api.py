"""Frappe-facing preview API for Korea payroll closing evidence packets.

This module wraps the framework-free evidence packet contract in a preview-only
whitelisted API. It accepts JSON/dict session payloads, delegates to the pure
helper by file-path import for no-bench execution, and never saves, submits,
approves, sends, calls providers, or mutates runtime documents.
"""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only inside a Frappe bench
	import frappe  # type: ignore
except ImportError:  # pragma: no cover - direct-run no-bench mode
	frappe = None  # type: ignore


def _whitelist(fn):
	if frappe is None:
		return fn
	return frappe.whitelist()(fn)


@_whitelist
def preview_korea_payroll_closing_evidence_packet(
	*,
	session: Any,
	actor: Any,
	purpose: Any = "payroll closing human review",
) -> dict[str, Any]:
	"""Return a side-effect-free preview of a payroll closing evidence packet."""

	session_payload = deepcopy(_coerce_mapping(session, "session"))
	core = _load_sibling_module("payroll_closing_evidence_packet.py", "korea_payroll_closing_evidence_packet")
	packet = deepcopy(
		core.build_korea_payroll_closing_evidence_packet(
			session_payload,
			actor=actor,
			purpose=purpose,
		)
	)
	evidence_packet_contract_type = packet.get("contract_type")
	packet.update(
		{
			"contract_type": "korea_payroll_closing_evidence_packet_preview_v1",
			"evidence_packet_contract_type": evidence_packet_contract_type,
			"runtime_action": "preview_only",
			"requires_runtime_apply": False,
		}
	)
	return packet


def _coerce_mapping(value: Any, fieldname: str) -> dict[str, Any]:
	coerced = _coerce_json_if_needed(value)
	if not isinstance(coerced, dict):
		raise ValueError(f"{fieldname} must be a dict or JSON object")
	return coerced


def _coerce_json_if_needed(value: Any) -> Any:
	if isinstance(value, str):
		text = value.strip()
		if text.startswith("{") or text.startswith("["):
			try:
				return json.loads(text)
			except json.JSONDecodeError as exc:
				raise ValueError("JSON payload is invalid") from exc
	return value


def _load_sibling_module(filename: str, module_name: str):
	path = Path(__file__).with_name(filename)
	spec = importlib.util.spec_from_file_location(module_name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = ["preview_korea_payroll_closing_evidence_packet"]
