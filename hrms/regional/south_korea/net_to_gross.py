"""NET(실수령액) → GROSS(세전 총액) 역산.

목표 실수령액을 만족하는 최소 세전 월급여를 이진 탐색으로 찾는다.
공제 규칙은 statutory_2026 엔진을 그대로 사용한다(요율 이중 정의 금지).

net(gross)은 절사·구간표 때문에 국소적으로 수 원 내려앉을 수 있어
이진 탐색으로 근방을 잡은 뒤 하한부터 선형 재확인으로 최소 gross를 확정한다.

framework-free — frappe 불요, importlib 직접 로드 가능.
"""

from __future__ import annotations

import importlib.util as _ilu
import pathlib as _pl
from typing import Any

_MODULE_DIR = _pl.Path(__file__).resolve().parent


def _load_statutory():
    spec = _ilu.spec_from_file_location(
        "_korea_statutory_2026_for_net", _MODULE_DIR / "statutory_2026.py"
    )
    module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_stat = _load_statutory()

# 이진 탐색 상한 배수: 근로자 공제 합계는 어떤 구간에서도 40% 미만이라
# gross ≤ target/0.6 이지만 여유를 두어 2배로 잡는다.
_SEARCH_UPPER_MULTIPLIER = 2.0
# 절사 경계의 국소 비단조(수 원 dip) 보정용 재확인 폭.
_LINEAR_RECHECK_WINDOW = 300


def _employee_deductions(
    gross: int,
    *,
    non_taxable: int,
    dependents: int,
    children_under_8: int,
    include_pension: bool,
    include_health: bool,
    include_longterm_care: bool,
    include_employment: bool,
    pension_override: int | None,
) -> dict[str, int]:
    """근로자 부담 공제 내역. 보험·소득세 기준액 = gross - 비과세."""
    base = max(0, int(gross) - int(non_taxable))

    pension = 0
    if include_pension:
        if pension_override is not None:
            pension = int(pension_override)
        elif base > 0:
            pension = _stat.calculate_pension(base)["employee"]

    health = 0
    longterm = 0
    if include_health and base > 0:
        h = _stat.calculate_health_insurance(base)
        health = h["health_employee"]
        if include_longterm_care:
            longterm = h["longterm_care_employee"]

    employment = 0
    if include_employment and base > 0:
        employment = _stat.calculate_employment_insurance(base)["employee"]

    income_tax = 0
    local_tax = 0
    if base > 0:
        tax = _stat.calculate_income_tax(
            base, dependents=dependents, children_under_8=children_under_8
        )
        income_tax = tax["income_tax"]
        local_tax = tax["local_income_tax"]

    total = pension + health + longterm + employment + income_tax + local_tax
    return {
        "pension": pension,
        "health": health,
        "longterm_care": longterm,
        "employment": employment,
        "income_tax": income_tax,
        "local_income_tax": local_tax,
        "total": total,
    }


def reverse_net_to_gross(
    target_net: Any,
    *,
    non_taxable: Any = 0,
    dependents: Any = 1,
    children_under_8: Any = 0,
    include_pension: bool = True,
    include_health: bool = True,
    include_longterm_care: bool = True,
    include_employment: bool = True,
    pension_override: Any = None,
) -> dict[str, Any]:
    """목표 실수령액을 만족하는 최소 세전 월급여를 찾는다.

    Args:
        target_net: 목표 실수령액 (원).
        non_taxable: 월 비과세액 (식대 등) — 보험·소득세 기준에서 제외.
        dependents: 부양가족 수 (본인 포함, 간이세액표 열).
        children_under_8: 8세 미만 자녀 수.
        include_pension: 국민연금 공제 여부 (60세 이상 등 제외 시 False).
        include_health: 건강보험 공제 여부. False면 장기요양도 함께 제외.
        include_longterm_care: 장기요양 공제 여부 (외국인 제외자 등).
        include_employment: 고용보험 공제 여부 (65세 이상 등 제외 시 False).
        pension_override: 국민연금 수동 입력액 (기준소득월액 결정 이력 등).

    Returns:
        {
            "gross": 최소 세전 총액(int),
            "achieved_net": gross 적용 시 실수령액(int),
            "target_net": 목표액(int),
            "diff": achieved_net - target_net (>= 0),
            "exact": achieved_net == target_net,
            "insurance_base": 보험·소득세 기준액(gross - 비과세),
            "non_taxable": 비과세액,
            "deductions": {pension, health, longterm_care, employment,
                           income_tax, local_income_tax, total},
        }

    Raises:
        ValueError: target_net이 양수가 아니거나 non_taxable이 음수일 때.
    """
    try:
        target = int(target_net)
    except (TypeError, ValueError):
        raise ValueError(f"target_net must be a positive integer; got {target_net!r}")
    if target <= 0:
        raise ValueError(f"target_net must be positive; got {target}")

    non_tax = int(non_taxable or 0)
    if non_tax < 0:
        raise ValueError(f"non_taxable must be >= 0; got {non_tax}")

    dep = max(1, int(dependents or 1))
    children = max(0, int(children_under_8 or 0))
    override = None if pension_override in (None, "", 0) else int(pension_override)

    opts = dict(
        non_taxable=non_tax,
        dependents=dep,
        children_under_8=children,
        include_pension=include_pension,
        include_health=include_health,
        include_longterm_care=include_longterm_care,
        include_employment=include_employment,
        pension_override=override,
    )

    def net_of(gross: int) -> int:
        return gross - _employee_deductions(gross, **opts)["total"]

    # 이진 탐색: net(g) >= target 을 만족하는 g의 근방을 찾는다.
    lo = target  # 공제 >= 0 이므로 gross >= net
    hi = max(int(target * _SEARCH_UPPER_MULTIPLIER), lo + non_tax + 1_000_000)
    while lo < hi:
        mid = (lo + hi) // 2
        if net_of(mid) >= target:
            hi = mid
        else:
            lo = mid + 1

    # 절사 경계 비단조 보정: 하한 아래 구간을 선형 재확인해 최소 gross 확정.
    best = lo
    start = max(target, lo - _LINEAR_RECHECK_WINDOW)
    for g in range(start, lo):
        if net_of(g) >= target:
            best = g
            break

    deductions = _employee_deductions(best, **opts)
    achieved = best - deductions["total"]

    return {
        "gross": int(best),
        "achieved_net": int(achieved),
        "target_net": target,
        "diff": int(achieved - target),
        "exact": achieved == target,
        "insurance_base": max(0, best - non_tax),
        "non_taxable": non_tax,
        "deductions": deductions,
    }
