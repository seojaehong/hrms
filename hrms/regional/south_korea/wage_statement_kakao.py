"""임금명세서 카카오 알림톡 발송 path — Phase 2-A skeleton.

mutation boundary:
  - 이 모듈은 카카오 알림톡 payload 구성까지만 담당합니다.
  - 실제 카카오 API 호출(provider dispatch)은 Phase 2-D에서 구현합니다.
  - human_approved 파라미터가 정확히 True(bool)가 아니면 fail-closed 합니다.
  - 이 함수는 외부 API, DB, 파일 시스템을 호출하지 않습니다.

Phase 2-D 구현 시 교체 포인트:
  - _PHASE_2D_PLACEHOLDER 마크를 검색해 실제 provider dispatch 로직을 삽입합니다.
"""

from __future__ import annotations

import pathlib
import importlib.util
from typing import Any

# kakao_notification.py 를 직접 임포트 (framework-free)
_KAKAO_MODULE_PATH = pathlib.Path(__file__).resolve().parent / "kakao_notification.py"

# 모듈 캐시 — 반복 호출 시 재로드 방지
_KAKAO_MODULE_CACHE: "Any | None" = None


def _load_kakao_module() -> "Any":
    global _KAKAO_MODULE_CACHE
    if _KAKAO_MODULE_CACHE is not None:
        return _KAKAO_MODULE_CACHE
    spec = importlib.util.spec_from_file_location("korea_kakao_notification", _KAKAO_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    _KAKAO_MODULE_CACHE = module
    return module


# 임금명세서 알림 템플릿 (사전 승인된 카카오 알림톡 템플릿 코드)
# Phase 2-D에서 실제 승인된 템플릿 코드로 교체합니다.
WAGE_STATEMENT_TEMPLATE_CODE = "WAGE_STATEMENT_READY"  # _PHASE_2D_PLACEHOLDER

# 임금명세서 알림 템플릿 본문 (카카오 비즈메시지 심사 시 제출하는 원문)
WAGE_STATEMENT_TEMPLATE_BODY = (
    "{{employee_name}}님의 {{period}} 임금명세서가 발급되었습니다.\n"
    "지급일: {{payment_date}}\n"
    "실지급액: {{net_pay}}원\n\n"
    "* 본 메시지는 근로기준법 시행령 제27조의2에 따라 발송됩니다."
)


def build_wage_statement_kakao_queue_item(
    *,
    wage_statement_payload: dict[str, Any],
    recipient_phone: str,
    recipient_consent: bool,
    human_approved: bool,
    provider_key: str = "unassigned",
    scheduled_at: str | None = None,
    opted_out: bool = False,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """임금명세서 카카오 알림톡 발송 queue item 구성 — Phase 2-A skeleton.

    이 함수는 카카오 API를 호출하지 않습니다.
    반환값은 Phase 2-D runtime worker가 처리할 queue item 계약입니다.

    Parameters
    ----------
    wage_statement_payload:
        build_korea_wage_statement_pdf_payload() 반환값.
        contract_type이 "korea_wage_statement_pdf_v1"이어야 합니다.
    recipient_phone:
        수신자 휴대폰 번호 (01x-xxxx-xxxx 형식 또는 숫자만).
    recipient_consent:
        수신자의 카카오 알림톡 수신 동의 여부. False이면 즉시 오류.
    human_approved:
        반드시 bool True여야 합니다. 정확히 True가 아니면 fail-closed.
    provider_key:
        Phase 2-D에서 실제 provider 키로 교체합니다.
    scheduled_at:
        발송 예약 시각 (ISO datetime with timezone). None이면 즉시 발송 대기.
    opted_out:
        수신자가 수신 거부 상태이면 True.
    max_attempts:
        최대 재시도 횟수 (기본 3).

    Returns
    -------
    dict — korea_kakao_send_queue_v1 형식 queue item.
    """

    # ── mutation boundary: human_approved는 반드시 bool True ──────
    if human_approved is not True:
        raise ValueError(
            "human_approved must be exactly True (bool). "
            "Truthy values (1, 'yes', non-empty string) are not accepted. "
            "This is a hard mutation boundary: wage statement Kakao dispatch "
            "requires explicit human approval."
        )

    # ── wage statement payload 검증 ──────────────────────────────
    if not isinstance(wage_statement_payload, dict):
        raise TypeError("wage_statement_payload must be a dict")
    if wage_statement_payload.get("contract_type") != "korea_wage_statement_pdf_v1":
        raise ValueError(
            "wage_statement_payload.contract_type must be 'korea_wage_statement_pdf_v1'. "
            "Pass the output of build_korea_wage_statement_pdf_payload()."
        )

    # ── 템플릿 변수 구성 ─────────────────────────────────────────
    employee_name = str(wage_statement_payload.get("employee_name") or "").strip()
    payment_date = str(wage_statement_payload.get("payment_date") or "").strip()
    period_start = str(wage_statement_payload.get("period_start") or "").strip()
    period_end = str(wage_statement_payload.get("period_end") or "").strip()
    net_pay = wage_statement_payload.get("net_pay", 0)

    if not employee_name:
        raise ValueError("wage_statement_payload.employee_name is required for Kakao notification")
    if not payment_date:
        raise ValueError("wage_statement_payload.payment_date is required for Kakao notification")
    if not period_start or not period_end:
        raise ValueError("wage_statement_payload.period_start/period_end are required for Kakao notification")

    period = f"{period_start} ~ {period_end}"
    net_pay_str = f"{int(net_pay):,}" if isinstance(net_pay, (int, float)) else str(net_pay)

    template_variables: dict[str, str] = {
        "employee_name": employee_name,
        "period": period,
        "payment_date": payment_date,
        "net_pay": net_pay_str,
    }

    # ── kakao_notification 모듈 사용 ────────────────────────────
    kakao = _load_kakao_module()

    kakao_payload = kakao.build_kakao_template_payload(
        recipient_phone=recipient_phone,
        template_code=WAGE_STATEMENT_TEMPLATE_CODE,
        variables=template_variables,
    )

    queue_item = kakao.build_kakao_send_queue_item(
        payload=kakao_payload,
        recipient_consent=recipient_consent,
        opted_out=opted_out,
        scheduled_at=scheduled_at,
        provider_key=provider_key,
        max_attempts=max_attempts,
    )

    # ── Phase 2-A: 실제 dispatch는 placeholder ───────────────────
    # Phase 2-D에서 아래 _PHASE_2D_PLACEHOLDER 블록을 교체합니다:
    #
    #   provider_dispatch = kakao.build_kakao_provider_dispatch_request(
    #       queue_item=queue_item,
    #       provider={"provider_key": provider_key, "provider_type": ..., "endpoint_key": ...},
    #       requested_at=frappe.utils.now_datetime().isoformat() + "+09:00",
    #   )
    #   return _call_kakao_provider(provider_dispatch)  # 실제 HTTP 호출
    #
    # Phase 2-A에서는 queue_item을 반환하며 dispatch는 하지 않습니다.
    # _PHASE_2D_PLACEHOLDER

    return {
        **queue_item,
        "wage_statement_source": wage_statement_payload.get("source_salary_slip"),
        "phase": "2-A-skeleton",
        "dispatch_pending": True,
        "dispatch_note": "Phase 2-D에서 실제 provider dispatch 구현 예정",
    }


def send_korea_wage_statement_kakao(
    *,
    salary_slip: dict[str, Any],
    human_approved: bool,
) -> dict[str, Any]:
    """임금명세서 카카오 발송 entrypoint — Phase 2-A stub.

    이 함수는 Phase 2-D에서 실제 구현이 완성됩니다.
    Phase 2-A에서는 human_approved 검증 및 payload 구성만 수행하고,
    실제 발송은 수행하지 않습니다.

    Parameters
    ----------
    salary_slip:
        Frappe Salary Slip 문서 dict (또는 dict-like).
        build_korea_wage_statement_pdf_payload()에 전달할 수 있는 형태여야 합니다.
    human_approved:
        반드시 bool True여야 합니다. fail-closed.

    Returns
    -------
    dict — {status: "pending_phase_2d", ...} 형태 응답.
    """

    # ── mutation boundary: human_approved는 반드시 bool True ──────
    if human_approved is not True:
        raise ValueError(
            "human_approved must be exactly True (bool). "
            "This is a hard mutation boundary: Kakao dispatch requires explicit human approval."
        )

    if not isinstance(salary_slip, dict):
        raise TypeError("salary_slip must be a dict")

    # Phase 2-D 구현 전 stub 응답
    return {
        "status": "pending_phase_2d",
        "runtime_action": "stub_no_send",
        "mutation_boundary": "no_send_no_provider_call_phase_2a_skeleton",
        "requires_phase_2d": True,
        "human_approved": True,
        "salary_slip_name": salary_slip.get("name"),
        "note": (
            "Phase 2-A: Kakao 발송 skeleton입니다. "
            "build_wage_statement_kakao_queue_item()로 queue item 구성은 가능합니다. "
            "실제 provider dispatch는 Phase 2-D에서 구현됩니다."
        ),
    }


__all__ = [
    "build_wage_statement_kakao_queue_item",
    "send_korea_wage_statement_kakao",
    "WAGE_STATEMENT_TEMPLATE_CODE",
    "WAGE_STATEMENT_TEMPLATE_BODY",
]
