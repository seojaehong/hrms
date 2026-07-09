# -*- coding: utf-8 -*-
"""주민등록번호(RRN) 검증·마스킹·파생 — framework-free 코어.

4대보험 신고 등은 전체 주민번호가 필요하다(암호화 저장). 이 모듈은 그 값의
**구조 검증·마스킹·생년월일/성별 파생**을 담당한다. frappe 의존 없음 →
`python3 hrms/tests/test_korea_rrn.py` 직접 실행 검증.

형식: YYMMDD-GSSSSSC (13자리). G=성별/세기, C=검증숫자.
- 성별숫자 G: 1·3·5·7·9=남, 2·4·6·8·0=여.
- 세기: 1,2→1900s / 3,4→2000s / 9,0→1800s / 5,6→1900s(외국인) / 7,8→2000s(외국인).
- 검증숫자(C): 가중치 [2,3,4,5,6,7,8,9,2,3,4,5] 합의 mod 11 기반.
  ⚠️ 2020-10 개편 이후 발급분은 뒷자리가 임의화되어 이 체크섬을 만족하지 않을 수 있으므로,
  체크섬은 **정보성(경고)** 으로만 쓰고 구조검증(길이·날짜·성별)만 유효성 판정에 사용한다.
"""
from __future__ import annotations

import datetime as _dt
import re as _re

_DIGITS_ONLY = _re.compile(r"\D")
_CHECKSUM_WEIGHTS = (2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5)


def normalize(rrn: str) -> str:
	"""하이픈·공백 제거 후 13자리 숫자 문자열 반환. 아니면 ValueError."""
	if rrn is None:
		raise ValueError("rrn is required")
	digits = _DIGITS_ONLY.sub("", str(rrn))
	if len(digits) != 13:
		raise ValueError("주민등록번호는 13자리여야 합니다")
	return digits


def _century_and_gender(gender_digit: int) -> tuple[int, str]:
	mapping = {
		1: (1900, "M"), 2: (1900, "F"),
		3: (2000, "M"), 4: (2000, "F"),
		5: (1900, "M"), 6: (1900, "F"),  # 외국인
		7: (2000, "M"), 8: (2000, "F"),  # 외국인
		9: (1800, "M"), 0: (1800, "F"),
	}
	if gender_digit not in mapping:
		raise ValueError("성별숫자(7번째 자리)가 올바르지 않습니다")
	return mapping[gender_digit]


def birth_date(rrn: str) -> _dt.date:
	"""생년월일을 date로 반환 (세기 보정 포함). 날짜가 유효하지 않으면 ValueError."""
	d = normalize(rrn)
	century, _ = _century_and_gender(int(d[6]))
	year = century + int(d[0:2])
	month = int(d[2:4])
	day = int(d[4:6])
	return _dt.date(year, month, day)  # 잘못된 날짜면 ValueError


def gender(rrn: str) -> str:
	"""'M' 또는 'F'."""
	d = normalize(rrn)
	return _century_and_gender(int(d[6]))[1]


def checksum_ok(rrn: str) -> bool:
	"""전통 체크섬 충족 여부(정보성). 2020-10 이후 발급분은 False일 수 있음."""
	d = normalize(rrn)
	total = sum(int(d[i]) * _CHECKSUM_WEIGHTS[i] for i in range(12))
	check = (11 - (total % 11)) % 10
	return check == int(d[12])


def is_valid_rrn(rrn: str) -> bool:
	"""구조 유효성(길이·날짜·성별숫자). 체크섬은 판정에 쓰지 않음(개편 대응)."""
	try:
		birth_date(rrn)  # 길이·성별숫자·날짜 전부 검증
		return True
	except (ValueError, KeyError):
		return False


def mask_rrn(rrn: str) -> str:
	"""마스킹 표기 'YYMMDD-G******' (뒤 6자리 은닉). 개인정보보호법 관행."""
	d = normalize(rrn)
	return f"{d[0:6]}-{d[6]}{'*' * 6}"


def format_rrn(rrn: str) -> str:
	"""하이픈 표기 'YYMMDD-SSSSSSS'."""
	d = normalize(rrn)
	return f"{d[0:6]}-{d[6:13]}"
