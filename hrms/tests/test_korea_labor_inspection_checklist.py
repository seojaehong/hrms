#!/usr/bin/env python3
"""Direct-run tests for Korea labor inspection checklist loader (framework-free)."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "labor_inspection_checklist.py"
)
DATA_PATH = (
	pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "data" / "labor_inspection_checklist.json"
)

REQUIRED_FIELDS = ("id", "category", "item", "legal_basis", "evidence_needed", "risk", "automated_check")
REQUIRED_RISK_FIELDS = ("type",)


def load_module():
	spec = importlib.util.spec_from_file_location("korea_labor_inspection_checklist", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaLaborInspectionChecklist(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_loads_default_checklist_with_required_fields(self):
		items = self.mod.load_labor_inspection_checklist()

		self.assertIsInstance(items, list)
		self.assertGreaterEqual(len(items), 10)
		for item in items:
			for field in REQUIRED_FIELDS:
				self.assertIn(field, item, f"missing field {field} in {item.get('id')}")
			self.assertIsInstance(item["evidence_needed"], list)
			self.assertGreater(len(item["evidence_needed"]), 0)
			self.assertIsInstance(item["risk"], dict)
			for field in REQUIRED_RISK_FIELDS:
				self.assertIn(field, item["risk"])

	def test_ids_are_unique(self):
		items = self.mod.load_labor_inspection_checklist()
		ids = [item["id"] for item in items]
		self.assertEqual(len(ids), len(set(ids)), "duplicate checklist ids found")

	def test_loads_from_explicit_path(self):
		items = self.mod.load_labor_inspection_checklist(path=DATA_PATH)
		self.assertGreaterEqual(len(items), 10)

	def test_missing_file_raises_file_not_found(self):
		with self.assertRaises(FileNotFoundError):
			self.mod.load_labor_inspection_checklist(path=DATA_PATH.parent / "does_not_exist.json")

	def test_validate_rejects_duplicate_ids(self):
		items = [
			{
				"id": "LI-001",
				"category": "c",
				"item": "i",
				"legal_basis": "b",
				"evidence_needed": ["x"],
				"risk": {"type": "과태료"},
				"automated_check": "none",
			},
			{
				"id": "LI-001",
				"category": "c",
				"item": "i2",
				"legal_basis": "b",
				"evidence_needed": ["x"],
				"risk": {"type": "과태료"},
				"automated_check": "none",
			},
		]
		with self.assertRaises(ValueError):
			self.mod.validate_labor_inspection_checklist(items)

	def test_validate_rejects_missing_required_field(self):
		items = [
			{
				"id": "LI-001",
				"category": "c",
				"item": "i",
				"legal_basis": "b",
				"evidence_needed": ["x"],
				"risk": {"type": "과태료"},
				# automated_check missing
			}
		]
		with self.assertRaises(ValueError):
			self.mod.validate_labor_inspection_checklist(items)

	def test_validate_rejects_empty_evidence_needed(self):
		items = [
			{
				"id": "LI-001",
				"category": "c",
				"item": "i",
				"legal_basis": "b",
				"evidence_needed": [],
				"risk": {"type": "과태료"},
				"automated_check": "none",
			}
		]
		with self.assertRaises(ValueError):
			self.mod.validate_labor_inspection_checklist(items)

	def test_filter_by_category(self):
		items = self.mod.load_labor_inspection_checklist()
		wage_items = self.mod.filter_by_category(items, "임금")
		self.assertTrue(all(item["category"] == "임금" for item in wage_items))
		self.assertGreater(len(wage_items), 0)

	def test_filter_by_automated_check_excludes_unconfirmed(self):
		items = self.mod.load_labor_inspection_checklist()
		automatable = self.mod.filter_automatable(items)
		self.assertTrue(all(not item["automated_check"].startswith("미확인") for item in automatable))
		self.assertGreater(len(automatable), 0)
		self.assertLess(len(automatable), len(items))


if __name__ == "__main__":
	unittest.main()
