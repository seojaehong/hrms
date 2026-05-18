"""5인 미만 사업장 룰 엔진. framework-free.

근로기준법 시행령 제7조 및 별표 1 기준 (2024년 기준).

workplace_profile 스키마:
    headcount: int
        상시근로자수 직접 입력. 존재하면 monthly_employee_counts 보다 우선.
    monthly_employee_counts: list[int]
        월말 인원 목록 (최대 12개). 평균을 계산하여 상시근로자수로 사용.
        가장 보수적인 방식 — 직전 연도 12개월 평균.
    company: str (optional)
        감사/로깅 용도.
    branch: str (optional)
        감사/로깅 용도.
    as_of: str (optional)
        ISO 날짜 (예: "2026-05-01"). 판정 기준일.

headcount 와 monthly_employee_counts 모두 없으면 ValueError 발생.

payroll_component 스키마 (filter_payroll_for_small_workplace 입력):
    code: str
        가산수당 판별 키. OVERTIME_PREMIUM_CODES 에 있으면 제외.
    기타 필드는 그대로 통과.

leave_allocation 스키마 (filter_leave_allocations_for_small_workplace 입력):
    leave_type_key: str
        휴가 종류 키. EXEMPT_LEAVE_KEYS 에 있으면 제외.
    기타 필드는 그대로 통과.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 조항 사전
# ---------------------------------------------------------------------------

# 5인 미만 적용 제외 조항 (근기법 시행령 별표 1)
EXEMPT_PROVISIONS: dict[str, str] = {
    "interruption_pay": "근기법 제46조 (휴업수당)",
    "unfair_dismissal_remedy": "근기법 제28조 (부당해고 구제신청)",
    "overtime_premium": "근기법 제56조 (연장·야간·휴일 가산수당)",
    "annual_paid_leave": "근기법 제60조 (연차 유급휴가)",
    "menstruation_leave": "근기법 제73조 (생리휴가)",
    "weekly_work_hour_limit": "근기법 제53조 (주 12시간 연장 한도) — 일부",
}

# 5인 미만에도 적용되는 조항
ALWAYS_APPLY_PROVISIONS: dict[str, str] = {
    "wage_regular_payment": "근기법 제43조 (임금 정기 지급)",
    "minimum_wage": "최저임금법",
    "severance_pay": "근로자퇴직급여 보장법 제8조 (퇴직금, 1년 이상 근로)",
    "weekly_holiday": "근기법 제55조 (주휴일)",
    "maternity_protection": "근기법 제74조 (임산부 보호)",
    "industrial_accident_insurance": "산업재해보상보험법",
}

# 페이롤 가산수당 코드 (filter_payroll_for_small_workplace 사용)
# overtime_premium 적용 제외에 해당하는 페이롤 컴포넌트 코드 목록
OVERTIME_PREMIUM_CODES: frozenset[str] = frozenset(
    {
        "overtime_premium",       # 연장근로 가산수당
        "night_premium",          # 야간근로 가산수당
        "holiday_premium",        # 휴일근로 가산수당
        "overtime_allowance",     # 연장수당 (별칭)
        "night_allowance",        # 야간수당 (별칭)
        "holiday_allowance",      # 휴일수당 (별칭)
    }
)

# 휴가 배정 제외 키 (filter_leave_allocations_for_small_workplace 사용)
EXEMPT_LEAVE_KEYS: frozenset[str] = frozenset(
    {
        "annual_paid_leave",    # 연차 유급휴가 (근기법 60조)
        "menstruation_leave",   # 생리휴가 (근기법 73조)
    }
)

# ---------------------------------------------------------------------------
# 상시근로자수 판정
# ---------------------------------------------------------------------------

SMALL_WORKPLACE_THRESHOLD = 5  # 5인 미만 = headcount < 5


def _compute_effective_headcount(workplace_profile: dict) -> int:
    """workplace_profile 에서 실효 상시근로자수를 계산한다.

    우선순위:
    1. headcount (직접 입력)
    2. monthly_employee_counts 평균 (소수점 버림 — 가장 보수적)

    둘 다 없으면 ValueError.
    """
    if "headcount" in workplace_profile:
        value = workplace_profile["headcount"]
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"headcount 는 0 이상의 숫자여야 합니다. 입력값: {value!r}")
        return int(value)

    monthly = workplace_profile.get("monthly_employee_counts")
    if monthly is not None:
        if not isinstance(monthly, (list, tuple)) or len(monthly) == 0:
            raise ValueError("monthly_employee_counts 는 비어있지 않은 리스트여야 합니다.")
        avg = sum(monthly) / len(monthly)
        return int(avg)  # 소수점 버림 (보수적)

    raise ValueError(
        "workplace_profile 에 headcount 또는 monthly_employee_counts 가 필요합니다."
    )


def is_small_workplace(workplace_profile: dict) -> bool:
    """5인 미만 사업장 여부 판정.

    상시근로자수 < 5  → True  (5인 미만, 일부 조항 적용 제외)
    상시근로자수 >= 5 → False (5인 이상, 근기법 전면 적용)

    상시근로자수 계산:
    - headcount 직접 입력 시 우선 사용
    - monthly_employee_counts 제공 시 월평균으로 계산 (소수점 버림)

    Args:
        workplace_profile: 사업장 프로필 dict. 스키마는 모듈 docstring 참조.

    Returns:
        True if 상시근로자수 < 5, else False.
    """
    return _compute_effective_headcount(workplace_profile) < SMALL_WORKPLACE_THRESHOLD


# ---------------------------------------------------------------------------
# 조항별 적용 여부 판정
# ---------------------------------------------------------------------------

def evaluate_provision(
    *,
    workplace_profile: dict,
    provision_key: str,
) -> dict:
    """특정 조항의 5인 미만 적용 여부 판정.

    Args:
        workplace_profile: 사업장 프로필 dict.
        provision_key: 조항 키. EXEMPT_PROVISIONS 또는 ALWAYS_APPLY_PROVISIONS 에 있어야 함.

    Returns:
        {
            "provision_key": str,
            "law": str,          # 법 조항 설명
            "applies": bool,     # True = 이 사업장에 해당 조항 적용됨
            "reason": str,       # "small_workplace_exempt" | "always_applies" | "above_5"
        }

    Raises:
        ValueError: provision_key 가 알 수 없는 키인 경우.
    """
    all_known = {**EXEMPT_PROVISIONS, **ALWAYS_APPLY_PROVISIONS}
    if provision_key not in all_known:
        raise ValueError(
            f"알 수 없는 provision_key: {provision_key!r}. "
            f"알 수 있는 키: {sorted(all_known)}"
        )

    law = all_known[provision_key]

    # 항상 적용되는 조항
    if provision_key in ALWAYS_APPLY_PROVISIONS:
        return {
            "provision_key": provision_key,
            "law": law,
            "applies": True,
            "reason": "always_applies",
        }

    # 적용 제외 가능 조항 — 사업장 규모 판정
    small = is_small_workplace(workplace_profile)

    if small:
        return {
            "provision_key": provision_key,
            "law": law,
            "applies": False,
            "reason": "small_workplace_exempt",
        }
    else:
        return {
            "provision_key": provision_key,
            "law": law,
            "applies": True,
            "reason": "above_5",
        }


# ---------------------------------------------------------------------------
# 페이롤 필터
# ---------------------------------------------------------------------------

def filter_payroll_for_small_workplace(
    *,
    workplace_profile: dict,
    payroll_components: list[dict],
) -> dict:
    """페이롤 항목 중 5인 미만 적용 제외 항목(연장·야간·휴일 가산수당) 제거.

    가산수당 판별 기준: 각 컴포넌트의 ``code`` 필드가 OVERTIME_PREMIUM_CODES 에 포함되는지 여부.

    Args:
        workplace_profile: 사업장 프로필 dict.
        payroll_components: 페이롤 컴포넌트 list. 각 dict 는 ``code`` 필드를 가져야 함.

    Returns:
        {
            "applied_components": list[dict],   # 적용 컴포넌트
            "excluded_components": list[dict],  # 제외된 컴포넌트 (가산수당)
            "reason": str,
        }
    """
    if not is_small_workplace(workplace_profile):
        return {
            "applied_components": list(payroll_components),
            "excluded_components": [],
            "reason": "above_5_all_components_applied",
        }

    applied: list[dict] = []
    excluded: list[dict] = []

    for component in payroll_components:
        code = component.get("code", "")
        if code in OVERTIME_PREMIUM_CODES:
            excluded.append(component)
        else:
            applied.append(component)

    return {
        "applied_components": applied,
        "excluded_components": excluded,
        "reason": "small_workplace_exempt_overtime_premium",
    }


# ---------------------------------------------------------------------------
# 휴가 배정 필터
# ---------------------------------------------------------------------------

def filter_leave_allocations_for_small_workplace(
    *,
    workplace_profile: dict,
    leave_allocations: list[dict],
) -> dict:
    """휴가 배정 중 5인 미만 적용 제외 항목(연차·생리휴가) 제거.

    휴가 종류 판별 기준: 각 배정의 ``leave_type_key`` 필드가 EXEMPT_LEAVE_KEYS 에 포함되는지 여부.

    Args:
        workplace_profile: 사업장 프로필 dict.
        leave_allocations: 휴가 배정 list. 각 dict 는 ``leave_type_key`` 필드를 가져야 함.

    Returns:
        {
            "applied_allocations": list[dict],   # 적용 배정
            "excluded_allocations": list[dict],  # 제외된 배정
            "reason": str,
        }
    """
    if not is_small_workplace(workplace_profile):
        return {
            "applied_allocations": list(leave_allocations),
            "excluded_allocations": [],
            "reason": "above_5_all_allocations_applied",
        }

    applied: list[dict] = []
    excluded: list[dict] = []

    for allocation in leave_allocations:
        key = allocation.get("leave_type_key", "")
        if key in EXEMPT_LEAVE_KEYS:
            excluded.append(allocation)
        else:
            applied.append(allocation)

    return {
        "applied_allocations": applied,
        "excluded_allocations": excluded,
        "reason": "small_workplace_exempt_leave",
    }


# ---------------------------------------------------------------------------
# 적용 법령 요약
# ---------------------------------------------------------------------------

def get_applicable_law_summary(workplace_profile: dict) -> dict:
    """5인 미만 / 5인 이상 적용 법령 요약.

    Args:
        workplace_profile: 사업장 프로필 dict.

    Returns:
        {
            "is_small_workplace": bool,
            "headcount": int,
            "exempt_provisions": list[dict],      # 적용 제외 조항 (5인 미만만 존재)
            "always_applicable": list[dict],       # 항상 적용 조항
            "legal_summary": str,                  # 사람이 읽을 수 있는 한국어 요약
        }
    """
    headcount = _compute_effective_headcount(workplace_profile)
    small = headcount < SMALL_WORKPLACE_THRESHOLD

    always_applicable = [
        {"key": k, "law": v} for k, v in ALWAYS_APPLY_PROVISIONS.items()
    ]

    if small:
        exempt_provisions = [
            {"key": k, "law": v} for k, v in EXEMPT_PROVISIONS.items()
        ]
        legal_summary = (
            f"상시근로자수 {headcount}인으로 5인 미만 사업장에 해당합니다. "
            f"근로기준법 시행령 제7조 및 별표 1에 따라 "
            f"휴업수당(46조), 부당해고 구제신청(28조), "
            f"연장·야간·휴일 가산수당(56조), 연차 유급휴가(60조), "
            f"생리휴가(73조), 주 12시간 연장 한도(53조 일부)는 적용되지 않습니다. "
            f"임금 정기 지급, 최저임금, 퇴직금(1년 이상), 주휴일, "
            f"임산부 보호, 산재보험은 계속 적용됩니다."
        )
    else:
        exempt_provisions = []
        legal_summary = (
            f"상시근로자수 {headcount}인으로 5인 이상 사업장에 해당합니다. "
            f"근로기준법 전면 적용 대상입니다."
        )

    return {
        "is_small_workplace": small,
        "headcount": headcount,
        "exempt_provisions": exempt_provisions,
        "always_applicable": always_applicable,
        "legal_summary": legal_summary,
    }
