# -*- coding: utf-8 -*-
"""4대보험 조회 API (CODEF 경유) — 신고(insurance_filing)와 분리된 조회 전용 레이어.

배경: 공단 포털(4대사회보험 정보연계센터·EDI·토탈서비스)에는 공식 API가 없다.
사설 스크래핑 API(CODEF)로 사업장 가입자명부·고지내역을 조회한다.
참조: docs/korea_hrms/research-4insure-private-api.md (§6 추천안, §7 Phase 1).

안전 불변식:
- 조회 전용 — 어떤 신고·제출도 하지 않는다 (제출은 P3, 별도 승인 구조).
- 자격증명 없으면 네트워크 0회 + status="not_configured" (fail-closed).
- 데모 키(demo=True)가 기본 — 정식 전환은 site_config에서 명시적으로.

자격증명 우선순위: site_config(codef_client_id/secret/codef_demo) → 환경변수.
테스트 환경(frappe 없음)에서도 importlib 직접 로드 가능 (조건부 import 컨벤션).
"""
from __future__ import annotations

import importlib.util as _ilu
import os as _os
import pathlib as _pl
from typing import Any

try:
	import frappe as _frappe  # noqa: PLC0415

	_FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
	_frappe = None  # type: ignore[assignment]
	_FRAPPE_AVAILABLE = False


def _whitelist(fn):
	if _FRAPPE_AVAILABLE and _frappe is not None:
		return _frappe.whitelist()(fn)
	return fn


_MODULE_DIR = _pl.Path(__file__).resolve().parent


def _load_core(name: str):
	path = _MODULE_DIR / f"{name}.py"
	spec = _ilu.spec_from_file_location(f"_korea_{name}_core", path)
	module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
	spec.loader.exec_module(module)  # type: ignore[union-attr]
	return module


_codef = _load_core("codef_client")


def _conf(key: str) -> Any:
	"""site_config 우선, 환경변수 폴백."""
	if _FRAPPE_AVAILABLE and _frappe is not None:
		try:
			val = _frappe.conf.get(key)
			if val not in (None, ""):
				return val
		except Exception:
			pass
	return _os.environ.get(key.upper())


def _build_client(transport=None) -> Any:
	demo_flag = _conf("codef_demo")
	demo = True if demo_flag in (None, "") else str(demo_flag).strip().lower() not in ("0", "false", "no")
	return _codef.CodefClient(
		_conf("codef_client_id"),
		_conf("codef_client_secret"),
		demo=demo,
		transport=transport,
	)


@_whitelist
def codef_connection_status() -> dict[str, Any]:
	"""자격증명·모드 상태 (네트워크 0회 — 키 존재 여부만)."""
	client = _build_client()
	return {
		"configured": client.is_configured(),
		"mode": "demo" if client.demo else "production",
		"base": client.base,
	}


@_whitelist
def fetch_insured_roster(
	workplace_mgmt_number: str,
	business_registration_number: str | None = None,
	product_path: str | None = None,
	extra: Any = None,
) -> dict[str, Any]:
	"""사업장 가입자 명부 조회 (CODEF — 4대사회보험 정보연계센터 경유).

	Args:
		workplace_mgmt_number: 사업장 관리번호 (다관리번호 법인은 관리번호별 각각 조회).
		business_registration_number: 사업자등록번호 (상품에 따라 요구).
		product_path: 상품 경로 오버라이드 (계약 상품에 따라 다를 수 있음).
		extra: 상품별 추가 파라미터 dict (인증 파라미터 등 — 데모에서는 불필요).

	Returns:
		{"status": "ok", "data": ...}
		{"status": "not_configured", "reason": ...}   # 키 없음 — 네트워크 0회
		{"status": "error", "code": ..., "message": ...}  # CODEF 업무/전송 오류
	"""
	client = _build_client()
	if not client.is_configured():
		return {
			"status": "not_configured",
			"reason": "CODEF 키 미설정 — USER_INPUT_HANDOFF.md §CODEF 데모 신청 참조",
		}
	payload: dict[str, Any] = {
		"organization": "0005",  # CODEF 기관코드(연계센터 계열) — 상품 확정 시 조정
		"workplaceMgmtNo": str(workplace_mgmt_number).strip(),
	}
	if business_registration_number:
		payload["bizNo"] = str(business_registration_number).replace("-", "").strip()
	if isinstance(extra, dict):
		payload.update(extra)
	try:
		data = client.request_product(product_path or _codef.PRODUCT_INSURED_ROSTER, payload)
		return {"status": "ok", "data": data, "mode": "demo" if client.demo else "production"}
	except _codef.CodefError as exc:
		return {"status": "error", "code": getattr(exc, "code", None), "message": str(exc)}
