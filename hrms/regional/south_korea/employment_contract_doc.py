"""근로계약서 데이터 빌더 + 마크다운 렌더러 — 근로기준법 제17조 준수.

Framework-free: 외부 LLM API 사용 없음. Frappe mutation 없음. raise 대신
missing[] 누락 검출 방식(§17② 서면 명시·교부 전 검수용). 기존
`employment_contract.py`(계약유형별 HTML 4종)와 달리, 이 모듈은 임금
구성항목(hourly_wage.compose_hourly_earnings 형식 호환 리스트)을 그대로
받아 포괄임금 분해를 표기하는 단일 빌더 + 마크다운 렌더러를 제공한다.

근거:
- 근로기준법 제17조제1항: 임금, 소정근로시간, 제55조에 따른 휴일,
  제60조에 따른 연차 유급휴가, 그 밖에 대통령령으로 정하는 근로조건.
- 근로기준법 제17조제2항: 서면 명시 및 교부 의무.
- 시행령 세부 항목(취업규칙 필수기재 준용 등) 중 본 모듈이 확정하지 않은
  부분은 "시행령 §8 — 검수 필요"로 표기한다(창작 금지).
"""

from __future__ import annotations

import importlib.util as _ilu
import pathlib as _pl
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# ---------------------------------------------------------------------------
# mask_rrn 재사용 — 기존 employment_contract.py 로드 (framework-free, 중복 금지)
# ---------------------------------------------------------------------------

_THIS_DIR = _pl.Path(__file__).resolve().parent


def _load_sibling(name: str):
	spec = _ilu.spec_from_file_location(f"_korea_{name}_doc_dep", _THIS_DIR / f"{name}.py")
	module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
	assert spec.loader is not None
	spec.loader.exec_module(module)  # type: ignore[union-attr]
	return module


_employment_contract = _load_sibling("employment_contract")
mask_rrn = _employment_contract.mask_rrn

# NET(실수령액) 참고 표기 — net_to_gross.py의 forward 공제 로직 재사용 (요율 이중 정의 금지)
_net_to_gross = _load_sibling("net_to_gross")

# ---------------------------------------------------------------------------
# 스케줄 → 근로시간 상수 (inclusive_wage.py와 동일값 — DI 원칙상 재정의, cross-import 금지)
# ---------------------------------------------------------------------------

# 주 법정 근로시간 한도 (근로기준법 §50①)
WEEKLY_STATUTORY_HOURS = Decimal("40")
# 주 연장근로 한도 (근로기준법 §53①)
WEEKLY_OVERTIME_LIMIT_HOURS = Decimal("12")
# 월평균 주 수 = 365 ÷ 12 ÷ 7 ≈ 4.345 (inclusive_wage.py:AVG_WEEKS_PER_MONTH와 동일값 — 재정의)
AVG_WEEKS_PER_MONTH = Decimal("365") / Decimal("12") / Decimal("7")

# 수습기간 감액 하한 90% (최저임금법 §5③ — 단순노무직 제외 취지)
PROBATION_WAGE_PERCENT_FLOOR = 90
# 수습 감액 허용 기간 3개월 (최저임금법 시행령 §3 — 수습 시작 후 3개월 이내만 감액 가능)
PROBATION_REDUCTION_MONTH_LIMIT = 3

# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

STATUTE_NOTE_17_1 = (
	"근로기준법 제17조제1항: 임금, 소정근로시간, 제55조에 따른 휴일, "
	"제60조에 따른 연차 유급휴가, 그 밖에 대통령령으로 정하는 근로조건을 명시하여야 한다."
)
STATUTE_NOTE_17_2 = "근로기준법 제17조제2항: 이 계약서는 서면으로 명시하여 근로자에게 교부하여야 한다."
STATUTE_NOTE_ENFORCEMENT_DECREE = "시행령 §8 — 검수 필요 (세부 기재사항은 사업장별 확인 후 보완)"


def compute_schedule_hours(schedule: list[Any]) -> dict[str, Any]:
	"""주간 근무 스케줄 블록 → 주 소정/연장·월 연장시간 산출 (포괄임금 설계용).

	Parameters
	----------
	schedule: list of dict
		[{"day": str, "start_time": "HH:MM", "end_time": "HH:MM", "break_minutes": int}, ...]
		종업시각이 시업시각 이하이면 익일 종업(야간 교대)으로 본다.

	Returns
	-------
	dict:
		{
		  "weekly_total_hours": Decimal,      # 휴게 제외 주 실근로시간
		  "weekly_scheduled_hours": Decimal,  # 주 소정근로시간 (최대 40h — §50①)
		  "weekly_overtime_hours": Decimal,   # 주 연장시간 (40h 초과분)
		  "monthly_overtime_hours": Decimal,  # 주 연장 × 4.345 (365÷12÷7), 소수 둘째자리 반올림
		  "warnings": list[str],              # §53① 주 12시간 한도 초과 경고 (raise 아님)
		}
	"""
	if not isinstance(schedule, list):
		raise TypeError(f"schedule must be a list, got {type(schedule).__name__}")

	total_minutes = 0
	for block in schedule:
		if not isinstance(block, dict):
			raise TypeError("schedule 항목은 dict여야 합니다")
		start = _parse_hhmm(block.get("start_time"), "start_time")
		end = _parse_hhmm(block.get("end_time"), "end_time")
		if end <= start:
			end += 24 * 60  # 익일 종업 (야간 교대)
		try:
			break_minutes = int(block.get("break_minutes") or 0)
		except (TypeError, ValueError) as exc:
			raise ValueError(f"break_minutes must be an integer: {block.get('break_minutes')!r}") from exc
		if break_minutes < 0:
			raise ValueError("break_minutes must be >= 0")
		total_minutes += max(0, end - start - break_minutes)

	weekly_total = (Decimal(total_minutes) / Decimal(60)).quantize(
		Decimal("0.01"), rounding=ROUND_HALF_UP
	)
	weekly_scheduled = min(weekly_total, WEEKLY_STATUTORY_HOURS)
	weekly_overtime = max(weekly_total - WEEKLY_STATUTORY_HOURS, Decimal("0"))
	monthly_overtime = (weekly_overtime * AVG_WEEKS_PER_MONTH).quantize(
		Decimal("0.01"), rounding=ROUND_HALF_UP
	)

	warnings: list[str] = []
	if weekly_overtime > WEEKLY_OVERTIME_LIMIT_HOURS:
		warnings.append(
			f"주 연장근로 {weekly_overtime}h가 주 12시간 한도를 초과합니다 (근로기준법 §53①)."
		)

	return {
		"weekly_total_hours": weekly_total,
		"weekly_scheduled_hours": weekly_scheduled,
		"weekly_overtime_hours": weekly_overtime,
		"monthly_overtime_hours": monthly_overtime,
		"warnings": warnings,
	}


def build_employment_contract(data: dict[str, Any]) -> dict[str, Any]:
	"""근로계약서 입력 데이터를 검증하고 §17 필수기재 누락을 검출한다 (raise 아님).

	Parameters
	----------
	data: dict
		{
		  "company": {company_name, representative_name, address, business_registration_number, contact?},
		  "employee": {employee_name, address, contact?, resident_registration_number?},
		  "workplace": str,
		  "job_description": str,
		  "contract_period": {"start_date": str|date, "end_date": str|date|None},
		  "scheduled_work": {"start_time": str, "end_time": str, "work_days": str, "break_time"?: str},
		  "holidays": str,        # §55
		  "annual_leave": str,    # §60
		  "wage_components": [{"component": str, "amount": int}, ...],  # 포괄임금이면 항목 분해 그대로
		  "wage_payment_date": str,
		  "wage_payment_method": str,
		  "social_insurance"?: str,
		  "other_terms"?: str,
		}

	Returns
	-------
	dict:
		{
		  "doc_type": "korea_employment_contract_draft_v2",
		  "company": {...},
		  "employee": {...},              # RRN 마스킹 적용
		  "workplace": str,
		  "job_description": str,
		  "contract_period": {...},
		  "scheduled_work": {...},
		  "holidays": str,
		  "annual_leave": str,
		  "wage_components": [...],       # 그대로 통과 (compose_hourly_earnings 호환)
		  "wage_total": int,
		  "wage_payment_date": str,
		  "wage_payment_method": str,
		  "missing": list[str],           # 누락 필드 키 (raise 아님)
		  "required_fields_complete": bool,
		  "requires_human_approval": True,
		  "ai_role": "assistant_only",
		}
	"""
	if not isinstance(data, dict):
		raise TypeError(f"data must be a dict, got {type(data).__name__}")

	company_raw = data.get("company") or {}
	employee_raw = data.get("employee") or {}
	contract_period_raw = data.get("contract_period") or {}
	scheduled_work_raw = data.get("scheduled_work") or {}
	wage_components_raw = data.get("wage_components") or []

	if not isinstance(company_raw, dict):
		raise TypeError("data['company'] must be a dict")
	if not isinstance(employee_raw, dict):
		raise TypeError("data['employee'] must be a dict")
	if not isinstance(contract_period_raw, dict):
		raise TypeError("data['contract_period'] must be a dict")
	if not isinstance(scheduled_work_raw, dict):
		raise TypeError("data['scheduled_work'] must be a dict")
	if not isinstance(wage_components_raw, list):
		raise TypeError("data['wage_components'] must be a list")

	company = _sanitize_company(company_raw)
	employee = _sanitize_employee(employee_raw)
	contract_period = _sanitize_contract_period(contract_period_raw)
	scheduled_work = _sanitize_scheduled_work(scheduled_work_raw)
	wage_components = _sanitize_wage_components(wage_components_raw)
	wage_total = sum(int(item["amount"]) for item in wage_components)

	warnings: list[str] = []

	# 수습기간 (최저임금법 §5③·시행령 §3) — 경고는 raise 아님 (판단은 노무사)
	probation = _sanitize_probation(data.get("probation") or {}, warnings)

	# 주간 스케줄 → 월 연장시간 (포괄임금 설계용) — 미입력 시 None
	work_schedule_raw = data.get("work_schedule")
	schedule_summary = None
	if work_schedule_raw:
		schedule_summary = compute_schedule_hours(work_schedule_raw)
		warnings.extend(schedule_summary["warnings"])

	# 예상 실수령액 참고 표기 — 옵션 (net_to_gross forward 공제 재사용)
	net_preview = _build_net_preview(data.get("net_preview") or {}, wage_total)

	workplace = str(data.get("workplace") or "").strip()
	job_description = str(data.get("job_description") or "").strip()
	holidays = str(data.get("holidays") or "").strip()
	annual_leave = str(data.get("annual_leave") or "").strip()
	wage_payment_date = str(data.get("wage_payment_date") or "").strip()
	wage_payment_method = str(data.get("wage_payment_method") or "").strip()
	social_insurance = str(data.get("social_insurance") or "").strip()
	other_terms = str(data.get("other_terms") or "").strip()

	missing = _detect_missing(
		company=company,
		employee=employee,
		contract_period=contract_period,
		scheduled_work=scheduled_work,
		wage_components=wage_components,
		workplace=workplace,
		job_description=job_description,
		holidays=holidays,
		annual_leave=annual_leave,
		wage_payment_date=wage_payment_date,
		wage_payment_method=wage_payment_method,
	)

	return {
		"doc_type": "korea_employment_contract_draft_v2",
		"company": company,
		"employee": employee,
		"workplace": workplace,
		"job_description": job_description,
		"contract_period": contract_period,
		"scheduled_work": scheduled_work,
		"holidays": holidays,
		"annual_leave": annual_leave,
		"wage_components": wage_components,
		"wage_total": wage_total,
		"wage_payment_date": wage_payment_date,
		"wage_payment_method": wage_payment_method,
		"social_insurance": social_insurance,
		"other_terms": other_terms,
		"probation": probation,
		"schedule_summary": schedule_summary,
		"net_preview": net_preview,
		"warnings": warnings,
		"missing": missing,
		"required_fields_complete": len(missing) == 0,
		"requires_human_approval": True,
		"ai_role": "assistant_only",
	}


def render_contract_markdown(contract: dict[str, Any]) -> str:
	"""build_employment_contract() 결과를 §17②용 서면 초안 마크다운으로 렌더링.

	필수기재 누락이 있으면 문서 최상단에 경고 블록을 먼저 출력한다.
	"""
	lines: list[str] = []

	missing = contract.get("missing") or []
	if missing:
		lines.append("> ⚠️ **필수기재 누락 경고** — 서면 교부 전 아래 항목을 보완하십시오.")
		lines.append(">")
		for field in missing:
			lines.append(f"> - {field}")
		lines.append("")

	warnings = contract.get("warnings") or []
	if warnings:
		lines.append("> ⚠️ **법정 기준 경고** — 서면 교부 전 아래 사항을 검토하십시오.")
		lines.append(">")
		for warning in warnings:
			lines.append(f"> - {warning}")
		lines.append("")

	company = contract.get("company", {})
	employee = contract.get("employee", {})
	contract_period = contract.get("contract_period", {})
	scheduled_work = contract.get("scheduled_work", {})
	wage_components = contract.get("wage_components", [])

	lines.append("# 표준 근로계약서 (초안)")
	lines.append("")
	lines.append(
		f'사업주 **{company.get("company_name", "")}**(이하 "사업주"라 함)와 '
		f'근로자 **{employee.get("employee_name", "")}**(이하 "근로자"라 함)는 '
		"다음과 같이 근로계약을 체결한다."
	)
	lines.append("")

	lines.append("## 제1조 (근로계약기간)")
	lines.append(f"- 계약 시작일: {_blank(contract_period.get('start_date'))}")
	lines.append(f"- 계약 종료일: {_blank(contract_period.get('end_date'), '기간의 정함 없음')}")
	probation = contract.get("probation") or {}
	if int(probation.get("months") or 0) > 0:
		lines.append(f"- 수습기간: 계약 시작일부터 {probation['months']}개월")
		lines.append(
			f"- 수습기간 중 임금: 이 계약 임금의 {probation.get('wage_percent', 100)}% "
			"(최저임금법 제5조제3항·같은 법 시행령 제3조에 따른 범위 내)"
		)
	lines.append("")

	lines.append("## 제2조 (근무장소 및 업무)")
	lines.append(f"- 근무장소: {_blank(contract.get('workplace'))}")
	lines.append(f"- 업무 내용: {_blank(contract.get('job_description'))}")
	lines.append("")

	lines.append("## 제3조 (소정근로시간)")
	lines.append(
		f"- 소정근로시간: {_blank(scheduled_work.get('start_time'))} ~ "
		f"{_blank(scheduled_work.get('end_time'))} "
		f"(휴게시간 {_blank(scheduled_work.get('break_time'), '1시간')})"
	)
	lines.append(f"- 근무일: {_blank(scheduled_work.get('work_days'))}")
	schedule_summary = contract.get("schedule_summary")
	if schedule_summary:
		lines.append(f"- 주 소정근로시간: {schedule_summary['weekly_scheduled_hours']}시간")
		lines.append(f"- 주 연장근로시간: {schedule_summary['weekly_overtime_hours']}시간")
		lines.append(
			f"- 월 연장근로시간: {schedule_summary['monthly_overtime_hours']}시간 "
			"(주 연장 × 월평균 주수 4.345 — 포괄임금 설계용)"
		)
	lines.append("")

	lines.append("## 제4조 (휴일) — 근로기준법 제55조")
	lines.append(f"- 휴일: {_blank(contract.get('holidays'))}")
	lines.append("")

	lines.append("## 제5조 (임금)")
	if wage_components:
		lines.append("| 구성항목 | 금액(원) |")
		lines.append("| --- | ---: |")
		for item in wage_components:
			lines.append(f"| {item['component']} | {item['amount']:,} |")
		lines.append(f"| **합계** | **{contract.get('wage_total', 0):,}** |")
	else:
		lines.append("- (임금 구성항목 미기재 — 보완 필요)")
	lines.append(f"- 임금 지급일: {_blank(contract.get('wage_payment_date'))}")
	lines.append(f"- 지급 방법: {_blank(contract.get('wage_payment_method'))}")
	net_preview = contract.get("net_preview")
	if net_preview:
		lines.append(
			f"- ※ 예상 실수령액(참고용): {net_preview['estimated_net']:,}원 — "
			f"부양가족 {net_preview['dependents']}인(본인 포함)·"
			f"월 비과세 {net_preview['non_taxable']:,}원 가정, 법정 요율 기준 추정치이며 "
			"실제 공제액과 다를 수 있음 (계약 임금이 아님)"
		)
	lines.append("")

	lines.append("## 제6조 (연차유급휴가) — 근로기준법 제60조")
	lines.append(f"- 연차유급휴가: {_blank(contract.get('annual_leave'))}")
	lines.append("")

	lines.append("## 제7조 (사회보험 적용)")
	lines.append(f"- 적용 보험: {_blank(contract.get('social_insurance'), '고용·산재·국민연금·건강보험 가입')}")
	lines.append("")

	lines.append("## 제8조 (기타)")
	lines.append("이 계약에 정함이 없는 사항은 근로기준법령에 의한다.")
	if contract.get("other_terms"):
		lines.append(str(contract["other_terms"]))
	lines.append("")

	lines.append("## 서명")
	lines.append("")
	lines.append("| 사업주 | 근로자 |")
	lines.append("| --- | --- |")
	lines.append(
		f"| 사업체명: {company.get('company_name', '')} | 성명: {employee.get('employee_name', '')} |"
	)
	lines.append(
		f"| 대표자: {company.get('representative_name', '')} | 주소: {employee.get('address', '')} |"
	)
	lines.append(
		f"| 주소: {company.get('address', '')} | 주민등록번호: {employee.get('resident_registration_number', '')} |"
	)
	lines.append(
		f"| 사업자등록번호: {company.get('business_registration_number', '')} | (서명 또는 인) |"
	)
	lines.append("| (서명 또는 인) | |")
	lines.append("")

	lines.append("---")
	lines.append(f"※ {STATUTE_NOTE_17_1}")
	lines.append("")
	lines.append(f"※ {STATUTE_NOTE_17_2}")
	lines.append("")
	lines.append(f"※ {STATUTE_NOTE_ENFORCEMENT_DECREE}")

	return "\n".join(lines)


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _parse_hhmm(value: Any, name: str) -> int:
	"""'HH:MM' → 자정 기준 분(minute). 형식 불일치 시 ValueError."""
	text = str(value or "").strip()
	parts = text.split(":")
	if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
		raise ValueError(f"{name} must be 'HH:MM': {value!r}")
	hour, minute = int(parts[0]), int(parts[1])
	if hour > 23 or minute > 59:
		raise ValueError(f"{name} must be 'HH:MM': {value!r}")
	return hour * 60 + minute


def _sanitize_probation(probation: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
	"""수습기간 입력 검증 — 법정 기준 위반은 warnings에 누적 (raise 아님)."""
	if not isinstance(probation, dict):
		raise TypeError("data['probation'] must be a dict")
	try:
		months = int(probation.get("months") or 0)
	except (TypeError, ValueError) as exc:
		raise ValueError(f"probation.months must be an integer: {probation.get('months')!r}") from exc
	if months < 0:
		raise ValueError("probation.months must be >= 0")
	try:
		wage_percent = int(probation.get("wage_percent") or 100)
	except (TypeError, ValueError) as exc:
		raise ValueError(
			f"probation.wage_percent must be an integer: {probation.get('wage_percent')!r}"
		) from exc
	if wage_percent <= 0 or wage_percent > 100:
		raise ValueError("probation.wage_percent must be in 1..100")

	if months > 0 and wage_percent < PROBATION_WAGE_PERCENT_FLOOR:
		warnings.append(
			f"수습기간 중 임금 {wage_percent}%가 감액 하한 {PROBATION_WAGE_PERCENT_FLOOR}% 미만입니다 "
			"(최저임금법 §5③ — 단순노무직은 감액 불가)."
		)
	if months > PROBATION_REDUCTION_MONTH_LIMIT and wage_percent < 100:
		warnings.append(
			f"수습 감액은 수습 시작 후 {PROBATION_REDUCTION_MONTH_LIMIT}개월 이내만 가능합니다 "
			f"(최저임금법 시행령 §3 — 수습 {months}개월 전체 감액 불가)."
		)

	return {"months": months, "wage_percent": wage_percent}


def _build_net_preview(options: dict[str, Any], wage_total: int) -> dict[str, Any] | None:
	"""예상 실수령액 참고 산출 — net_to_gross._employee_deductions (forward) 재사용.

	참고용: 부양가족·비과세 가정을 결과에 명시하고, 미신청(enabled 아님)이거나
	임금 합계가 0이면 None을 반환한다.
	"""
	if not isinstance(options, dict):
		raise TypeError("data['net_preview'] must be a dict")
	if not options.get("enabled") or wage_total <= 0:
		return None

	non_taxable = int(options.get("non_taxable") or 0)
	if non_taxable < 0:
		raise ValueError("net_preview.non_taxable must be >= 0")
	dependents = max(1, int(options.get("dependents") or 1))

	deductions = _net_to_gross._employee_deductions(
		wage_total,
		non_taxable=non_taxable,
		dependents=dependents,
		children_under_8=0,
		include_pension=True,
		include_health=True,
		include_longterm_care=True,
		include_employment=True,
		pension_override=None,
	)
	return {
		"gross": wage_total,
		"non_taxable": non_taxable,
		"dependents": dependents,
		"deductions": deductions,
		"estimated_net": wage_total - deductions["total"],
	}


def _blank(value: Any, default: str = "　　　　　　") -> str:
	if value is None:
		return default
	text = str(value).strip()
	return text if text else default


def _sanitize_company(company: dict[str, Any]) -> dict[str, Any]:
	return {
		"company_name": str(company.get("company_name") or "").strip(),
		"representative_name": str(company.get("representative_name") or "").strip(),
		"address": str(company.get("address") or "").strip(),
		"business_registration_number": str(company.get("business_registration_number") or "").strip(),
		"contact": str(company.get("contact") or "").strip(),
	}


def _sanitize_employee(employee: dict[str, Any]) -> dict[str, Any]:
	raw_rrn = str(employee.get("resident_registration_number") or "").strip()
	return {
		"employee_name": str(employee.get("employee_name") or "").strip(),
		"address": str(employee.get("address") or "").strip(),
		"contact": str(employee.get("contact") or "").strip(),
		"resident_registration_number": mask_rrn(raw_rrn) if raw_rrn else "",
	}


def _sanitize_contract_period(period: dict[str, Any]) -> dict[str, Any]:
	def _norm(value: Any) -> str | None:
		if value is None:
			return None
		if hasattr(value, "isoformat"):
			return value.isoformat()
		text = str(value).strip()
		return text or None

	return {
		"start_date": _norm(period.get("start_date")),
		"end_date": _norm(period.get("end_date")),
	}


def _sanitize_scheduled_work(work: dict[str, Any]) -> dict[str, Any]:
	return {
		"start_time": str(work.get("start_time") or "").strip(),
		"end_time": str(work.get("end_time") or "").strip(),
		"work_days": str(work.get("work_days") or "").strip(),
		"break_time": str(work.get("break_time") or "").strip(),
	}


def _sanitize_wage_components(items: list[Any]) -> list[dict[str, Any]]:
	out: list[dict[str, Any]] = []
	for item in items:
		if not isinstance(item, dict):
			continue
		component = str(item.get("component") or "").strip()
		if not component:
			continue
		try:
			amount = int(item.get("amount") or 0)
		except (TypeError, ValueError):
			amount = 0
		out.append({"component": component, "amount": amount})
	return out


def _detect_missing(
	*,
	company: dict[str, Any],
	employee: dict[str, Any],
	contract_period: dict[str, Any],
	scheduled_work: dict[str, Any],
	wage_components: list[dict[str, Any]],
	workplace: str,
	job_description: str,
	holidays: str,
	annual_leave: str,
	wage_payment_date: str,
	wage_payment_method: str,
) -> list[str]:
	missing: list[str] = []

	for field in ("company_name", "representative_name", "address", "business_registration_number"):
		if not company.get(field):
			missing.append(f"company.{field}")

	for field in ("employee_name", "address"):
		if not employee.get(field):
			missing.append(f"employee.{field}")

	if not contract_period.get("start_date"):
		missing.append("contract_period.start_date")

	if not workplace:
		missing.append("workplace")
	if not job_description:
		missing.append("job_description")

	if not scheduled_work.get("start_time"):
		missing.append("scheduled_work.start_time")
	if not scheduled_work.get("end_time"):
		missing.append("scheduled_work.end_time")

	# §55 휴일
	if not holidays:
		missing.append("holidays")

	# §60 연차 유급휴가
	if not annual_leave:
		missing.append("annual_leave")

	# 임금 (§17①1호) — 구성항목 없으면 누락
	if not wage_components:
		missing.append("wage_components")

	# 그 밖에 대통령령으로 정하는 사항(시행령) 중 실무상 확정 가능한 지급일/방법
	if not wage_payment_date:
		missing.append("wage_payment_date")
	if not wage_payment_method:
		missing.append("wage_payment_method")

	return missing


__all__ = [
	"build_employment_contract",
	"compute_schedule_hours",
	"render_contract_markdown",
	"STATUTE_NOTE_17_1",
	"STATUTE_NOTE_17_2",
	"STATUTE_NOTE_ENFORCEMENT_DECREE",
]
