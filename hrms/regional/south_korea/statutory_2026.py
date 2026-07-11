"""2026년 한국 법정 공제 정밀 계산. framework-free.

반올림/절사 규칙 (한국 실무 기준):
  - 국민연금: 원단위 절사 (int(x))
  - 건강보험: 원단위 절사 (int(x))
  - 장기요양보험: 10원 단위 절사 (int(x / 10) * 10)
  - 고용보험: 원단위 절사 (int(x))
  - 산재보험: 원단위 절사 (int(x))
  - 소득세: 원단위 절사 (int(x))
  - 지방세: 원단위 절사 (int(x))

출처 및 적용 기준:
  - 국민연금: 2026년 요율 각 4.75% (연금개혁 단계인상, §88③·published 노드 국민연금요율_2026). 상한 5,950,000 / 하한 380,000 (2025.7.1 기준, 매년 7월 갱신)
  - 건강보험: 2026년 요율 7.19% (근로자 3.595%, 사업주 3.595% — 시행령 §44①, published 노드 건강보험요율_2026)
  - 장기요양: 건강보험료의 12.95% (2026년 기준)
  - 고용보험: 2026년 실업급여 근로자 0.9%, 사업주 0.9%
  - 소득세: 국세청 근로소득 간이세액표 기반 (2026년 고시)
"""

from __future__ import annotations

import json
import math
import os
from typing import Any

# ---------------------------------------------------------------------------
# 2026년 요율 상수
# ---------------------------------------------------------------------------

# 국민연금 (National Pension)
PENSION_RATE_EMPLOYEE: float = 0.0475
PENSION_RATE_EMPLOYER: float = 0.0475
PENSION_MIN_BASE: int = 380_000   # 월 기준소득월액 하한 (2025.7.1 기준)
PENSION_MAX_BASE: int = 5_950_000  # 월 기준소득월액 상한 (2025.7.1 기준)

# 건강보험 (Health Insurance)
HEALTH_RATE_EMPLOYEE: float = 0.03595
HEALTH_RATE_EMPLOYER: float = 0.03595
LONGTERM_CARE_RATE: float = 0.1295  # 장기요양보험 = 건강보험료의 12.95%

# 고용보험 (Employment Insurance)
EMPLOYMENT_INSURANCE_RATE_EMPLOYEE: float = 0.009  # 실업급여 근로자 부담
EMPLOYMENT_INSURANCE_RATE_EMPLOYER_BASE: float = 0.009  # 실업급여 사업주 부담
# 고용안정/직업능력개발 사업주 추가 부담 (사업장 규모별)
EMPLOYMENT_INSURANCE_RATE_EMPLOYER_STABILITY_SMALL: float = 0.0025   # 150인 미만
EMPLOYMENT_INSURANCE_RATE_EMPLOYER_STABILITY_MEDIUM: float = 0.0045  # 150인 이상 우선지원대상
EMPLOYMENT_INSURANCE_RATE_EMPLOYER_STABILITY_LARGE: float = 0.0065   # 1000인 이상

# 지방소득세 (Local Income Tax)
LOCAL_INCOME_TAX_RATE: float = 0.10  # 소득세의 10%

# ---------------------------------------------------------------------------
# 내부 유틸리티
# ---------------------------------------------------------------------------

def _truncate(amount: float) -> int:
    """원단위 절사 (버림)."""
    return int(amount)


def _truncate_10(amount: float) -> int:
    """10원 단위 절사."""
    return int(amount / 10) * 10


# ---------------------------------------------------------------------------
# 국민연금
# ---------------------------------------------------------------------------

def calculate_pension(monthly_base: float) -> dict[str, Any]:
    """국민연금 계산.

    Args:
        monthly_base: 기준소득월액 (신고 월급여). 상한/하한 클리핑 내부 처리.

    Returns:
        {
            "base": 실제 적용 기준소득월액,
            "employee": 근로자 부담분 (원, 절사),
            "employer": 사업주 부담분 (원, 절사),
            "total": 합계,
        }
    """
    base = max(PENSION_MIN_BASE, min(PENSION_MAX_BASE, float(monthly_base)))
    employee = _truncate(base * PENSION_RATE_EMPLOYEE)
    employer = _truncate(base * PENSION_RATE_EMPLOYER)
    return {
        "base": base,
        "employee": employee,
        "employer": employer,
        "total": employee + employer,
    }


# ---------------------------------------------------------------------------
# 건강보험 + 장기요양보험
# ---------------------------------------------------------------------------

def calculate_health_insurance(monthly_base: float) -> dict[str, Any]:
    """건강보험 + 장기요양보험 계산.

    장기요양보험료는 '건강보험료(원단위 절사 후)' × 12.95%로 산출하고 10원 단위 절사.

    Args:
        monthly_base: 보수월액 (비과세 제외 월급여).

    Returns:
        {
            "health_employee": 건강보험 근로자,
            "health_employer": 건강보험 사업주,
            "longterm_care_employee": 장기요양 근로자,
            "longterm_care_employer": 장기요양 사업주,
            "total_employee": 근로자 합계,
            "total_employer": 사업주 합계,
        }
    """
    base = float(monthly_base)
    health_employee = _truncate(base * HEALTH_RATE_EMPLOYEE)
    health_employer = _truncate(base * HEALTH_RATE_EMPLOYER)

    # 장기요양보험: 건강보험료 기준, 10원 단위 절사
    longterm_employee = _truncate_10(health_employee * LONGTERM_CARE_RATE)
    longterm_employer = _truncate_10(health_employer * LONGTERM_CARE_RATE)

    return {
        "health_employee": health_employee,
        "health_employer": health_employer,
        "longterm_care_employee": longterm_employee,
        "longterm_care_employer": longterm_employer,
        "total_employee": health_employee + longterm_employee,
        "total_employer": health_employer + longterm_employer,
    }


# ---------------------------------------------------------------------------
# 고용보험
# ---------------------------------------------------------------------------

def calculate_employment_insurance(
    monthly_base: float,
    company_size: str = "small",
) -> dict[str, Any]:
    """고용보험 계산.

    Args:
        monthly_base: 월평균 보수.
        company_size: 사업장 규모.
            "small"  — 150인 미만 (고용안정 0.25%)
            "medium" — 150인 이상 우선지원대상기업 (0.45%)
            "large"  — 1,000인 이상 또는 국가·지자체 (0.65%)

    Returns:
        {
            "employee": 근로자 부담 (실업급여만),
            "employer_unemployment": 사업주 실업급여,
            "employer_stability": 고용안정/직업능력개발 (사업주),
            "employer_total": 사업주 합계,
        }
    """
    base = float(monthly_base)
    stability_map = {
        "small": EMPLOYMENT_INSURANCE_RATE_EMPLOYER_STABILITY_SMALL,
        "medium": EMPLOYMENT_INSURANCE_RATE_EMPLOYER_STABILITY_MEDIUM,
        "large": EMPLOYMENT_INSURANCE_RATE_EMPLOYER_STABILITY_LARGE,
    }
    if company_size not in stability_map:
        raise ValueError(
            f"company_size must be one of {list(stability_map)}; got {company_size!r}"
        )

    employee = _truncate(base * EMPLOYMENT_INSURANCE_RATE_EMPLOYEE)
    employer_unemployment = _truncate(base * EMPLOYMENT_INSURANCE_RATE_EMPLOYER_BASE)
    employer_stability = _truncate(base * stability_map[company_size])

    return {
        "employee": employee,
        "employer_unemployment": employer_unemployment,
        "employer_stability": employer_stability,
        "employer_total": employer_unemployment + employer_stability,
    }


# ---------------------------------------------------------------------------
# 산재보험
# ---------------------------------------------------------------------------

def calculate_industrial_accident_insurance(
    monthly_base: float,
    industry_rate: float = 0.0143,
) -> dict[str, Any]:
    """산재보험 계산. 사업주 100% 부담.

    Args:
        monthly_base: 월평균 보수.
        industry_rate: 업종별 요율 (기본값 1.43% — 전 업종 평균).

    Returns:
        {
            "employee": 0 (근로자 부담 없음),
            "employer": 사업주 부담,
            "rate_applied": 적용 요율,
        }
    """
    base = float(monthly_base)
    employer = _truncate(base * industry_rate)
    return {
        "employee": 0,
        "employer": employer,
        "rate_applied": industry_rate,
    }


# ---------------------------------------------------------------------------
# 소득세 (간이세액표)
# ---------------------------------------------------------------------------

def _load_income_tax_table() -> dict | None:
    """JSON 간이세액표 로드. 파일 없으면 None 반환."""
    data_path = os.path.join(
        os.path.dirname(__file__), "data", "income_tax_table_2026.json"
    )
    try:
        with open(data_path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _fallback_income_tax(monthly_taxable_income: float, dependents: int) -> int:
    """간이세액표 미제공 시 fallback 추정치.

    국세청 2026년 근로소득 간이세액표 대표 구간 (부양가족 수 1명 기준).
    부양가족이 추가될수록 세액 감소 (1명당 약 1만~2만원 수준).

    구간 경계: 하한 이상 ~ 상한 미만. 단위: 원.
    실제 표는 1만원 단위로 세분화되어 있으나 v1은 대표 구간만 사용.
    """
    # (하한, 상한, 부양1 세액)
    # 국세청 2026년 간이세액표 대표값 (실무 근사치)
    BRACKETS_DEP1 = [
        (0,         1_060_000,      0),
        (1_060_000, 1_500_000,  18_520),
        (1_500_000, 2_000_000,  30_680),
        (2_000_000, 2_500_000,  54_970),
        (2_500_000, 3_000_000,  95_700),
        (3_000_000, 3_500_000, 134_480),
        (3_500_000, 4_000_000, 176_930),
        (4_000_000, 4_500_000, 234_510),
        (4_500_000, 5_000_000, 295_750),
        (5_000_000, 5_500_000, 358_400),
        (5_500_000, 6_000_000, 421_050),
        (6_000_000, 7_000_000, 506_820),
        (7_000_000, 8_000_000, 660_260),
        (8_000_000, 9_000_000, 820_980),
        (9_000_000, 10_000_000, 981_700),
        (10_000_000, float("inf"), 1_200_000),
    ]

    # 부양가족 1명 기준 세액 추출
    base_tax = 0
    for lower, upper, tax in BRACKETS_DEP1:
        if lower <= monthly_taxable_income < upper:
            base_tax = tax
            break
    else:
        if monthly_taxable_income >= 10_000_000:
            base_tax = BRACKETS_DEP1[-1][2]

    # 부양가족 추가 시 세액 공제 (1인당 약 12,500원 감소, 실무 근사치)
    # 단, 기준 1명이므로 dependents >= 1
    dep_clamp = max(1, min(dependents, 11))  # 표 최대 11명
    extra_dep = dep_clamp - 1  # 1명 초과분
    deduction_per_dep = 12_500
    adjusted = base_tax - (extra_dep * deduction_per_dep)
    return max(0, _truncate(adjusted))


def _get_dep_tax(bracket: dict, dep_key: str) -> float:
    """부양가족 키 기준 세액 추출. 키 없으면 "1" 사용."""
    by_dep = bracket.get("by_dependents", {})
    raw = by_dep.get(dep_key)
    if raw is None:
        raw = by_dep.get("1", 0)
    return float(raw)


def _lookup_table_tax(
    table_data: dict,
    monthly_taxable_income: float,
    dependents: int,
) -> int | None:
    """JSON 간이세액표에서 세액 조회 (구간 내 선형 보간 적용).

    table_data 스키마:
        {
          "year": 2026,
          "brackets": [
            {
              "income_from": 0,
              "income_to": 1060000,
              "by_dependents": {"1": 0, "2": 0, ..., "7+": 0}
            },
            ...
          ]
        }

    구간 내 선형 보간:
        현 구간 하한에서의 세액 ~ 다음 구간 하한에서의 세액을 소득 비율로 보간.
        마지막 구간(상한 없음)은 보간 없이 구간 세액 그대로.
    """
    brackets = table_data.get("brackets")
    if not isinstance(brackets, list):
        return None

    dep_key = str(min(dependents, 7))
    if dependents >= 7:
        dep_key = "7+"

    for idx, bracket in enumerate(brackets):
        lower = bracket.get("income_from", 0)
        upper = bracket.get("income_to", float("inf"))
        if lower <= monthly_taxable_income < upper:
            tax_at_lower = _get_dep_tax(bracket, dep_key)

            # 다음 구간이 있고, 현 구간 세액이 0보다 크면 선형 보간 적용.
            # 현 구간 세액이 0인 경우(비과세 구간)는 보간 없이 0 반환.
            if idx + 1 < len(brackets) and tax_at_lower > 0:
                next_bracket = brackets[idx + 1]
                next_lower = next_bracket.get("income_from", upper)
                tax_at_next = _get_dep_tax(next_bracket, dep_key)
                span = float(next_lower - lower)
                if span > 0:
                    ratio = (monthly_taxable_income - lower) / span
                    interpolated = tax_at_lower + ratio * (tax_at_next - tax_at_lower)
                    return max(0, _truncate(interpolated))

            # 비과세 구간이거나 마지막 구간: 보간 없이 직접 반환
            return max(0, _truncate(tax_at_lower))
    return None


def calculate_income_tax(
    monthly_taxable_income: float,
    dependents: int = 1,
    children_under_8: int = 0,
    simplified_table_data: dict | None = None,
) -> dict[str, Any]:
    """간이세액표 기반 소득세 계산.

    Args:
        monthly_taxable_income: 월 과세 급여 (비과세 제외).
        dependents: 부양가족 수 (본인 포함, 최소 1).
        children_under_8: 8세 미만 자녀 수 (세액공제용, v1 미반영).
        simplified_table_data: 외부에서 전달하는 JSON 간이세액표.
            None이면 내부 파일에서 로드 시도 → 실패 시 fallback 사용.

    Returns:
        {
            "income_tax": 소득세 (원, 절사),
            "local_income_tax": 지방소득세 (원, 절사),
            "source": "table" | "fallback",
        }
    """
    income = float(monthly_taxable_income)
    dep = max(1, int(dependents))

    # 표 데이터 결정 순서: 인자 > 파일 > fallback
    table = simplified_table_data
    source = "table"
    if table is None:
        table = _load_income_tax_table()
    if table is None:
        source = "fallback"

    if source == "table":
        tax = _lookup_table_tax(table, income, dep)
        if tax is None:
            source = "fallback"
            tax = _fallback_income_tax(income, dep)
    else:
        tax = _fallback_income_tax(income, dep)

    local_tax = calculate_local_income_tax(tax)
    return {
        "income_tax": tax,
        "local_income_tax": local_tax,
        "source": source,
    }


# ---------------------------------------------------------------------------
# 지방소득세
# ---------------------------------------------------------------------------

def calculate_local_income_tax(income_tax: float) -> int:
    """지방소득세 = 소득세 × 10%, 원단위 절사."""
    return _truncate(float(income_tax) * LOCAL_INCOME_TAX_RATE)


# ---------------------------------------------------------------------------
# 통합 계산
# ---------------------------------------------------------------------------

def calculate_all_statutory(
    *,
    monthly_base: float,
    monthly_taxable_income: float | None = None,
    company_size: str = "small",
    industry_rate: float = 0.0143,
    dependents: int = 1,
    children_under_8: int = 0,
) -> dict[str, Any]:
    """전체 법정 공제 한 번에 계산.

    Args:
        monthly_base: 기준 월 급여 (국민연금/건강보험/고용보험/산재보험 기준).
        monthly_taxable_income: 과세 월 급여 (소득세 기준).
            None이면 monthly_base와 동일하게 처리.
        company_size: 고용보험 사업장 규모 ("small"/"medium"/"large").
        industry_rate: 산재보험 업종별 요율 (기본 1.43%).
        dependents: 소득세 부양가족 수 (본인 포함).
        children_under_8: 8세 미만 자녀 수.

    Returns:
        {
            "monthly_base": ...,
            "monthly_taxable_income": ...,
            "pension": {...},
            "health": {...},
            "employment_insurance": {...},
            "industrial_accident": {...},
            "income_tax": {...},
            "summary": {
                "employee_total_deduction": 근로자 총 공제액,
                "employer_total_contribution": 사업주 총 부담액,
            },
        }
    """
    taxable = float(monthly_taxable_income if monthly_taxable_income is not None else monthly_base)
    base = float(monthly_base)

    pension = calculate_pension(base)
    health = calculate_health_insurance(base)
    employment = calculate_employment_insurance(base, company_size)
    accident = calculate_industrial_accident_insurance(base, industry_rate)
    income = calculate_income_tax(
        taxable,
        dependents=dependents,
        children_under_8=children_under_8,
    )

    employee_deduction = (
        pension["employee"]
        + health["total_employee"]
        + employment["employee"]
        + income["income_tax"]
        + income["local_income_tax"]
    )
    employer_contribution = (
        pension["employer"]
        + health["total_employer"]
        + employment["employer_total"]
        + accident["employer"]
    )

    return {
        "monthly_base": base,
        "monthly_taxable_income": taxable,
        "pension": pension,
        "health": health,
        "employment_insurance": employment,
        "industrial_accident": accident,
        "income_tax": income,
        "summary": {
            "employee_total_deduction": employee_deduction,
            "employer_total_contribution": employer_contribution,
        },
    }
