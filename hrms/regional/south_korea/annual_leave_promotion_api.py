"""Frappe 연동 API — 연차 유급휴가 사용 촉진 (근로기준법 §61).

코어(annual_leave_promotion)에 위임하는 whitelisted 래퍼.
웹 RPC 입력(ISO 날짜 문자열, JSON 문자열 dict, 문자열 불리언)을 코어 타입으로
변환하고 JSON-safe 결과(date 객체 없음)를 반환한다.

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


_core = _load_core("annual_leave_promotion")


def _parse_date(value: Any, name: str) -> datetime.date:
	"""ISO 문자열 또는 date 객체 → date. 그 외는 즉시 거부."""
	if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
		return value
	if isinstance(value, datetime.datetime):
		return value.date()
	if isinstance(value, str):
		try:
			return datetime.date.fromisoformat(value)
		except ValueError as exc:
			raise ValueError(f"{name}은 YYYY-MM-DD 형식이어야 합니다: {value!r}") from exc
	raise ValueError(f"{name}은 날짜여야 합니다: {value!r}")


def _parse_bool(value: Any) -> bool:
	"""Frappe RPC 불리언 — 'false'/'0'/0/'' 은 False."""
	return bool(value) and value not in ("false", "False", "0", 0)


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


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


@_whitelist
def promotion_schedule_api(
	hire_date: Any, as_of: Any, is_first_year: Any = False
) -> dict[str, Any]:
	"""§61 사용촉진 기한표 + 현재 단계 판정 (코어 위임).

	Returns:
		코어 결과 그대로(날짜는 ISO 문자열) — expiry_date /
		first_notice_window_start·deadline / second_notice_deadline / stage /
		legal_basis (+ 1년 미만 특칙이면 proviso_* 필드).
	"""
	result = _core.promotion_schedule(
		hire_date=_parse_date(hire_date, "hire_date"),
		as_of=_parse_date(as_of, "as_of"),
		is_first_year=_parse_bool(is_first_year),
	)
	return _json_safe(result)


@_whitelist
def promotion_notice_api(worker: Any, unused_days: Any, deadline: Any, stage: Any) -> str:
	"""§61 서면 촉구(1차)/통보(2차) 초안 마크다운 (코어 위임).

	worker는 dict, JSON 문자열 dict({"name": ...}), 또는 이름 문자열을 허용한다.
	"""
	if isinstance(worker, str):
		try:
			parsed = json.loads(worker)
			if isinstance(parsed, dict):
				worker = parsed
		except json.JSONDecodeError:
			pass  # 이름 문자열 그대로 사용
	return _core.promotion_notice_draft(
		worker=worker,
		unused_days=unused_days,
		deadline=_parse_date(deadline, "deadline"),
		stage=int(stage),
	)


@_whitelist
def settle_unused_leave_api(
	monthly_base_salary: Any, unused_days: Any, promotion_completed: Any
) -> dict[str, Any]:
	"""미사용 연차수당 정산 — 촉진 완료 시 보상 의무 면제 (코어 위임)."""
	result = _core.settle_unused_leave(
		monthly_base_salary=monthly_base_salary,
		unused_days=unused_days,
		promotion_completed=_parse_bool(promotion_completed),
	)
	return _json_safe(result)
