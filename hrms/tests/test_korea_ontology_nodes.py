import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ONTOLOGY_DIR = ROOT / "hrms" / "regional" / "south_korea" / "ontology"
LOADER_PATH = ONTOLOGY_DIR / "loader.py"
VALIDATE_PATH = ONTOLOGY_DIR / "validate.py"
WIKI_ROOT = ROOT / "wiki" / "ontology"

EXPECTED_NODE_IDS = {
	"근로기준법_제60조",
	"연차_산정",
	"연차_사용촉진",
}


def load_module(name, path):
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class KoreaOntologyNodesTest(unittest.TestCase):
	def setUp(self):
		self.loader = load_module("korea_ontology_loader", LOADER_PATH)
		self.validate = load_module("korea_ontology_validate", VALIDATE_PATH)
		# review_state=None → 상태 무관 전체 로드 (노드는 전부 draft).
		self.nodes, self.errors = self.loader.load_nodes(WIKI_ROOT, review_state=None)
		self.by_id = {n.node_id: n for n in self.nodes}

	def test_frontmatter_parses_without_errors(self):
		self.assertEqual(self.errors, [])

	def test_three_expected_nodes_present(self):
		self.assertTrue(EXPECTED_NODE_IDS.issubset(set(self.by_id)))

	def test_all_nodes_have_valid_review_state(self):
		# 에이전트는 draft만 생성 — published 승격은 사람(노무사) 몫.
		# (2026-07-11 노무사 검수·승인으로 1차 승격 완료 — 상태 고정 대신 유효값만 검증)
		for node_id in EXPECTED_NODE_IDS:
			self.assertIn(self.by_id[node_id].review_state, ("draft", "published"))

	def test_rules_nodes_edge_to_statute(self):
		self.assertIn("근로기준법_제60조", self.by_id["연차_산정"].edges)
		self.assertIn("근로기준법_제60조", self.by_id["연차_사용촉진"].edges)

	def test_nodes_have_sources(self):
		for node_id in EXPECTED_NODE_IDS:
			self.assertTrue(self.by_id[node_id].sources)

	def test_graph_validates_clean(self):
		self.assertEqual(self.validate.validate_graph(self.nodes), [])


if __name__ == "__main__":
	unittest.main()
