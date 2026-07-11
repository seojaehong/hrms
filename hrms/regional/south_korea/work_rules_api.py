"""Frappe 연동 API — 취업규칙 점검 (근로기준법 제93조·제94조).

코어(work_rules)에 위임하는 whitelisted 래퍼. 웹 RPC 입력(JSON 문자열·
문자열 불리언)을 코어 타입으로 변환하고 JSON-safe 결과를 반환한다.

테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import한다 (insurance_filing_api.py 컨벤션).
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import pathlib as _pl
from typing import Any

# ---------------------------------------------------------------------------
# Frappe 조건부 import — framework-free 테스트 환경에서 안전하게 로드
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


# ---------------------------------------------------------------------------
# 코어 모듈 동적 로드 (importlib으로 frappe 패키지 경로 우회)
# ---------------------------------------------------------------------------
_MODULE_DIR = _pl.Path(__file__).resolve().parent


def _load_core(name: str):
	path = _MODULE_DIR / (name + ".py")
	spec = _ilu.spec_from_file_location(f"_korea_{name}_core", path)
	module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
	spec.loader.exec_module(module)  # type: ignore[union-attr]
	return module


_core = _load_core("work_rules")

# 체크박스 UI용 항목별 고유 마커 — 코어 check_required_items의 substring 매칭에서
# 다른 호(號)와 교차 매칭되지 않는 키워드만 골랐다(테스트가 1:1 커버리지를 보장).
# 예: 라벨 원문을 보내면 "퇴직급여"(5호)가 "퇴직"(4호)까지 커버해 게이지가 어긋난다.
_COVERAGE_MARKERS: dict[str, str] = {
	"1": "교대",
	"2": "승급",
	"3": "가족수당",
	"4": "퇴직",
	"5": "상여",
	"6": "식비",
	"7": "교육시설",
	"8": "육아휴직",
	"9": "보건",
	"9의2": "사업장 환경",
	"10": "재해부조",
	"11": "괴롭힘",
	"12": "표창",
	"13": "그 밖에",
}


def _parse_outline(value: Any) -> dict | list:
	"""Frappe RPC의 dict/list 인자는 JSON 문자열로 올 수 있음 — 문자열이면 파싱."""
	if isinstance(value, str):
		try:
			parsed = json.loads(value)
		except json.JSONDecodeError as exc:
			raise ValueError(f"rules_outline은 JSON 리스트/딕셔너리 문자열이어야 합니다: {value!r}") from exc
		if not isinstance(parsed, (dict, list)):
			raise ValueError(f"rules_outline은 리스트 또는 딕셔너리여야 합니다: {value!r}")
		return parsed
	if isinstance(value, (dict, list)):
		return value
	raise ValueError(f"rules_outline은 리스트 또는 딕셔너리여야 합니다: {value!r}")


def _parse_bool(value: Any, name: str) -> bool:
	"""Frappe RPC의 불리언 인자는 'true'/'0'/1 등으로 올 수 있음."""
	if isinstance(value, bool):
		return value
	if isinstance(value, (int, float)):
		return bool(value)
	if isinstance(value, str):
		lowered = value.strip().lower()
		if lowered in ("true", "1", "yes"):
			return True
		if lowered in ("false", "0", "no", ""):
			return False
	raise ValueError(f"{name}은 불리언이어야 합니다: {value!r}")


@_whitelist
def check_required_items_api(rules_outline: Any) -> dict[str, Any]:
	"""근기법 §93 14개 호 커버리지 candidate 판정 (코어 위임).

	rules_outline은 조문 텍스트 리스트/딕셔너리 또는 그 JSON 문자열을 허용한다.
	"""
	return _core.check_required_items(_parse_outline(rules_outline))


@_whitelist
def amendment_procedure_api(
	is_disadvantageous: Any, headcount: Any, has_majority_union: Any = None
) -> dict[str, Any]:
	"""취업규칙 작성·변경 절차(§94) + 신고의무(§93) 판정 (코어 위임)."""
	is_disadvantageous = _parse_bool(is_disadvantageous, "is_disadvantageous")
	union: bool | None = None
	if has_majority_union is not None and has_majority_union != "":
		union = _parse_bool(has_majority_union, "has_majority_union")
	result = _core.amendment_procedure(is_disadvantageous, has_majority_union=union)
	result["filing_obligation"] = _core.filing_obligation(int(headcount))
	return result


@_whitelist
def list_required_items_api() -> list[dict[str, Any]]:
	"""§93 14개 필수기재 항목 목록 — 체크리스트 UI용 (ho/label/marker)."""
	return [
		{"ho": item["ho"], "label": item["label"], "marker": _COVERAGE_MARKERS[item["ho"]]}
		for item in _core.WORK_RULES_REQUIRED_ITEMS
	]
