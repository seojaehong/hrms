#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "expense_settlement.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_expense_settlement", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaExpenseSettlement(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_build_settlement_groups_claims_by_cost_center_and_tax_category(self):
		settlement = self.mod.build_cost_settlement(
			claims=[
				{"employee": "EMP-1", "cost_center": "Sales", "tax_category": "Taxable", "amount": 110000},
				{"employee": "EMP-2", "cost_center": "Sales", "tax_category": "Non Taxable", "amount": 50000},
				{"employee": "EMP-3", "cost_center": "R&D", "tax_category": "Taxable", "amount": 90000},
			]
		)

		self.assertEqual(settlement["total_amount"], 250000)
		self.assertEqual(settlement["by_cost_center"], {"R&D": 90000, "Sales": 160000})
		self.assertEqual(settlement["by_tax_category"], {"Non Taxable": 50000, "Taxable": 200000})
		self.assertEqual(settlement["claim_count"], 3)

	def test_reimbursement_batches_are_sorted_by_employee(self):
		batch = self.mod.build_reimbursement_batch([
			{"employee": "EMP-2", "amount": 50000},
			{"employee": "EMP-1", "amount": 10000},
			{"employee": "EMP-1", "amount": 15000},
		])

		self.assertEqual(batch, [{"employee": "EMP-1", "amount": 25000}, {"employee": "EMP-2", "amount": 50000}])

	def test_negative_claim_amount_is_rejected(self):
		with self.assertRaises(ValueError):
			self.mod.build_cost_settlement(claims=[{"employee": "EMP-1", "cost_center": "Sales", "tax_category": "Taxable", "amount": -1}])


if __name__ == "__main__":
	unittest.main()
