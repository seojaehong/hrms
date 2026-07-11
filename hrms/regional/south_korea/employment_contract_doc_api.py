"""Frappe 연동 API — 근로계약서 작성 (근로기준법 제17조).

코어(employment_contract_doc)에 위임하는 whitelisted 래퍼. 웹 RPC 입력(JSON
문자열 딕셔너리)을 코어 타입으로 변환하고 JSON-safe 결과를 반환한다.

테스트 환경(frappe 없음)에서도 importlib으로 직접 로드 가능하도록
frappe는 조건부로만 import한다 (insurance_filing_api.py 컨벤션).
"""

from __future__ import annotations

import datetime
import importlib.util as _ilu
import json
import pathlib as _pl
from decimal import Decimal
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


_core = _load_core("employment_contract_doc")


def _json_safe(obj: Any) -> Any:
	"""date → ISO 문자열, Decimal → int/float 재귀 변환 (Frappe RPC 직렬화)."""
	if isinstance(obj, datetime.date):
		return obj.isoformat()
	if isinstance(obj, Decimal):
		return int(obj) if obj == obj.to_integral_value() else float(obj)
	if isinstance(obj, dict):
		return {k: _json_safe(v) for k, v in obj.items()}
	if isinstance(obj, (list, tuple)):
		return [_json_safe(v) for v in obj]
	return obj


def _parse_dict(value: Any, name: str) -> dict:
	"""Frappe RPC의 딕셔너리 인자는 JSON 문자열로 올 수 있음 — 문자열이면 파싱."""
	if isinstance(value, str):
		try:
			parsed = json.loads(value)
		except json.JSONDecodeError as exc:
			raise ValueError(f"{name}은 JSON 딕셔너리 문자열이어야 합니다: {value!r}") from exc
		if not isinstance(parsed, dict):
			raise ValueError(f"{name}은 딕셔너리여야 합니다: {value!r}")
		return parsed
	if isinstance(value, dict):
		return value
	raise ValueError(f"{name}은 딕셔너리여야 합니다: {value!r}")


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


@_whitelist
def build_employment_contract_api(data: Any) -> dict[str, Any]:
	"""근로계약서 입력 데이터를 검증하고 §17 필수기재 누락을 검출한다 (코어 위임).

	data는 dict 또는 JSON 문자열 dict를 모두 허용한다.
	"""
	data = _parse_dict(data, "data")
	result = _core.build_employment_contract(data)
	return _json_safe(result)


@_whitelist
def render_contract_markdown_api(data: Any) -> str:
	"""build_employment_contract_api() 결과 → 서면 교부용 마크다운 (코어 위임).

	data는 dict 또는 JSON 문자열 dict를 모두 허용한다.
	"""
	data = _parse_dict(data, "data")
	return _core.render_contract_markdown(data)
