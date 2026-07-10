import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hrms" / "regional" / "south_korea" / "ontology" / "loader.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_ontology_loader", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def write_node(root, kind, node_id, review_state, sources, body, label="라벨"):
	src_lines = "".join(f"- {s}\n" for s in sources)
	text = (
		"---\n"
		f"node_id: {node_id}\n"
		f"kind: {kind}\n"
		f"label: {label}\n"
		f"review_state: {review_state}\n"
		"sources:\n"
		f"{src_lines}"
		"---\n"
		f"{body}\n"
	)
	node_dir = pathlib.Path(root) / kind
	node_dir.mkdir(parents=True, exist_ok=True)
	path = node_dir / f"{node_id}.md"
	path.write_text(text, encoding="utf-8")
	return path


class KoreaOntologyLoaderTest(unittest.TestCase):
	def setUp(self):
		self.loader = load_module()

	def test_default_returns_only_published_nodes(self):
		with tempfile.TemporaryDirectory() as tmp:
			write_node(tmp, "법령조항", "pub_node", "published", ["근로기준법 제60조"], "본문")
			write_node(tmp, "급여규칙", "draft_node", "draft", ["근로기준법 제60조"], "본문")

			nodes, errors = self.loader.load_nodes(tmp)

			self.assertEqual(errors, [])
			ids = {n.node_id for n in nodes}
			self.assertEqual(ids, {"pub_node"})

	def test_draft_filter_returns_only_draft_nodes(self):
		with tempfile.TemporaryDirectory() as tmp:
			write_node(tmp, "법령조항", "pub_node", "published", ["s"], "본문")
			write_node(tmp, "급여규칙", "draft_node", "draft", ["s"], "본문")

			nodes, errors = self.loader.load_nodes(tmp, review_state="draft")

			self.assertEqual(errors, [])
			self.assertEqual({n.node_id for n in nodes}, {"draft_node"})

	def test_review_state_none_returns_all_nodes(self):
		with tempfile.TemporaryDirectory() as tmp:
			write_node(tmp, "법령조항", "pub_node", "published", ["s"], "본문")
			write_node(tmp, "급여규칙", "draft_node", "draft", ["s"], "본문")

			nodes, errors = self.loader.load_nodes(tmp, review_state=None)

			self.assertEqual(errors, [])
			self.assertEqual({n.node_id for n in nodes}, {"pub_node", "draft_node"})

	def test_node_fields_are_parsed(self):
		with tempfile.TemporaryDirectory() as tmp:
			write_node(
				tmp,
				"급여규칙",
				"연차_산정",
				"published",
				["근로기준법 제60조", "근로기준법 제61조"],
				"연차 규칙 본문",
				label="연차 산정",
			)

			nodes, errors = self.loader.load_nodes(tmp)

			self.assertEqual(errors, [])
			node = nodes[0]
			self.assertEqual(node.node_id, "연차_산정")
			self.assertEqual(node.kind, "급여규칙")
			self.assertEqual(node.label, "연차 산정")
			self.assertEqual(node.review_state, "published")
			self.assertEqual(node.sources, ["근로기준법 제60조", "근로기준법 제61조"])
			self.assertIn("연차 규칙 본문", node.body)
			self.assertTrue(str(node.path).endswith("연차_산정.md"))

	def test_edges_are_extracted_from_wikilinks(self):
		with tempfile.TemporaryDirectory() as tmp:
			write_node(
				tmp,
				"급여규칙",
				"연차_산정",
				"published",
				["s"],
				"근거는 [[근로기준법_제60조]] 이며 [[연차_사용촉진]] 참고. 중복 [[근로기준법_제60조]].",
			)

			nodes, errors = self.loader.load_nodes(tmp)

			self.assertEqual(errors, [])
			self.assertEqual(nodes[0].edges, ["근로기준법_제60조", "연차_사용촉진"])

	def test_bad_frontmatter_is_reported_not_raised(self):
		with tempfile.TemporaryDirectory() as tmp:
			# no frontmatter delimiters at all
			no_fm = pathlib.Path(tmp) / "법령조항"
			no_fm.mkdir(parents=True)
			(no_fm / "broken.md").write_text("그냥 본문만 있음", encoding="utf-8")
			# missing node_id
			missing = (
				"---\n"
				"kind: 법령조항\n"
				"label: 라벨\n"
				"review_state: published\n"
				"sources:\n"
				"- s\n"
				"---\n"
				"본문\n"
			)
			(no_fm / "missing_id.md").write_text(missing, encoding="utf-8")
			write_node(tmp, "법령조항", "ok_node", "published", ["s"], "본문")

			nodes, errors = self.loader.load_nodes(tmp)

			self.assertEqual({n.node_id for n in nodes}, {"ok_node"})
			self.assertEqual(len(errors), 2)
			error_paths = " ".join(str(e["path"]) for e in errors)
			self.assertIn("broken.md", error_paths)
			self.assertIn("missing_id.md", error_paths)

	def test_missing_root_returns_empty(self):
		nodes, errors = self.loader.load_nodes(ROOT / "does_not_exist_ontology_xyz")
		self.assertEqual(nodes, [])
		self.assertEqual(errors, [])

	def test_empty_root_returns_empty(self):
		with tempfile.TemporaryDirectory() as tmp:
			nodes, errors = self.loader.load_nodes(tmp)
			self.assertEqual(nodes, [])
			self.assertEqual(errors, [])


if __name__ == "__main__":
	unittest.main()
