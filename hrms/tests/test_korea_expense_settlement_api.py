#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "expense_settlement_api.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_expense_settlement_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaExpenseSettlementApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()
		self.claims = [
			{"employee": "EMP-2", "cost_center": "Sales", "tax_category": "Taxable", "amount": 50000},
			{"employee": "EMP-1", "cost_center": "R&D", "tax_category": "Non Taxable", "amount": 25000},
			{"employee": "EMP-1", "cost_center": "R&D", "tax_category": "Taxable", "amount": 15000},
		]

	def test_preview_expense_settlement_accepts_json_claims_and_returns_contract_metadata(self):
		response = self.mod.preview_korea_expense_settlement(claims=json.dumps(self.claims))

		self.assertEqual(response["contract_type"], "korea_expense_settlement_preview_v1")
		self.assertEqual(response["runtime_action"], "preview_only")
		self.assertFalse(response["requires_runtime_apply"])
		self.assertEqual(response["settlement"]["total_amount"], 90000)
		self.assertEqual(response["settlement"]["by_cost_center"], {"R&D": 40000, "Sales": 50000})
		self.assertEqual(
			response["reimbursement_batch"],
			[{"employee": "EMP-1", "amount": 40000}, {"employee": "EMP-2", "amount": 50000}],
		)

	def test_preview_expense_settlement_defensively_copies_caller_claims(self):
		claims = list(self.claims)
		response = self.mod.preview_korea_expense_settlement(claims=claims)

		claims[0]["amount"] = 999999

		self.assertEqual(response["settlement"]["total_amount"], 90000)
		self.assertEqual(response["claims"][0]["amount"], 50000)

	def test_preview_expense_settlement_rejects_invalid_json_and_non_list_claims(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.mod.preview_korea_expense_settlement(claims="[")

		with self.assertRaisesRegex(ValueError, "claims must be a list or JSON array"):
			self.mod.preview_korea_expense_settlement(claims={"amount": 1})

	def test_preview_expense_settlement_rejects_non_dict_claim_items(self):
		with self.assertRaisesRegex(ValueError, "claims\[0\] must be a dict"):
			self.mod.preview_korea_expense_settlement(claims=["not-a-claim"])


if __name__ == "__main__":
	unittest.main()
