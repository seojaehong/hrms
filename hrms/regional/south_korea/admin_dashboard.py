"""Framework-free Korea admin home dashboard v1 helpers."""

from __future__ import annotations

from typing import Any

CARD_DEFINITIONS = (
	("open_approvals", "Open Approvals", "warning"),
	("overdue_compliance", "Overdue Compliance", "danger"),
	("pending_payslips", "Pending Payslips", "warning"),
	("unclosed_attendance", "Unclosed Attendance", "danger"),
)
CRITICAL_KEYS = {"overdue_compliance", "unclosed_attendance"}


def build_admin_dashboard(*, metrics: dict[str, Any]) -> dict[str, Any]:
	"""Build deterministic cards for the Korea HR admin home dashboard."""

	cards = []
	needs_attention = False
	for key, label, severity_when_nonzero in CARD_DEFINITIONS:
		value = int(metrics.get(key, 0) or 0)
		if value < 0:
			raise ValueError(f"{key} cannot be negative")
		severity = severity_when_nonzero if value else "neutral"
		if value and key in CRITICAL_KEYS:
			needs_attention = True
		cards.append({"key": key, "label": label, "value": value, "severity": severity})
	return {"status": "Needs Attention" if needs_attention else "Ready", "cards": cards}


__all__ = ["CARD_DEFINITIONS", "build_admin_dashboard"]
