"""한국 표준 고용계약서 4종 양식 생성 — 근로기준법 제17조 준수.

Framework-free: 외부 LLM API 사용 없음. Frappe mutation 없음.
PDF 생성은 human_approved=True 게이트 이후 API 레이어에서 수행.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

# ---------------------------------------------------------------------------
# 계약 유형 레지스트리
# ---------------------------------------------------------------------------

CONTRACT_TYPES = {
	"regular": "기간의 정함이 없는 근로계약서 (정규직)",
	"fixed_term": "기간의 정함이 있는 근로계약서 (계약직)",
	"daily": "일용근로계약서",
	"part_time": "단시간근로자 표준근로계약서",
}

# ---------------------------------------------------------------------------
# 근로기준법 17조 필수 항목 (공통)
# ---------------------------------------------------------------------------

_BASE_REQUIRED_FIELDS = [
	"workplace",          # 근무장소
	"job_description",    # 업무 내용
	"work_start_time",    # 소정근로시간 시작
	"work_end_time",      # 소정근로시간 종료
	"work_days",          # 근무일 (요일)
	"holidays",           # 주휴일 등
	"base_wage",          # 기본급
	"wage_payment_date",  # 임금 지급일
	"wage_payment_method",# 임금 지급방법
	"annual_leave",       # 연차 유급휴가
]

_CONTRACT_START_DATE_FIELD = "contract_start_date"

_REQUIRED_BY_TYPE: dict[str, list[str]] = {
	"regular": _BASE_REQUIRED_FIELDS + [_CONTRACT_START_DATE_FIELD],
	"fixed_term": _BASE_REQUIRED_FIELDS + [_CONTRACT_START_DATE_FIELD, "contract_end_date"],
	"daily": [
		"workplace",
		"job_description",
		"work_start_time",
		"work_end_time",
		"daily_wage",       # 일당
		"wage_payment_date",
		"wage_payment_method",
	],
	"part_time": _BASE_REQUIRED_FIELDS + [_CONTRACT_START_DATE_FIELD, "weekly_work_hours"],
}

# 주민등록번호 패턴 (뒷자리 마스킹)
_RRN_PATTERN = re.compile(r"(\d{6})-?(\d{7})")

# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


def build_korea_employment_contract(
	*,
	contract_type: str,
	company: dict[str, Any],
	employee: dict[str, Any],
	contract_terms: dict[str, Any],
) -> dict[str, Any]:
	"""근기법 17조 필수 항목 검증 + 계약서 dict 반환.

	Parameters
	----------
	contract_type:
		"regular" | "fixed_term" | "daily" | "part_time"
	company:
		사업주 정보. 필수: company_name, representative_name, address, business_registration_number
	employee:
		근로자 정보. 필수: employee_name, address. 선택: resident_registration_number (자동 마스킹)
	contract_terms:
		계약 조건. 유형별 필수 항목 참고.

	Returns
	-------
	dict:
		{
			"contract_type": "korea_employment_contract_draft_v1",
			"form_type": str,
			"form_title": str,
			"company": {...},
			"employee": {...},      # RRN 마스킹 적용
			"terms": {...},
			"required_fields_complete": bool,
			"missing_required_fields": list[str],
			"html_content": str,   # Jinja 렌더 없이 str.format_map 기반 플레인 HTML
		}
	"""
	if contract_type not in CONTRACT_TYPES:
		raise ValueError(
			f"contract_type must be one of: {', '.join(sorted(CONTRACT_TYPES))}. Got: {contract_type!r}"
		)

	_require_dict(company, "company")
	_require_dict(employee, "employee")
	_require_dict(contract_terms, "contract_terms")

	safe_company = _sanitize_company(company)
	safe_employee = _sanitize_employee(employee)
	safe_terms = _sanitize_terms(contract_terms, contract_type)

	missing = _check_required_fields(contract_type, safe_terms, safe_company, safe_employee)
	missing += _check_type_specific_constraints(contract_type, safe_terms)

	html_content = _render_html(contract_type, safe_company, safe_employee, safe_terms)

	return {
		"contract_type": "korea_employment_contract_draft_v1",
		"form_type": contract_type,
		"form_title": CONTRACT_TYPES[contract_type],
		"company": safe_company,
		"employee": safe_employee,
		"terms": safe_terms,
		"required_fields_complete": len(missing) == 0,
		"missing_required_fields": missing,
		"html_content": html_content,
		"mutation_boundary": "preview_only_no_submit_approve_send",
		"requires_human_approval": True,
		"ai_role": "assistant_only",
	}


def mask_rrn(value: str) -> str:
	"""주민등록번호 앞 6자리 + 뒷자리 ****** 마스킹.

	Examples
	--------
	"900101-1234567" → "900101-******"
	"9001011234567"  → "900101-******"
	"""
	if not isinstance(value, str):
		return "******-******"
	m = _RRN_PATTERN.search(value)
	if m:
		return f"{m.group(1)}-******"
	# 숫자만 있는 경우 앞 6자리
	digits = re.sub(r"\D", "", value)
	if len(digits) >= 6:
		return f"{digits[:6]}-******"
	return "******-******"


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 입력 검증 및 정제
# ---------------------------------------------------------------------------


def _require_dict(value: Any, field: str) -> None:
	if not isinstance(value, dict):
		raise TypeError(f"{field} must be a dict, got {type(value).__name__}")


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
		# 주민번호는 무조건 마스킹
		"resident_registration_number": mask_rrn(raw_rrn) if raw_rrn else "",
	}


def _sanitize_terms(terms: dict[str, Any], contract_type: str) -> dict[str, Any]:
	out: dict[str, Any] = {}
	for key, value in terms.items():
		if isinstance(value, date):
			out[key] = value.isoformat()
		elif value is None:
			out[key] = ""
		else:
			out[key] = value
	return out


def _check_required_fields(
	contract_type: str,
	terms: dict[str, Any],
	company: dict[str, Any],
	employee: dict[str, Any],
) -> list[str]:
	missing: list[str] = []
	required = _REQUIRED_BY_TYPE.get(contract_type, [])

	# 회사 필수 필드
	for field in ("company_name", "representative_name", "address", "business_registration_number"):
		if not company.get(field):
			missing.append(f"company.{field}")

	# 직원 필수 필드
	for field in ("employee_name", "address"):
		if not employee.get(field):
			missing.append(f"employee.{field}")

	# 계약 조건 필수 필드
	for field in required:
		if not _has_value(terms.get(field)):
			missing.append(f"contract_terms.{field}")

	return missing


def _check_type_specific_constraints(contract_type: str, terms: dict[str, Any]) -> list[str]:
	"""유형별 추가 비즈니스 규칙 검증."""
	issues: list[str] = []

	if contract_type == "fixed_term":
		start = terms.get("contract_start_date")
		end = terms.get("contract_end_date")
		if start and end:
			try:
				if _parse_date(end) <= _parse_date(start):
					issues.append("contract_terms.contract_end_date must be after contract_start_date")
			except ValueError:
				pass  # 날짜 포맷 오류는 missing_required_fields에서 처리

	if contract_type == "part_time":
		weekly_hours_raw = terms.get("weekly_work_hours")
		if weekly_hours_raw is not None:
			try:
				weekly_hours = float(weekly_hours_raw)
				if weekly_hours >= 40:
					issues.append(
						"contract_terms.weekly_work_hours must be less than 40 for part-time workers"
					)
			except (TypeError, ValueError):
				issues.append("contract_terms.weekly_work_hours must be a number")

	return issues


def _has_value(value: Any) -> bool:
	if value is None:
		return False
	if isinstance(value, str):
		return bool(value.strip())
	return True


def _parse_date(value: Any) -> date:
	if isinstance(value, date):
		return value
	if isinstance(value, str):
		return date.fromisoformat(value.strip())
	raise ValueError(f"Cannot parse date: {value!r}")


# ---------------------------------------------------------------------------
# HTML 렌더 (Jinja 없이 — framework-free)
# ---------------------------------------------------------------------------


def _render_html(
	contract_type: str,
	company: dict[str, Any],
	employee: dict[str, Any],
	terms: dict[str, Any],
) -> str:
	"""계약서 유형별 HTML 생성."""
	renderer = {
		"regular": _html_regular,
		"fixed_term": _html_fixed_term,
		"daily": _html_daily,
		"part_time": _html_part_time,
	}[contract_type]
	return renderer(company, employee, terms)


def _base_styles() -> str:
	return """<style>
body { font-family: 'Malgun Gothic', '맑은 고딕', 'NanumGothic', '나눔고딕', sans-serif; font-size: 10pt; line-height: 1.6; }
.contract-wrapper { max-width: 800px; margin: 0 auto; padding: 20px; }
h2.contract-title { text-align: center; font-size: 16pt; font-weight: bold; margin: 20px 0 30px; }
table.contract-table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
table.contract-table th, table.contract-table td { border: 1px solid #333; padding: 6px 10px; vertical-align: top; }
table.contract-table th { background-color: #f5f5f5; width: 30%; font-weight: bold; white-space: nowrap; }
.section-title { font-weight: bold; font-size: 11pt; margin: 20px 0 8px; border-bottom: 1px solid #333; padding-bottom: 4px; }
.signature-area { margin-top: 40px; }
.signature-row { display: flex; justify-content: space-between; margin-top: 30px; }
.signature-block { width: 45%; }
.signature-block p { margin: 4px 0; }
.sign-line { border-bottom: 1px solid #333; margin-top: 40px; }
.note { font-size: 9pt; color: #555; margin-top: 8px; }
.statute { font-size: 9pt; color: #444; margin-top: 20px; border-top: 1px dashed #999; padding-top: 10px; }
</style>"""


def _v(terms: dict[str, Any], key: str, default: str = "　　　　　　") -> str:
	"""terms에서 값을 가져오고 없으면 기본 공란 반환."""
	val = terms.get(key)
	if not _has_value(val):
		return default
	return str(val)


def _html_regular(company: dict, employee: dict, terms: dict) -> str:
	title = CONTRACT_TYPES["regular"]
	today = date.today().strftime("%Y년 %m월 %d일")
	return f"""{_base_styles()}
<div class="contract-wrapper">
<h2 class="contract-title">{title}</h2>

<p>사업주 <strong>{company.get("company_name","")}</strong>(이하 "사업주"라 함)와 근로자 <strong>{employee.get("employee_name","")}</strong>(이하 "근로자"라 함)는 다음과 같이 근로계약을 체결한다.</p>

<div class="section-title">제1조 (근로계약기간)</div>
<table class="contract-table">
  <tr><th>계약 시작일</th><td>{_v(terms, "contract_start_date")}</td></tr>
  <tr><th>계약 형태</th><td>기간의 정함이 없는 근로계약</td></tr>
</table>

<div class="section-title">제2조 (근무장소 및 업무)</div>
<table class="contract-table">
  <tr><th>근무장소</th><td>{_v(terms, "workplace")}</td></tr>
  <tr><th>업무 내용</th><td>{_v(terms, "job_description")}</td></tr>
</table>

<div class="section-title">제3조 (소정근로시간)</div>
<table class="contract-table">
  <tr><th>소정근로시간</th><td>{_v(terms, "work_start_time")} ~ {_v(terms, "work_end_time")}<br>(휴게시간 {_v(terms, "break_time", "1시간")})</td></tr>
  <tr><th>근무일</th><td>{_v(terms, "work_days")}</td></tr>
</table>

<div class="section-title">제4조 (휴일)</div>
<table class="contract-table">
  <tr><th>주휴일</th><td>{_v(terms, "holidays")}</td></tr>
  <tr><th>기타 휴일</th><td>{_v(terms, "other_holidays", "근로기준법 및 취업규칙에 따름")}</td></tr>
</table>

<div class="section-title">제5조 (임금)</div>
<table class="contract-table">
  <tr><th>기본급</th><td>{_v(terms, "base_wage")} 원</td></tr>
  <tr><th>기타 수당</th><td>{_v(terms, "other_allowances", "해당 없음")}</td></tr>
  <tr><th>임금 지급일</th><td>매월 {_v(terms, "wage_payment_date")}일</td></tr>
  <tr><th>지급 방법</th><td>{_v(terms, "wage_payment_method")}</td></tr>
</table>

<div class="section-title">제6조 (연차유급휴가)</div>
<table class="contract-table">
  <tr><th>연차유급휴가</th><td>{_v(terms, "annual_leave", "근로기준법에서 정하는 바에 따름")}</td></tr>
</table>

<div class="section-title">제7조 (사회보험 적용)</div>
<table class="contract-table">
  <tr><th>적용 보험</th><td>{_v(terms, "social_insurance", "고용·산재·국민연금·건강보험 가입")}</td></tr>
</table>

<div class="section-title">제8조 (기타)</div>
<p>이 계약에 정함이 없는 사항은 근로기준법령에 의한다.</p>
<p>{_v(terms, "other_terms", "")}</p>

{_signature_block(company, employee, today)}
{_statute_note()}
</div>"""


def _html_fixed_term(company: dict, employee: dict, terms: dict) -> str:
	title = CONTRACT_TYPES["fixed_term"]
	today = date.today().strftime("%Y년 %m월 %d일")
	return f"""{_base_styles()}
<div class="contract-wrapper">
<h2 class="contract-title">{title}</h2>

<p>사업주 <strong>{company.get("company_name","")}</strong>(이하 "사업주"라 함)와 근로자 <strong>{employee.get("employee_name","")}</strong>(이하 "근로자"라 함)는 다음과 같이 근로계약을 체결한다.</p>

<div class="section-title">제1조 (근로계약기간)</div>
<table class="contract-table">
  <tr><th>계약 시작일</th><td>{_v(terms, "contract_start_date")}</td></tr>
  <tr><th>계약 종료일</th><td>{_v(terms, "contract_end_date")}</td></tr>
  <tr><th>계약 사유</th><td>{_v(terms, "contract_reason", "업무상 필요")}</td></tr>
</table>

<div class="section-title">제2조 (근무장소 및 업무)</div>
<table class="contract-table">
  <tr><th>근무장소</th><td>{_v(terms, "workplace")}</td></tr>
  <tr><th>업무 내용</th><td>{_v(terms, "job_description")}</td></tr>
</table>

<div class="section-title">제3조 (소정근로시간)</div>
<table class="contract-table">
  <tr><th>소정근로시간</th><td>{_v(terms, "work_start_time")} ~ {_v(terms, "work_end_time")}<br>(휴게시간 {_v(terms, "break_time", "1시간")})</td></tr>
  <tr><th>근무일</th><td>{_v(terms, "work_days")}</td></tr>
</table>

<div class="section-title">제4조 (휴일)</div>
<table class="contract-table">
  <tr><th>주휴일</th><td>{_v(terms, "holidays")}</td></tr>
  <tr><th>기타 휴일</th><td>{_v(terms, "other_holidays", "근로기준법 및 취업규칙에 따름")}</td></tr>
</table>

<div class="section-title">제5조 (임금)</div>
<table class="contract-table">
  <tr><th>기본급</th><td>{_v(terms, "base_wage")} 원</td></tr>
  <tr><th>기타 수당</th><td>{_v(terms, "other_allowances", "해당 없음")}</td></tr>
  <tr><th>임금 지급일</th><td>매월 {_v(terms, "wage_payment_date")}일</td></tr>
  <tr><th>지급 방법</th><td>{_v(terms, "wage_payment_method")}</td></tr>
</table>

<div class="section-title">제6조 (연차유급휴가)</div>
<table class="contract-table">
  <tr><th>연차유급휴가</th><td>{_v(terms, "annual_leave", "근로기준법에서 정하는 바에 따름")}</td></tr>
</table>

<div class="section-title">제7조 (사회보험 적용)</div>
<table class="contract-table">
  <tr><th>적용 보험</th><td>{_v(terms, "social_insurance", "고용·산재·국민연금·건강보험 가입")}</td></tr>
</table>

<div class="section-title">제8조 (기타)</div>
<p>이 계약에 정함이 없는 사항은 근로기준법령에 의한다.</p>
<p>{_v(terms, "other_terms", "")}</p>

{_signature_block(company, employee, today)}
{_statute_note()}
</div>"""


def _html_daily(company: dict, employee: dict, terms: dict) -> str:
	title = CONTRACT_TYPES["daily"]
	today = date.today().strftime("%Y년 %m월 %d일")
	return f"""{_base_styles()}
<div class="contract-wrapper">
<h2 class="contract-title">{title}</h2>

<p>사업주 <strong>{company.get("company_name","")}</strong>(이하 "사업주"라 함)와 근로자 <strong>{employee.get("employee_name","")}</strong>(이하 "근로자"라 함)는 다음과 같이 일용근로계약을 체결한다.</p>

<div class="section-title">제1조 (근로계약기간)</div>
<table class="contract-table">
  <tr><th>근로일</th><td>{_v(terms, "work_date", today)}</td></tr>
  <tr><th>근로 형태</th><td>일용근로 (1일 단위)</td></tr>
</table>

<div class="section-title">제2조 (근무장소 및 업무)</div>
<table class="contract-table">
  <tr><th>근무장소</th><td>{_v(terms, "workplace")}</td></tr>
  <tr><th>업무 내용</th><td>{_v(terms, "job_description")}</td></tr>
</table>

<div class="section-title">제3조 (소정근로시간)</div>
<table class="contract-table">
  <tr><th>소정근로시간</th><td>{_v(terms, "work_start_time")} ~ {_v(terms, "work_end_time")}<br>(휴게시간 {_v(terms, "break_time", "1시간")})</td></tr>
</table>

<div class="section-title">제4조 (임금)</div>
<table class="contract-table">
  <tr><th>일당 (일급)</th><td>{_v(terms, "daily_wage")} 원</td></tr>
  <tr><th>임금 지급일</th><td>{_v(terms, "wage_payment_date")}</td></tr>
  <tr><th>지급 방법</th><td>{_v(terms, "wage_payment_method")}</td></tr>
</table>

<div class="section-title">제5조 (사회보험 적용)</div>
<table class="contract-table">
  <tr><th>고용보험</th><td>{_v(terms, "employment_insurance", "해당 여부 확인 필요")}</td></tr>
  <tr><th>산재보험</th><td>적용</td></tr>
</table>

<div class="section-title">제6조 (기타)</div>
<p>이 계약에 정함이 없는 사항은 근로기준법령에 의한다.</p>
<p>{_v(terms, "other_terms", "")}</p>

{_signature_block(company, employee, today)}
{_statute_note()}
</div>"""


def _html_part_time(company: dict, employee: dict, terms: dict) -> str:
	title = CONTRACT_TYPES["part_time"]
	today = date.today().strftime("%Y년 %m월 %d일")
	weekly_hours = _v(terms, "weekly_work_hours", "　　")
	return f"""{_base_styles()}
<div class="contract-wrapper">
<h2 class="contract-title">{title}</h2>

<p>사업주 <strong>{company.get("company_name","")}</strong>(이하 "사업주"라 함)와 단시간근로자 <strong>{employee.get("employee_name","")}</strong>(이하 "근로자"라 함)는 다음과 같이 근로계약을 체결한다.</p>

<p class="note">※ 단시간근로자: 주 소정근로시간이 통상근로자의 소정근로시간에 비하여 짧은 근로자 (근로기준법 제2조제1항제9호)</p>

<div class="section-title">제1조 (근로계약기간)</div>
<table class="contract-table">
  <tr><th>계약 시작일</th><td>{_v(terms, "contract_start_date")}</td></tr>
  <tr><th>계약 형태</th><td>단시간 근로계약 (주 {weekly_hours}시간)</td></tr>
</table>

<div class="section-title">제2조 (근무장소 및 업무)</div>
<table class="contract-table">
  <tr><th>근무장소</th><td>{_v(terms, "workplace")}</td></tr>
  <tr><th>업무 내용</th><td>{_v(terms, "job_description")}</td></tr>
</table>

<div class="section-title">제3조 (소정근로시간)</div>
<table class="contract-table">
  <tr><th>주 소정근로시간</th><td>{weekly_hours}시간</td></tr>
  <tr><th>근로시간</th><td>{_v(terms, "work_start_time")} ~ {_v(terms, "work_end_time")}<br>(휴게시간 {_v(terms, "break_time", "해당 법령에 따름")})</td></tr>
  <tr><th>근무일</th><td>{_v(terms, "work_days")}</td></tr>
</table>

<div class="section-title">제4조 (휴일)</div>
<table class="contract-table">
  <tr><th>주휴일</th><td>{_v(terms, "holidays")}</td></tr>
  <tr><th>기타 휴일</th><td>{_v(terms, "other_holidays", "근로기준법 및 취업규칙에 따름")}</td></tr>
</table>

<div class="section-title">제5조 (임금)</div>
<table class="contract-table">
  <tr><th>시급 / 기본급</th><td>{_v(terms, "base_wage")} 원</td></tr>
  <tr><th>기타 수당</th><td>{_v(terms, "other_allowances", "해당 없음")}</td></tr>
  <tr><th>임금 지급일</th><td>매월 {_v(terms, "wage_payment_date")}일</td></tr>
  <tr><th>지급 방법</th><td>{_v(terms, "wage_payment_method")}</td></tr>
</table>

<div class="section-title">제6조 (연차유급휴가)</div>
<table class="contract-table">
  <tr><th>연차유급휴가</th><td>{_v(terms, "annual_leave", "근로기준법에서 정하는 비례 계산에 따름")}</td></tr>
</table>

<div class="section-title">제7조 (초과근로)</div>
<table class="contract-table">
  <tr><th>초과근로</th><td>{_v(terms, "overtime_terms", "근로자 동의 시 1주 12시간 이내. 가산임금 지급 (근로기준법 제56조)")}</td></tr>
</table>

<div class="section-title">제8조 (사회보험 적용)</div>
<table class="contract-table">
  <tr><th>적용 보험</th><td>{_v(terms, "social_insurance", "고용·산재 가입. 국민연금·건강보험은 월 60시간 이상 시 적용")}</td></tr>
</table>

<div class="section-title">제9조 (기타)</div>
<p>이 계약에 정함이 없는 사항은 근로기준법령에 의한다.</p>
<p>{_v(terms, "other_terms", "")}</p>

{_signature_block(company, employee, today)}
{_statute_note()}
</div>"""


def _signature_block(company: dict, employee: dict, today: str) -> str:
	company_name = company.get("company_name", "")
	representative = company.get("representative_name", "")
	company_address = company.get("address", "")
	business_reg = company.get("business_registration_number", "")
	employee_name = employee.get("employee_name", "")
	employee_address = employee.get("address", "")
	employee_rrn = employee.get("resident_registration_number", "")

	return f"""<div class="signature-area">
<p style="text-align:center; margin-top: 30px;">{today}</p>
<div class="signature-row">
  <div class="signature-block">
    <p><strong>사업주</strong></p>
    <p>사업체명: {company_name}</p>
    <p>대표자: {representative}</p>
    <p>주소: {company_address}</p>
    <p>사업자등록번호: {business_reg}</p>
    <div class="sign-line"></div>
    <p style="text-align:right;">(서명 또는 인)</p>
  </div>
  <div class="signature-block">
    <p><strong>근로자</strong></p>
    <p>성명: {employee_name}</p>
    <p>주소: {employee_address}</p>
    <p>주민등록번호: {employee_rrn if employee_rrn else "　　　　　　"}</p>
    <div class="sign-line"></div>
    <p style="text-align:right;">(서명 또는 인)</p>
  </div>
</div>
</div>"""


def _statute_note() -> str:
	return """<div class="statute">
<p>※ 근로기준법 제17조에 따라 사업주는 근로계약 체결 시 임금, 소정근로시간, 제55조에 따른 휴일, 제60조에 따른 연차 유급휴가, 그 밖에 대통령령으로 정하는 근로조건을 명시하여야 합니다.</p>
<p>※ 이 계약서는 근로자에게 교부하여야 합니다 (근로기준법 제17조제2항).</p>
</div>"""


__all__ = [
	"CONTRACT_TYPES",
	"build_korea_employment_contract",
	"mask_rrn",
]
