# -*- coding: utf-8 -*-
"""v2 시맨틱 retriever 환경 팩토리(semantic_config.py) 테스트.

env(임베딩 키 + Supabase 접속)로 embedder·rpc_caller·retriever를 조립한다.
Supabase 미설정이면 None → chat_query는 v1로 폴백(더러운 로컬 카탈로그는
키가 있는 프로덕션에서만 v2로 은퇴). HTTP는 주입해 실네트워크 없이 검증.

framework-free. 실행: python3 hrms/tests/test_korea_semantic_config.py
"""
import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "hrms" / "regional" / "south_korea" / "semantic_config.py"
_spec = importlib.util.spec_from_file_location("semantic_config", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

build_semantic_retriever_from_env = _mod.build_semantic_retriever_from_env
DEFAULT_SOURCES = _mod.DEFAULT_SOURCES


def _fake_http(routes):
    calls = []

    def http_post(url, headers=None, json=None):
        calls.append(url)
        for frag, resp in routes.items():
            if frag in url:
                return resp
        return []

    return http_post, calls


class TestBuildFromEnv(unittest.TestCase):
    def test_none_when_supabase_unconfigured(self):
        r = build_semantic_retriever_from_env({}, http_post=lambda *a, **k: [])
        self.assertIsNone(r)

    def test_none_when_only_partial_supabase(self):
        env = {"YELLOW_ENVELOPE_SUPABASE_URL": "https://x.supabase.co"}  # 키 없음
        self.assertIsNone(build_semantic_retriever_from_env(env, http_post=lambda *a, **k: []))

    def test_builds_retriever_when_configured(self):
        env = {
            "YELLOW_ENVELOPE_SUPABASE_URL": "https://x.supabase.co",
            "YELLOW_ENVELOPE_SUPABASE_KEY": "SK",
            "OPENAI_API_KEY": "OK",
            "GEMINI_API_KEY": "GK",
        }
        routes = {
            "openai.com": {"data": [{"embedding": [0.1] * 1536}]},
            "generativelanguage": {"embedding": {"values": [0.2] * 768}},
            "rpc/search_faq_semantic": [{"question": "주휴수당?", "answer": "주15h+개근",
                                          "unified_category": "임금", "similarity": 0.91}],
            "rpc/": [],
        }
        http_post, calls = _fake_http(routes)
        retriever = build_semantic_retriever_from_env(env, http_post=http_post,
                                                      sources=["faq"])
        self.assertIsNotNone(retriever)
        docs = retriever(query="주휴수당 요건?", top_k=3)
        self.assertEqual(docs[0]["type"], "faq")
        self.assertEqual(docs[0]["text"], "주15h+개근")
        self.assertTrue(any("openai.com" in u for u in calls))       # 1536 임베딩
        self.assertTrue(any("search_faq_semantic" in u for u in calls))  # RPC 호출

    def test_default_sources_cover_all_five(self):
        self.assertEqual(set(DEFAULT_SOURCES),
                         {"pkb", "interpretation", "cases", "faq", "nlrc"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
