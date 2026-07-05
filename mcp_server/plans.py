# Korea HRMS 플랜 티어 — AI 사용 쿼터·과금의 단일 정의 (S2 과금 연결).
#
# 레지스트리(multi_site.json)의 tenants[].plan 과 토큰 발급(issue_token.py),
# 쿼터 강제(http_server.py), 월간 리포트(usage_report.py)가 모두 이 정의를 쓴다.

from __future__ import annotations

PLANS: dict[str, dict] = {
    "starter": {
        "label": "스타터",
        "ai_daily_limit": 200,
        "monthly_price_krw": 0,  # 베타 기간 무료 — 확정 시 갱신
    },
    "professional": {
        "label": "프로페셔널",
        "ai_daily_limit": 2000,
        "monthly_price_krw": 99000,
    },
    "enterprise": {
        "label": "엔터프라이즈",
        "ai_daily_limit": 20000,
        "monthly_price_krw": 299000,
    },
}

DEFAULT_PLAN = "starter"


def plan_daily_limit(plan: str | None) -> int:
    return PLANS.get(plan or DEFAULT_PLAN, PLANS[DEFAULT_PLAN])["ai_daily_limit"]
