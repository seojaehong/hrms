# -*- coding: utf-8 -*-
"""근로기준법 §61 연차 유급휴가 사용 촉진 — framework-free 코어.

1차 근거(그대로 구현): published 온톨로지 노드
``wiki/ontology/급여규칙/연차_사용촉진.md`` (노무사 승인본, sources=근로기준법 제61조).

기존 모듈 재사용(불변):
    - ``annual_leave.py``의 ``completed_years``/``add_years``/``add_months`` — 소멸일(만료일)
      산정에 동일한 연차 기준일 산식을 그대로 쓴다.
    - ``hourly_wage.unused_leave_allowance`` — 미사용 연차수당 금액 산정.

규칙 요지 (§61, 온톨로지 노드 그대로):
    일반(§60①·②·④, 1년 미만자의 §60② 제외):
        1차: 소멸 6개월 전 기준 10일 이내 서면 촉구.
        2차: 1차 촉구 후 10일 내 미통보 시, 소멸 2개월 전까지 서면 통보.
    1년 미만자 특칙(§60②):
        1차: 최초 1년 만료 3개월 전 기준 10일 이내 서면 촉구.
             (단서) 촉구 후 발생한 휴가는 만료 1개월 전 기준 5일 이내 촉구.
        2차: 만료 1개월 전까지 서면 통보. (단서분은 만료 10일 전까지 서면 통보)

프레임워크 비의존 — ``python3 hrms/tests/test_korea_annual_leave_promotion.py``로
frappe 없이 직접 실행 검증 가능.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

# §61 근거 인용 베이스 — published 온톨로지 노드가 없을 때의 폴백 (annual_leave/hourly_wage 패턴).
LEGAL_BASIS_BASE_FALLBACK = "근로기준법 제61조"

_ONTOLOGY_NODE_ID = "연차_사용촉진"

# 단계 판정 라벨 (schedule/proviso 공용)
STAGE_BEFORE_WINDOW = "촉구_전"
STAGE_FIRST_NOTICE_WINDOW = "1차_촉구_기간"
STAGE_SECOND_NOTICE_WINDOW = "2차_통보_기간"
STAGE_OVERDUE = "통보_기한_도과"
STAGE_LAPSED = "소멸"


def _load_sibling_module(filename: str, module_name: str):
	"""같은 디렉토리 모듈을 동적으로 로드 (annual_leave_attendance_ratio.py 컨벤션)."""
	path = Path(__file__).with_name(filename)
	spec = importlib.util.spec_from_file_location(module_name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


def _annual_leave():
	return _load_sibling_module("annual_leave.py", "korea_annual_leave_for_promotion")


def _hourly_wage():
	return _load_sibling_module("hourly_wage.py", "korea_hourly_wage_for_promotion")


def legal_basis_base() -> str:
	"""§61 촉진 규칙 인용 베이스 — published 온톨로지 노드 우선, 폴백 상수.

	노드 부재/미발행/로더 실패 시 조용히 폴백한다(annual_leave/hourly_wage와 동일 컨벤션).
	"""
	try:
		loader = _load_sibling_module(
			str(Path("ontology") / "loader.py"), "korea_ontology_loader_for_promotion"
		)
		root = Path(__file__).resolve().parents[3] / "wiki" / "ontology"
		nodes, _errors = loader.load_nodes(root, review_state="published")
		for node in nodes:
			if getattr(node, "node_id", None) == _ONTOLOGY_NODE_ID:
				sources = getattr(node, "sources", None) or []
				if sources:
					return sources[0]
	except Exception:
		pass
	return LEGAL_BASIS_BASE_FALLBACK


def _validate_dates(hire_date: dt.date, as_of: dt.date) -> None:
	if not isinstance(hire_date, dt.date) or isinstance(hire_date, dt.datetime):
		raise TypeError("hire_date must be a datetime.date value")
	if not isinstance(as_of, dt.date) or isinstance(as_of, dt.datetime):
		raise TypeError("as_of must be a datetime.date value")
	if as_of < hire_date:
		raise ValueError("as_of cannot be before hire_date")


def _stage_for(
	as_of: dt.date,
	window_start: dt.date,
	window_deadline: dt.date,
	second_deadline: dt.date,
	expiry_date: dt.date,
) -> str:
	if as_of >= expiry_date:
		return STAGE_LAPSED
	if as_of < window_start:
		return STAGE_BEFORE_WINDOW
	if as_of <= window_deadline:
		return STAGE_FIRST_NOTICE_WINDOW
	if as_of <= second_deadline:
		return STAGE_SECOND_NOTICE_WINDOW
	return STAGE_OVERDUE


def promotion_schedule(hire_date: dt.date, as_of: dt.date, is_first_year: bool = False) -> dict[str, Any]:
	"""근기법 §61 사용촉진 기한표 + 현재 단계 판정.

	Args:
		hire_date: 입사일.
		as_of: 판정 기준일(오늘 등). 각 단계 창의 경계는 전부 포함(inclusive)한다.
		is_first_year: True면 §60② 1년 미만자 특칙(3개월전/1개월전 단서 포함) 스케줄을,
			False면 일반(§60①·④) 스케줄을 계산한다.

	Returns:
		일반: expiry_date, first_notice_window_start/deadline, second_notice_deadline,
			stage, legal_basis.
		1년 미만: 위 필드 + proviso_notice_window_start/deadline, proviso_second_deadline,
			proviso_stage.
	"""
	_validate_dates(hire_date, as_of)

	al = _annual_leave()
	if is_first_year:
		expiry_date = al.add_years(hire_date, 1)
	else:
		service_years = al.completed_years(hire_date, as_of)
		# 경계 보정: as_of가 정확히 해당 서비스이언(anniversary) 당일이면, 그 날은
		# "새 기간의 첫날"이 아니라 "직전 기간이 막 소멸하는 날"로 취급한다 —
		# 그래야 소멸 당일에 stage="소멸"이 나오고, 그 다음 날부터 새 기간(촉구_전)으로
		# 넘어간다(annual_leave.py의 부여 시점 산식과는 별개의 촉진 스케줄 전용 규칙).
		if service_years > 0 and al.add_years(hire_date, service_years) == as_of:
			service_years -= 1
		expiry_date = al.add_years(hire_date, service_years + 1)

	result: dict[str, Any] = {
		"hire_date": hire_date,
		"as_of": as_of,
		"is_first_year": is_first_year,
		"expiry_date": expiry_date,
		"legal_basis": [legal_basis_base()],
	}

	if is_first_year:
		# 1차 촉구: 만료 3개월 전 기준 10일 이내
		first_window_start = al.add_months(expiry_date, -3)
		first_window_deadline = first_window_start + dt.timedelta(days=9)
		# 2차 통보: 만료 1개월 전까지
		second_deadline = al.add_months(expiry_date, -1)
		# 단서(촉구 후 발생분) 1차: 만료 1개월 전 기준 5일 이내
		proviso_window_start = al.add_months(expiry_date, -1)
		proviso_window_deadline = proviso_window_start + dt.timedelta(days=4)
		# 단서 2차: 만료 10일 전까지
		proviso_second_deadline = expiry_date - dt.timedelta(days=10)

		result.update(
			{
				"first_notice_window_start": first_window_start,
				"first_notice_deadline": first_window_deadline,
				"second_notice_deadline": second_deadline,
				"proviso_notice_window_start": proviso_window_start,
				"proviso_notice_deadline": proviso_window_deadline,
				"proviso_second_deadline": proviso_second_deadline,
				"stage": _stage_for(
					as_of, first_window_start, first_window_deadline, second_deadline, expiry_date
				),
				"proviso_stage": _stage_for(
					as_of,
					proviso_window_start,
					proviso_window_deadline,
					proviso_second_deadline,
					expiry_date,
				),
			}
		)
	else:
		# 1차 촉구: 소멸 6개월 전 기준 10일 이내
		first_window_start = al.add_months(expiry_date, -6)
		first_window_deadline = first_window_start + dt.timedelta(days=9)
		# 2차 통보: 소멸 2개월 전까지
		second_deadline = al.add_months(expiry_date, -2)

		result.update(
			{
				"first_notice_window_start": first_window_start,
				"first_notice_deadline": first_window_deadline,
				"second_notice_deadline": second_deadline,
				"stage": _stage_for(
					as_of, first_window_start, first_window_deadline, second_deadline, expiry_date
				),
			}
		)

	return result


def promotion_notice_draft(worker: Any, unused_days: Any, deadline: dt.date, stage: int) -> str:
	"""§61 서면 촉구(1차)/통보(2차) 초안 마크다운.

	Args:
		worker: 근로자 정보. dict({"name": ...})이면 name 필드를 쓰고, 그 외는 str()로 표기.
		unused_days: 미사용 연차 일수.
		deadline: 해당 단계의 기한 날짜(1차=촉구 응답 기한, 2차=사용자 통보 기한).
		stage: 1(서면 촉구) 또는 2(사용자 서면 통보). 그 외 값은 ValueError.

	Returns:
		마크다운 문자열. §61 요건 문구 포함:
			1차 — "근로자가 사용시기 지정·통보하라"
			2차 — "사용시기 지정 통보"
	"""
	if stage not in (1, 2):
		raise ValueError("stage must be 1 (서면 촉구) or 2 (서면 통보)")

	worker_name = worker.get("name") if isinstance(worker, dict) else str(worker)
	deadline_str = deadline.isoformat() if isinstance(deadline, dt.date) else str(deadline)
	basis = legal_basis_base()

	if stage == 1:
		return (
			f"# 연차 유급휴가 사용 촉구서\n\n"
			f"수신: {worker_name}\n\n"
			f"귀하의 미사용 연차 유급휴가는 **{unused_days}일**입니다.\n\n"
			f"{basis}에 따라, 근로자가 사용시기 지정·통보하라는 취지로 아래와 같이 촉구합니다.\n\n"
			f"- 미사용 일수: {unused_days}일\n"
			f"- 통보 기한: **{deadline_str}**까지\n\n"
			f"위 기한까지 사용 시기를 정하여 서면으로 통보하여 주시기 바랍니다.\n"
			f"기한 내 통보가 없을 경우, 회사가 사용 시기를 정하여 별도로 통보할 수 있습니다.\n"
		)

	return (
		f"# 연차 유급휴가 사용 시기 지정 통보서\n\n"
		f"수신: {worker_name}\n\n"
		f"귀하가 사용 시기를 통보하지 않아, {basis}에 따라 회사가 아래와 같이 "
		f"미사용 연차 유급휴가의 사용시기 지정 통보를 합니다.\n\n"
		f"- 미사용 일수: {unused_days}일\n"
		f"- 지정 사용 기한: **{deadline_str}**까지\n\n"
		f"위 기한 내에 미사용 연차 유급휴가를 사용하시기 바랍니다.\n"
	)


def settle_unused_leave(
	monthly_base_salary: Any, unused_days: Any, promotion_completed: bool
) -> dict[str, Any]:
	"""미사용 연차수당 정산.

	사용촉진 조치를 모두 이행했음에도 근로자가 사용하지 않아 소멸한 경우
	(§60⑦ 본문 소멸 + §61 촉진 완료), 사용자는 보상 의무가 없다(수당 0).
	촉진이 완료되지 않았다면 기존 ``hourly_wage.unused_leave_allowance``로
	미사용 연차수당을 계산해 원 단위(반올림)로 반환한다.

	Args:
		monthly_base_salary: 월 기본급.
		unused_days: 미사용 연차 일수.
		promotion_completed: §61 촉진 조치(1·2차)를 모두 적법하게 이행했는지 여부.

	Returns:
		{"allowance_won": int, "compensation_exempt": bool, "reason": str}
	"""
	basis = legal_basis_base()
	if promotion_completed:
		return {
			"allowance_won": 0,
			"compensation_exempt": True,
			"reason": (
				f"{basis} 사용촉진 조치를 모두 이행하여 §60⑦ 본문에 따라 미사용 휴가가 "
				"소멸함 — 사용자의 보상 의무가 면제됨(§60⑦ 단서의 귀책사유에 해당하지 않음)."
			),
		}

	hw = _hourly_wage()
	raw = hw.unused_leave_allowance(monthly_base_salary, unused_days)
	allowance_won = int(Decimal(raw).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
	return {
		"allowance_won": allowance_won,
		"compensation_exempt": False,
		"reason": f"{basis} 사용촉진 조치 미이행(또는 불완전) — 미사용 연차수당 지급 의무 발생.",
	}


__all__ = [
	"legal_basis_base",
	"promotion_schedule",
	"promotion_notice_draft",
	"settle_unused_leave",
	"LEGAL_BASIS_BASE_FALLBACK",
]
