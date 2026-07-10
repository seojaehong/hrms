import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hrms" / "regional" / "south_korea" / "ontology" / "validate.py"


def load_module():
	spec = importlib.util.spec_from_file_location("korea_ontology_validate", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class _Node:
	"""Minimal stand-in for loader.OntologyNode (same duck-typed fields)."""

	def __init__(self, node_id, edges=None, sources=None, review_state="published"):
		self.node_id = node_id
		self.edges = list(edges or [])
		self.sources = list(sources or [])
		self.review_state = review_state
		self.kind = "급여규칙"
		self.label = node_id
		self.body = ""
		self.path = f"{node_id}.md"


class KoreaOntologyValidateTest(unittest.TestCase):
	def setUp(self):
		self.validate = load_module()

	def test_valid_graph_has_no_errors(self):
		nodes = [
			_Node("근로기준법_제60조", sources=["근로기준법 제60조"]),
			_Node("연차_산정", edges=["근로기준법_제60조"], sources=["근로기준법 제60조"]),
		]
		self.assertEqual(self.validate.validate_graph(nodes), [])

	def test_orphan_edge_is_detected(self):
		nodes = [
			_Node("연차_산정", edges=["존재하지_않는_노드"], sources=["s"]),
		]
		errors = self.validate.validate_graph(nodes)
		self.assertTrue(errors)
		joined = " ".join(errors)
		self.assertIn("존재하지_않는_노드", joined)
		self.assertIn("연차_산정", joined)

	def test_duplicate_node_id_is_detected(self):
		nodes = [
			_Node("연차_산정", sources=["s"]),
			_Node("연차_산정", sources=["s"]),
		]
		errors = self.validate.validate_graph(nodes)
		self.assertTrue(errors)
		self.assertIn("연차_산정", " ".join(errors))

	def test_published_node_without_sources_is_detected(self):
		nodes = [
			_Node("연차_산정", sources=[], review_state="published"),
		]
		errors = self.validate.validate_graph(nodes)
		self.assertTrue(errors)
		self.assertIn("연차_산정", " ".join(errors))

	def test_draft_node_without_sources_is_allowed(self):
		# Only published nodes require sources; drafts are still being authored.
		nodes = [
			_Node("연차_산정", sources=[], review_state="draft"),
		]
		self.assertEqual(self.validate.validate_graph(nodes), [])

	def test_empty_graph_has_no_errors(self):
		self.assertEqual(self.validate.validate_graph([]), [])


if __name__ == "__main__":
	unittest.main()
