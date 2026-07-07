"""입사자 등록 요청 API — 표준 폼 제출로 4대보험 취득신고 파이프라인 연결.

고객사가 입사자 정보를 채팅으로 산발 전달하던 흐름을
Korea Employee Onboarding Request 폼 제출로 대체한다.

테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import한다 (insurance_filing_api.py 컨벤션).

PII 불변식 (주민번호):
  - rrn은 Password 필드로 암호화 저장하며, 어떤 로그·print·응답 dict에도 평문 포함 금지.
  - 목록/응답에는 masked_rrn("9401**-1******")만 노출한다.
  - 검증 실패 메시지에도 입력 rrn을 절대 echo하지 않는다.
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


DOCTYPE = "Korea Employee Onboarding Request"

CONTRACT_TYPES = ("정규직", "계약직", "파트타임", "일용직")

REQUEST_STATUSES = ("requested", "processing", "completed", "rejected")

# status 전이 규칙 — 완료/반려는 종결 상태
_ALLOWED_TRANSITIONS = {
	"requested": {"processing", "completed", "rejected"},
	"processing": {"completed", "rejected"},
	"completed": set(),
	"rejected": set(),
}

REQUIRED_FIELDS = (
	"company",
	"full_name",
	"rrn",
	"join_date",
	"reported_monthly_wage",
	"contract_type",
)

# 목록 조회 필드 — rrn(Password)은 절대 포함하지 않는다
LIST_FIELDS = (
	"name",
	"company",
	"full_name",
	"masked_rrn",
	"join_date",
	"reported_monthly_wage",
	"contract_type",
	"phone",
	"status",
	"requested_by",
	"processed_by",
	"processed_at",
	"employee",
)


# ---------------------------------------------------------------------------
# framework-free 함수 — rrn 검증/마스킹 (doctype validate에서도 재사용)
# ---------------------------------------------------------------------------


def normalize_rrn(raw: Any) -> str:
	"""하이픈/공백 제거한 주민등록번호 문자열 반환 (검증은 하지 않음)."""
	if raw is None:
		return ""
	return str(raw).replace("-", "").replace(" ", "").strip()


def validate_rrn(raw: Any) -> str:
	"""주민등록번호 형식 검증 후 정규화된 13자리 문자열 반환.

	검증: 13자리 숫자(하이픈 허용 후 제거), 생년월일(월 1-12, 일 1-31),
	7번째 자리 성별코드 1-8.

	주의: 오류 메시지에 입력값을 절대 포함하지 않는다 (로그 유출 방지).
	"""
	rrn = normalize_rrn(raw)
	if not rrn:
		raise ValueError("주민등록번호가 입력되지 않았습니다.")
	if not rrn.isdigit() or len(rrn) != 13:
		raise ValueError("주민등록번호는 13자리 숫자여야 합니다 (하이픈 허용).")
	month = int(rrn[2:4])
	day = int(rrn[4:6])
	if not (1 <= month <= 12):
		raise ValueError("주민등록번호의 생년월일(월)이 올바르지 않습니다.")
	if not (1 <= day <= 31):
		raise ValueError("주민등록번호의 생년월일(일)이 올바르지 않습니다.")
	if rrn[6] not in "12345678":
		raise ValueError("주민등록번호의 성별코드(7번째 자리)가 올바르지 않습니다.")
	return rrn


def mask_rrn(raw: Any) -> str:
	"""마스킹된 주민등록번호 반환 — "9401**-1******" 형식.

	생년(YYMM 중 앞 4자리)과 성별코드만 남기고 전부 마스킹한다.
	"""
	rrn = validate_rrn(raw)
	return f"{rrn[:4]}**-{rrn[6]}******"


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


@_whitelist
def create_onboarding_request(payload: dict | str) -> dict[str, Any]:
	"""입사자 등록 요청 폼 제출 (HR User / HR Manager).

	Args:
		payload: {company, full_name, rrn, join_date, reported_monthly_wage,
			contract_type, phone?, note?} — dict 또는 JSON 문자열.

	Returns:
		rrn을 제외한 요약 dict (masked_rrn만 포함).
	"""
	if isinstance(payload, str):
		payload = json.loads(payload)
	if not isinstance(payload, dict):
		raise ValueError("payload는 dict 또는 JSON object여야 합니다.")

	missing = [f for f in REQUIRED_FIELDS if not payload.get(f)]
	if missing:
		raise ValueError(f"필수 항목 누락: {', '.join(missing)}")

	contract_type = str(payload["contract_type"])
	if contract_type not in CONTRACT_TYPES:
		raise ValueError(f"contract_type must be one of {CONTRACT_TYPES}: {contract_type!r}")

	rrn = validate_rrn(payload["rrn"])
	masked = mask_rrn(rrn)

	_require_roles(("System Manager", "HR Manager", "HR User"))
	requested_by = _session_user()

	doc = _frappe.get_doc(  # type: ignore[union-attr]
		{
			"doctype": DOCTYPE,
			"company": payload["company"],
			"full_name": payload["full_name"],
			"rrn": rrn,  # Password 필드 — 암호화 저장, 응답/로그 노출 금지
			"masked_rrn": masked,
			"join_date": payload["join_date"],
			"reported_monthly_wage": payload["reported_monthly_wage"],
			"contract_type": contract_type,
			"phone": payload.get("phone") or "",
			"note": payload.get("note") or "",
			"status": "requested",
			"requested_by": requested_by,
		}
	)
	doc.insert(ignore_permissions=False)

	summary = {
		"name": doc.get("name"),
		"company": payload["company"],
		"full_name": payload["full_name"],
		"masked_rrn": masked,
		"join_date": payload["join_date"],
		"reported_monthly_wage": payload["reported_monthly_wage"],
		"contract_type": contract_type,
		"phone": payload.get("phone") or "",
		"status": "requested",
		"requested_by": requested_by,
	}

	# HR Manager 알림 — best effort (실패해도 요청 자체는 성공)
	# TODO: 외부(텔레그램) 알림 연동은 이번 범위 밖 — notification_dispatcher 확장 시 여기서 호출.
	_notify_hr_managers_safe(summary)

	return summary


@_whitelist
def list_onboarding_requests(
	company: str | None = None, status: str | None = None
) -> dict[str, Any]:
	"""입사자 등록 요청 목록 — rrn은 masked_rrn 별도 필드로만 노출."""
	_require_roles(("System Manager", "HR Manager", "HR User"))

	filters: dict[str, Any] = {}
	if company:
		filters["company"] = company
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
	requests = []
	for row in rows:
		item = dict(row)
		item.pop("rrn", None)  # 방어적 이중 차단 — 평문 rrn은 어떤 경로로도 응답 금지
		requests.append(item)
	return {"requests": requests, "count": len(requests)}


@_whitelist
def mark_onboarding_processed(
	name: str, employee: str | None = None, status: str = "completed"
) -> dict[str, Any]:
	"""요청 처리 완료 표시 — HR Manager 전용. status 전이 + 처리자 기록."""
	if status not in ("processing", "completed", "rejected"):
		raise ValueError("status must be one of ('processing', 'completed', 'rejected')")

	_require_roles(("System Manager", "HR Manager"))

	doc = _frappe.get_doc(DOCTYPE, name)  # type: ignore[union-attr]
	current = str(doc.get("status") or "requested")
	if status not in _ALLOWED_TRANSITIONS.get(current, set()):
		raise ValueError(f"허용되지 않는 상태 전이입니다: {current} → {status}")

	processed_at = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
	doc.set("status", status)
	doc.set("processed_by", _session_user())
	doc.set("processed_at", processed_at)
	if employee:
		doc.set("employee", employee)
	doc.save(ignore_permissions=False)

	return {
		"name": name,
		"company": doc.get("company"),
		"full_name": doc.get("full_name"),
		"masked_rrn": doc.get("masked_rrn"),
		"status": status,
		"employee": doc.get("employee"),
		"processed_by": doc.get("processed_by"),
		"processed_at": processed_at,
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


def _notify_hr_managers_safe(summary: dict[str, Any]) -> None:
	"""HR Manager 전원에게 Notification Log 생성 — 실패는 조용히 무시(best effort).

	알림 본문에는 masked_rrn만 사용한다 (평문 rrn 금지).
	"""
	if _frappe is None:
		return
	try:
		managers = _frappe.get_all(
			"Has Role",
			filters={"role": "HR Manager", "parenttype": "User"},
			fields=["parent"],
		)
		users = sorted({m.get("parent") for m in managers if m.get("parent")})
		subject = f"입사자 등록 요청: {summary.get('full_name')} ({summary.get('company')})"
		message = (
			f"입사일 {summary.get('join_date')} · {summary.get('contract_type')} · "
			f"신고보수 {summary.get('reported_monthly_wage')}원 · "
			f"주민번호 {summary.get('masked_rrn')}"
		)
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
