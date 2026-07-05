"""4대보험 신고서 xlsx 생성기 — framework-free.

US-001 실측 매핑(docs/korea_hrms/insurance-templates-map.md)을 단일 출처로 사용해,
템플릿 원본을 복사한 뒤 데이터 행을 채워 실파일(xlsx)을 생성한다.

안전 불변식 (스킬 사고이력 2026-05-15):
  - candidates가 비어 있으면 ValueError — 빈 신고서를 만들지 않는다(fail-closed).
  - 사람 확인 게이트(human_approved)는 상위 _api 래퍼가 책임진다. 이 코어는 순수 생성만 한다.
  - 주민번호(rrn)는 후보에 있을 때만 채우고, 없으면 빈칸으로 둔다.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import openpyxl

# 취득신고서 '서식' 시트 매핑 (US-001)
ACQUISITION_SHEET = "서식"
ACQUISITION_DATA_START_ROW = 3
# 취득일은 4개 보험(H/P/V/AD)에 동일, 보수월액은 G/O/U/AC에 동일 기입
ACQUISITION_DATE_COLS = ("H", "P", "V", "AD")
ACQUISITION_WAGE_COLS = ("G", "O", "U", "AC")


def _yyyymmdd(iso_value: Any) -> str:
	"""ISO date(YYYY-MM-DD) 또는 date → 신고 서식용 'YYYYMMDD' 문자열."""
	if iso_value in (None, ""):
		return ""
	if isinstance(iso_value, dt.date):
		return iso_value.strftime("%Y%m%d")
	day = dt.date.fromisoformat(str(iso_value)[:10])
	return day.strftime("%Y%m%d")


def generate_acquisition_report(
	template_path: str,
	candidates: list[dict],
	out_path: str,
	workplace_info: dict | None = None,
) -> str:
	"""취득신고서 xlsx 생성.

	candidates: insurance_filing.detect_acquisitions 출력
	  [{employee, employee_name, acquisition_date(ISO), monthly_wage, rrn?}]
	workplace_info: 사업장 정보(대표자여부 기본값 등 선택) — 없으면 기본값 사용.
	반환: out_path.
	"""
	if not candidates:
		raise ValueError("candidates is empty — 빈 취득신고서를 생성하지 않는다 (fail-closed).")

	workplace_info = workplace_info or {}
	default_representative = str(workplace_info.get("representative_flag", "N"))

	wb = openpyxl.load_workbook(template_path)
	ws = wb[ACQUISITION_SHEET]

	for offset, cand in enumerate(candidates):
		row = ACQUISITION_DATA_START_ROW + offset
		ws[f"A{row}"] = str(cand.get("rrn") or "")
		ws[f"B{row}"] = cand.get("employee_name", "")
		ws[f"C{row}"] = str(cand.get("representative_flag") or default_representative)
		acq_date = _yyyymmdd(cand.get("acquisition_date"))
		wage = int(cand.get("monthly_wage") or 0)
		for col in ACQUISITION_DATE_COLS:
			ws[f"{col}{row}"] = acq_date
		for col in ACQUISITION_WAGE_COLS:
			ws[f"{col}{row}"] = wage

	wb.save(out_path)
	wb.close()
	return out_path
