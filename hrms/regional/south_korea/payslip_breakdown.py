# -*- coding: utf-8 -*-
"""임금명세서 산정내역 분해 생성기 — 근로기준법 §48②(임금명세서) 엔진화.

개인 스킬 `~/.claude/skills/명세서생성/`의 산정내역 분해 사상("각 항목의 계산방법을
검산 가능한 문자열로 명시")을 프레임워크 비의존 엔진 모듈로 이식한다. 스킬은
읽기 전용 참고자료이며, 사업장별 커스텀(디자인·엑셀 자동화)은 이식 대상이 아니다.

이 모듈은 새 조립 모듈이다 — 계산 코어(hourly_wage.py, statutory_2026.py)는
확장하지 않고 그대로 재사용한다. overtime_premium.py의 가산 배수(1.5/0.5/1.5)는
이 모듈에도 DI 원칙에 따라 상수로 재정의한다(hourly_wage.py의 선례와 동일).

법정 요건(근로기준법 시행령 §27조의2, §48②):
    ① 임금 구성항목별 금액
    ② 구성항목별 계산방법 ("계산방법 문자열" — 이 모듈의 핵심 산출물)
    ③ 공제내역(항목·금액·산출근거)
    ④ 실지급액

frappe 의존 없음 → `python3 hrms/tests/test_korea_payslip_breakdown.py` 직접 실행 검증 가능.
금액은 전부 정수 원(ROUND_HALF_UP). Decimal 기반 계산, 원 단위 확정은 이 모듈에서 1회.
"""
from __future__ import annotations

import importlib.util as _ilu
import pathlib as _pl
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

_MODULE_DIR = _pl.Path(__file__).resolve().parent


def _load_core(name: str):
    """sibling framework-free 모듈을 파일 경로로 직접 로드 (hourly_wage_api.py 컨벤션).

    `hrms/__init__.py`가 frappe를 import하므로 패키지 import 대신 이 방식을 쓴다.
    """
    path = _MODULE_DIR / f"{name}.py"
    spec = _ilu.spec_from_file_location(f"_korea_payslip_breakdown_{name}", path)
    module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_hourly = _load_core("hourly_wage")
_statutory = _load_core("statutory_2026")

# §56 가산 배수 — overtime_premium.py/hourly_wage.py와 동일 값을 DI 원칙에 따라 재정의.
MULTIPLIER_OVERTIME = Decimal("1.5")
MULTIPLIER_NIGHT_ADDEND = Decimal("0.5")
MULTIPLIER_HOLIDAY = Decimal("1.5")

_WAGE_TYPES = ("monthly", "hourly")


def build_payslip_breakdown(
    *,
    employee: str,
    period: str,
    payment_date: str,
    wage_type: str,
    base_salary: Any = None,
    hourly_rate: Any = None,
    regular_hours: Any = 0,
    contracted_weekly_hours: Any = None,
    perfect_attendance: bool = True,
    weeks_per_month: Any = None,
    overtime_hours: Any = 0,
    night_hours: Any = 0,
    holiday_work_hours: Any = 0,
    annual_leave_hours: Any = 0,
    extra_earnings: list[dict[str, Any]] | None = None,
    monthly_taxable_income: Any = None,
    insurance_base: Any = None,
    company_size: str = "small",
    industry_rate: Any = 0.0143,
    dependents: int = 1,
    children_under_8: int = 0,
) -> dict[str, Any]:
    """임금명세서 산정내역(earnings) + 공제(deductions) 분해 payload를 구성한다.

    wage_type="monthly": 기본급(base_salary) + 고정 계약. 209h 월 소정근로가
        주휴를 이미 포함하므로 별도 주휴 라인은 만들지 않는다.
    wage_type="hourly": 시급(hourly_rate) × 근로시간 버킷 + 별도 주휴수당 라인.

    두 모드 공통으로 연장(1.5)/야간(0.5 가산)/휴일(1.5)/연차수당 시간 버킷을
    받아 통상시급 기준으로 가산 계산하고, 각 항목에 검산 가능한 계산방법
    문자열(basis)을 반드시 채운다.

    공제는 `statutory_2026.calculate_all_statutory`를 그대로 재사용한다.

    Returns:
        {
            "employee", "period", "payment_date", "wage_type",
            "earnings": [{"label", "amount", "basis"}...],
            "gross_pay": int,
            "deductions": [{"label", "amount", "basis"}...],
            "total_deductions": int,
            "net_pay": int,
            "compliance": {"compliant": bool, "missing_basis_labels": [...]},
        }
    """
    employee = _require_text(employee, "employee")
    period = _require_text(period, "period")
    payment_date = _require_text(payment_date, "payment_date")
    if wage_type not in _WAGE_TYPES:
        raise ValueError(f"wage_type must be one of {_WAGE_TYPES}; got {wage_type!r}")

    weeks_used = (
        _dec(weeks_per_month, "weeks_per_month")
        if weeks_per_month is not None
        else _hourly.AVG_WEEKS_PER_MONTH
    )

    earnings: list[dict[str, Any]] = []

    if wage_type == "monthly":
        if base_salary is None:
            raise ValueError("base_salary is required when wage_type='monthly'")
        base = _dec(base_salary, "base_salary")
        if base < 0:
            raise ValueError("base_salary must be >= 0")
        rate = _hourly.ordinary_hourly_wage(base)
        earnings.append(
            {
                "label": "기본급",
                "amount": _round_won(base),
                "basis": (
                    f"월 소정근로 {_fmt_hours(_hourly.MONTHLY_ORDINARY_HOURS)}h × "
                    f"통상시급 {_fmt_won(rate)}원"
                ),
            }
        )
    else:
        if hourly_rate is None:
            raise ValueError("hourly_rate is required when wage_type='hourly'")
        if contracted_weekly_hours is None:
            raise ValueError("contracted_weekly_hours is required when wage_type='hourly'")
        rate = _dec(hourly_rate, "hourly_rate")
        if rate < 0:
            raise ValueError("hourly_rate must be >= 0")
        reg_hours = _dec(regular_hours, "regular_hours")
        if reg_hours < 0:
            raise ValueError("regular_hours must be >= 0")
        if reg_hours > 0:
            earnings.append(
                {
                    "label": "기본급",
                    "amount": _round_won(reg_hours * rate),
                    "basis": f"{_fmt_hours(reg_hours)}h × {_fmt_won(rate)}원",
                }
            )

        weekly_allowance = _hourly.monthly_weekly_holiday_allowance(
            contracted_weekly_hours=contracted_weekly_hours,
            hourly_rate=rate,
            perfect_attendance=perfect_attendance,
            weeks_per_month=weeks_used,
        )
        if weekly_allowance:
            weekly_hours = _hourly.weekly_holiday_hours(contracted_weekly_hours)
            total_hours = weekly_hours * weeks_used
            earnings.append(
                {
                    "label": "주휴수당",
                    "amount": weekly_allowance,
                    "basis": (
                        f"주{_fmt_hours(_dec(contracted_weekly_hours, 'contracted_weekly_hours'))}h "
                        f"계약 → 주휴 {_fmt_hours(weekly_hours)}h × {_fmt_hours(weeks_used)}주 "
                        f"× {_fmt_won(rate)}원 = {_fmt_hours(total_hours)}h 환산"
                    ),
                }
            )

    ot_hours = _dec(overtime_hours, "overtime_hours")
    if ot_hours > 0:
        earnings.append(
            {
                "label": "연장근로수당",
                "amount": _round_won(ot_hours * rate * MULTIPLIER_OVERTIME),
                "basis": f"{_fmt_hours(ot_hours)}h × {_fmt_won(rate)}원 × 1.5",
            }
        )

    ni_hours = _dec(night_hours, "night_hours")
    if ni_hours > 0:
        earnings.append(
            {
                "label": "야간근로수당",
                "amount": _round_won(ni_hours * rate * MULTIPLIER_NIGHT_ADDEND),
                "basis": f"{_fmt_hours(ni_hours)}h × {_fmt_won(rate)}원 × 0.5(가산분)",
            }
        )

    hol_hours = _dec(holiday_work_hours, "holiday_work_hours")
    if hol_hours > 0:
        earnings.append(
            {
                "label": "휴일근로수당",
                "amount": _round_won(hol_hours * rate * MULTIPLIER_HOLIDAY),
                "basis": f"{_fmt_hours(hol_hours)}h × {_fmt_won(rate)}원 × 1.5",
            }
        )

    leave_hours = _dec(annual_leave_hours, "annual_leave_hours")
    if leave_hours > 0:
        earnings.append(
            {
                "label": "연차수당",
                "amount": _round_won(leave_hours * rate),
                "basis": f"{_fmt_hours(leave_hours)}h × {_fmt_won(rate)}원",
            }
        )

    for index, extra in enumerate(extra_earnings or []):
        earnings.append(_normalize_extra_earning(extra, index))

    if not earnings:
        raise ValueError("earnings must not be empty (no wage components produced)")

    gross_pay = sum(line["amount"] for line in earnings)

    base_for_insurance = (
        _dec(insurance_base, "insurance_base") if insurance_base is not None else Decimal(gross_pay)
    )
    taxable = (
        _dec(monthly_taxable_income, "monthly_taxable_income")
        if monthly_taxable_income is not None
        else Decimal(gross_pay)
    )

    statutory = _statutory.calculate_all_statutory(
        monthly_base=float(base_for_insurance),
        monthly_taxable_income=float(taxable),
        company_size=company_size,
        industry_rate=float(industry_rate),
        dependents=dependents,
        children_under_8=children_under_8,
    )

    deductions = _build_deduction_lines(statutory, dependents=dependents)
    total_deductions = sum(line["amount"] for line in deductions)
    net_pay = gross_pay - total_deductions

    missing_basis_labels = [line["label"] for line in earnings if not line.get("basis")]

    return {
        "employee": employee,
        "period": period,
        "payment_date": payment_date,
        "wage_type": wage_type,
        "earnings": earnings,
        "gross_pay": gross_pay,
        "deductions": deductions,
        "total_deductions": total_deductions,
        "net_pay": net_pay,
        "compliance": {
            "compliant": not missing_basis_labels,
            "missing_basis_labels": missing_basis_labels,
        },
    }


def render_payslip_markdown(breakdown: dict[str, Any]) -> str:
    """build_payslip_breakdown() 결과 → 교부용 마크다운(법정 기재사항 전부 포함)."""
    if not isinstance(breakdown, dict):
        raise ValueError("breakdown must be a dict")

    lines: list[str] = []
    lines.append("# 임금명세서")
    lines.append("")
    lines.append(f"- 근로자: {breakdown.get('employee', '')}")
    lines.append(f"- 임금 산정기간: {breakdown.get('period', '')}")
    lines.append(f"- 임금 지급일: {breakdown.get('payment_date', '')}")
    lines.append("")
    lines.append("## 지급내역")
    lines.append("")
    lines.append("| 항목 | 금액 | 계산방법 |")
    lines.append("|---|---:|---|")
    for line in breakdown.get("earnings", []):
        basis = line.get("basis") or "(계산방법 미기재 — §48② 위반 위험)"
        lines.append(f"| {line['label']} | {line['amount']:,}원 | {basis} |")
    lines.append(f"\n**지급합계: {breakdown.get('gross_pay', 0):,}원**")
    lines.append("")
    lines.append("## 공제내역")
    lines.append("")
    lines.append("| 항목 | 금액 | 산출근거 |")
    lines.append("|---|---:|---|")
    for line in breakdown.get("deductions", []):
        basis = line.get("basis") or "(산출근거 미기재)"
        lines.append(f"| {line['label']} | {line['amount']:,}원 | {basis} |")
    lines.append(f"\n**공제합계: {breakdown.get('total_deductions', 0):,}원**")
    lines.append("")
    lines.append(f"## 실지급액: {breakdown.get('net_pay', 0):,}원")

    compliance = breakdown.get("compliance") or {}
    if not compliance.get("compliant", True):
        lines.append("")
        missing = ", ".join(compliance.get("missing_basis_labels", []))
        lines.append(f"> ⚠ 근로기준법 §48② 위반 위험: 계산방법 미기재 항목 — {missing}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _build_deduction_lines(statutory: dict[str, Any], *, dependents: int) -> list[dict[str, Any]]:
    pension = statutory["pension"]
    health = statutory["health"]
    employment = statutory["employment_insurance"]
    income = statutory["income_tax"]
    base = statutory["monthly_base"]
    taxable = statutory["monthly_taxable_income"]

    return [
        {
            "label": "국민연금",
            "amount": pension["employee"],
            "basis": f"기준소득월액 {pension['base']:,.0f}원 × {_rate_pct(_statutory.PENSION_RATE_EMPLOYEE)}",
        },
        {
            "label": "건강보험",
            "amount": health["health_employee"],
            "basis": f"보수월액 {base:,.0f}원 × {_rate_pct(_statutory.HEALTH_RATE_EMPLOYEE)}",
        },
        {
            "label": "장기요양보험",
            "amount": health["longterm_care_employee"],
            "basis": (
                f"건강보험료 {health['health_employee']:,}원 × "
                f"{_rate_pct(_statutory.LONGTERM_CARE_RATE)}"
            ),
        },
        {
            "label": "고용보험",
            "amount": employment["employee"],
            "basis": (
                f"보수월액 {base:,.0f}원 × "
                f"{_rate_pct(_statutory.EMPLOYMENT_INSURANCE_RATE_EMPLOYEE)}"
            ),
        },
        {
            "label": "소득세",
            "amount": income["income_tax"],
            "basis": f"간이세액표 (월과세소득 {taxable:,.0f}원, 부양가족 {dependents}명)",
        },
        {
            "label": "지방소득세",
            "amount": income["local_income_tax"],
            "basis": f"소득세 {income['income_tax']:,}원 × 10%",
        },
    ]


def _normalize_extra_earning(extra: Any, index: int) -> dict[str, Any]:
    if not isinstance(extra, dict):
        raise ValueError(f"extra_earnings[{index}] must be a dict")
    label = _require_text(extra.get("label"), f"extra_earnings[{index}].label")
    amount = _round_won(_dec(extra.get("amount", 0), f"extra_earnings[{index}].amount"))
    if amount < 0:
        raise ValueError(f"extra_earnings[{index}].amount must be >= 0")
    basis_raw = extra.get("basis")
    basis = str(basis_raw).strip() if isinstance(basis_raw, str) and basis_raw.strip() else None
    return {"label": label, "amount": amount, "basis": basis}


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _dec(value: Any, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number, not bool")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be numeric: {value!r}") from exc


def _round_won(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _fmt_won(value: Decimal) -> str:
    return f"{_round_won(value):,}"


def _rate_pct(rate: float) -> str:
    """요율(비율, 예: 0.0475) → 표시용 퍼센트 문자열(예: "4.75%").

    statutory_2026 상수를 하드코딩 문자열로 다시 적지 않기 위한 동적 포맷.
    ``.6g``(유효숫자 6자리)를 쓰면 4.75/3.595/0.9 같은 단순 요율은 그대로,
    장기요양 환산율(13.140472...%)은 13.1405%로 정확히 표기된다(기존 "13.14%"
    는 4자리로 잘려 부정확했다).
    """
    return f"{rate * 100:.6g}%"


def _fmt_hours(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


__all__ = ["build_payslip_breakdown", "render_payslip_markdown"]
