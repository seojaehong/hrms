"""SaaS 구독 + 결제 sketch.

Framework-free 코어 — frappe를 import하지 않음.
Frappe adapter는 _api.py 참조.

dry_run=True (기본값):  인보이스 객체만 반환, 실제 결제 X
dry_run=False:          실제 Stripe/토스 charge → v2 구현 예정
human_approved 미통과:  PermissionError 즉시 raise
"""

from __future__ import annotations

import datetime as dt
import uuid

# ---------------------------------------------------------------------------
# 플랜 정의
# ---------------------------------------------------------------------------

PLAN_TIERS: dict[str, dict] = {
    "starter": {
        "name": "Starter (스타터)",
        "monthly_price_krw": 50_000,
        "max_employees": 10,
        "features": ["기본 HR", "한국 페이롤", "근태", "공휴일"],
    },
    "growth": {
        "name": "Growth (성장)",
        "monthly_price_krw": 150_000,
        "max_employees": 50,
        "features": ["+ 컴플라이언스 진단", "+ AI 챗봇", "+ 통합 검색", "+ 카카오 알림"],
    },
    "enterprise": {
        "name": "Enterprise",
        "monthly_price_krw": "협의",
        "max_employees": None,  # unlimited
        "features": ["+ 멀티 사이트", "+ SSO", "+ 전담 매니저", "+ SLA 99.9%"],
    },
}

PAYMENT_PROVIDERS: dict[str, dict] = {
    "stripe": {"name": "Stripe", "currencies": ["USD", "KRW"]},
    "toss": {"name": "토스페이먼츠", "currencies": ["KRW"]},
}

# 플랜당 초과 직원 요금 (KRW / 명 / 월)
OVERAGE_PRICE_PER_EMPLOYEE_KRW = 5_000


# ---------------------------------------------------------------------------
# 조회 헬퍼
# ---------------------------------------------------------------------------


def get_plan(tier: str) -> dict:
    """플랜 조회.

    Returns:
        플랜 dict (PLAN_TIERS의 shallow copy).

    Raises:
        ValueError: 존재하지 않는 tier.
    """
    if tier not in PLAN_TIERS:
        raise ValueError(f"알 수 없는 플랜: {tier!r}. 가능: {list(PLAN_TIERS)}")
    return dict(PLAN_TIERS[tier])


# ---------------------------------------------------------------------------
# 청구 계산
# ---------------------------------------------------------------------------


def calculate_monthly_invoice(
    *,
    tier: str,
    employee_count: int,
    period_start: dt.date,
    period_end: dt.date,
) -> dict:
    """월 청구액 계산.

    Enterprise 플랜은 가격이 "협의"이므로 base_amount=None, note 포함 반환.
    employee_count가 max_employees 초과 시 overage_amount 추가.

    Args:
        tier:            플랜 키 (starter / growth / enterprise).
        employee_count:  현재 활성 직원 수.
        period_start:    청구 시작일.
        period_end:      청구 종료일.

    Returns:
        {
            "tier": str,
            "period_start": str,
            "period_end": str,
            "employee_count": int,
            "base_amount_krw": int | None,
            "overage_count": int,
            "overage_amount_krw": int,
            "total_amount_krw": int | None,
            "currency": "KRW",
            "note": str | None,
        }
    """
    plan = get_plan(tier)
    price = plan["monthly_price_krw"]
    max_emp: int | None = plan["max_employees"]

    if isinstance(price, str):
        # Enterprise: 협의
        return {
            "tier": tier,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "employee_count": employee_count,
            "base_amount_krw": None,
            "overage_count": 0,
            "overage_amount_krw": 0,
            "total_amount_krw": None,
            "currency": "KRW",
            "note": "Enterprise 플랜은 별도 협의가 필요합니다. 담당 매니저에게 문의하세요.",
        }

    overage_count = max(0, employee_count - max_emp) if max_emp is not None else 0
    overage_amount = overage_count * OVERAGE_PRICE_PER_EMPLOYEE_KRW
    base_amount = int(price)
    total_amount = base_amount + overage_amount

    return {
        "tier": tier,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "employee_count": employee_count,
        "base_amount_krw": base_amount,
        "overage_count": overage_count,
        "overage_amount_krw": overage_amount,
        "total_amount_krw": total_amount,
        "currency": "KRW",
        "note": f"초과 {overage_count}명 × {OVERAGE_PRICE_PER_EMPLOYEE_KRW:,}원" if overage_count else None,
    }


# ---------------------------------------------------------------------------
# 구독 관리 (dry_run 전용 — 실제 결제는 v2)
# ---------------------------------------------------------------------------


def initiate_subscription(
    *,
    company: str,
    tier: str,
    payment_method: str,
    billing_email: str,
    human_approved: bool,
    dry_run: bool = True,
) -> dict:
    """구독 시작.

    dry_run=True:  인보이스만 생성, 결제 X
    dry_run=False: 실제 Stripe/토스 charge (v2 — NotImplementedError)

    Args:
        company:        Frappe Company 이름.
        tier:           플랜 키.
        payment_method: "stripe" | "toss".
        billing_email:  청구서 수신 이메일.
        human_approved: True가 아니면 PermissionError.
        dry_run:        False이면 실제 결제 시도 (현재 v2 미구현).

    Returns:
        {
            "status": "dry_run" | "initiated",
            "subscription_id": str,
            "company": str,
            "tier": str,
            "payment_method": str,
            "billing_email": str,
            "invoice": dict,   # calculate_monthly_invoice 결과
            "dry_run": bool,
            "message": str,
        }

    Raises:
        PermissionError: human_approved가 False.
        ValueError:      잘못된 tier 또는 payment_method.
        NotImplementedError: dry_run=False (v2 미구현).
    """
    _require_human_approved(human_approved, "initiate_subscription")
    get_plan(tier)  # 존재 여부 검증
    _validate_payment_method(payment_method)

    today = dt.date.today()
    period_start = today.replace(day=1)
    # 다음 달 1일 - 1일 = 이번 달 마지막 날
    next_month = (period_start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    period_end = next_month - dt.timedelta(days=1)

    invoice = calculate_monthly_invoice(
        tier=tier,
        employee_count=0,  # 신규 구독이므로 직원 0명으로 초기 인보이스
        period_start=period_start,
        period_end=period_end,
    )

    subscription_id = f"KR-SUB-{uuid.uuid4().hex[:12].upper()}"

    if not dry_run:
        _charge_payment(subscription_id, payment_method, invoice)  # v2에서 구현

    return {
        "status": "dry_run" if dry_run else "initiated",
        "subscription_id": subscription_id,
        "company": company,
        "tier": tier,
        "payment_method": payment_method,
        "billing_email": billing_email,
        "invoice": invoice,
        "dry_run": dry_run,
        "message": (
            "[DRY RUN] 인보이스가 생성되었습니다. 실제 결제는 이루어지지 않았습니다."
            if dry_run
            else "구독이 시작되었습니다."
        ),
    }


def cancel_subscription(*, subscription_id: str, human_approved: bool) -> dict:
    """구독 해지.

    Args:
        subscription_id: 구독 ID.
        human_approved:  True가 아니면 PermissionError.

    Returns:
        {"status": "cancelled", "subscription_id": str, "cancelled_at": str}

    Raises:
        PermissionError: human_approved가 False.
    """
    _require_human_approved(human_approved, "cancel_subscription")

    return {
        "status": "cancelled",
        "subscription_id": subscription_id,
        "cancelled_at": dt.datetime.utcnow().isoformat() + "Z",
        "message": "구독이 해지되었습니다. 현재 청구 기간 종료 시까지 서비스가 유지됩니다.",
    }


def upgrade_downgrade(
    *, subscription_id: str, new_tier: str, human_approved: bool
) -> dict:
    """플랜 변경 (업그레이드 / 다운그레이드).

    Args:
        subscription_id: 구독 ID.
        new_tier:        변경할 플랜 키.
        human_approved:  True가 아니면 PermissionError.

    Returns:
        {"status": "plan_changed", "subscription_id": str, "new_tier": str, "changed_at": str}

    Raises:
        PermissionError: human_approved가 False.
        ValueError:      존재하지 않는 new_tier.
    """
    _require_human_approved(human_approved, "upgrade_downgrade")
    get_plan(new_tier)  # 존재 여부 검증

    return {
        "status": "plan_changed",
        "subscription_id": subscription_id,
        "new_tier": new_tier,
        "changed_at": dt.datetime.utcnow().isoformat() + "Z",
        "message": f"플랜이 '{PLAN_TIERS[new_tier]['name']}'(으)로 변경되었습니다.",
    }


def list_invoices(*, company: str, limit: int = 12) -> list[dict]:
    """청구 history.

    v2에서 DB 연동 예정. 현재는 빈 리스트 반환 (dry_run 환경).

    Args:
        company: Frappe Company 이름.
        limit:   최대 반환 건수 (기본 12).

    Returns:
        인보이스 dict 리스트 (최신순).
    """
    # v2: frappe.db.get_all("Korea Subscription Invoice", filters={"company": company}, ...)
    return []


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _require_human_approved(human_approved: bool, operation: str) -> None:
    """human_approved 미통과 시 PermissionError."""
    if not human_approved:
        raise PermissionError(
            f"{operation}은(는) 관리자의 명시적 승인(human_approved=True)이 필요합니다."
        )


def _validate_payment_method(payment_method: str) -> None:
    """지원하지 않는 결제 수단이면 ValueError."""
    if payment_method not in PAYMENT_PROVIDERS:
        raise ValueError(
            f"지원하지 않는 결제 수단: {payment_method!r}. "
            f"가능: {list(PAYMENT_PROVIDERS)}"
        )


def _charge_payment(
    subscription_id: str, payment_method: str, invoice: dict
) -> None:
    """실제 결제 호출 (v2 전용).

    현재 NotImplementedError — v2에서 stripe_adapter / toss_adapter 연결 예정.
    실제 결제가 필요하면 payments/ 어댑터를 직접 import하여 사용.
    """
    if payment_method == "stripe":
        raise NotImplementedError(
            "Stripe 결제는 v2에서 구현됩니다. "
            "payments/stripe_adapter.py의 charge()를 구현하세요."
        )
    elif payment_method == "toss":
        raise NotImplementedError(
            "토스페이먼츠 결제는 v2에서 구현됩니다. "
            "payments/toss_adapter.py의 charge()를 구현하세요."
        )
    else:
        raise ValueError(f"알 수 없는 결제 수단: {payment_method!r}")
