"""
hrms/regional/south_korea/approval_inbox_api.py
Frappe @whitelist 엔드포인트 — 결재 인박스 PWA용 HTTP API.

framework-free 테스트 환경에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import합니다.
"""
from __future__ import annotations

import copy
import datetime as dt
import importlib.util as _ilu
import json
import pathlib as _pl
from typing import Any

# ---------------------------------------------------------------------------
# Frappe 조건부 import
# ---------------------------------------------------------------------------
try:
	import frappe as _frappe  # noqa: PLC0415

	_FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
	_frappe = None  # type: ignore[assignment]
	_FRAPPE_AVAILABLE = False


def _whitelist(fn=None, *, methods=None):
	"""@frappe.whitelist() 데코레이터 — Frappe 없으면 no-op."""
	def decorator(f):
		if _FRAPPE_AVAILABLE and _frappe is not None:
			return _frappe.whitelist(methods=methods)(f) if methods else _frappe.whitelist()(f)
		return f
	if fn is not None:
		return decorator(fn)
	return decorator


def _throw(msg: str) -> None:
	if _FRAPPE_AVAILABLE and _frappe is not None:
		_frappe.throw(msg)
	raise ValueError(msg)


# ---------------------------------------------------------------------------
# approval_inbox 모듈 참조 (Frappe 환경에서만 사용)
# ---------------------------------------------------------------------------
_core = None  # Lazy-loaded in Frappe runtime functions only


def _get_core():
	"""approval_inbox 모듈 동적 로드 — Frappe 런타임에서만 호출."""
	global _core
	if _core is None:
		_MODULE_DIR = _pl.Path(__file__).resolve().parent
		_INBOX_CORE = _MODULE_DIR / "approval_inbox.py"
		_spec = _ilu.spec_from_file_location("_approval_inbox_core", _INBOX_CORE)
		_c = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
		_spec.loader.exec_module(_c)  # type: ignore[union-attr]
		_core = _c
	return _core


# ---------------------------------------------------------------------------
# 기존 Frappe whitelist API (하위 호환)
# ---------------------------------------------------------------------------


@_whitelist
def get_pending_approvals(as_of_date: str | None = None) -> list[dict]:
	"""현재 로그인 사용자가 결재해야 할 항목 목록.

	as_of_date: YYYY-MM-DD 형식. 미입력 시 오늘.
	"""
	if not _FRAPPE_AVAILABLE or _frappe is None:
		raise RuntimeError("get_pending_approvals requires Frappe runtime")
	approver = _frappe.session.user
	if not approver or approver == "Guest":
		_frappe.throw("로그인이 필요합니다.", _frappe.AuthenticationError)

	if as_of_date:
		try:
			date_obj = dt.date.fromisoformat(as_of_date)
		except ValueError:
			_frappe.throw("as_of_date는 YYYY-MM-DD 형식이어야 합니다.")
	else:
		date_obj = dt.date.today()

	return _get_core().list_pending_approvals(approver=approver, as_of_date=date_obj)


@_whitelist
def count_pending_for_others(as_of_date: str | None = None) -> dict:
	"""다른 결재자에게 배정된 결재 대기 건수 (read-only, HR Manager 한정).

	빈 결재함 화면에서 "다른 결재자에게 배정된 대기 N건" 보조 문구용.
	mutation 없음 — 카운트 조회 전용.
	"""
	if not _FRAPPE_AVAILABLE or _frappe is None:
		raise RuntimeError("count_pending_for_others requires Frappe runtime")
	approver = _frappe.session.user
	if not approver or approver == "Guest":
		_frappe.throw("로그인이 필요합니다.", _frappe.AuthenticationError)
	# 타인 결재 현황 노출이므로 HR Manager/System Manager 한정
	_frappe.only_for(["HR Manager", "System Manager"])

	if as_of_date:
		try:
			date_obj = dt.date.fromisoformat(as_of_date)
		except ValueError:
			_frappe.throw("as_of_date는 YYYY-MM-DD 형식이어야 합니다.")
	else:
		date_obj = dt.date.today()

	return _get_core().count_pending_for_others(approver=approver, as_of_date=date_obj)


@_whitelist(methods=["POST"])
def approve_inbox_item(
	doctype: str,
	name: str,
	comment: str | None = None,
) -> dict:
	"""결재 승인."""
	if not _FRAPPE_AVAILABLE or _frappe is None:
		raise RuntimeError("approve_inbox_item requires Frappe runtime")
	approver = _frappe.session.user
	if not approver or approver == "Guest":
		_frappe.throw("로그인이 필요합니다.", _frappe.AuthenticationError)
	if not doctype or not name:
		_frappe.throw("doctype과 name은 필수입니다.")

	return _get_core().approve_item(
		doctype=doctype,
		name=name,
		approver=approver,
		human_approved=True,
		comment=comment or None,
	)


@_whitelist(methods=["POST"])
def reject_inbox_item(
	doctype: str,
	name: str,
	comment: str | None = None,
) -> dict:
	"""결재 반려."""
	if not _FRAPPE_AVAILABLE or _frappe is None:
		raise RuntimeError("reject_inbox_item requires Frappe runtime")
	approver = _frappe.session.user
	if not approver or approver == "Guest":
		_frappe.throw("로그인이 필요합니다.", _frappe.AuthenticationError)
	if not doctype or not name:
		_frappe.throw("doctype과 name은 필수입니다.")

	return _get_core().reject_item(
		doctype=doctype,
		name=name,
		approver=approver,
		human_approved=True,
		comment=comment or None,
	)


# ---------------------------------------------------------------------------
# Phase 2-A Preview API — framework-free, 실제 mutation 없음
# ---------------------------------------------------------------------------

_OPEN_STATUSES = frozenset(["Open", "Pending", "Draft", "Submitted"])
_ACTION_TO_STATUS = {"approve": "Approved", "reject": "Rejected"}


def _coerce_strict_int_nonneg(val: Any, fieldname: str) -> int:
	"""Coerce to strict non-negative int. Reject bool, float, negative."""
	if isinstance(val, bool):
		raise ValueError(f"{fieldname} must be a non-negative integer")
	if isinstance(val, str):
		try:
			parsed = int(val)
		except ValueError:
			raise ValueError(f"{fieldname} must be a non-negative integer")
		if parsed < 0:
			raise ValueError(f"{fieldname} must be a non-negative integer")
		return parsed
	if not isinstance(val, int):
		raise ValueError(f"{fieldname} must be a non-negative integer")
	if val < 0:
		raise ValueError(f"{fieldname} must be a non-negative integer")
	return val


@_whitelist
def preview_korea_approval_inbox(
	*,
	records: list[dict] | str,
	actor: str,
	today: str | None = None,
	overdue_after_days: int | str = 7,
) -> dict[str, Any]:
	"""결재 인박스 미리보기 — framework-free, 실제 mutation 없음."""
	# Coerce records from JSON string
	if isinstance(records, str):
		try:
			records = json.loads(records)
		except (json.JSONDecodeError, TypeError) as exc:
			raise ValueError("JSON payload is invalid") from exc
	if not isinstance(records, list):
		raise ValueError("records must be a list or JSON array")

	# Validate overdue_after_days
	overdue_after_days = _coerce_strict_int_nonneg(overdue_after_days, "overdue_after_days")

	# Parse today
	if today:
		try:
			today_date = dt.date.fromisoformat(today)
		except ValueError:
			today_date = dt.date.today()
	else:
		today_date = dt.date.today()

	# Filter records for this actor
	items = []
	summary: dict[str, int] = {}
	for rec in records:
		if not isinstance(rec, dict):
			continue
		if rec.get("approver") != actor:
			continue
		if rec.get("status") not in _OPEN_STATUSES:
			continue
		item = copy.deepcopy(rec)
		# Compute overdue
		posting_date_raw = rec.get("posting_date")
		if posting_date_raw and today:
			try:
				posting_date = dt.date.fromisoformat(str(posting_date_raw))
				days_open = (today_date - posting_date).days
				item["overdue"] = days_open > overdue_after_days
				item["days_open"] = days_open
			except Exception:
				item["overdue"] = False
		items.append(item)
		doctype = rec.get("doctype", "Unknown")
		summary[doctype] = summary.get(doctype, 0) + 1

	return {
		"contract_type": "korea_approval_inbox_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": False,
		"actor": actor,
		"items": items,
		"summary": summary,
	}


@_whitelist
def preview_korea_approval_action(
	*,
	item: dict[str, Any] | str,
	action: str,
	actor: str,
	note: str | None = None,
) -> dict[str, Any]:
	"""결재 단일 액션 미리보기 — framework-free, 실제 mutation 없음."""
	# Coerce item from JSON string
	if isinstance(item, str):
		try:
			item = json.loads(item)
		except (json.JSONDecodeError, TypeError) as exc:
			raise ValueError("JSON payload is invalid") from exc
	if not isinstance(item, dict):
		raise ValueError("item must be a dict or JSON object")

	# Validate actor is the approver
	approver = item.get("approver", "")
	if actor != approver:
		raise ValueError(f"actor is not the assigned approver: {actor!r} != {approver!r}")

	# Validate status is open
	status = item.get("status", "")
	if status not in _OPEN_STATUSES:
		raise ValueError(f"only open approval items can be actioned: {status!r}")

	result_status = _ACTION_TO_STATUS.get(action, action.capitalize())
	doctype = item.get("source_doctype") or item.get("doctype", "Unknown")
	name = item.get("name", "")

	return {
		"contract_type": "korea_approval_action_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"action": action,
		"actor": actor,
		"target": {"doctype": doctype, "name": name},
		"result_status": result_status,
		"note": note,
	}


@_whitelist
def preview_korea_approval_batch_action(
	*,
	items: list[dict] | str,
	action: str,
	actor: str,
	note: str | None = None,
) -> dict[str, Any]:
	"""결재 일괄 액션 미리보기 — framework-free, 실제 mutation 없음."""
	# Coerce items from JSON string
	if isinstance(items, str):
		try:
			items = json.loads(items)
		except (json.JSONDecodeError, TypeError) as exc:
			raise ValueError("JSON payload is invalid") from exc
	if not isinstance(items, list):
		raise ValueError("items must be a list or JSON array")

	if len(items) == 0:
		raise ValueError("at least one approval item is required")

	actions = []
	doctype_counts: dict[str, int] = {}
	for item in items:
		if not isinstance(item, dict):
			continue
		action_preview = preview_korea_approval_action(
			item=item,
			action=action,
			actor=actor,
			note=note,
		)
		actions.append(action_preview)
		doctype = item.get("source_doctype") or item.get("doctype", "Unknown")
		doctype_counts[doctype] = doctype_counts.get(doctype, 0) + 1

	return {
		"contract_type": "korea_approval_batch_action_preview_v1",
		"runtime_action": "preview_only",
		"requires_runtime_apply": True,
		"action": action,
		"actor": actor,
		"actions": actions,
		"summary": {"total": len(actions), "by_doctype": doctype_counts},
	}
