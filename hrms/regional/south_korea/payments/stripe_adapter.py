"""Stripe 결제 게이트웨이 어댑터 — v2 stub.

실제 구현은 v2에서 stripe SDK를 설치한 후 아래 함수들을 채워넣는다:
    pip install stripe

환경 변수:
    STRIPE_SECRET_KEY   서버 사이드 시크릿 키
    STRIPE_WEBHOOK_SECRET  웹훅 검증용 시크릿

v2 체크리스트:
  - [ ] stripe.api_key = frappe.conf.stripe_secret_key
  - [ ] charge() → stripe.PaymentIntent.create(...)
  - [ ] create_customer() → stripe.Customer.create(...)
  - [ ] list_invoices() → stripe.Invoice.list(...)
  - [ ] webhook handler → stripe.Webhook.construct_event(...)
"""

from __future__ import annotations


def charge(
    *,
    subscription_id: str,
    amount_krw: int,
    currency: str = "KRW",
    customer_email: str,
    description: str = "",
) -> dict:
    """Stripe PaymentIntent 생성 후 즉시 결제.

    Args:
        subscription_id: 내부 구독 ID.
        amount_krw:      결제 금액 (KRW).
        currency:        통화 코드 (기본 "KRW").
        customer_email:  고객 이메일.
        description:     결제 설명.

    Returns:
        Stripe PaymentIntent 응답 dict.

    Raises:
        NotImplementedError: v2 미구현.
    """
    raise NotImplementedError(
        "stripe_adapter.charge는 v2에서 구현됩니다. "
        "dry_run=True 모드를 사용하세요."
    )


def create_customer(*, email: str, name: str, metadata: dict | None = None) -> dict:
    """Stripe Customer 생성.

    Raises:
        NotImplementedError: v2 미구현.
    """
    raise NotImplementedError("stripe_adapter.create_customer는 v2에서 구현됩니다.")


def cancel_subscription(*, stripe_subscription_id: str) -> dict:
    """Stripe Subscription 해지.

    Raises:
        NotImplementedError: v2 미구현.
    """
    raise NotImplementedError("stripe_adapter.cancel_subscription는 v2에서 구현됩니다.")


def list_invoices(*, stripe_customer_id: str, limit: int = 12) -> list[dict]:
    """Stripe 인보이스 목록 조회.

    Raises:
        NotImplementedError: v2 미구현.
    """
    raise NotImplementedError("stripe_adapter.list_invoices는 v2에서 구현됩니다.")
