"""Frappe-facing runtime API for Korea payroll closing draft insertion.

This wrapper is the first operator-callable runtime mutation boundary for the
Korea payroll closing draft. It accepts only the core
``korea_payroll_closing_draft_apply_plan_v1`` contract, delegates to the DocType
controller runtime adapter, and creates only a draft row. It never submits,
approves, sends notifications, calls providers, or creates payroll documents.
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
def create_korea_payroll_closing_draft_runtime(*, apply_plan: Any, actor: Any | None = None) -> dict[str, Any]:
	"""Create a Korea Payroll Closing Draft from a reviewed apply plan.

	This endpoint intentionally performs only the draft insert delegated to the
	DocType controller. The apply plan must be the core runtime apply contract, not
	the preview API wrapper contract.
	"""

	apply_plan_payload = deepcopy(_coerce_mapping(apply_plan, "apply_plan"))
	actor_was_omitted = actor is None
	actor_text = _resolve_actor(actor)
	if actor_was_omitted:
		apply_plan_payload["actor"] = actor_text
	controller = _load_doctype_controller()
	result = deepcopy(
		controller.create_korea_payroll_closing_draft_from_apply_plan(
			apply_plan_payload,
			actor=actor_text,
		)
	)
	runtime_insert_contract_type = result.get("contract_type")
	result.update(
		{
			"contract_type": "korea_payroll_closing_draft_runtime_insert_api_v1",
			"runtime_insert_contract_type": runtime_insert_contract_type,
			"runtime_action": "runtime_draft_created",
			"requires_runtime_apply": False,
			"mutation_boundary": "draft_only_no_submit_no_approve_no_send",
			"requires_human_approval": True,
			"ai_role": "assistant_only",
		}
	)
	return result


def _resolve_actor(actor: Any | None) -> str:
	if actor is None:
		if frappe is None or not getattr(frappe, "session", None):
			raise ValueError("actor is required outside a Frappe session")
		actor = getattr(frappe.session, "user", None)
	if not isinstance(actor, str) or not actor.strip():
		raise ValueError("actor must be a non-empty string")
	return actor.strip()


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


def _load_doctype_controller():
	path = Path(__file__).resolve().parents[2] / "hr" / "doctype" / "korea_payroll_closing_draft" / "korea_payroll_closing_draft.py"
	spec = importlib.util.spec_from_file_location("korea_payroll_closing_draft_doctype_runtime", path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


__all__ = ["create_korea_payroll_closing_draft_runtime"]
