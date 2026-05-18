"""토스페이먼츠 결제 게이트웨이 어댑터 — v2 stub.

실제 구현은 v2에서 토스페이먼츠 API를 직접 HTTP 호출로 연동한다
(별도 SDK 없음 — requests 사용).

토스페이먼츠 API 문서:
    https://docs.tosspayments.com/reference

환경 변수:
    TOSS_SECRET_KEY     시크릿 키 (sk_test_... or sk_live_...)
    TOSS_WIDGET_CLIENT_KEY  위젯 클라이언트 키

v2 체크리스트:
  - [ ] POST /v1/payments/confirm → charge()
  - [ ] GET  /v1/payments?orderId=... → list_invoices()
  - [ ] POST /v1/payments/{paymentKey}/cancel → cancel_payment()
  - [ ] 웹훅 검수 신청 후 핸들러 연결
  - [ ] Basic Auth: base64(secret_key + ":")
"""

from __future__ import annotations


def charge(
    *,
    subscription_id: str,
    amount_krw: int,
    order_name: str,
    customer_email: str,
    customer_name: str,
    payment_key: str | None = None,
) -> dict:
    """토스페이먼츠 결제 승인.

    Args:
        subscription_id: 내부 구독 ID (orderId 생성에 사용).
        amount_krw:      결제 금액 (KRW, 원화).
        order_name:      주문명 (예: "HRMS Growth 플랜 구독").
        customer_email:  고객 이메일.
        customer_name:   고객명.
        payment_key:     프론트엔드에서 받은 paymentKey.

    Returns:
        토스 결제 응답 dict.

    Raises:
        NotImplementedError: v2 미구현.
    """
    raise NotImplementedError(
        "toss_adapter.charge는 v2에서 구현됩니다. "
        "dry_run=True 모드를 사용하세요."
    )


def cancel_payment(*, payment_key: str, cancel_reason: str = "고객 요청") -> dict:
    """토스페이먼츠 결제 취소.

    Raises:
        NotImplementedError: v2 미구현.
    """
    raise NotImplementedError("toss_adapter.cancel_payment는 v2에서 구현됩니다.")


def list_invoices(*, order_id_prefix: str, limit: int = 12) -> list[dict]:
    """토스페이먼츠 결제 내역 조회.

    Raises:
        NotImplementedError: v2 미구현.
    """
    raise NotImplementedError("toss_adapter.list_invoices는 v2에서 구현됩니다.")
