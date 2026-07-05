# Korea HRMS MCP Server v0 (stdio) — "채용 없이 이용하는 AI HR 담당자"의 도구 계층.
#
# 순수 파이썬 코어(hrms/regional/south_korea/*, frappe 미의존)를 MCP 도구로 노출한다.
# AI가 연차·퇴직금·법정공제를 추론이 아니라 검증된 계산으로 답하게 하는 것이 목적.
# 숫자 출력에는 항상 산정 근거(basis) 필드를 그대로 노출한다.
#
# 실행:   python3 mcp_server/server.py            (stdio)
# 연결:   claude mcp add korea-hrms -- python3 <repo>/mcp_server/server.py
#
# 주의: `import hrms` 금지 — hrms/__init__.py가 frappe를 import한다.
#       테스트와 동일하게 importlib 파일 경로 로드를 쓴다.

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import pathlib
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "hrms" / "regional" / "south_korea"


def _load_core(name: str):
    spec = importlib.util.spec_from_file_location(f"korea_{name}", CORE_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


annual_leave = _load_core("annual_leave")
attendance_summary = _load_core("attendance_summary")
statutory_payroll = _load_core("statutory_payroll")
compliance_checklist = _load_core("compliance_checklist")
severance_pay = _load_core("severance_pay")
ai_chat = _load_core("ai_chat")


def _date(value: str, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD): {value!r}") from error


def _jsonable(value: Any) -> Any:
    """코어 반환값(dict, date 포함)을 JSON 직렬화 가능한 형태로 변환한다."""
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


mcp = FastMCP(
    "korea-hrms",
    stateless_http=True,  # AI 플레인 확장 불변식: HTTP 모드 무상태 (http_server.py)
    instructions=(
        "Korea HRMS 노무 계산 도구. 연차·퇴직금·법정공제 등 숫자는 반드시 이 도구의 계산 결과와 "
        "산정 근거를 그대로 인용하고, 자체 산수로 대체하지 말 것."
    ),
)


@mcp.tool()
def calculate_annual_leave(
    hire_date: str,
    as_of_date: str,
    basis: str = "Hire Date",
    fiscal_year_start_month: int = 1,
    fiscal_year_start_day: int = 1,
    employment_end_date: str | None = None,
) -> dict:
    """근로기준법 연차유급휴가 산정. 1년 미만 월 개근 1일(최대 11), 1년 이상 15일,
    3년차부터 2년마다 +1(최대 25). basis는 "Hire Date"(입사일 기준) 또는 "Fiscal Year"(회계연도).
    날짜는 YYYY-MM-DD."""
    result = annual_leave.calculate_annual_leave_entitlement(
        hire_date=_date(hire_date, "hire_date"),
        as_of_date=_date(as_of_date, "as_of_date"),
        basis=basis,
        fiscal_year_start_month=fiscal_year_start_month,
        fiscal_year_start_day=fiscal_year_start_day,
        employment_end_date=_date(employment_end_date, "employment_end_date")
        if employment_end_date
        else None,
    )
    return _jsonable(result)


@mcp.tool()
def calculate_severance(
    hire_date: str,
    severance_date: str,
    average_wage_per_day: float,
    ordinary_wage_per_day: float | None = None,
    exclusion_periods: list[list[str]] | None = None,
) -> dict:
    """퇴직금 계산 (근로자퇴직급여 보장법 제8조): max(평균임금, 통상임금)×30×(재직일수/365).
    severance_date는 마지막 근무일 다음 날. exclusion_periods는 [["YYYY-MM-DD","YYYY-MM-DD"], ...]
    (육아휴직 등 재직일수 제외 구간). 1년 미만은 퇴직금 0."""
    exclusions = None
    if exclusion_periods:
        exclusions = [
            (_date(start, "exclusion start"), _date(end, "exclusion end"))
            for start, end in exclusion_periods
        ]
    result = severance_pay.calculate_severance_pay(
        hire_date=_date(hire_date, "hire_date"),
        severance_date=_date(severance_date, "severance_date"),
        average_wage_per_day=average_wage_per_day,
        ordinary_wage_per_day=ordinary_wage_per_day,
        exclusions=exclusions,
    )
    return _jsonable(result)


def _to_attendance_records(records: list[dict]) -> list:
    normalized = []
    for index, raw in enumerate(records):
        row = dict(raw)
        if "attendance_date" not in row:
            raise ValueError(f"records[{index}] is missing attendance_date")
        row["attendance_date"] = _date(str(row["attendance_date"]), f"records[{index}].attendance_date")
        normalized.append(attendance_summary.AttendanceRecord(**row))
    return normalized


@mcp.tool()
def summarize_attendance(
    records: list[dict],
    period_start: str,
    period_end: str,
    unmarked_days_by_employee: dict[str, float] | None = None,
) -> dict:
    """근태 기록을 직원별로 마감 요약. records 항목: {employee, attendance_date(YYYY-MM-DD),
    status, working_hours?, late_entry?, early_exit?, overtime_hours?, leave_type?, holiday?,
    weekly_off?, half_day_status?}. 지각·조퇴·연장·휴일근로·미체크일 신호를 보존해 반환."""
    summary = attendance_summary.summarize_attendance(
        _to_attendance_records(records),
        period_start=_date(period_start, "period_start"),
        period_end=_date(period_end, "period_end"),
        unmarked_days_by_employee=unmarked_days_by_employee,
    )
    return _jsonable(summary)


@mcp.tool()
def get_attendance_closing_period(as_of_date: str, cutoff_day: int) -> dict:
    """급여 산정 기간(마감 구간) 계산. cutoff_day가 말일 마감이면 31, 20일 마감이면 20 등."""
    start, end = attendance_summary.closing_period_for(_date(as_of_date, "as_of_date"), cutoff_day)
    return _jsonable({"period_start": start, "period_end": end, "cutoff_day": cutoff_day})


@mcp.tool()
def build_statutory_payroll(earnings: list[dict], policy: dict) -> dict:
    """법정공제(4대보험 등) 스냅샷 계산. policy에는 당해연도 요율을 호출자가 명시해야 한다
    (연도 하드코딩·기본 요율 없음 — 요율 누락 시 명시적 오류). earnings는 임금 항목 목록."""
    return _jsonable(statutory_payroll.build_statutory_payroll_snapshot(earnings=earnings, policy=policy))


@mcp.tool()
def get_salary_component_presets() -> dict:
    """한국 급여 구성항목 프리셋(기본급·수당·공제 항목 정의) 조회."""
    return _jsonable(statutory_payroll.load_korea_salary_component_presets())


@mcp.tool()
def run_compliance_diagnosis(items: list[dict], evidence: dict[str, list[str]] | None = None) -> dict:
    """노동법 컴플라이언스 진단 컨트랙트 생성. 결정적 점검 결과와 조치 항목을 반환하며
    법률 자문·수치 리스크 점수가 아니다(사람 검토 전제)."""
    return _jsonable(compliance_checklist.build_compliance_diagnosis(items, evidence=evidence))


@mcp.tool()
def hr_chat(question: str, user_role: str = "employee", session_id: str = "mcp") -> dict:
    """노동법·HR 질문에 법령/판례 인용과 함께 답변 (retrieval 기반, LLM 아님 — 카탈로그 조회).
    답변은 AI 보조이며 확정 판단은 담당자/노무사 검토 필수. user_role: employee | manager | hr."""
    return _jsonable(
        ai_chat.chat_query(
            user_question=question,
            user_role=user_role,
            session_id=session_id,
        )
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    mcp.run()
