# -*- coding: utf-8 -*-
"""ai_chat v2 시맨틱 배선(ai_chat_semantic.py + chat_query retriever 주입) 테스트.

v2 정규화 문서(semantic_retrieval)를 v1 문서 형태로 매핑해 기존 _build_answer/
_docs_to_citations 경로를 그대로 재사용하고, chat_query에 retriever를 주입하면
char-bigram 로컬 카탈로그 대신 시맨틱 결과로 답변이 구성되는지 검증한다.

framework-free. 실행: python3 hrms/tests/test_korea_ai_chat_semantic.py
"""
import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load(name):
    path = _REPO_ROOT / "hrms" / "regional" / "south_korea" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_sem = _load("ai_chat_semantic")
_chat = _load("ai_chat")

map_v2_to_v1_doc = _sem.map_v2_to_v1_doc
make_semantic_retriever = _sem.make_semantic_retriever
chat_query = _chat.chat_query


class TestMapV2ToV1Doc(unittest.TestCase):
    def test_interpretation_maps_to_law_type(self):
        nd = {"source": "행정해석", "title": "주휴수당 산정", "text": "회시: ...",
              "ref": "근기68207-216", "url": "u", "score": 0.8}
        d = map_v2_to_v1_doc(nd)
        self.assertEqual(d["type"], "law")
        self.assertEqual(d["law"], "행정해석")
        self.assertEqual(d["text"], "회시: ...")
        self.assertIn("근기68207-216", d["title"])  # 사건번호 추적성 보존

    def test_case_and_nlrc_map_to_case_type(self):
        self.assertEqual(map_v2_to_v1_doc({"source": "판례", "title": "t", "text": "x"})["type"], "case")
        self.assertEqual(
            map_v2_to_v1_doc({"source": "노동위 판정례", "title": "t", "text": "x"})["type"], "case")

    def test_faq_maps_to_faq_type(self):
        d = map_v2_to_v1_doc({"source": "상담 FAQ", "title": "q", "text": "a"})
        self.assertEqual(d["type"], "faq")

    def test_pkb_reference_maps_to_internal(self):
        d = map_v2_to_v1_doc({"source": "최영우 레퍼런스", "title": "통상임금", "text": "x",
                              "ref": "레퍼런스/1권.md"})
        self.assertEqual(d["type"], "internal")

    def test_title_falls_back_to_ref(self):
        d = map_v2_to_v1_doc({"source": "판례", "title": "", "text": "x", "ref": "2020다1"})
        self.assertEqual(d["title"], "2020다1")


class TestSemanticRetriever(unittest.TestCase):
    def test_retriever_calls_build_and_maps(self):
        captured = {}

        def fake_build(query, sources, top_k):
            captured["query"] = query
            captured["sources"] = sources
            captured["top_k"] = top_k
            return [{"source": "행정해석", "title": "주휴수당", "text": "회시...",
                     "ref": "근기1", "url": None, "score": 0.9}]

        retriever = make_semantic_retriever(retrieve_fn=fake_build,
                                            sources=["interpretation", "faq"])
        docs = retriever(query="주휴수당?", top_k=3)
        self.assertEqual(captured["sources"], ["interpretation", "faq"])
        self.assertEqual(captured["top_k"], 3)
        self.assertEqual(docs[0]["type"], "law")
        self.assertEqual(docs[0]["text"], "회시...")


class TestChatQueryWithInjectedRetriever(unittest.TestCase):
    def test_answer_built_from_semantic_docs_not_local_catalog(self):
        sentinel = "이것은 시맨틱 검색으로만 나오는 고유 회시 본문입니다"

        def retriever(query, top_k):
            return [{"law": "행정해석", "title": "주휴수당 산정 [근기68207-216]",
                     "text": sentinel, "type": "law"}]

        r = chat_query(user_question="주휴수당 발생요건?", user_role="hr_manager",
                       session_id="s1", retriever=retriever)
        self.assertIn(sentinel, r["answer"])
        self.assertTrue(any("행정해석" in c["ref"] for c in r["citations"]))

    def test_default_retriever_still_v1(self):
        # retriever 미주입 → 기존 v1 경로 동작(회귀 방지)
        r = chat_query(user_question="연차휴가 며칠?", user_role="hr_manager", session_id="s2")
        self.assertTrue(r["answer"])
        self.assertEqual(r["contract_type"], _chat.CONTRACT_TYPE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
