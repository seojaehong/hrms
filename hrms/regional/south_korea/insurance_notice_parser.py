# -*- coding: utf-8 -*-
"""공단 고지내역 xlsx 파서 — framework-free 코어.

공단 EDI에서 내려받은 4대보험 고지내역 xlsx를 대사 표준행으로 파싱한다.
실제 공단 서식은 절대 가정하지 않는다 — 컬럼 위치는 전부 column_map으로 주입한다
(예: {"match_key": "B", "national_pension": "E", "health_insurance": "F"}, 값은 엑셀 컬럼 레터).

반환: {"rows": [...], "errors": [...]}
- rows: {"match_key": str, <금액키>: int} — 금액 키는 column_map에 있는 것만 포함.
- errors: 금액 파싱 불가 셀을 숨기지 않고 행별로 노출
          {"row": <엑셀 행번호>, "column": <레터>, "value": <원본값>, "reason": str}.

원칙:
- match_key가 비어있는(완전 빈) 행은 skip.
- 금액이 파싱 불가한 행은 숨기지 않고 errors로 드러낸다.
- 계산·조회 없음. openpyxl은 함수 내부에서 import한다.

실행 검증: python3 hrms/tests/test_korea_insurance_notice_parser.py
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

# match_key는 금액 컬럼이 아니라 매칭 키 — column_map에서 특별 취급.
_MATCH_KEY = "match_key"


def _clean_amount(value: Any) -> int | None:
	"""셀 값을 원 단위 정수로 정리. 빈 값이면 None(해당 금액 없음), 파싱 불가면 ValueError."""
	if value is None:
		return None
	if isinstance(value, bool):
		# True/False가 금액으로 잘못 들어온 경우 — 숨기지 말고 오류로.
		raise ValueError(f"금액이 boolean입니다: {value!r}")
	if isinstance(value, int):
		return int(value)
	if isinstance(value, float):
		if value != int(value):
			raise ValueError(f"금액에 소수부가 있습니다: {value!r}")
		return int(value)
	# 문자열: 콤마/공백/'원' 표기 제거 후 정수 변환
	s = str(value).replace(",", "").replace(" ", "").replace("원", "").strip()
	if s == "":
		return None
	try:
		dec = Decimal(s)
	except Exception as exc:  # noqa: BLE001
		raise ValueError(f"금액이 숫자가 아닙니다: {value!r}") from exc
	if dec != dec.to_integral_value():
		raise ValueError(f"금액에 소수부가 있습니다: {value!r}")
	return int(dec)


def _column_index(letter: str) -> int:
	"""엑셀 컬럼 레터('A','B',...,'AA') → 1-기반 인덱스."""
	letter = str(letter).strip().upper()
	if not letter or not letter.isalpha():
		raise ValueError(f"유효하지 않은 컬럼 레터: {letter!r}")
	idx = 0
	for ch in letter:
		idx = idx * 26 + (ord(ch) - ord("A") + 1)
	return idx


def parse_notice_xlsx(
	path: str,
	column_map: dict[str, str],
	header_row: int = 1,
) -> dict[str, Any]:
	"""공단 고지 xlsx → 대사 표준행 리스트.

	Args:
		path: xlsx 파일 경로.
		column_map: {"match_key": <레터>, "national_pension": <레터>, ...}.
			키는 표준행 필드명, 값은 엑셀 컬럼 레터. "match_key"는 필수.
		header_row: 헤더 행 번호(1-기반). 데이터는 header_row+1 행부터 읽는다.

	Returns:
		{"rows": [{"match_key": str, <금액키>: int}...],
		 "errors": [{"row", "column", "value", "reason"}...]}
	"""
	from openpyxl import load_workbook

	if _MATCH_KEY not in column_map:
		raise ValueError("column_map에 'match_key'가 필요합니다")

	match_col = _column_index(column_map[_MATCH_KEY])
	amount_cols: list[tuple[str, str, int]] = [
		(field, letter, _column_index(letter))
		for field, letter in column_map.items()
		if field != _MATCH_KEY
	]

	wb = load_workbook(path, read_only=True, data_only=True)
	try:
		ws = wb.active
		rows: list[dict[str, Any]] = []
		errors: list[dict[str, Any]] = []
		for r in range(header_row + 1, (ws.max_row or 0) + 1):
			match_raw = ws.cell(row=r, column=match_col).value
			match_key = "" if match_raw is None else str(match_raw).strip()
			if not match_key:
				continue  # 완전 빈 행 skip
			row: dict[str, Any] = {"match_key": match_key}
			for field, letter, col in amount_cols:
				raw = ws.cell(row=r, column=col).value
				try:
					amount = _clean_amount(raw)
				except ValueError as exc:
					errors.append({
						"row": r,
						"column": letter,
						"value": raw,
						"reason": str(exc),
					})
					continue
				if amount is not None:
					row[field] = amount
			rows.append(row)
		return {"rows": rows, "errors": errors}
	finally:
		wb.close()
