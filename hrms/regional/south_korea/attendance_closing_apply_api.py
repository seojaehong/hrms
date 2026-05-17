"""Frappe-facing runtime apply API for Korea Attendance Closing.

Wraps ``apply_korea_attendance_closing`` with ``frappe.whitelist()`` so it is
callable from Frappe's REST/RPC layer.
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
def apply_korea_attendance_closing_api(
    *,
    snapshot: Any,
    human_approved: Any,
    apply_actor: Any = None,
) -> dict[str, Any]:
    """Frappe whitelisted wrapper around apply_korea_attendance_closing.

    Parameters
    ----------
    snapshot:
        The ``snapshot`` payload from ``preview_korea_attendance_closing``
        (dict or JSON string).
    human_approved:
        Must be the boolean ``True`` (or ``"true"``/``1`` from HTTP) to allow
        mutation.  Any falsy value triggers a fail-closed no-op.
    apply_actor:
        Identifier of the human actor performing the apply (optional).

    Returns
    -------
    dict with ``contract_type`` = ``korea_attendance_closing_runtime_apply_v1``.
    """

    snapshot_payload = deepcopy(_coerce_mapping(snapshot, "snapshot"))
    approved = _coerce_bool(human_approved, "human_approved")
    actor = _coerce_optional_str(apply_actor, "apply_actor")

    core = _load_sibling_module("attendance_closing_apply.py", "korea_attendance_closing_apply")
    return core.apply_korea_attendance_closing(
        snapshot=snapshot_payload,
        human_approved=approved,
        apply_actor=actor,
    )


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


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


def _coerce_bool(value: Any, fieldname: str) -> bool:
    """Accept bool, int (0/1), or string ('true'/'false'/'0'/'1')."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "1", "yes"):
            return True
        if text in ("false", "0", "no", ""):
            return False
    return False  # fail-closed for any unrecognised input


def _coerce_optional_str(value: Any, fieldname: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value).strip() or None
    return value.strip() or None


def _load_sibling_module(filename: str, module_name: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


__all__ = ["apply_korea_attendance_closing_api"]
