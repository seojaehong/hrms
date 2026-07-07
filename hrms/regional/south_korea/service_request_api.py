"""F3 요청 보드 API — Korea Service Request 폼 제출/조회/상태 변경.

고객사(노호 등)가 급여·4대보험·증명서·연차/근태 관련 요청을 채팅으로
산발 전달하던 흐름을 Korea Service Request 폼 제출로 대체한다.

테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import한다 (insurance_filing_api.py / onboarding_request_api.py 컨벤션).

경계:
  - update_service_request_status는 HR Manager 전용 (상태 전이 규칙 강제).
  - create는 요청자(고객사 담당) 제출 — requested_by에 세션 사용자 기록.
  - 생성 시 HR Manager 전원에게 Notification Log (best effort — 실패해도 제출은 성공).
"""

from __future__ import annotations

import datetime
import json
from typing import Any

# ---------------------------------------------------------------------------
# Frappe 조건부 import — framework-free 테스트 환경에서 안전하게 로드
# ---------------------------------------------------------------------------
try:
	import frappe as _frappe  # noqa: PLC0415

	_FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
	_frappe = None  # type: ignore[assignment]
	_FRAPPE_AVAILABLE = False


def _whitelist(fn):
	"""@frappe.whitelist() 데코레이터 — Frappe 없으면 no-op."""
	if _FRAPPE_AVAILABLE and _frappe is not None:
		return _frappe.whitelist()(fn)
	return fn


DOCTYPE = "Korea Service Request"

CATEGORIES = ("급여", "4대보험", "증명서", "연차·근태", "기타")

REQUEST_STATUSES = ("접수", "처리중", "완료", "보류")

# status 전이 규칙 — 완료는 종결 상태(재오픈 불가)
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
	"접수": {"처리중", "완료", "보류"},
	"처리중": {"완료", "보류", "접수"},
	"보류": {"처리중", "완료", "접수"},
	"완료": set(),
}

# 완료로 전이될 때 resolved_at 을 기록한다.
_RESOLVED_STATUSES = ("완료",)

LIST_FIELDS = (
	"name",
	"company",
	"title",
	"category",
	"detail",
	"status",
	"requested_by",
	"resolved_at",
	"resolution_note",
)


# ---------------------------------------------------------------------------
# framework-free 검증 함수 (doctype validate에서도 재사용)
# ---------------------------------------------------------------------------


def validate_category(category: Any) -> str:
	"""분류 검증 후 정규화 문자열 반환."""
	value = str(category or "").strip()
	if not value:
		raise ValueError("분류(category)를 선택해 주세요.")
	if value not in CATEGORIES:
		raise ValueError(f"category must be one of {CATEGORIES}: {value!r}")
	return value


def validate_status_transition(current: Any, target: Any) -> str:
	"""상태 전이 규칙 검증 후 target 반환.

	- target이 허용 상태가 아니면 ValueError.
	- current → target 전이가 규칙에 없으면 ValueError (완료는 종결).
	"""
	cur = str(current or "접수").strip() or "접수"
	tgt = str(target or "").strip()
	if tgt not in REQUEST_STATUSES:
		raise ValueError(f"status must be one of {REQUEST_STATUSES}: {tgt!r}")
	if tgt not in _ALLOWED_TRANSITIONS.get(cur, set()):
		raise ValueError(f"허용되지 않는 상태 전이입니다: {cur} → {tgt}")
	return tgt


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


@_whitelist
def create_service_request(payload: dict | str) -> dict[str, Any]:
	"""요청 접수 폼 제출.

	Args:
		payload: {company?, title, category, detail?} — dict 또는 JSON 문자열.
			company 미지정 시 Global Defaults.default_company 폴백.

	Returns:
		생성된 요청 요약 dict.
	"""
	if isinstance(payload, str):
		payload = json.loads(payload)
	if not isinstance(payload, dict):
		raise ValueError("payload는 dict 또는 JSON object여야 합니다.")

	title = str(payload.get("title") or "").strip()
	if not title:
		raise ValueError("제목(title)을 입력해 주세요.")

	category = validate_category(payload.get("category"))

	_require_roles(("System Manager", "HR Manager", "HR User", "Employee"))

	company = payload.get("company") or _default_company()
	if not company:
		raise ValueError("회사(company)가 지정되지 않았고 기본 회사도 설정되어 있지 않습니다.")

	requested_by = _session_user()

	doc = _frappe.get_doc(  # type: ignore[union-attr]
		{
			"doctype": DOCTYPE,
			"company": company,
			"title": title,
			"category": category,
			"detail": payload.get("detail") or "",
			"status": "접수",
			"requested_by": requested_by,
		}
	)
	doc.insert(ignore_permissions=False)

	summary = {
		"name": doc.get("name"),
		"company": company,
		"title": title,
		"category": category,
		"detail": payload.get("detail") or "",
		"status": "접수",
		"requested_by": requested_by,
	}

	_notify_hr_managers_safe(summary)

	return summary


@_whitelist
def list_service_requests(
	company: str | None = None, status: str | None = None
) -> dict[str, Any]:
	"""요청 목록 — company(미지정 시 Global Defaults 폴백) · status 필터."""
	_require_roles(("System Manager", "HR Manager", "HR User", "Employee"))

	filters: dict[str, Any] = {}
	resolved_company = company or _default_company()
	if resolved_company:
		filters["company"] = resolved_company
	if status:
		if status not in REQUEST_STATUSES:
			raise ValueError(f"status must be one of {REQUEST_STATUSES}: {status!r}")
		filters["status"] = status

	rows = _frappe.get_all(  # type: ignore[union-attr]
		DOCTYPE,
		filters=filters,
		fields=list(LIST_FIELDS),
		order_by="creation desc",
	)
	requests = [dict(row) for row in rows]
	return {"requests": requests, "count": len(requests), "company": resolved_company}


@_whitelist
def update_service_request_status(
	name: str, status: str, resolution_note: str | None = None
) -> dict[str, Any]:
	"""요청 상태 변경 — HR Manager 전용. 상태 전이 규칙 + 완료 시각 기록."""
	_require_roles(("System Manager", "HR Manager"))

	doc = _frappe.get_doc(DOCTYPE, name)  # type: ignore[union-attr]
	current = str(doc.get("status") or "접수")
	target = validate_status_transition(current, status)

	doc.set("status", target)
	if resolution_note is not None:
		doc.set("resolution_note", resolution_note)
	resolved_at = None
	if target in _RESOLVED_STATUSES:
		resolved_at = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
		doc.set("resolved_at", resolved_at)
	doc.save(ignore_permissions=False)

	return {
		"name": name,
		"company": doc.get("company"),
		"title": doc.get("title"),
		"category": doc.get("category"),
		"status": target,
		"resolved_at": doc.get("resolved_at"),
		"resolution_note": doc.get("resolution_note"),
	}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _require_roles(roles: tuple[str, ...]) -> None:
	if _frappe is not None and hasattr(_frappe, "only_for"):
		_frappe.only_for(roles)


def _session_user() -> str | None:
	if _frappe is not None and hasattr(_frappe, "session"):
		return getattr(_frappe.session, "user", None)
	return None


def _default_company() -> str | None:
	if _frappe is not None and hasattr(_frappe, "db"):
		return _frappe.db.get_single_value("Global Defaults", "default_company")
	return None


def _notify_hr_managers_safe(summary: dict[str, Any]) -> None:
	"""HR Manager 전원에게 Notification Log 생성 — 실패는 조용히 무시(best effort)."""
	if _frappe is None:
		return
	try:
		managers = _frappe.get_all(
			"Has Role",
			filters={"role": "HR Manager", "parenttype": "User"},
			fields=["parent"],
		)
		users = sorted({m.get("parent") for m in managers if m.get("parent")})
		subject = f"신규 요청: [{summary.get('category')}] {summary.get('title')} ({summary.get('company')})"
		message = f"분류 {summary.get('category')} · 요청자 {summary.get('requested_by')}"
		for user in users:
			log = _frappe.get_doc(
				{
					"doctype": "Notification Log",
					"for_user": user,
					"type": "Alert",
					"subject": subject,
					"email_content": message,
					"document_type": DOCTYPE,
					"document_name": summary.get("name"),
				}
			)
			log.insert(ignore_permissions=True)
	except Exception:
		# 알림 실패가 요청 제출을 막아서는 안 된다.
		return
