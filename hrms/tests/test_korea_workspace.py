"""
Wave 3-C: Korea HR Workspace — structural validation tests.

These tests run without Frappe/ERPNext installed (pure Python).
They assert:
  1. The workspace JSON file exists and is valid JSON.
  2. Every required top-level field is present (Frappe v15 schema parity).
  3. All Korea-specific DocTypes appear in the links.
  4. Card names in `content` match Card Break labels in `links`.
  5. Shortcuts contain the three priority entries with valid colors.
"""

import json
import pathlib
import unittest

# Resolve the workspace file relative to this test file.
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_WORKSPACE_FILE = (
    _REPO_ROOT
    / "hrms"
    / "hr"
    / "workspace"
    / "korea_hr"
    / "korea_hr.json"
)

# Frappe v15 required top-level workspace keys (derived from leaves.json reference).
_REQUIRED_KEYS = {
    "app",
    "charts",
    "content",
    "creation",
    "custom_blocks",
    "docstatus",
    "doctype",
    "for_user",
    "hide_custom",
    "icon",
    "idx",
    "is_hidden",
    "label",
    "links",
    "modified",
    "modified_by",
    "module",
    "name",
    "number_cards",
    "owner",
    "parent_page",
    "public",
    "quick_lists",
    "roles",
    "sequence_id",
    "shortcuts",
    "title",
    "type",
}

# DocTypes that must appear as Link targets in this workspace.
_REQUIRED_DOCTYPES = {
    # Korea-specific (Wave 3-A/3-B)
    "Korea Workplace Profile",
    "Korea Employment Profile",
    "Korea Payroll Closing Draft",
    "Korea Payroll Closing Review Audit Log",
    # Standard HRMS DocTypes
    "Leave Allocation",
    "Leave Application",
    "Leave Policy",
    "Attendance",
    "Holiday List",
    "Salary Slip",
    "Salary Structure",
    "Payroll Entry",
}

# Valid shortcut colors in Frappe desk.
_VALID_COLORS = {"Blue", "Green", "Purple", "Red", "Orange", "Yellow", "Gray", "Pink"}

# Priority shortcuts expected in this workspace.
_EXPECTED_SHORTCUTS = {
    ("Korea Payroll Closing Draft", "Blue"),
    ("Korea Workplace Profile", "Green"),
    ("Korea Employment Profile", "Purple"),
}


class TestKoreaWorkspaceFile(unittest.TestCase):
    """Test 1 & 2: File exists, valid JSON, required keys present."""

    def setUp(self):
        self.assertTrue(
            _WORKSPACE_FILE.exists(),
            f"Workspace JSON not found: {_WORKSPACE_FILE}",
        )
        with _WORKSPACE_FILE.open(encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_file_is_valid_json(self):
        """JSON must parse without error."""
        self.assertIsInstance(self.data, dict)

    def test_required_top_level_keys_present(self):
        """All Frappe v15 workspace fields must be present."""
        missing = _REQUIRED_KEYS - set(self.data.keys())
        self.assertEqual(
            missing,
            set(),
            f"Missing required workspace keys: {missing}",
        )

    def test_doctype_is_workspace(self):
        self.assertEqual(self.data["doctype"], "Workspace")

    def test_name_is_ascii_friendly(self):
        """name field should be ASCII (URL-safe); Korean goes in label/title."""
        self.assertEqual(self.data["name"], "Korea HR")

    def test_label_is_korean(self):
        self.assertEqual(self.data["label"], "HR 홈")

    def test_module_is_hr(self):
        self.assertEqual(self.data["module"], "HR")

    def test_public_flag(self):
        self.assertEqual(self.data["public"], 1)

    def test_is_not_hidden(self):
        self.assertEqual(self.data["is_hidden"], 0)


class TestKoreaWorkspaceContent(unittest.TestCase):
    """Test content string: parseable, contains expected card types."""

    def setUp(self):
        with _WORKSPACE_FILE.open(encoding="utf-8") as fh:
            self.data = json.load(fh)
        self.content = json.loads(self.data["content"])

    def test_content_is_parseable_json_string(self):
        self.assertIsInstance(self.content, list)

    def test_content_has_header(self):
        types = [item["type"] for item in self.content]
        self.assertIn("header", types)

    def test_content_has_cards(self):
        cards = [item for item in self.content if item["type"] == "card"]
        self.assertGreaterEqual(len(cards), 5, "Expected at least 5 cards")

    def test_content_card_names_match_card_break_labels(self):
        """card_name in content must exactly match Card Break labels in links."""
        card_names = {
            item["data"]["card_name"]
            for item in self.content
            if item["type"] == "card"
        }
        card_break_labels = {
            link["label"]
            for link in self.data["links"]
            if link["type"] == "Card Break"
        }
        self.assertEqual(
            card_names,
            card_break_labels,
            "Mismatch between content card_names and links Card Break labels.\n"
            f"  content: {sorted(card_names)}\n"
            f"  links:   {sorted(card_break_labels)}",
        )


class TestKoreaWorkspaceLinks(unittest.TestCase):
    """Test 3: All required DocTypes appear in links."""

    def setUp(self):
        with _WORKSPACE_FILE.open(encoding="utf-8") as fh:
            self.data = json.load(fh)
        self.link_targets = {
            link["link_to"]
            for link in self.data["links"]
            if link.get("type") == "Link" and link.get("link_to")
        }

    def test_required_doctypes_in_links(self):
        missing = _REQUIRED_DOCTYPES - self.link_targets
        self.assertEqual(
            missing,
            set(),
            f"DocTypes missing from workspace links: {missing}",
        )

    def test_links_have_correct_structure(self):
        """Every Link entry must have hidden, is_query_report, label, link_to, link_type, type."""
        required_link_fields = {"hidden", "is_query_report", "label", "link_to", "link_type", "type"}
        for link in self.data["links"]:
            if link.get("type") == "Link":
                missing = required_link_fields - set(link.keys())
                self.assertEqual(
                    missing,
                    set(),
                    f"Link entry missing fields {missing}: {link}",
                )

    def test_card_breaks_have_link_count(self):
        """Card Break entries must have a link_count."""
        for link in self.data["links"]:
            if link.get("type") == "Card Break":
                self.assertIn(
                    "link_count",
                    link,
                    f"Card Break missing link_count: {link}",
                )


class TestKoreaWorkspaceShortcuts(unittest.TestCase):
    """Test 5: Shortcuts — correct entries and valid colors."""

    def setUp(self):
        with _WORKSPACE_FILE.open(encoding="utf-8") as fh:
            self.data = json.load(fh)
        self.shortcuts = self.data.get("shortcuts", [])

    def test_shortcuts_present(self):
        self.assertGreater(len(self.shortcuts), 0, "No shortcuts defined")

    def test_expected_priority_shortcuts(self):
        actual = {(s["link_to"], s["color"]) for s in self.shortcuts}
        missing = _EXPECTED_SHORTCUTS - actual
        self.assertEqual(
            missing,
            set(),
            f"Expected shortcuts missing: {missing}\nActual: {actual}",
        )

    def test_shortcut_colors_are_valid(self):
        for shortcut in self.shortcuts:
            self.assertIn(
                shortcut.get("color"),
                _VALID_COLORS,
                f"Invalid color '{shortcut.get('color')}' in shortcut: {shortcut}",
            )

    def test_shortcuts_have_required_fields(self):
        required = {"label", "link_to", "type", "color"}
        for shortcut in self.shortcuts:
            missing = required - set(shortcut.keys())
            self.assertEqual(
                missing,
                set(),
                f"Shortcut missing fields {missing}: {shortcut}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
