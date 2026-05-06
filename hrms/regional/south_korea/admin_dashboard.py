"""Framework-free Korea admin home dashboard v1 helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

CARD_DEFINITIONS = (
	("open_approvals", "Open Approvals", "warning"),
	("overdue_compliance", "Overdue Compliance", "danger"),
	("pending_payslips", "Pending Payslips", "warning"),
	("unclosed_attendance", "Unclosed Attendance", "danger"),
	("blocked_payroll_closings", "Blocked Payroll Closings", "danger"),
)
CRITICAL_KEYS = {"overdue_compliance", "unclosed_attendance", "blocked_payroll_closings"}
ACTION_DEFINITIONS = {
	"open_approvals": ("review_approval_inbox", "korea-approval-inbox"),
	"overdue_compliance": ("open_compliance_diagnosis", "korea-compliance-diagnosis"),
	"pending_payslips": ("open_payroll_closing_center", "korea-closing-center"),
	"unclosed_attendance": ("open_attendance_closing_center", "korea-closing-center"),
	"blocked_payroll_closings": ("open_payroll_closing_session", "korea-payroll-closing-session"),
}


def build_admin_dashboard(*, metrics: dict[str, Any]) -> dict[str, Any]:
	"""Build deterministic cards for the Korea HR admin home dashboard."""

	cards = []
	needs_attention = False
	for key, label, severity_when_nonzero in CARD_DEFINITIONS:
		value = _normalize_metric_count(metrics.get(key, 0), key)
		severity = severity_when_nonzero if value else "neutral"
		if value and key in CRITICAL_KEYS:
			needs_attention = True
		cards.append({"key": key, "label": label, "value": value, "severity": severity, "action": _build_card_action(key, value)})
	return {"status": "Needs Attention" if needs_attention else "Ready", "cards": cards}


def _build_card_action(key: str, value: int) -> dict[str, Any]:
	action, route = ACTION_DEFINITIONS[key]
	return {
		"action": action,
		"route": route,
		"enabled": value > 0,
		"requires_runtime_apply": False,
	}


def _normalize_metric_count(value: Any, fieldname: str) -> int:
	if isinstance(value, bool):
		raise ValueError(f"{fieldname} must be a non-negative integer")
	try:
		number = Decimal(str(value or 0))
	except (InvalidOperation, ValueError) as exc:
		raise ValueError(f"{fieldname} must be a non-negative integer") from exc
	if not number.is_finite() or number != number.to_integral_value():
		raise ValueError(f"{fieldname} must be a non-negative integer")
	count = int(number)
	if count < 0:
		raise ValueError(f"{fieldname} cannot be negative")
	return count


__all__ = ["CARD_DEFINITIONS", "ACTION_DEFINITIONS", "build_admin_dashboard"]
