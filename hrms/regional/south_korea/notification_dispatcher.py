"""한국 알림톡 디스패처 — Frappe doc_event hook 연결.

Salary Slip on_submit    → 임금명세서 발행 알림 (pending approval 큐 기록)
Leave Application approve → 휴가 승인 알림 (pending approval 큐 기록)

설계 원칙:
  hook 은 발송 의도를 기록(Comment + frappe.log)하는 데만 책임진다.
  실제 발송은 HR 담당자가 api_send_kakao_alimtalk(human_approved=True) 를
  명시적으로 호출해야 한다 (fail-closed 아키텍처).

  이유: human_approved 플래그가 문서 필드에 있으면 실수로 활성화될 위험이
  있어 의도적으로 "기록만, 발송은 별도 승인" 패턴을 채택한다.
"""

from __future__ import annotations

from typing import Any

import frappe

from hrms.regional.south_korea.kakao_notification import (
	list_alimtalk_templates,
	preview_kakao_alimtalk,
)


# ---------------------------------------------------------------------------
# Salary Slip on_submit hook
# ---------------------------------------------------------------------------


def on_salary_slip_submit(doc: Any, method: str | None = None) -> None:
	"""임금명세서 제출 시 알림톡 발송 의도를 기록합니다.

	실제 발송은 하지 않습니다 (human_approved 없음).
	HR 담당자가 검토 후 api_send_kakao_alimtalk 를 직접 호출해야 합니다.
	"""
	try:
		employee_phone = _get_employee_phone(doc.employee)
		if not employee_phone:
			frappe.logger("kakao_alimtalk").info(
				f"[KakaoDispatcher] Salary Slip {doc.name}: no phone, skip alimtalk queue"
			)
			return

		template_variables = _build_wage_statement_variables(doc)
		preview = preview_kakao_alimtalk(
			pf_id="",
			template_id="korea_wage_statement",
			to=employee_phone,
			template_variables=template_variables,
		)

		_insert_pending_comment(
			reference_doctype="Salary Slip",
			reference_name=doc.name,
			template_id="korea_wage_statement",
			to=employee_phone,
			preview_content=preview.get("rendered_content", ""),
			missing_variables=preview.get("missing_variables", []),
		)
	except Exception as exc:
		frappe.log_error(
			f"[KakaoDispatcher] on_salary_slip_submit failed for {getattr(doc, 'name', '?')}: {exc}",
			"KakaoAlimtalkDispatcher",
		)


# ---------------------------------------------------------------------------
# Leave Application on_approve hook
# ---------------------------------------------------------------------------


def on_leave_application_approve(doc: Any, method: str | None = None) -> None:
	"""휴가 승인 시 알림톡 발송 의도를 기록합니다.

	실제 발송은 하지 않습니다 (human_approved 없음).

	중복 방지: status 가 Approved 로 처음 전환될 때만 기록한다.
	이미 Approved 인 문서가 다시 저장되면 무시한다.
	"""
	# 현재 상태 확인
	if getattr(doc, "status", None) != "Approved":
		return

	# 전환 감지: 이전 상태가 Approved 이면 이미 처리된 것 → 무시
	# Frappe on_update 는 save 마다 호출되므로 중복 방지 필요
	previous_status = _get_previous_status(doc)
	if previous_status == "Approved":
		# 이미 Approved 인 문서의 재저장 → 중복 Comment 방지
		return

	try:
		employee_phone = _get_employee_phone(doc.employee)
		if not employee_phone:
			frappe.logger("kakao_alimtalk").info(
				f"[KakaoDispatcher] Leave Application {doc.name}: no phone, skip alimtalk queue"
			)
			return

		template_variables = _build_leave_approved_variables(doc)
		preview = preview_kakao_alimtalk(
			pf_id="",
			template_id="korea_leave_approved",
			to=employee_phone,
			template_variables=template_variables,
		)

		_insert_pending_comment(
			reference_doctype="Leave Application",
			reference_name=doc.name,
			template_id="korea_leave_approved",
			to=employee_phone,
			preview_content=preview.get("rendered_content", ""),
			missing_variables=preview.get("missing_variables", []),
		)
	except Exception as exc:
		frappe.log_error(
			f"[KakaoDispatcher] on_leave_application_approve failed for {getattr(doc, 'name', '?')}: {exc}",
			"KakaoAlimtalkDispatcher",
		)


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _get_previous_status(doc: Any) -> str | None:
	"""Frappe doc 의 저장 전 status 조회.

	frappe.db.get_value 로 현재 DB 값을 읽는다.
	DB 에 아직 없으면 (신규 문서) None 반환.
	"""
	db = getattr(frappe, "db", None)
	if not db:
		return None
	try:
		doctype = getattr(doc, "doctype", None) or "Leave Application"
		return db.get_value(doctype, doc.name, "status")
	except Exception:
		return None


def _get_employee_phone(employee_id: str) -> str | None:
	"""직원의 휴대폰 번호 조회 (cell_number 또는 custom_mobile_number)."""
	if not employee_id:
		return None

	db = getattr(frappe, "db", None)
	if not db:
		return None

	# 표준 필드 우선, custom 필드 fallback
	for field in ("cell_number", "custom_kakao_phone", "custom_mobile_number"):
		try:
			phone = db.get_value("Employee", employee_id, field)
			if phone:
				return str(phone).strip()
		except Exception:
			continue
	return None


def _build_wage_statement_variables(doc: Any) -> dict[str, str]:
	"""임금명세서 템플릿 변수 구성."""
	employee_name = getattr(doc, "employee_name", "") or ""
	period = _format_period(doc)
	net_pay = getattr(doc, "net_pay", 0) or 0
	total_amount = f"{int(net_pay):,}"

	# 문서 URL (Frappe 환경에서만)
	link = ""
	try:
		site_url = frappe.utils.get_url()
		link = f"{site_url}/app/salary-slip/{doc.name}"
	except Exception:
		link = ""

	return {
		"employee_name": employee_name,
		"period": period,
		"total_amount": total_amount,
		"link": link,
	}


def _build_leave_approved_variables(doc: Any) -> dict[str, str]:
	"""휴가 승인 템플릿 변수 구성."""
	employee_name = getattr(doc, "employee_name", "") or ""
	leave_type = getattr(doc, "leave_type", "") or ""
	from_date = str(getattr(doc, "from_date", "") or "")
	to_date = str(getattr(doc, "to_date", "") or "")
	total_leave_days = getattr(doc, "total_leave_days", 0) or 0
	leave_days = str(int(total_leave_days)) if total_leave_days else "1"

	# 승인자 이름 조회
	approver_name = ""
	try:
		approver_id = getattr(doc, "leave_approver", "") or ""
		if approver_id:
			approver_name = frappe.db.get_value("User", approver_id, "full_name") or approver_id
	except Exception:
		approver_name = ""

	return {
		"employee_name": employee_name,
		"leave_type": leave_type,
		"from_date": from_date,
		"to_date": to_date,
		"leave_days": leave_days,
		"approver_name": approver_name,
	}


def _format_period(doc: Any) -> str:
	"""Salary Slip 의 급여 기간 문자열 생성."""
	start = str(getattr(doc, "start_date", "") or "")
	end = str(getattr(doc, "end_date", "") or "")
	if start and end:
		return f"{start} ~ {end}"
	return getattr(doc, "month_start_date", "") or ""


def _insert_pending_comment(
	reference_doctype: str,
	reference_name: str,
	template_id: str,
	to: str,
	preview_content: str,
	missing_variables: list[str],
) -> None:
	"""발송 대기 Comment 기록.

	HR 담당자가 이 Comment 를 보고 api_send_kakao_alimtalk 호출 여부를 결정합니다.
	"""
	missing_note = ""
	if missing_variables:
		missing_note = f"\n미입력 변수: {', '.join(missing_variables)} (발송 전 확인 필요)"

	content = (
		f"[카카오 알림톡 발송 대기]\n"
		f"템플릿: {template_id}\n"
		f"수신자: {to}\n"
		f"미리보기:\n{preview_content}"
		f"{missing_note}\n\n"
		f"실제 발송은 api_send_kakao_alimtalk(human_approved=True) 를 호출해 주세요."
	)

	try:
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Info",
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"content": content,
			}
		).insert(ignore_permissions=True)
	except Exception as exc:
		frappe.log_error(
			f"[KakaoDispatcher] Failed to insert pending comment for {reference_name}: {exc}",
			"KakaoAlimtalkDispatcher",
		)
