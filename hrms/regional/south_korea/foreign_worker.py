"""외국인근로자 비자별 룰 엔진.

framework-free — frappe 의존 없음. 순수 Python (stdlib only).

법적 근거:
- 외국인근로자의 고용 등에 관한 법률 (외고법)
- 출입국관리법 시행령
- 국민연금법, 국민건강보험법, 고용보험법, 산업재해보상보험법
- 소득세법 제119조 (비거주자 과세), 제156조 (원천징수)
- 각국 사회보장협정 (국민연금공단)
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
from typing import Any

# ---------------------------------------------------------------------------
# 비자 유형 정의
# ---------------------------------------------------------------------------

VISA_TYPES: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------------
    # E-9: 비전문취업 (외국인고용허가제 / Employment Permit System)
    # 외고법 제18조의2: 3년 + 연장 1년 10개월 (또는 2년 미만 재입국 1년 10개월)
    # 최초 허가 3년, 연장 최대 1년 10개월 (합계 4년 10개월)
    # 국민연금: 협정국 제외 시 당연 가입. 사업장 변경 제한: 1년 1회 원칙.
    # ------------------------------------------------------------------
    "E-9": {
        "name": "비전문취업 (외국인고용허가제)",
        "category": "non_professional",
        "permit_employment": True,
        "max_stay_months": 58,          # 3년(36개월) + 연장 1년 10개월(22개월) = 58개월
        "max_extension_months": 22,     # 연장 허용 최대 기간 (1년 10개월 = 22개월)
        "national_pension_mandatory": True,       # 협정국 여부로 최종 결정 (국민연금법 §126)
        "health_insurance_required": True,
        "employment_insurance_required": True,
        "industrial_accident_required": True,     # 산재: 사업주 100%, 모든 비자
        "long_term_care_required": True,           # 장기요양: 건강보험료의 12.95% (2024)
        "max_weekly_overtime_hours": 12,           # 근로기준법 §53
        "workplace_change_limit_per_year": 1,     # 외고법 §25 (1년 1회, 사유 있을 시 허가)
        "income_tax_rule": "resident",            # 거주자: 국내원천소득 일반세율
        "simple_tax_rate_option": False,          # 단일세율(19%) 선택 불가
        "dangerousness_duty_restriction": False,  # 업종 제한은 고용허가서 범위 내
        "notes": [
            "사업장 변경은 원칙적으로 1년 1회, 사유 인정 시 추가 가능 (외고법 §25)",
            "재입국 특례: 성실 근로자 1회 출국 후 재입국, 최대 1년 10개월 추가 허용",
            "고용허가제 대상 업종 외 취업 시 불법 → 즉시 차단 필요",
        ],
    },

    # ------------------------------------------------------------------
    # H-2: 방문취업 (재외동포, 32개 이상 직종 허용)
    # 출입국관리법 시행령 별표1의2
    # 체류기간: 최초 3년, 연장 1회 2년 → 합계 5년 (점수제 아님)
    # ------------------------------------------------------------------
    "H-2": {
        "name": "방문취업 (재외동포)",
        "category": "ethnic_korean_overseas",
        "permit_employment": True,
        "max_stay_months": 60,          # 최초 3년 + 연장 2년 = 5년
        "national_pension_mandatory": True,
        "health_insurance_required": True,
        "employment_insurance_required": True,
        "industrial_accident_required": True,
        "long_term_care_required": True,
        "max_weekly_overtime_hours": 12,
        "workplace_change_limit_per_year": None,  # 제한 없음
        "income_tax_rule": "resident",
        "simple_tax_rate_option": False,
        "dangerousness_duty_restriction": False,
        "notes": [
            "허용 직종: 서비스업·제조업·농축산업·어업·건설업 등 지정 직종 (38개 직종군)",
            "전문직종(의사·변호사·교사 등) 취업 불가",
            "체류기간 연장: 최초 3년 후 2년 추가, 총 5년 상한",
        ],
    },

    # ------------------------------------------------------------------
    # F-2: 거주 (점수제 이민 또는 특정 자격 취득)
    # 일반 내국인 근로자와 동일한 수준으로 취급
    # ------------------------------------------------------------------
    "F-2": {
        "name": "거주 (점수제)",
        "category": "resident",
        "permit_employment": True,
        "max_stay_months": None,        # 연장 가능 (비자 유효기간 내)
        "national_pension_mandatory": True,
        "health_insurance_required": True,
        "employment_insurance_required": True,
        "industrial_accident_required": True,
        "long_term_care_required": True,
        "max_weekly_overtime_hours": 12,
        "workplace_change_limit_per_year": None,
        "income_tax_rule": "resident",
        "simple_tax_rate_option": False,
        "dangerousness_duty_restriction": False,
        "notes": [
            "내국인과 동등한 취업 자유",
            "취업 제한 없음 (단, 공무원 등 국적 요건이 있는 직종 제외)",
        ],
    },

    # ------------------------------------------------------------------
    # F-4: 재외동포 (외국국적동포)
    # 재외동포법에 의한 체류자격
    # 단순노무 직종 취업 금지 (재외동포법 §5, 동법 시행령 §3)
    # ------------------------------------------------------------------
    "F-4": {
        "name": "재외동포",
        "category": "overseas_korean",
        "permit_employment": True,
        "max_stay_months": None,        # 연장 가능 (통상 2년 단위)
        "national_pension_mandatory": True,
        "health_insurance_required": True,
        "employment_insurance_required": True,
        "industrial_accident_required": True,
        "long_term_care_required": True,
        "max_weekly_overtime_hours": 12,
        "workplace_change_limit_per_year": None,
        "income_tax_rule": "resident",
        "simple_tax_rate_option": False,
        "dangerousness_duty_restriction": True,    # 단순노무 직종 제한
        "notes": [
            "단순노무 직종 취업 금지 (재외동포법 시행령 §3): 청소·경비·단순조립 등",
            "단순노무 위반 여부는 직종(직무) 확인 필요 — 비자만으로 자동 차단 불가",
            "국적: 중국·구소련 동포(조선족·고려인) 포함",
        ],
    },

    # ------------------------------------------------------------------
    # F-5: 영주 (Permanent Residence)
    # 내국인과 사실상 동일. 취업·체류 제한 없음.
    # ------------------------------------------------------------------
    "F-5": {
        "name": "영주",
        "category": "permanent_resident",
        "permit_employment": True,
        "max_stay_months": None,        # 영구 (10년 단위 체류 카드 갱신)
        "national_pension_mandatory": True,
        "health_insurance_required": True,
        "employment_insurance_required": True,
        "industrial_accident_required": True,
        "long_term_care_required": True,
        "max_weekly_overtime_hours": 12,
        "workplace_change_limit_per_year": None,
        "income_tax_rule": "resident",
        "simple_tax_rate_option": False,
        "dangerousness_duty_restriction": False,
        "notes": [
            "내국인과 동등한 취업 자유 (공무원 등 국적 요건 직종 제외)",
        ],
    },

    # ------------------------------------------------------------------
    # E-7: 특정활동 (전문인력)
    # 사업주가 지정한 특정 직종에 한정 취업 허용
    # 고소득 전문직: 연봉 기준 충족 시 단일세율(19%) 선택 가능
    #   (소득세법 §18의2, 외국인기술자 5년간 50% 감면 별도)
    # ------------------------------------------------------------------
    "E-7": {
        "name": "특정활동 (전문인력)",
        "category": "professional",
        "permit_employment": True,
        "max_stay_months": None,        # 허가서 기간에 따라 상이 (통상 1~3년, 연장 가능)
        "national_pension_mandatory": True,
        "health_insurance_required": True,
        "employment_insurance_required": True,
        "industrial_accident_required": True,
        "long_term_care_required": True,
        "max_weekly_overtime_hours": 12,
        "workplace_change_limit_per_year": None,
        "income_tax_rule": "resident",
        "simple_tax_rate_option": True,            # 소득세법 §18의2: 19% 단일세율 선택 가능
        "dangerousness_duty_restriction": False,
        "notes": [
            "지정 직종 외 취업 불가 (고용허가서에 명시된 직종만)",
            "단일세율 19% 적용은 비거주자 또는 거주자가 선택 가능 (5년 이내)",
            "외국인기술자 소득세 감면: 국내 최초 취업일로부터 5년 (조특법 §18)",
        ],
    },

    # ------------------------------------------------------------------
    # D-10: 구직 (Job Seeker)
    # 일반 취업 불허. 인턴십·시험 등 제한적 활동만 가능.
    # ------------------------------------------------------------------
    "D-10": {
        "name": "구직",
        "category": "job_seeker",
        "permit_employment": False,     # 일반 취업 불허
        "max_stay_months": 6,          # 6개월, 연장 1회 가능 (합계 최대 1년)
        "national_pension_mandatory": False,
        "health_insurance_required": False,
        "employment_insurance_required": False,
        "industrial_accident_required": False,
        "long_term_care_required": False,
        "max_weekly_overtime_hours": 0,
        "workplace_change_limit_per_year": None,
        "income_tax_rule": "non_resident",
        "simple_tax_rate_option": False,
        "dangerousness_duty_restriction": False,
        "notes": [
            "일반 고용 계약 체결 불가",
            "무급 인턴·직업훈련 등 법무부 허가 활동에 한해 가능",
        ],
    },
}

# ---------------------------------------------------------------------------
# 사회보장협정 국가 캐시
# ---------------------------------------------------------------------------

_TREATY_COUNTRY_CODES: frozenset[str] | None = None


def _load_treaty_countries() -> frozenset[str]:
    global _TREATY_COUNTRY_CODES
    if _TREATY_COUNTRY_CODES is None:
        data_path = pathlib.Path(__file__).parent / "data" / "social_security_treaty_countries.json"
        with data_path.open(encoding="utf-8") as f:
            data = json.load(f)
        _TREATY_COUNTRY_CODES = frozenset(code.upper() for code in data.get("iso_code_set", []))
    return _TREATY_COUNTRY_CODES


def is_treaty_country(country_code: str) -> bool:
    """ISO-3166 Alpha-2 또는 QC(퀘벡) 코드로 사회보장협정 체결 여부 조회."""
    return country_code.upper() in _load_treaty_countries()


# ---------------------------------------------------------------------------
# 공개 API — 비자 룰 조회
# ---------------------------------------------------------------------------


def get_visa_rules(visa_type: str) -> dict[str, Any]:
    """비자별 룰 dict 조회.

    Args:
        visa_type: 비자 코드 (예: "E-9", "H-2", "F-4")

    Returns:
        비자 룰 dict. 미지원 비자 코드면 빈 dict.
    """
    return dict(VISA_TYPES.get(visa_type.upper() if visa_type else "", {}))


def list_supported_visa_types() -> list[str]:
    """지원하는 비자 코드 목록."""
    return list(VISA_TYPES.keys())


# ---------------------------------------------------------------------------
# 공개 API — 고용 적합성 검증
# ---------------------------------------------------------------------------


def validate_visa_for_employment(
    *,
    employee: dict[str, Any],
    employment_terms: dict[str, Any],
) -> dict[str, Any]:
    """비자별 고용 적합성 검증.

    Args:
        employee: {
            "visa_type": str,               # 예: "E-9"
            "country_of_origin": str,       # ISO Alpha-2 (예: "VN")
            "visa_expiry_date": str,        # "YYYY-MM-DD" (nullable)
            "date_of_joining": str,         # "YYYY-MM-DD"
            "workplace_changes_this_year": int,  # (E-9 전용)
        }
        employment_terms: {
            "weekly_overtime_hours": float,     # 계획된 주당 연장근로시간
            "job_category": str | None,         # 직종 카테고리 (F-4 단순노무 체크용)
        }

    Returns:
        {
            "visa_type": str,
            "valid_for_employment": bool,
            "warnings": list[str],
            "blockers": list[str],
            "applicable_insurances": dict,
            "max_weekly_overtime_hours": int,
            "stay_expiry_date": str | None,
            "stay_remaining_days": int | None,
        }
    """
    visa_type: str = str(employee.get("visa_type") or "").strip().upper()
    country_of_origin: str = str(employee.get("country_of_origin") or "").strip().upper()
    visa_expiry_raw: str | None = employee.get("visa_expiry_date")
    weekly_ot_hours: float = float(employment_terms.get("weekly_overtime_hours") or 0)
    job_category: str | None = employment_terms.get("job_category")

    warnings: list[str] = []
    blockers: list[str] = []

    # 비자 코드 미지원 처리
    if visa_type not in VISA_TYPES:
        return {
            "visa_type": visa_type or "(unknown)",
            "valid_for_employment": False,
            "warnings": [],
            "blockers": [f"비자 코드 '{visa_type}'은(는) 지원하지 않거나 정의되지 않은 유형입니다."],
            "applicable_insurances": {},
            "max_weekly_overtime_hours": 0,
            "stay_expiry_date": None,
            "stay_remaining_days": None,
        }

    rules = VISA_TYPES[visa_type]
    today = dt.date.today()

    # 1. 취업 허가 여부
    if not rules["permit_employment"]:
        blockers.append(
            f"비자 유형 {visa_type}({rules['name']})은(는) 일반 취업이 허용되지 않습니다."
        )

    # 2. 체류 기간 확인
    stay_expiry_date: str | None = None
    stay_remaining_days: int | None = None

    if visa_expiry_raw:
        try:
            expiry_date = dt.date.fromisoformat(str(visa_expiry_raw))
            stay_expiry_date = expiry_date.isoformat()
            stay_remaining_days = (expiry_date - today).days
            if stay_remaining_days < 0:
                blockers.append(
                    f"체류기간 만료: 비자가 {stay_expiry_date}에 만료되었습니다 "
                    f"({abs(stay_remaining_days)}일 초과)."
                )
            elif stay_remaining_days == 0:
                blockers.append(f"체류기간이 오늘({today.isoformat()})로 만료됩니다.")
            elif stay_remaining_days <= 30:
                warnings.append(
                    f"체류기간 임박: {stay_remaining_days}일 후 ({stay_expiry_date}) 만료. "
                    f"비자 연장 또는 체류자격 변경 절차를 진행하세요."
                )
            elif stay_remaining_days <= 90:
                warnings.append(
                    f"체류기간 90일 이내 만료 예정 ({stay_expiry_date}). 사전 준비가 필요합니다."
                )
        except (ValueError, TypeError):
            warnings.append(f"visa_expiry_date 형식이 올바르지 않습니다: {visa_expiry_raw!r}")

    # 3. 연장근로 한도
    max_ot = rules.get("max_weekly_overtime_hours", 12)
    if weekly_ot_hours > max_ot:
        if max_ot == 0:
            blockers.append(
                f"비자 유형 {visa_type}은(는) 연장근로가 허용되지 않습니다."
            )
        else:
            warnings.append(
                f"주당 연장근로 계획({weekly_ot_hours}시간)이 법정 한도({max_ot}시간)를 초과합니다. "
                f"근로기준법 §53 위반 주의."
            )

    # 4. 4대보험 요건
    applicable_insurances = _compute_applicable_insurances(
        rules=rules,
        country_of_origin=country_of_origin,
        visa_type=visa_type,
    )

    # 5. 사업장 변경 제한 (E-9)
    if visa_type == "E-9":
        wp_changes = int(employee.get("workplace_changes_this_year") or 0)
        limit = rules.get("workplace_change_limit_per_year", 1)
        if limit is not None and wp_changes >= limit:
            warnings.append(
                f"E-9 사업장 변경 횟수가 연간 한도({limit}회)에 도달했습니다 (현재 {wp_changes}회). "
                f"추가 변경은 고용노동부 허가가 필요합니다 (외고법 §25)."
            )

    # 6. F-4 단순노무 직종 경고
    if visa_type == "F-4" and rules.get("dangerousness_duty_restriction"):
        simple_labor_categories = {"simple_labor", "cleaning", "security", "assembly", "단순노무"}
        if job_category and str(job_category).lower() in simple_labor_categories:
            warnings.append(
                f"F-4 비자는 단순노무 직종({job_category}) 취업이 제한됩니다 "
                f"(재외동포법 시행령 §3). 직종 적합성을 확인하세요."
            )
        else:
            warnings.append(
                "F-4(재외동포) 비자는 단순노무 직종 취업 불가 (재외동포법 시행령 §3). "
                "배정 직무가 단순노무에 해당하지 않는지 반드시 확인하세요."
            )

    # 7. E-7 단일세율 선택 안내
    if visa_type == "E-7" and rules.get("simple_tax_rate_option"):
        warnings.append(
            "E-7(전문인력)은 소득세법 §18의2에 따라 19% 단일세율 선택이 가능합니다. "
            "연도 초 또는 최초 지급 전 선택 여부를 확인하세요."
        )

    valid_for_employment = len(blockers) == 0

    return {
        "visa_type": visa_type,
        "valid_for_employment": valid_for_employment,
        "warnings": warnings,
        "blockers": blockers,
        "applicable_insurances": applicable_insurances,
        "max_weekly_overtime_hours": max_ot,
        "stay_expiry_date": stay_expiry_date,
        "stay_remaining_days": stay_remaining_days,
    }


def _compute_applicable_insurances(
    *,
    rules: dict[str, Any],
    country_of_origin: str,
    visa_type: str,
) -> dict[str, Any]:
    """비자 룰과 국적 기반으로 4대보험 적용 여부 계산."""
    # 산재보험: 모든 외국인 근로자에게 적용 (산재보험법 §6, 사업주 100% 부담)
    industrial_accident = rules.get("industrial_accident_required", False)

    # 국민연금: 협정국 여부로 최종 결정
    pension_mandatory = rules.get("national_pension_mandatory", False)
    pension_treaty_exempt = False
    if pension_mandatory and country_of_origin:
        if is_treaty_country(country_of_origin):
            pension_treaty_exempt = True
            pension_mandatory = False  # 협정국은 자국 연금 가입 증명 시 면제

    health = rules.get("health_insurance_required", False)
    employment = rules.get("employment_insurance_required", False)
    long_term_care = rules.get("long_term_care_required", False) and health

    return {
        "national_pension": {
            "required": pension_mandatory,
            "treaty_exempt": pension_treaty_exempt,
            "note": (
                "사회보장협정 체결국: 자국 연금 가입 증명서 제출 시 면제 가능"
                if pension_treaty_exempt
                else ("당연 가입" if pension_mandatory else "적용 제외")
            ),
        },
        "health_insurance": {
            "required": health,
            "note": "당연 가입" if health else "적용 제외",
        },
        "long_term_care_insurance": {
            "required": long_term_care,
            "note": "건강보험 가입자 동시 적용" if long_term_care else "적용 제외",
        },
        "employment_insurance": {
            "required": employment,
            "note": "당연 가입" if employment else "적용 제외",
        },
        "industrial_accident_insurance": {
            "required": industrial_accident,
            "employer_pays_100_percent": True,
            "note": "전 사업장 적용 (사업주 전액 부담, 외국인 여부 무관)",
        },
    }


# ---------------------------------------------------------------------------
# 공개 API — 4대보험 금액 계산
# ---------------------------------------------------------------------------

# 2024년 기준 요율 (매년 고시 변경될 수 있음)
_RATES_2024: dict[str, float] = {
    "national_pension_employee_rate": 0.045,   # 4.5% (사용자 4.5%, 합계 9%)
    "national_pension_employer_rate": 0.045,
    "health_insurance_employee_rate": 0.03545, # 3.545% (2024)
    "health_insurance_employer_rate": 0.03545,
    "long_term_care_rate_on_health": 0.1295,   # 건강보험료의 12.95% (2024)
    "employment_insurance_employee_rate": 0.009,  # 0.9% (실업급여)
    "employment_insurance_employer_rate": 0.009,  # 0.9% + 고용안정·직능개발 별도
    "industrial_accident_rate": 0.0,           # 업종별 상이 — 사업주 전액 (계산 제외)
}


def calculate_foreign_worker_insurance(
    *,
    visa_type: str,
    country_of_origin: str,
    monthly_base_salary: float,
    pension_treaty_country: bool = False,
) -> dict[str, Any]:
    """외국인 4대보험 월 부담액 계산.

    국민연금:
    - 사회보장협정 국가(pension_treaty_country=True) 또는 is_treaty_country() 해당 시:
      자국 연금 가입 증명서 제출 시 면제 가능. 본 함수는 면제 적용으로 계산.
    - 그 외: 일반 거주자와 동일하게 4.5% 적용.

    산재보험: 요율이 업종별로 다르므로 금액 계산 제외, 적용 여부만 반환.

    Args:
        visa_type: 비자 코드 (예: "E-9")
        country_of_origin: ISO Alpha-2 국가 코드 (예: "VN")
        monthly_base_salary: 월 기준 보수 (원)
        pension_treaty_country: 사회보장협정 국가 여부 (True면 강제 면제 처리)

    Returns:
        {
            "visa_type": str,
            "country_of_origin": str,
            "monthly_base_salary": float,
            "pension_exempt": bool,
            "pension_exempt_reason": str | None,
            "employee_deductions": {
                "national_pension": float,
                "health_insurance": float,
                "long_term_care_insurance": float,
                "employment_insurance": float,
                "total": float,
            },
            "employer_contributions": {
                "national_pension": float,
                "health_insurance": float,
                "long_term_care_insurance": float,
                "employment_insurance": float,
                "industrial_accident": str,
                "total_calculable": float,
            },
            "applicable_insurances": dict,
            "rates_as_of": str,
        }
    """
    rules = VISA_TYPES.get(visa_type.upper() if visa_type else "", {})
    salary = float(monthly_base_salary or 0)
    rates = _RATES_2024

    # 연금 면제 여부 결정
    pension_exempt = pension_treaty_country or is_treaty_country(country_of_origin.upper())
    pension_exempt_reason: str | None = None
    if pension_exempt:
        pension_exempt_reason = (
            f"사회보장협정 체결국({country_of_origin.upper()}) — "
            "자국 연금 가입 증명서(Certificate of Coverage) 제출 시 국민연금 면제"
        )

    pension_base = rules.get("national_pension_mandatory", False) and not pension_exempt
    health_base = rules.get("health_insurance_required", False)
    employment_base = rules.get("employment_insurance_required", False)

    # 연금
    emp_pension = round(salary * rates["national_pension_employee_rate"]) if pension_base else 0.0
    er_pension = round(salary * rates["national_pension_employer_rate"]) if pension_base else 0.0

    # 건강보험
    emp_health = round(salary * rates["health_insurance_employee_rate"]) if health_base else 0.0
    er_health = round(salary * rates["health_insurance_employer_rate"]) if health_base else 0.0

    # 장기요양 (건강보험료 × 12.95%)
    emp_ltc = round(emp_health * rates["long_term_care_rate_on_health"]) if health_base else 0.0
    er_ltc = round(er_health * rates["long_term_care_rate_on_health"]) if health_base else 0.0

    # 고용보험
    emp_ei = round(salary * rates["employment_insurance_employee_rate"]) if employment_base else 0.0
    er_ei = round(salary * rates["employment_insurance_employer_rate"]) if employment_base else 0.0

    emp_total = emp_pension + emp_health + emp_ltc + emp_ei
    er_total_calculable = er_pension + er_health + er_ltc + er_ei

    applicable = _compute_applicable_insurances(
        rules=rules,
        country_of_origin=country_of_origin,
        visa_type=visa_type,
    )

    return {
        "visa_type": visa_type,
        "country_of_origin": country_of_origin.upper(),
        "monthly_base_salary": salary,
        "pension_exempt": pension_exempt,
        "pension_exempt_reason": pension_exempt_reason,
        "employee_deductions": {
            "national_pension": emp_pension,
            "health_insurance": emp_health,
            "long_term_care_insurance": emp_ltc,
            "employment_insurance": emp_ei,
            "total": emp_total,
        },
        "employer_contributions": {
            "national_pension": er_pension,
            "health_insurance": er_health,
            "long_term_care_insurance": er_ltc,
            "employment_insurance": er_ei,
            "industrial_accident": "업종별 요율 적용 (별도 산정 필요)",
            "total_calculable": er_total_calculable,
        },
        "applicable_insurances": applicable,
        "rates_as_of": "2024",
    }


# ---------------------------------------------------------------------------
# 공개 API — 체류 만료 임박 알람
# ---------------------------------------------------------------------------


def get_stay_expiry_warning(
    *,
    visa_expiry_date: dt.date,
    as_of_date: dt.date,
    warning_days: int = 90,
) -> dict[str, Any]:
    """체류 만료 임박 알람.

    Args:
        visa_expiry_date: 비자 만료일
        as_of_date: 기준일 (통상 오늘)
        warning_days: 경고 기준 일수 (기본 90일)

    Returns:
        {
            "visa_expiry_date": str,      # ISO 형식
            "as_of_date": str,
            "remaining_days": int,        # 음수면 이미 만료
            "is_expired": bool,
            "is_warning": bool,           # remaining_days <= warning_days (만료 아직 X)
            "severity": str,              # "expired" | "critical" | "warning" | "ok"
            "message": str,
        }
    """
    remaining = (visa_expiry_date - as_of_date).days

    is_expired = remaining < 0
    is_warning = not is_expired and remaining <= warning_days

    if is_expired:
        severity = "expired"
        message = (
            f"체류기간이 {abs(remaining)}일 전 만료되었습니다 ({visa_expiry_date.isoformat()}). "
            f"즉시 출입국관리소에 확인 또는 출국 조치가 필요합니다."
        )
    elif remaining == 0:
        severity = "critical"
        message = f"체류기간이 오늘({visa_expiry_date.isoformat()}) 만료됩니다."
    elif remaining <= 30:
        severity = "critical"
        message = (
            f"체류기간이 {remaining}일 후 만료됩니다 ({visa_expiry_date.isoformat()}). "
            f"긴급히 비자 연장 또는 체류자격 변경 절차를 진행하세요."
        )
    elif remaining <= warning_days:
        severity = "warning"
        message = (
            f"체류기간이 {remaining}일 후 만료됩니다 ({visa_expiry_date.isoformat()}). "
            f"사전에 연장 준비를 시작하세요."
        )
    else:
        severity = "ok"
        message = f"체류기간 잔여 {remaining}일 ({visa_expiry_date.isoformat()})."

    return {
        "visa_expiry_date": visa_expiry_date.isoformat(),
        "as_of_date": as_of_date.isoformat(),
        "remaining_days": remaining,
        "is_expired": is_expired,
        "is_warning": is_warning,
        "severity": severity,
        "message": message,
    }
