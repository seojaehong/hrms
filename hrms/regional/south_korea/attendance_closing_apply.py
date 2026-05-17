"""Framework-free Korea Attendance Closing runtime apply.

Converts a ``korea_attendance_closing_preview_v1`` snapshot (produced by
``attendance_closing_api.preview_korea_attendance_closing``) into a persisted
record inside an existing Korea Payroll Closing Draft document.

Storage strategy: attendance snapshots are stored as JSON in the
``attendance_snapshot`` field of an existing ``Korea Payroll Closing Draft``
record.  The payroll closing draft is the natural owner of period+workplace
scope, and this avoids introducing a new DocType migration for Wave 1.

Rules
-----
- ``human_approved=False`` → fail-closed (returns ``applied=False``, no write)
- Matching draft must already exist (workplace + period_start + period_end).
  If none exists, this function raises — draft creation is a separate workflow.
- If a draft exists, its ``attendance_snapshot`` field is updated (idempotent
  on re-apply: the field is simply overwritten).
- ``blocking_messages`` present → draft status kept at ``"Blocked"`` (or
  left as-is); the status field on the draft is not promoted.
- Mutation: ``frappe.get_doc`` + ``.save()`` only.  No submit / cancel /
  approve / notification / provider call.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

CLOSING_DRAFT_DOCTYPE = "Korea Payroll Closing Draft"
SNAPSHOT_CONTRACT_TYPE = "korea_attendance_closing_preview_v1"
CONTRACT_TYPE = "korea_attendance_closing_runtime_apply_v1"
MUTATION_BOUNDARY = "draft_only_no_submit_no_approve_no_send"
_FORBIDDEN_SCORE_KEY_FRAGMENTS = ("risk_score", "probability", "success_rate")
_FORBIDDEN_NORMALIZED_SCORE_FRAGMENTS = ("riskscore", "probability", "successrate")


def apply_korea_attendance_closing(
    *,
    snapshot: dict[str, Any],
    human_approved: bool,
    apply_actor: str | None = None,
) -> dict[str, Any]:
    """Apply a Korea attendance closing snapshot to an existing Payroll Closing Draft.

    Parameters
    ----------
    snapshot:
        The ``snapshot`` sub-dict from ``preview_korea_attendance_closing``'s
        return value (i.e. the ``build_closing_snapshot`` output).
    human_approved:
        Explicit boolean; must be ``True`` to allow mutation.
    apply_actor:
        Free-text identifier of the human/process performing the apply.

    Returns
    -------
    dict with ``contract_type`` = ``korea_attendance_closing_runtime_apply_v1``.

    Raises
    ------
    ValueError
        If ``snapshot`` fails contract validation.
    RuntimeError
        If Frappe is not importable (bench-free context) and mutation is requested.
    LookupError
        If no Korea Payroll Closing Draft exists for the snapshot's
        workplace + period_start + period_end.
    """

    try:
        import frappe as _frappe  # type: ignore
    except ImportError:
        _frappe = None  # type: ignore

    _forbid_numeric_score_fields(snapshot)
    actor = _sanitize_actor(apply_actor)

    # --- fail-closed guard ---
    if not human_approved:
        return {
            "contract_type": CONTRACT_TYPE,
            "runtime_action": "attendance_closing_runtime_apply",
            "applied": False,
            "idempotent_hit": False,
            "korea_payroll_closing_draft_name": None,
            "human_approval_verified": False,
            "apply_actor": actor,
            "blocking_messages": list(snapshot.get("blocking_messages", [])) if isinstance(snapshot, dict) else [],
        }

    _validate_snapshot(snapshot)

    workplace = _require_string_text(snapshot.get("workplace"), "snapshot.workplace")
    period_start = _coerce_date_str(snapshot.get("period_start"), "snapshot.period_start")
    period_end = _coerce_date_str(snapshot.get("period_end"), "snapshot.period_end")
    blocking_messages: list[str] = list(snapshot.get("blocking_messages") or [])

    # --- mutation boundary check ---
    if _frappe is None:
        raise RuntimeError(
            "apply_korea_attendance_closing requires a Frappe runtime context (frappe not importable)"
        )

    db = getattr(_frappe, "db", None)
    if db is None:
        raise RuntimeError("frappe.db is not available — mutation boundary violation")

    # --- locate existing draft ---
    existing_name = db.get_value(
        CLOSING_DRAFT_DOCTYPE,
        {
            "workplace": workplace,
            "period_start": period_start,
            "period_end": period_end,
            "docstatus": 0,
        },
        "name",
    )
    if not existing_name:
        raise LookupError(
            f"No Korea Payroll Closing Draft found for workplace={workplace!r}, "
            f"period_start={period_start!r}, period_end={period_end!r}. "
            "Create a Korea Payroll Closing Draft first before applying an attendance snapshot."
        )

    # --- check idempotency: was snapshot already stored? ---
    existing_snapshot_raw = db.get_value(CLOSING_DRAFT_DOCTYPE, existing_name, "attendance_snapshot")
    idempotent_hit = bool(existing_snapshot_raw and existing_snapshot_raw.strip())

    # --- persist snapshot into the draft ---
    doc = _frappe.get_doc(CLOSING_DRAFT_DOCTYPE, existing_name)
    doc.attendance_snapshot = _json_dumps(snapshot)
    doc.save()

    return {
        "contract_type": CONTRACT_TYPE,
        "runtime_action": "attendance_closing_runtime_apply",
        "applied": True,
        "idempotent_hit": idempotent_hit,
        "korea_payroll_closing_draft_name": existing_name,
        "human_approval_verified": True,
        "apply_actor": actor,
        "blocking_messages": blocking_messages,
    }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_snapshot(snapshot: Any) -> None:
    """Raise ValueError if the snapshot fails contract boundary checks."""
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a dict")
    if not snapshot.get("workplace"):
        raise ValueError("snapshot.workplace is required")
    _require_string_text(snapshot.get("workplace"), "snapshot.workplace")
    _coerce_date_str(snapshot.get("period_start"), "snapshot.period_start")
    _coerce_date_str(snapshot.get("period_end"), "snapshot.period_end")


def _coerce_date_str(value: Any, fieldname: str) -> str:
    import datetime as dt

    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    text = _require_string_text(str(value) if value is not None else "", fieldname)
    try:
        dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{fieldname} must be an ISO date") from exc
    return text


def _require_string_text(value: Any, fieldname: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{fieldname} must be a non-empty string")
    return value.strip()


def _sanitize_actor(actor: Any) -> str | None:
    if not isinstance(actor, str):
        return None
    text = actor.strip()
    return text or None


def _json_dumps(value: Any) -> str:
    def _default(obj):
        import datetime as dt

        if isinstance(obj, (dt.date, dt.datetime)):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=_default)


_FORBIDDEN_SCORE_KEYS = {"risk_score", "probability", "success_rate", "legal_risk_score"}


def _forbid_numeric_score_fields(value: Any, *, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            display_path = (*path, key) if isinstance(key, str) else path
            if _is_forbidden_score_key(key, parent_path=path):
                raise ValueError(
                    f"{'.'.join(display_path) if display_path else key} is not allowed in attendance closing apply payloads"
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


__all__ = ["apply_korea_attendance_closing"]
