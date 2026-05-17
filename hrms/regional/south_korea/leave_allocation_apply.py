"""Framework-free Korea Leave Allocation runtime apply.

Converts a ``korea_leave_allocation_preview_v1`` payload (produced by
``leave_allocation_api.preview_korea_leave_allocation_draft``) into an actual
Frappe Leave Allocation document.

This module is intentionally side-effect-free when used without Frappe — all
mutation (``frappe.get_doc``, ``.insert()``, ``.save()``) lives in
``apply_korea_leave_allocation``, which requires an explicit
``human_approved=True`` flag.  Tests mock the Frappe layer.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from copy import deepcopy
from typing import Any

LEAVE_DOCTYPE = "Leave Allocation"
MUTATION_BOUNDARY = "draft_only_no_submit_no_approve_no_send"
CONTRACT_TYPE = "korea_leave_allocation_runtime_apply_v1"
PREVIEW_CONTRACT_TYPE = "korea_leave_allocation_preview_v1"
DRAFT_CONTRACT_TYPE = "korea_leave_allocation_draft_v1"
_FORBIDDEN_SCORE_KEY_FRAGMENTS = ("risk_score", "probability", "success_rate")
_FORBIDDEN_NORMALIZED_SCORE_FRAGMENTS = ("riskscore", "probability", "successrate")


def apply_korea_leave_allocation(
    *,
    draft: dict[str, Any],
    human_approved: bool,
    apply_actor: str | None = None,
) -> dict[str, Any]:
    """Apply a previewed Korea Leave Allocation draft to Frappe DB.

    Parameters
    ----------
    draft:
        The ``draft`` sub-dict from ``preview_korea_leave_allocation_draft``'s
        return value (i.e. the ``korea_leave_allocation_draft_v1`` payload).
    human_approved:
        Explicit boolean; must be ``True`` to allow mutation.  Passing
        ``False`` returns a structured no-op result (fail-closed).
    apply_actor:
        Free-text identifier of the person/process calling apply (audit trail).

    Returns
    -------
    dict with contract_type ``korea_leave_allocation_runtime_apply_v1``.
    """

    try:
        import frappe as _frappe  # type: ignore
    except ImportError:
        _frappe = None  # type: ignore

    _forbid_numeric_score_fields(draft)

    # --- fail-closed guard ---
    if not human_approved:
        return {
            "contract_type": CONTRACT_TYPE,
            "runtime_action": "leave_allocation_runtime_apply",
            "applied": False,
            "idempotent_hit": False,
            "leave_allocation_name": None,
            "human_approval_verified": False,
            "apply_actor": _sanitize_actor(apply_actor),
            "draft_reference": _draft_summary(draft),
        }

    _validate_draft(draft)

    employee = _require_string_text(draft.get("employee"), "draft.employee")
    leave_type = _require_string_text(draft.get("leave_type"), "draft.leave_type")
    from_date = _parse_iso_date_text(draft.get("from_date"), "draft.from_date")
    to_date = _parse_iso_date_text(draft.get("to_date"), "draft.to_date")
    new_leaves = _require_positive_number(draft.get("new_leaves_allocated"), "draft.new_leaves_allocated")
    actor = _sanitize_actor(apply_actor)

    # --- mutation boundary check ---
    if _frappe is None:
        raise RuntimeError(
            "apply_korea_leave_allocation requires a Frappe runtime context (frappe not importable)"
        )

    db = getattr(_frappe, "db", None)
    if db is None:
        raise RuntimeError("frappe.db is not available — mutation boundary violation")

    # --- idempotency check ---
    existing_name = db.exists(
        LEAVE_DOCTYPE,
        {
            "employee": employee,
            "leave_type": leave_type,
            "from_date": from_date,
            "to_date": to_date,
            "docstatus": ["!=", 2],  # exclude cancelled
        },
    )
    if existing_name:
        return {
            "contract_type": CONTRACT_TYPE,
            "runtime_action": "leave_allocation_runtime_apply",
            "applied": False,
            "idempotent_hit": True,
            "leave_allocation_name": existing_name,
            "human_approval_verified": True,
            "apply_actor": actor,
            "draft_reference": _draft_summary(draft),
        }

    # --- actual mutation (save only, no submit) ---
    doc = _frappe.get_doc(
        {
            "doctype": LEAVE_DOCTYPE,
            "employee": employee,
            "employee_name": draft.get("employee_name"),
            "company": draft.get("company"),
            "leave_type": leave_type,
            "from_date": from_date,
            "to_date": to_date,
            "new_leaves_allocated": new_leaves,
            "unused_leaves": draft.get("unused_leaves", new_leaves),
            "carry_forward": int(bool(draft.get("carry_forward", False))),
        }
    )
    saved = doc.insert()
    name = getattr(saved, "name", None)

    return {
        "contract_type": CONTRACT_TYPE,
        "runtime_action": "leave_allocation_runtime_apply",
        "applied": True,
        "idempotent_hit": False,
        "leave_allocation_name": name,
        "human_approval_verified": True,
        "apply_actor": actor,
        "draft_reference": _draft_summary(draft),
    }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_draft(draft: Any) -> None:
    """Raise ValueError if the draft payload fails boundary checks."""
    if not isinstance(draft, dict):
        raise ValueError("draft must be a dict")
    if draft.get("contract_type") != DRAFT_CONTRACT_TYPE:
        raise ValueError(f"draft.contract_type must be {DRAFT_CONTRACT_TYPE!r}")
    if draft.get("requires_runtime_apply") is not True:
        raise ValueError("draft.requires_runtime_apply must be true")
    if draft.get("doctype") != LEAVE_DOCTYPE:
        raise ValueError(f"draft.doctype must be {LEAVE_DOCTYPE!r}")


def _draft_summary(draft: Any) -> dict[str, Any]:
    """Return a minimal summary of the draft for audit embedding."""
    if not isinstance(draft, dict):
        return {}
    return {
        "contract_type": draft.get("contract_type"),
        "employee": draft.get("employee"),
        "leave_type": draft.get("leave_type"),
        "from_date": draft.get("from_date"),
        "to_date": draft.get("to_date"),
        "new_leaves_allocated": draft.get("new_leaves_allocated"),
        "requires_runtime_apply": draft.get("requires_runtime_apply"),
    }


def _sanitize_actor(actor: Any) -> str | None:
    if not isinstance(actor, str):
        return None
    text = actor.strip()
    return text or None


def _require_string_text(value: Any, fieldname: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{fieldname} must be a non-empty string")
    return value.strip()


def _parse_iso_date_text(value: Any, fieldname: str) -> str:
    text = _require_string_text(value, fieldname)
    try:
        parsed = dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{fieldname} must be an ISO date") from exc
    return parsed.isoformat()


def _require_positive_number(value: Any, fieldname: str) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{fieldname} must be a number") from exc
    if num < 0:
        raise ValueError(f"{fieldname} must be >= 0")
    return num


_FORBIDDEN_SCORE_KEYS = {"risk_score", "probability", "success_rate", "legal_risk_score"}


def _forbid_numeric_score_fields(value: Any, *, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            display_path = (*path, key) if isinstance(key, str) else path
            if _is_forbidden_score_key(key, parent_path=path):
                raise ValueError(
                    f"{'.'.join(display_path) if display_path else key} is not allowed in leave allocation apply payloads"
                )
            _forbid_numeric_score_fields(nested, path=display_path)
    elif isinstance(value, list):
        for item in value:
            _forbid_numeric_score_fields(item, path=path)


def _is_forbidden_score_key(key: Any, *, parent_path: tuple[str, ...] = ()) -> bool:
    if not isinstance(key, str):
        return False
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    parent_normalized = re.sub(r"[^a-z0-9]", "", "".join(parent_path).lower())
    return (
        key in _FORBIDDEN_SCORE_KEYS
        or any(fragment in key for fragment in _FORBIDDEN_SCORE_KEY_FRAGMENTS)
        or any(fragment in normalized for fragment in _FORBIDDEN_NORMALIZED_SCORE_FRAGMENTS)
        or (
            normalized == "score"
            and any(fragment in parent_normalized for fragment in ("legal", "risk", "probability", "success"))
        )
    )


__all__ = ["apply_korea_leave_allocation"]
