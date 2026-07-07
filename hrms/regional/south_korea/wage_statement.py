"""Framework-free Korea wage statement PDF payload builder.

근로기준법 시행령 제27조의2 (임금명세서) 준수 — 7개 법정 기재 사항 전부 포함.

이 모듈은 Frappe/ERPNext 프레임워크 없이도 임포트 가능한 순수 함수만 포함합니다.
PDF 생성 자체는 Frappe Print Format 레이어에서 처리하며,
이 함수는 그 전 단계인 "검증된 데이터 payload" 구성만 담당합니다.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import pathlib
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

# ---------------------------------------------------------------------------
# Frappe 조건부 import — framework-free 테스트 환경에서 안전하게 로드
# (insurance_filing_api.py 컨벤션)
# ---------------------------------------------------------------------------
try:
    import frappe as _frappe  # noqa: PLC0415

    _FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
    _frappe = None  # type: ignore[assignment]
    _FRAPPE_AVAILABLE = False


def _whitelist(fn):
    """@frappe.whitelist() 데코레이터 — Frappe 없으면 no-op."""
    if _FRAPPE_AVAILABLE and _frappe is not None:
        return _frappe.whitelist()(fn)
    return fn

# HTML 템플릿 경로 (이 모듈과 같은 패키지 내)
_PRINT_FORMAT_HTML_PATH = (
    pathlib.Path(__file__).resolve().parent / "print_formats" / "korea_wage_statement.html"
)

# ──────────────────────────────────────────────────────────────
# 비과세 항목 인식 (근로기준법 제12조 및 소득세법 시행령 §17의2 등)
# 명시적 플래그(is_tax_exempt=True) 우선, 없으면 한글 라벨 패턴 매칭
# ──────────────────────────────────────────────────────────────
_TAX_EXEMPT_LABEL_PATTERNS: frozenset[str] = frozenset(
    [
        "식대",
        "식비",
        "식사대",
        "차량유지비",
        "자가운전보조금",
        "육아수당",
        "출산수당",
        "보육수당",
        "연구활동비",
        "취재수당",
        "벽지수당",
        "재해위로금",
    ]
)

# 비과세 한도 참고 (분류 목적만, 금액 초과 시 별도 표시용)
_TAX_EXEMPT_MONTHLY_CAPS_KRW: dict[str, int] = {
    "식대": 200_000,
    "식비": 200_000,
    "식사대": 200_000,
    "차량유지비": 200_000,
    "자가운전보조금": 200_000,
    "육아수당": 100_000,
    "보육수당": 100_000,
    "출산수당": 100_000,
}


def build_korea_wage_statement_pdf_payload(
    *,
    salary_slip: dict[str, Any],
    actor: str,
) -> dict[str, Any]:
    """임금명세서 PDF payload 구성 — 근로기준법 시행령 §27조의2 7개 항목 전부 포함.

    이 함수는 read-only입니다. Frappe DB·파일 시스템·외부 API를 호출하지 않습니다.
    PDF 렌더링(Print Format), 저장, 발송은 상위 레이어에서 별도로 처리하십시오.

    Parameters
    ----------
    salary_slip:
        Frappe Salary Slip 문서의 dict 표현 또는 같은 키를 가진 테스트용 dict.
        필수 키: name, employee, employee_name, employee_id,
                 employee_birth_date (YYYY-MM-DD), company,
                 period_start (YYYY-MM-DD), period_end (YYYY-MM-DD),
                 payment_date (YYYY-MM-DD), earnings, deductions.
        선택 키: department, designation.
        earnings/deductions 항목 형태:
            {"label": str, "amount": int, "basis": str,
             "is_tax_exempt": bool (선택)}
    actor:
        작업 수행 담당자 식별자 (감사 로그용, 비어 있으면 안 됨).

    Returns
    -------
    dict — contract_type "korea_wage_statement_pdf_v1" 페이로드.
    """

    if not isinstance(salary_slip, dict):
        raise ValueError("salary_slip must be a dict")

    actor = _require_text(actor, "actor")
    source_name = _require_text(salary_slip.get("name"), "salary_slip.name")
    employee_id = _require_text(salary_slip.get("employee"), "salary_slip.employee")
    employee_name = _require_text(salary_slip.get("employee_name"), "salary_slip.employee_name")

    # 법정 §1: 사원번호 — employee 값을 employee_id로 사용
    # employee_id 필드가 명시적으로 있으면 우선 사용
    employee_registration_id = (
        str(salary_slip.get("employee_id") or "").strip() or employee_id
    )

    # 법정 §1: 생년월일 (필수)
    birth_date_raw = salary_slip.get("employee_birth_date")
    employee_birth_date = _require_iso_date(birth_date_raw, "salary_slip.employee_birth_date").isoformat()

    company = _require_text(salary_slip.get("company"), "salary_slip.company")

    # 법정 §2: 임금 지급일 (필수)
    payment_date = _require_iso_date(salary_slip.get("payment_date"), "salary_slip.payment_date").isoformat()

    # 임금 산정 기간
    period_start_date = _require_iso_date(salary_slip.get("period_start"), "salary_slip.period_start")
    period_end_date = _require_iso_date(salary_slip.get("period_end"), "salary_slip.period_end")
    if period_start_date > period_end_date:
        raise ValueError("salary_slip.period_start cannot be after salary_slip.period_end")
    period_start = period_start_date.isoformat()
    period_end = period_end_date.isoformat()

    # 선택 항목
    department = str(salary_slip.get("department") or "").strip() or None
    designation = str(salary_slip.get("designation") or "").strip() or None

    # 법정 §4·§5: 임금 구성 항목별 금액 + 계산 방법 (basis)
    earnings = _normalize_ws_lines(salary_slip.get("earnings"), "earnings")
    # 법정 §6: 공제 항목별 금액·산출 내역
    deductions = _normalize_ws_lines(salary_slip.get("deductions", []), "deductions")

    # 법정 §3: 임금 총액
    gross_pay = sum(line["amount"] for line in earnings)
    total_deductions = sum(line["amount"] for line in deductions)
    net_pay = gross_pay - total_deductions

    # 법정 §7: 비과세 항목 (자동 인식 + 명시적 플래그)
    tax_exempt_items = _extract_tax_exempt_items(earnings)

    # 산출근거 통합 (지급 + 공제)
    calculation_basis = [
        {"section": "지급", "label": line["label"], "basis": line["basis"], "amount": line["amount"]}
        for line in earnings
    ] + [
        {"section": "공제", "label": line["label"], "basis": line["basis"], "amount": line["amount"]}
        for line in deductions
    ]

    payload: dict[str, Any] = {
        # ── 계약 식별자 ──────────────────────────────────────────
        "contract_type": "korea_wage_statement_pdf_v1",
        "runtime_action": "pdf_payload_only",
        "requires_runtime_apply": False,
        "mutation_boundary": "pdf_payload_only_no_submit_no_approve_no_send_no_provider_call",
        "requires_human_approval": True,
        "ai_role": "assistant_only",
        # ── 출처 ─────────────────────────────────────────────────
        "source_salary_slip": source_name,
        # ── 법정 §1: 근로자 특정 정보 ───────────────────────────
        "employee_id": employee_registration_id,
        "employee_name": employee_name,
        "employee_birth_date": employee_birth_date,
        "company": company,
        "department": department,
        "designation": designation,
        # ── 법정 §2: 임금 지급일 ─────────────────────────────────
        "payment_date": payment_date,
        # ── 임금 산정 기간 ────────────────────────────────────────
        "period_start": period_start,
        "period_end": period_end,
        # ── 법정 §3: 임금 총액 ───────────────────────────────────
        "gross_pay": gross_pay,
        "total_deductions": total_deductions,
        "net_pay": net_pay,
        # ── 법정 §4·§5: 항목별 금액·계산방법 ────────────────────
        "earnings": earnings,
        # ── 법정 §6: 공제 항목별 금액·산출 내역 ─────────────────
        "deductions": deductions,
        # ── 법정 §7: 비과세 항목 ─────────────────────────────────
        "tax_exempt_items": tax_exempt_items,
        # ── 산출근거 통합 (Print Format 편의용) ───────────────────
        "calculation_basis": calculation_basis,
        # ── 한글 라벨 (Print Format 렌더링용) ────────────────────
        "print_labels": {
            "title": "임금명세서",
            "employee_id": "사번",
            "employee_name": "성명",
            "employee_birth_date": "생년월일",
            "company": "회사명",
            "department": "부서",
            "designation": "직급",
            "payment_date": "임금 지급일",
            "period": "임금 산정 기간",
            "earnings": "지급 내역",
            "deductions": "공제 내역",
            "tax_exempt_items": "비과세 항목",
            "calculation_basis": "산출근거",
            "gross_pay": "지급 합계",
            "total_deductions": "공제 합계",
            "net_pay": "실지급액",
        },
        # ── 감사 ──────────────────────────────────────────────────
        "prepared_by": actor,
    }

    payload["checksum"] = _checksum(payload)
    return payload


def render_korea_wage_statement_html(*, payload: dict[str, Any]) -> str:
    """임금명세서 HTML 렌더링 — 근로기준법 시행령 §27조의2 준수.

    build_korea_wage_statement_pdf_payload() 반환값을 Jinja2 템플릿에
    주입하여 완성된 HTML 문자열을 반환합니다.

    이 함수는 Frappe 런타임 없이도 동작합니다.
    PDF 변환(wkhtmltopdf 등)은 상위 레이어에서 처리하십시오.

    Parameters
    ----------
    payload:
        build_korea_wage_statement_pdf_payload() 반환 dict.
        contract_type이 "korea_wage_statement_pdf_v1"이어야 합니다.

    Returns
    -------
    str — 렌더링된 HTML 문자열.
    """
    try:
        import jinja2  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "jinja2가 필요합니다. `pip install jinja2` 또는 "
            "requirements.txt에 추가하십시오."
        ) from exc

    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    if payload.get("contract_type") != "korea_wage_statement_pdf_v1":
        raise ValueError(
            "payload.contract_type must be 'korea_wage_statement_pdf_v1'. "
            "Pass the output of build_korea_wage_statement_pdf_payload()."
        )

    template_source = _PRINT_FORMAT_HTML_PATH.read_text(encoding="utf-8")

    # Jinja2 환경 — undefined 변수를 빈 문자열로 처리 (법정 항목 미입력 시 렌더 실패 방지)
    env = jinja2.Environment(
        undefined=jinja2.Undefined,
        autoescape=jinja2.select_autoescape(["html"]),
        keep_trailing_newline=True,
    )
    template = env.from_string(template_source)

    # payload를 Jinja2 AttributeDict-compatible object로 감쌉니다.
    # 템플릿이 payload.foo 와 payload["foo"] 양쪽 모두 지원하도록.
    class _AttrDict(dict):  # type: ignore[type-arg]
        def __getattr__(self, item: str):
            try:
                val = self[item]
            except KeyError:
                return ""
            # 중첩 리스트/dict도 AttrDict로 변환
            if isinstance(val, list):
                return [_AttrDict(v) if isinstance(v, dict) else v for v in val]
            if isinstance(val, dict):
                return _AttrDict(val)
            return val

        def get(self, key, default=None):  # type: ignore[override]
            val = super().get(key, default)
            if isinstance(val, dict):
                return _AttrDict(val)
            if isinstance(val, list):
                return [_AttrDict(v) if isinstance(v, dict) else v for v in val]
            return val

    return template.render(payload=_AttrDict(payload))


# ──────────────────────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────────────────────


def _normalize_ws_lines(lines: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(lines, list):
        raise ValueError(f"salary_slip.{field} must be a list")
    if field == "earnings" and not lines:
        raise ValueError("salary_slip.earnings must not be empty")
    return [_normalize_ws_line(line, f"salary_slip.{field}[{i}]") for i, line in enumerate(lines)]


def _normalize_ws_line(line: Any, field: str) -> dict[str, Any]:
    if not isinstance(line, dict):
        raise ValueError(f"{field} must be a dict")
    label = _require_text(line.get("label"), f"{field}.label")
    basis = _require_text(line.get("basis"), f"{field}.basis")
    amount = _coerce_integer_krw(line.get("amount"), f"{field}.amount")
    if amount < 0:
        raise ValueError(f"{field}.amount cannot be negative")

    # 비과세 플래그: 명시적 bool 우선, 없으면 라벨 자동 인식
    explicit = line.get("is_tax_exempt")
    if explicit is None:
        is_tax_exempt = _is_label_tax_exempt(label)
    elif isinstance(explicit, bool):
        is_tax_exempt = explicit
    else:
        raise ValueError(f"{field}.is_tax_exempt must be a bool or absent")

    result: dict[str, Any] = {
        "label": label,
        "amount": amount,
        "basis": basis,
        "is_tax_exempt": is_tax_exempt,
    }

    # 비과세 한도 초과 여부 참고 표시 (법적 의무는 아니나 실무 편의)
    cap = _TAX_EXEMPT_MONTHLY_CAPS_KRW.get(label)
    if is_tax_exempt and cap is not None and amount > cap:
        result["tax_exempt_cap_exceeded"] = True
        result["tax_exempt_cap"] = cap
    return result


def _extract_tax_exempt_items(earnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """법정 §7: 비과세 항목만 추출."""
    return [
        {
            "label": line["label"],
            "amount": line["amount"],
            "basis": line["basis"],
            **({"cap_exceeded": True, "cap": line["tax_exempt_cap"]} if line.get("tax_exempt_cap_exceeded") else {}),
        }
        for line in earnings
        if line.get("is_tax_exempt")
    ]


def _is_label_tax_exempt(label: str) -> bool:
    return label.strip() in _TAX_EXEMPT_LABEL_PATTERNS


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _require_iso_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date string (YYYY-MM-DD)")
    text = value.strip()
    if len(text) != 10:
        raise ValueError(f"{field} must be an ISO date string (YYYY-MM-DD)")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date string (YYYY-MM-DD)") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{field} must be an ISO date string (YYYY-MM-DD)")
    return parsed


def _coerce_integer_krw(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be integer KRW")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{field} must be integer KRW")
        if "e" in text.lower() or "." in text:
            raise ValueError(f"{field} must be integer KRW")
        try:
            amount = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(f"{field} must be integer KRW") from exc
        if not amount.is_finite() or amount != amount.to_integral_value():
            raise ValueError(f"{field} must be integer KRW")
        return int(amount)
    raise ValueError(f"{field} must be integer KRW")


def _checksum(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        {k: v for k, v in payload.items() if k != "checksum"},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


# ──────────────────────────────────────────────────────────────
# PWA 임금명세서 어댑터 — 프론트(KoreaWageStatementDashboard) 계약
#
#   list_korea_wage_statements        최근 N개월 [{pay_year_month, net_pay}]
#   build_korea_wage_statement_preview  해당 월 명세서 프리뷰 (법정 항목 그리드)
#
# 순수 매핑(map_salary_slip_to_wage_statement 등)은 framework-free —
# frappe 없이 직접 실행하는 테스트에서 실측 데이터로 검증한다.
# ──────────────────────────────────────────────────────────────

# 공제 컴포넌트명 → 프론트 응답 키 매핑 (포함 매칭, 순서 중요:
# "지방소득세"가 "소득세"를 포함하므로 지방소득세를 먼저 판정)
_DEDUCTION_KEY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("local_income_tax", ("지방소득세", "주민세")),
    ("income_tax", ("소득세",)),
    ("national_pension", ("국민연금",)),
    ("long_term_care_insurance", ("장기요양",)),
    ("health_insurance", ("건강보험",)),
    ("employment_insurance", ("고용보험",)),
)

_DEDUCTION_KEYS: tuple[str, ...] = tuple(key for key, _pats in _DEDUCTION_KEY_RULES)


def _component_name(row: dict[str, Any]) -> str:
    """급여 컴포넌트 행에서 컴포넌트명 추출 (salary_component 우선, label 폴백)."""
    for key in ("salary_component", "label"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _amount_int_krw(value: Any) -> int:
    """금액을 1원 단위 정수로 강제 (float 오차 방지: round 후 int)."""
    if value in (None, ""):
        return 0
    return int(round(float(value)))


def _classify_deduction(component_name: str) -> str | None:
    """공제 컴포넌트명 → 응답 키. 매칭 없으면 None."""
    for key, patterns in _DEDUCTION_KEY_RULES:
        if any(pattern in component_name for pattern in patterns):
            return key
    return None


def map_salary_slip_to_wage_statement(slip: dict[str, Any]) -> dict[str, Any]:
    """Salary Slip dict → 임금명세서 프리뷰 응답 (framework-free 순수 함수).

    입력 slip 계약:
        earnings / deductions: [{"salary_component": str, "amount": num}, ...]
        total_deduction, net_pay: 슬립 필드 그대로

    응답 키 (프론트 KoreaWageStatementDashboard 가 읽는 키 — 정확히 유지):
        base_salary               "기본급" 컴포넌트 금액 (없으면 첫 earning)
        allowances                기본급·비과세 제외 earnings
                                  [{"code", "label", "amount"}]
        non_taxable_total         컴포넌트명에 "비과세" 포함 earnings 합
        income_tax / local_income_tax / national_pension /
        health_insurance / long_term_care_insurance / employment_insurance
        total_deduction, net_pay  슬립 필드 그대로 (정수 강제)
    """
    if not isinstance(slip, dict):
        raise ValueError("slip must be a dict")

    earnings_raw = slip.get("earnings") or []
    if not isinstance(earnings_raw, list):
        raise ValueError("slip.earnings must be a list")
    deductions_raw = slip.get("deductions") or []
    if not isinstance(deductions_raw, list):
        raise ValueError("slip.deductions must be a list")

    earnings = [
        {"name": _component_name(row), "amount": _amount_int_krw(row.get("amount"))}
        for row in earnings_raw
        if isinstance(row, dict)
    ]

    # 기본급: 정확히 "기본급" 컴포넌트 우선, 없으면 첫 earning
    base_row = next((e for e in earnings if e["name"] == "기본급"), None)
    if base_row is None and earnings:
        base_row = earnings[0]

    non_taxable_total = 0
    allowances: list[dict[str, Any]] = []
    for row in earnings:
        if row is base_row:
            continue
        if "비과세" in row["name"]:
            non_taxable_total += row["amount"]
            continue
        allowances.append({"code": row["name"], "label": row["name"], "amount": row["amount"]})

    result: dict[str, Any] = {
        "base_salary": base_row["amount"] if base_row else 0,
        "allowances": allowances,
        "non_taxable_total": non_taxable_total,
        "total_deduction": _amount_int_krw(slip.get("total_deduction")),
        "net_pay": _amount_int_krw(slip.get("net_pay")),
    }
    for key in _DEDUCTION_KEYS:
        result[key] = 0
    for row in deductions_raw:
        if not isinstance(row, dict):
            continue
        key = _classify_deduction(_component_name(row))
        if key is not None:
            result[key] += _amount_int_krw(row.get("amount"))
    return result


def build_wage_statement_history(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Salary Slip 목록 행 → [{"pay_year_month": "YYYY-MM", "net_pay": int}].

    start_date 는 date/datetime/ISO 문자열 모두 수용 (frappe get_all 반환 다양성).
    framework-free 순수 함수.
    """
    history: list[dict[str, Any]] = []
    for row in rows or []:
        raw = row.get("start_date")
        if isinstance(raw, datetime):
            raw = raw.date()
        if isinstance(raw, date):
            pay_year_month = f"{raw.year:04d}-{raw.month:02d}"
        elif isinstance(raw, str) and len(raw) >= 7:
            pay_year_month = raw[:7]
        else:
            continue  # start_date 없는 행은 목록에서 제외 (프론트 키가 pay_year_month)
        history.append({"pay_year_month": pay_year_month, "net_pay": _amount_int_krw(row.get("net_pay"))})
    return history


# ---------------------------------------------------------------------------
# Frappe 글루 (사이트 조회 + 권한) — 위 순수 함수에 위임
# ---------------------------------------------------------------------------


def _require_frappe():
    if not (_FRAPPE_AVAILABLE and _frappe is not None):
        raise RuntimeError("frappe runtime is required for this endpoint")
    return _frappe


def _check_employee_scope(employee: str) -> None:
    """본인(session user 의 Employee) 또는 HR Manager 만 허용. 그 외 PermissionError."""
    fr = _require_frappe()
    user = getattr(getattr(fr, "session", None), "user", None)
    if user == "Administrator":
        return
    roles: set[str] = set()
    get_roles = getattr(fr, "get_roles", None)
    if callable(get_roles):
        roles = set(get_roles(user) if user else get_roles())
    if "HR Manager" in roles or "System Manager" in roles:
        return
    own_employee = fr.db.get_value("Employee", {"user_id": user}, "name") if user else None
    if own_employee and own_employee == employee:
        return
    exc = getattr(fr, "PermissionError", PermissionError)
    raise exc("본인 임금명세서만 조회할 수 있습니다 (HR Manager 제외)")


def _require_employee_arg(employee: Any) -> str:
    if not isinstance(employee, str) or not employee.strip():
        raise ValueError("employee is required")
    return employee.strip()


def _row_value(row: Any, key: str) -> Any:
    """frappe get_doc 자식행(객체)·dict 양쪽 지원 접근자."""
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


@_whitelist
def list_korea_wage_statements(employee: str, limit: int | str = 12) -> list[dict[str, Any]]:
    """해당 직원의 Salary Slip(docstatus 0/1) 을 start_date 내림차순 limit 개.

    응답: [{"pay_year_month": "2026-05", "net_pay": 6481553}, ...]
    권한: 본인 또는 HR Manager.
    """
    fr = _require_frappe()
    employee = _require_employee_arg(employee)
    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        raise ValueError("limit must be an integer") from None
    limit_int = max(1, min(limit_int, 120))

    _check_employee_scope(employee)

    rows = fr.get_all(
        "Salary Slip",
        filters={"employee": employee, "docstatus": ["in", [0, 1]]},
        fields=["start_date", "net_pay"],
        order_by="start_date desc",
        limit=limit_int,
    )
    return build_wage_statement_history([dict(r) for r in rows])


@_whitelist
def build_korea_wage_statement_preview(
    employee: str, year: int | str, month: int | str
) -> dict[str, Any]:
    """해당 월(start_date 기준) Salary Slip 1건 → 임금명세서 프리뷰.

    없으면 frappe.throw("해당 월의 명세서가 없습니다") — 프론트는 resource.error 로 처리.
    권한: 본인 또는 HR Manager.
    """
    fr = _require_frappe()
    employee = _require_employee_arg(employee)
    try:
        year_int = int(year)
        month_int = int(month)
    except (TypeError, ValueError):
        raise ValueError("year/month must be integers") from None
    if not (1 <= month_int <= 12):
        raise ValueError(f"invalid month: {month_int}")

    _check_employee_scope(employee)

    month_start = date(year_int, month_int, 1)
    month_end = date(year_int, month_int, calendar.monthrange(year_int, month_int)[1])
    slips = fr.get_all(
        "Salary Slip",
        filters={
            "employee": employee,
            "docstatus": ["in", [0, 1]],
            "start_date": ["between", [month_start.isoformat(), month_end.isoformat()]],
        },
        fields=["name"],
        order_by="docstatus desc, modified desc",
        limit=1,
    )
    if not slips:
        fr.throw("해당 월의 명세서가 없습니다")

    doc = fr.get_doc("Salary Slip", _row_value(slips[0], "name"))
    slip_dict = {
        "earnings": [
            {"salary_component": _row_value(row, "salary_component"), "amount": _row_value(row, "amount")}
            for row in (_row_value(doc, "earnings") or [])
        ],
        "deductions": [
            {"salary_component": _row_value(row, "salary_component"), "amount": _row_value(row, "amount")}
            for row in (_row_value(doc, "deductions") or [])
        ],
        "total_deduction": _row_value(doc, "total_deduction"),
        "net_pay": _row_value(doc, "net_pay"),
    }
    return map_salary_slip_to_wage_statement(slip_dict)


__all__ = [
    "build_korea_wage_statement_pdf_payload",
    "render_korea_wage_statement_html",
    "map_salary_slip_to_wage_statement",
    "build_wage_statement_history",
    "list_korea_wage_statements",
    "build_korea_wage_statement_preview",
]
