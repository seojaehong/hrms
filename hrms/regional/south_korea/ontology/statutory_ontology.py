# -*- coding: utf-8 -*-
"""법정 확정값 온톨로지 리더 — published 노드에서만 법정 수치를 읽는다. framework-free.

최저임금처럼 "출처 있는 확정값"은 코드 상수나 임의 인자가 아니라 사람이 승인한
published 온톨로지 노드에서 와야 한다(2026 최저 10,320을 10,030으로 스모크한 사고 대응).

frappe 의존 없음. loader.py의 load_nodes를 재사용한다.
"""
from __future__ import annotations

import importlib.util as _ilu
import pathlib as _pl
from typing import Any

_DIR = _pl.Path(__file__).resolve().parent


def _loader():
	spec = _ilu.spec_from_file_location("korea_ontology_loader", _DIR / "loader.py")
	m = _ilu.module_from_spec(spec)
	spec.loader.exec_module(m)
	return m


def get_statutory_value(wiki_root: Any, node_id: str, year: int) -> float | None:
	"""임의 법정수치 published 노드의 value를 float로 반환. 없으면 None.

	kind=법정수치·node_id 정확 일치·effective_year 일치·published만 —
	get_minimum_hourly_wage와 동일한 신뢰 규칙의 일반형 (요율 등 소수값용).
	"""
	loader = _loader()
	nodes, _errors = loader.load_nodes(wiki_root, review_state="published")
	for node in nodes:
		fm = getattr(node, "frontmatter", None) or {}
		if str(fm.get("kind") or getattr(node, "kind", "")).strip() != "법정수치":
			continue
		nid = str(fm.get("node_id") or getattr(node, "node_id", "")).strip()
		if nid != str(node_id).strip():
			continue
		ey = fm.get("effective_year")
		if ey is None or int(ey) != int(year):
			continue
		val = fm.get("value")
		if val in (None, ""):
			return None
		return float(val)
	return None


def get_minimum_hourly_wage(wiki_root: Any, year: int) -> int | None:
	"""해당 연도의 최저시급(원)을 published 노드에서 반환. 없으면 None.

	노드 frontmatter: kind=법정수치, effective_year=<연도>, value=<시급>, review_state=published.
	draft·미존재 연도는 None(확정값 없음 → 호출자가 판단 보류).
	같은 kind·연도에 요율 등 다른 법정수치 노드가 공존하므로 node_id로 특정한다.
	"""
	loader = _loader()
	nodes, _errors = loader.load_nodes(wiki_root, review_state="published")
	expected_node_id = f"최저임금_{int(year)}"
	for node in nodes:
		fm = getattr(node, "frontmatter", None) or {}
		if str(fm.get("kind") or getattr(node, "kind", "")).strip() != "법정수치":
			continue
		node_id = str(fm.get("node_id") or getattr(node, "node_id", "")).strip()
		if node_id != expected_node_id:
			continue
		ey = fm.get("effective_year")
		if ey is None or int(ey) != int(year):
			continue
		val = fm.get("value")
		if val in (None, ""):
			return None
		return int(val)
	return None
