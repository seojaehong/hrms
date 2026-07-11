"""Framework-free loader/validator for the Korea labor inspection checklist.

Data source: data/labor_inspection_checklist.json — 고용노동부 자율점검표·근로감독관
집무규정·근로기준법 등 공식 법령 조문을 리서치해 구조화한 정적 체크리스트. 각
item의 legal_basis/risk.note는 공식 출처(법제처 원문) 조회 결과를 인용하며,
원문 확인이 실패한 항목은 automated_check 또는 risk.note에 "미확인" 접두어로
표시한다(추측 금지).

이 모듈은 조회·검증 전용이며 DB mutation이나 AI 판단을 포함하지 않는다.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

_DEFAULT_DATA_PATH = pathlib.Path(__file__).resolve().parent / "data" / "labor_inspection_checklist.json"

REQUIRED_FIELDS = ("id", "category", "item", "legal_basis", "evidence_needed", "risk", "automated_check")


def load_labor_inspection_checklist(*, path: pathlib.Path | str | None = None) -> list[dict[str, Any]]:
	"""Load and validate the labor inspection checklist from JSON.

	Args:
		path: optional override path (defaults to the bundled data file).

	Raises:
		FileNotFoundError: if the JSON file does not exist.
		ValueError: if the checklist fails structural validation.
	"""

	data_path = pathlib.Path(path) if path is not None else _DEFAULT_DATA_PATH
	if not data_path.exists():
		raise FileNotFoundError(f"labor inspection checklist not found: {data_path}")

	with open(data_path, encoding="utf-8") as f:
		items = json.load(f)

	validate_labor_inspection_checklist(items)
	return items


def validate_labor_inspection_checklist(items: list[dict[str, Any]]) -> None:
	"""Validate checklist structure: required fields, non-empty evidence, unique ids."""

	if not isinstance(items, list):
		raise ValueError("checklist must be a list")

	seen_ids: set[str] = set()
	for item in items:
		if not isinstance(item, dict):
			raise ValueError("checklist items must be dicts")

		for field in REQUIRED_FIELDS:
			if field not in item:
				raise ValueError(f"checklist item missing required field '{field}': {item}")

		item_id = item["id"]
		if item_id in seen_ids:
			raise ValueError(f"duplicate checklist id: {item_id}")
		seen_ids.add(item_id)

		if not isinstance(item["evidence_needed"], list) or not item["evidence_needed"]:
			raise ValueError(f"checklist item {item_id} must have non-empty evidence_needed list")

		if not isinstance(item["risk"], dict) or "type" not in item["risk"]:
			raise ValueError(f"checklist item {item_id} must have risk.type")


def filter_by_category(items: list[dict[str, Any]], category: str) -> list[dict[str, Any]]:
	"""Return checklist items matching the given category."""

	return [item for item in items if item.get("category") == category]


def filter_automatable(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Return checklist items whose automated_check maps to a confirmed engine module.

	Items whose automated_check starts with "미확인" have no existing automation
	hook yet and are excluded (they require a human/manual check for now).
	"""

	return [item for item in items if not str(item.get("automated_check", "")).startswith("미확인")]


__all__ = [
	"load_labor_inspection_checklist",
	"validate_labor_inspection_checklist",
	"filter_by_category",
	"filter_automatable",
]
