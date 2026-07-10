# -*- coding: utf-8 -*-
"""PII 필터 — 에이전트→LLM으로 나가는 도구 결과의 구조적 방어선. framework-free.

보안플랜 P1-④: 주민번호·계좌·키류가 외부 LLM으로 나가는 것을 **지시문이 아니라
코드로** 차단한다. 하네스가 도구 결과를 대화에 넣기 직전 redact_sensitive를 통과시킨다.

설계:
- 키 거부목록: 이름에 민감 패턴이 포함된 키의 값을 "[PII 제외]"로 치환.
  (rrn_masked처럼 이미 마스킹된 표기 키는 예외 허용)
- 값 패턴: 자유 텍스트 속 주민번호 표기(6자리-7자리)를 마스킹(YYMMDD-G******).
  하이픈 없는 13자리 연속 숫자는 금액·계좌와 구분 불가 → 오탐 방지 위해 보존.
- 깊은 복사 — 원본 불변. dict/list/str 재귀, 그 외 타입은 그대로.
"""
from __future__ import annotations

import re
from typing import Any

REDACTED = "[PII 제외]"

# 키 이름 거부 패턴 (소문자 비교, 부분일치)
_DENY_KEY_PATTERNS = (
	"resident_registration",  # 전체 주민번호 필드
	"resident_no",
	"rrn",                    # 단, 마스킹 표기 키는 아래 allowlist로 구제
	"주민",
	"password",
	"secret",
	"api_key",
	"apikey",
	"token",
	"bank_account",
	"account_no",
	"계좌",
)
# 거부 패턴에 걸려도 허용하는 키 (이미 안전한 파생 표기)
_ALLOW_KEYS = ("rrn_masked",)

# 자유 텍스트 속 주민번호 표기: 6자리-7자리 (뒤 6자리 마스킹)
_RRN_TEXT_PATTERN = re.compile(r"\b(\d{6})-(\d)(\d{6})\b")


def _is_denied_key(key: Any) -> bool:
	k = str(key).lower()
	if k in _ALLOW_KEYS:
		return False
	return any(p in k for p in _DENY_KEY_PATTERNS)


def _mask_text(text: str) -> str:
	return _RRN_TEXT_PATTERN.sub(lambda m: f"{m.group(1)}-{m.group(2)}******", text)


def redact_sensitive(data: Any) -> Any:
	"""민감 정보를 제거/마스킹한 깊은 사본을 반환한다 (원본 불변)."""
	if isinstance(data, dict):
		out: dict = {}
		for key, value in data.items():
			if _is_denied_key(key):
				out[key] = REDACTED
			else:
				out[key] = redact_sensitive(value)
		return out
	if isinstance(data, list):
		return [redact_sensitive(item) for item in data]
	if isinstance(data, str):
		return _mask_text(data)
	return data
