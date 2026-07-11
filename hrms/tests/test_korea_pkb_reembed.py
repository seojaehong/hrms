# -*- coding: utf-8 -*-
"""pkb 재임베딩 순수 코어(pkb_reembed.py) 테스트.

최영우 pkb를 Gemini 768 → OpenAI 1536으로 통일 재임베딩하는 배치 로직(순수).
실제 I/O(OpenAI·Supabase)는 scripts/reembed_pkb_openai.py가 이 코어를 호출.

framework-free. 실행: python3 hrms/tests/test_korea_pkb_reembed.py
"""
import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "hrms" / "regional" / "south_korea" / "pkb_reembed.py"
_spec = importlib.util.spec_from_file_location("pkb_reembed", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

chunk_batches = _mod.chunk_batches
parse_openai_embeddings = _mod.parse_openai_embeddings
assemble_write_payload = _mod.assemble_write_payload
truncate_for_embedding = _mod.truncate_for_embedding


class TestTruncateForEmbedding(unittest.TestCase):
    def test_short_text_unchanged(self):
        self.assertEqual(truncate_for_embedding("주휴수당"), "주휴수당")

    def test_long_korean_truncated_to_limit(self):
        # 한국어 ~2토큰/자 → 8k자 청크가 8192토큰 한도 초과(실사고). 3000자로 절단.
        long = "가" * 8000
        out = truncate_for_embedding(long)
        self.assertEqual(len(out), 3000)
        self.assertEqual(out, "가" * 3000)

    def test_empty_becomes_single_space(self):
        # OpenAI는 빈 문자열 입력을 거부 → 공백 1자로 대체
        self.assertEqual(truncate_for_embedding(""), " ")
        self.assertEqual(truncate_for_embedding("   "), " ")


class TestChunkBatches(unittest.TestCase):
    def test_splits_by_size(self):
        out = chunk_batches(list(range(250)), 100)
        self.assertEqual([len(b) for b in out], [100, 100, 50])

    def test_empty(self):
        self.assertEqual(chunk_batches([], 100), [])


class TestParseOpenAIEmbeddings(unittest.TestCase):
    def test_orders_by_index(self):
        resp = {"data": [{"index": 1, "embedding": [0.2]}, {"index": 0, "embedding": [0.1]}]}
        self.assertEqual(parse_openai_embeddings(resp), [[0.1], [0.2]])

    def test_count_mismatch_raises(self):
        with self.assertRaises(ValueError):
            parse_openai_embeddings({"data": [{"index": 0, "embedding": [0.1]}]}, expected=2)


class TestAssembleWritePayload(unittest.TestCase):
    def test_pairs_ids_with_vectors(self):
        payload = assemble_write_payload([11, 22], [[0.1, 0.2], [0.3, 0.4]])
        self.assertEqual(payload, [{"id": 11, "emb": [0.1, 0.2]},
                                   {"id": 22, "emb": [0.3, 0.4]}])

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            assemble_write_payload([1, 2], [[0.1]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
