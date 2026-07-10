# -*- coding: utf-8 -*-
"""행정해석 카탈로그 정화 — 노동 문서 꼬리에 접합된 산업위생 이물 문장 제거. framework-free.

스크래핑 아티팩트로 일부 노동관계 행정해석(휴업수당·수당·퇴직금 등)의 text 끝에
무관한 산업위생 문장(노출기준·mg/㎥·총분진 등)이 붙어 있다. v1 답변(_build_answer)은
primary 문서 text 전문을 그대로 내보내므로 이 이물이 답변에 새어 나갔다
(휴업수당 질의 → '석탄분진을 총분진으로 채취…' 삽입 사고).

정화 원리(보수적):
- 산업위생 토큰이 text의 **뒷부분(≥60%)** 에서 처음 등장하면 = 앞부분(본문)은 노동,
  뒤는 접합된 이물 → 그 직전 문장경계에서 자른다.
- 토큰이 **앞부분**에서 등장하면 본문 전체가 산업위생인 정상 문서 → 건드리지 않는다.
- 문장경계(마침표 또는 한국어 종결어미)를 못 찾으면 안전하게 원문 유지.

frappe 의존 없음 → `python3 hrms/tests/test_korea_catalog_sanitize.py` 직접 실행.
"""
from __future__ import annotations

import re

# 산업위생 노출기준 신호 토큰(노동 행정해석에는 나올 이유가 없다)
_HYGIENE = re.compile(r"(mg/㎥|㎎/㎥|㎍/㎥|호흡성분진|총분진|노출기준|ppm)")

# 이물로 판정할 최소 위치 비율(이 지점 이후 첫 토큰이면 꼬리 접합으로 본다)
_MIN_TAIL_POSITION = 0.6

# 제목 도메인 게이트 — "노동 문서인데 산업위생 꼬리"만 정화한다.
# 제목에 노동 키워드가 있고 산업위생 키워드가 없어야 = 본문이 노동, 꼬리가 이물.
# (제목에 산업위생 키워드가 있으면 정상 산업위생/다주제 문서 → 절대 손대지 않음)
LABOR_TITLE_KW = (
    "임금", "수당", "휴업", "주휴", "연차", "해고", "퇴직", "근로시간",
    "통상임금", "평균임금", "근로계약", "휴가", "휴일", "체불", "선임수당",
)
HYGIENE_TITLE_KW = (
    "분진", "노출기준", "측정", "작업환경", "유해", "소음", "건강진단",
    "산업위생", "화학물질", "석면", "dB", "농도", "용제", "특수건강", "위생",
)


def is_labor_domain_title(title):
    """제목이 노동 도메인(정화 대상)인지 판정 — 노동 키워드 有 & 산업위생 키워드 無."""
    t = title or ""
    return any(k in t for k in LABOR_TITLE_KW) and not any(k in t for k in HYGIENE_TITLE_KW)

# 문장 종결 표시(뒤에 공백): 마침표 또는 한국어 서술형 종결어미
_TERMINALS = ".。"
_ENDERS = ("다", "음", "임", "됨", "함")


def strip_foreign_hygiene_tail(text, title=""):
    """노동 문서 꼬리에 접합된 산업위생 이물 문장을 제거해 반환.

    - text가 비었거나 산업위생 토큰이 없으면 원문 그대로.
    - 제목이 노동 도메인이 아니면(산업위생/다주제 문서) 원문 그대로 — 오정화 방지.
    - 첫 토큰이 앞부분(<60%)이면 정상 산업위생 문서로 보고 원문 그대로.
    - 그 외에는 토큰 직전 문장경계에서 잘라 앞(본문)만 반환.
    """
    if not text:
        return text
    if not is_labor_domain_title(title):
        return text
    m = _HYGIENE.search(text)
    if not m:
        return text
    if m.start() / len(text) < _MIN_TAIL_POSITION:
        return text

    # 토큰 직전의 마지막 문장경계(종결문자 + 공백) 위치를 찾는다.
    cut = -1
    for i in range(m.start() - 1):
        ch = text[i]
        nxt = text[i + 1]
        if nxt.isspace() and (ch in _TERMINALS or ch in _ENDERS):
            cut = i
    if cut < 0:
        return text  # 안전하게 자르지 못하면 원문 유지

    head = text[: cut + 1].rstrip()
    # 목록형 문서에서 잘린 뒤 남는 고아 항목번호("… 여부. 4.") 정리
    head = re.sub(r"\s+\d+\.?$", "", head).rstrip()
    return head
