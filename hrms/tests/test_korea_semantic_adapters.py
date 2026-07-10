# -*- coding: utf-8 -*-
"""v2 시맨틱 검색 어댑터(semantic_adapters.py) 테스트 — 임베딩 API·Supabase RPC HTTP 글루.

semantic_retrieval 코어가 주입받는 두 어댑터의 HTTP 계약을 검증한다. 실제 네트워크는
http_post를 주입해 격리(키·엔드포인트·페이로드·파싱·차원검증). 실키 불필요.

framework-free. 실행: python3 hrms/tests/test_korea_semantic_adapters.py
"""
import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "hrms" / "regional" / "south_korea" / "semantic_adapters.py"
_spec = importlib.util.spec_from_file_location("semantic_adapters", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

make_embedder = _mod.make_embedder
make_rpc_caller = _mod.make_rpc_caller


class TestEmbedder(unittest.TestCase):
    def _spy(self, resp):
        calls = []

        def http_post(url, headers=None, json=None):
            calls.append({"url": url, "headers": headers or {}, "json": json or {}})
            return resp

        return http_post, calls

    def test_gemini_768_endpoint_payload_and_parse(self):
        vec = [0.01] * 768
        http_post, calls = self._spy({"embedding": {"values": vec}})
        embed = make_embedder(gemini_key="GK", openai_key="OK", http_post=http_post)
        out = embed("gemini-768", "주휴수당?")
        self.assertEqual(out, vec)
        c = calls[0]
        self.assertIn("text-embedding-004", c["url"])
        self.assertIn("GK", c["url"])  # 키는 쿼리파라미터
        self.assertEqual(c["json"]["content"]["parts"][0]["text"], "주휴수당?")

    def test_openai_1536_endpoint_payload_and_parse(self):
        vec = [0.02] * 1536
        http_post, calls = self._spy({"data": [{"embedding": vec}]})
        embed = make_embedder(gemini_key="GK", openai_key="OK", http_post=http_post)
        out = embed("openai-1536", "연차 계산")
        self.assertEqual(out, vec)
        c = calls[0]
        self.assertIn("api.openai.com", c["url"])
        self.assertEqual(c["headers"].get("Authorization"), "Bearer OK")
        self.assertEqual(c["json"]["input"], "연차 계산")

    def test_dimension_mismatch_raises(self):
        http_post, _ = self._spy({"embedding": {"values": [0.1] * 512}})  # 768이 아님
        embed = make_embedder(gemini_key="GK", openai_key="OK", http_post=http_post)
        with self.assertRaises(ValueError):
            embed("gemini-768", "x")

    def test_unknown_model_raises(self):
        http_post, _ = self._spy({})
        embed = make_embedder(gemini_key="GK", openai_key="OK", http_post=http_post)
        with self.assertRaises(ValueError):
            embed("mystery-model", "x")

    def test_missing_key_raises(self):
        http_post, _ = self._spy({})
        embed = make_embedder(gemini_key="", openai_key="OK", http_post=http_post)
        with self.assertRaises(ValueError):
            embed("gemini-768", "x")


class TestRpcCaller(unittest.TestCase):
    def _spy(self, resp):
        calls = []

        def http_post(url, headers=None, json=None):
            calls.append({"url": url, "headers": headers or {}, "json": json or {}})
            return resp

        return http_post, calls

    def test_posts_to_postgrest_rpc_with_auth_headers(self):
        http_post, calls = self._spy([{"title": "t", "similarity": 0.8}])
        rpc = make_rpc_caller(base_url="https://x.supabase.co", api_key="AK", http_post=http_post)
        rows = rpc("pkb_search", {"query_embedding": [0.1], "match_count": 3})
        self.assertEqual(rows, [{"title": "t", "similarity": 0.8}])
        c = calls[0]
        self.assertEqual(c["url"], "https://x.supabase.co/rest/v1/rpc/pkb_search")
        self.assertEqual(c["headers"].get("apikey"), "AK")
        self.assertEqual(c["headers"].get("Authorization"), "Bearer AK")
        self.assertEqual(c["json"]["match_count"], 3)

    def test_non_list_response_returns_empty(self):
        http_post, _ = self._spy({"error": "boom"})
        rpc = make_rpc_caller(base_url="https://x.supabase.co", api_key="AK", http_post=http_post)
        self.assertEqual(rpc("pkb_search", {}), [])

    def test_missing_config_raises(self):
        http_post, _ = self._spy([])
        with self.assertRaises(ValueError):
            make_rpc_caller(base_url="", api_key="AK", http_post=http_post)


if __name__ == "__main__":
    unittest.main(verbosity=2)
