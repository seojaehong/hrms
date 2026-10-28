"""Offline checks for persistent, port-specific fail-closed guards."""
from __future__ import annotations
import importlib.util
import pathlib
import unittest

SPEC = importlib.util.spec_from_file_location("sign_firewall", pathlib.Path(__file__).with_name("firewall.py"))
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GuardTests(unittest.TestCase):
    def test_inserts_only_in_filter_before_input_rules(self) -> None:
        source = "*mangle\n:INPUT ACCEPT [0:0]\nCOMMIT\n*filter\n:INPUT ACCEPT [0:0]\n-A INPUT -p tcp --dport 443 -j ACCEPT\nCOMMIT\n"
        result = MODULE.with_guard(source)
        self.assertEqual(result.replace(MODULE.GUARD_LINE + "\n", ""), source)
        self.assertLess(result.index(MODULE.GUARD_LINE), result.index("-A INPUT -p tcp --dport 443"))
        self.assertEqual(MODULE.with_guard(result), result)

    def test_inserts_before_commit_without_input_rules(self) -> None:
        source = "*filter\n:INPUT ACCEPT [0:0]\nCOMMIT\n"
        self.assertIn(MODULE.GUARD_LINE + "\nCOMMIT", MODULE.with_guard(source))

    def test_missing_filter_fails(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.with_guard("*nat\nCOMMIT\n")

    def test_empty_or_broad_range_list_fails(self) -> None:
        for source in ("", "0.0.0.0/0\n", "::/0\n", "not-a-cidr"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                MODULE.parse_ranges(source)

    def test_ranges_are_validated_and_deduplicated(self) -> None:
        self.assertEqual(MODULE.parse_ranges("192.0.2.0/24\n192.0.2.0/24\n"), ["192.0.2.0/24"])


if __name__ == "__main__":
    unittest.main()
