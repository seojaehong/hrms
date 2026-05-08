"""Frappe-facing preview API for Korea payroll closing draft review actions.

This wrapper exposes the framework-free human-review action contract to Desk/UI
callers without performing status mutation. It accepts only the runtime draft
insert contract, delegates to ``payroll_closing_draft_review.py``, and returns a
preview wrapper that preserves the future runtime boundary.
"""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only inside a Frappe bench or test stub
	import frappe  # type: ignore
except ImportError:  # pragma: no cover - direct-run no-bench import mode
	frappe = None  # type: ignore


def _whitelist(fn):
	if frappe is None:
		return fn
	return frappe.whitelist()(fn)


@_whitelist
def preview_korea_payroll_closing_draft_review_action(
	*,
	draft: Any,
	actor: Any,
	action: Any,
	note: Any | None = None,
) -> dict[str, Any]:
	"""Build a preview-only human-review action for a runtime draft.

	No save/submit/approve/send/provider operation is performed here. The wrapper
	JSON-coerces only the API boundary input, delegates all contract validation to
	the pure helper, and defensive-copies both caller input and returned output.
	"""

	draft_payload = deepcopy(_coerce_mapping(draft, "draft"))
	actor_text = _require_text(actor, "actor")
	action_text = _require_text(action, "action")
	note_value = None if note is None else _require_optional_text(note, "note")

	core = _load_core()
	result = deepcopy(
		core.build_korea_payroll_closing_draft_review_action(
			draft_payload,
			actor=actor_text,
			action=action_text,
			note=note_value,
		)
	)
	review_action_contract_type = result.get("contract_type")
	result.update(
		{
			"contract_type": "korea_payroll_closing_draft_review_action_preview_v1",
			"review_action_contract_type": review_action_contract_type,
			"runtime_action": "preview_only",
			"requires_runtime_apply": True,
			"mutation_boundary": "human_review_only_no_submit_no_send_no_provider_call",
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		}
	)
	return result


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


def _require_text(value: Any, label: str) -> str:
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"{label} must be a non-empty string")
	return value.strip()


def _require_optional_text(value: Any, label: str) -> str:
	if not isinstance(value, str):
		raise ValueError(f"{label} must be a string")
	return value.strip()


def _load_core():
	path = Path(__file__).resolve().with_name("payroll_closing_draft_review.py")
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_review_core", path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = ["preview_korea_payroll_closing_draft_review_action"]
