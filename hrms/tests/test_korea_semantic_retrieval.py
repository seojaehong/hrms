# -*- coding: utf-8 -*-
"""v2 시맨틱 검색 코어(semantic_retrieval.py) 테스트.

ai_chat v1은 char-bigram + 로컬 JSON(석탄분진 오염 사고의 원인). v2는 yellow-envelope-law
Supabase의 임베딩 코퍼스(최영우 pkb 768d, 행정해석·판례·FAQ 1536d, 판정례)를 기존 검색
RPC로 조회한다. 이 코어는 외부 의존(임베딩 API·Supabase)을 **주입**받는 순수 로직:
소스별 올바른 임베딩 모델 선택 → RPC 파라미터 구성 → 결과 정규화 → 병합·랭킹.

framework-free: semantic_retrieval.py는 frappe·requests·supabase import 없음(어댑터 주입).
실행: python3 hrms/tests/test_korea_semantic_retrieval.py
"""
import importlib.util
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "hrms" / "regional" / "south_korea" / "semantic_retrieval.py"

_spec = importlib.util.spec_from_file_location("semantic_retrieval", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

select_model = _mod.select_model
normalize_row = _mod.normalize_row
merge_and_rank = _mod.merge_and_rank
build_retrieval = _mod.build_retrieval
SOURCES = _mod.SOURCES


class TestSelectModel(unittest.TestCase):
    def test_pkb_uses_gemini_768(self):
        self.assertEqual(select_model("pkb"), "gemini-768")

    def test_interpretation_cases_faq_use_openai_1536(self):
        self.assertEqual(select_model("interpretation"), "openai-1536")
        self.assertEqual(select_model("cases"), "openai-1536")
        self.assertEqual(select_model("faq"), "openai-1536")

    def test_nlrc_is_text_only_no_model(self):
        self.assertIsNone(select_model("nlrc"))


class TestNormalizeRow(unittest.TestCase):
    def test_pkb_row(self):
        row = {"title": "통상임금 판단기준", "section": "3장", "content": "정기·일률·고정성...",
               "source_path": "레퍼런스/최영우/1권.md", "folder": "레퍼런스", "similarity": 0.82}
        d = normalize_row("pkb", row)
        self.assertEqual(d["source"], "최영우 레퍼런스")
        self.assertEqual(d["title"], "통상임금 판단기준")
        self.assertEqual(d["text"], "정기·일률·고정성...")
        self.assertEqual(d["ref"], "레퍼런스/최영우/1권.md")
        self.assertAlmostEqual(d["score"], 0.82)

    def test_interpretation_row(self):
        row = {"case_number": "근기68207-216", "title": "주휴수당 산정",
               "inquiry_summary": "질의...", "answer_summary": "회시: 주휴수당은...",
               "url": "http://x", "similarity": 0.7}
        d = normalize_row("interpretation", row)
        self.assertEqual(d["source"], "행정해석")
        self.assertEqual(d["ref"], "근기68207-216")
        self.assertIn("주휴수당", d["text"])
        self.assertEqual(d["url"], "http://x")

    def test_faq_row(self):
        row = {"question": "주휴수당 발생요건?", "answer": "주 15시간 이상+개근",
               "unified_category": "임금", "similarity": 0.9}
        d = normalize_row("faq", row)
        self.assertEqual(d["source"], "상담 FAQ")
        self.assertEqual(d["title"], "주휴수당 발생요건?")
        self.assertEqual(d["text"], "주 15시간 이상+개근")

    def test_cases_row(self):
        row = {"case_number": "2020다123", "court": "대법원", "title": "퇴직금",
               "summary": "판시...", "url": "u", "similarity": 0.6}
        d = normalize_row("cases", row)
        self.assertEqual(d["source"], "판례")
        self.assertEqual(d["ref"], "2020다123")

    def test_nlrc_row_uses_relevance_as_score(self):
        row = {"case_number": "2021부해1", "title": "부당해고", "holding_summary": "요지...",
               "url": "u", "relevance": 0.55}
        d = normalize_row("nlrc", row)
        self.assertEqual(d["source"], "노동위 판정례")
        self.assertAlmostEqual(d["score"], 0.55)


class TestMergeAndRank(unittest.TestCase):
    def test_sorts_by_score_desc(self):
        rows = [{"source": "a", "ref": "1", "score": 0.3, "title": "t", "text": "x", "url": None},
                {"source": "b", "ref": "2", "score": 0.9, "title": "t", "text": "x", "url": None}]
        out = merge_and_rank({"a": [rows[0]], "b": [rows[1]]}, top_k=5, per_source_cap=3)
        self.assertEqual([r["ref"] for r in out], ["2", "1"])

    def test_per_source_cap(self):
        many = [{"source": "a", "ref": str(i), "score": 1 - i * 0.1, "title": "t",
                 "text": "x", "url": None} for i in range(5)]
        out = merge_and_rank({"a": many}, top_k=10, per_source_cap=2)
        self.assertEqual(len(out), 2)

    def test_top_k_limit(self):
        rows = {s: [{"source": s, "ref": s, "score": 0.5, "title": "t", "text": "x", "url": None}]
                for s in ("a", "b", "c", "d")}
        out = merge_and_rank(rows, top_k=2, per_source_cap=3)
        self.assertEqual(len(out), 2)

    def test_dedup_by_source_ref(self):
        dup = [{"source": "a", "ref": "1", "score": 0.5, "title": "t", "text": "x", "url": None},
               {"source": "a", "ref": "1", "score": 0.4, "title": "t", "text": "x", "url": None}]
        out = merge_and_rank({"a": dup}, top_k=5, per_source_cap=5)
        self.assertEqual(len(out), 1)


class TestBuildRetrieval(unittest.TestCase):
    def _fakes(self):
        embed_calls = []
        rpc_calls = []

        def embedder(model, text):
            embed_calls.append((model, text))
            return [0.1, 0.2, 0.3]

        def rpc_caller(rpc, params):
            rpc_calls.append((rpc, params))
            if rpc == "pkb_search":
                return [{"title": "최영우", "content": "통상임금...", "source_path": "ref/1",
                         "similarity": 0.8}]
            if rpc == "search_faq_semantic":
                return [{"question": "q", "answer": "a", "unified_category": "임금",
                         "similarity": 0.95}]
            return []

        return embedder, rpc_caller, embed_calls, rpc_calls

    def test_embeds_each_semantic_source_with_correct_model(self):
        embedder, rpc_caller, embed_calls, rpc_calls = self._fakes()
        build_retrieval("주휴수당?", ["pkb", "faq"], embedder=embedder,
                        rpc_caller=rpc_caller, top_k=5)
        models = {m for m, _ in embed_calls}
        self.assertEqual(models, {"gemini-768", "openai-1536"})

    def test_returns_merged_normalized_ranked(self):
        embedder, rpc_caller, _, _ = self._fakes()
        out = build_retrieval("주휴수당?", ["pkb", "faq"], embedder=embedder,
                              rpc_caller=rpc_caller, top_k=5)
        # faq(0.95) > pkb(0.8)
        self.assertEqual(out[0]["source"], "상담 FAQ")
        self.assertEqual(out[1]["source"], "최영우 레퍼런스")

    def test_semantic_rpcs_pass_low_min_similarity(self):
        # 검색은 낮은 min_similarity로 넓게 뽑는다(판정은 팩트체크 τ가). 3-small 인도메인~0.35라 필수.
        embedder, rpc_caller, _, rpc_calls = self._fakes()
        build_retrieval("주휴수당?", ["interpretation"], embedder=embedder,
                        rpc_caller=rpc_caller, top_k=5)
        rpc, params = rpc_calls[0]
        self.assertEqual(rpc, "search_interpretation_semantic")
        self.assertIn("min_similarity", params)
        self.assertLessEqual(params["min_similarity"], 0.25)

    def test_nlrc_text_source_gets_query_not_embedding(self):
        embedder, rpc_caller, embed_calls, rpc_calls = self._fakes()
        build_retrieval("부당해고", ["nlrc"], embedder=embedder,
                        rpc_caller=rpc_caller, top_k=5)
        # nlrc는 텍스트 검색 → 임베딩 호출 없음, query 문자열이 params에
        self.assertEqual(embed_calls, [])
        rpc, params = rpc_calls[0]
        self.assertEqual(rpc, "search_nlrc")
        self.assertEqual(params.get("query"), "부당해고")

    def test_query_redacted_before_embedding(self):
        embedder, rpc_caller, embed_calls, _ = self._fakes()
        build_retrieval("직원 홍길동", ["pkb"], embedder=embedder, rpc_caller=rpc_caller,
                        top_k=5, redactor=lambda t: t.replace("홍길동", "[이름]"))
        self.assertIn("[이름]", embed_calls[0][1])
        self.assertNotIn("홍길동", embed_calls[0][1])

    def test_failed_source_does_not_break_others(self):
        embedder, _, _, _ = self._fakes()

        def flaky_rpc(rpc, params):
            if rpc == "pkb_search":
                raise RuntimeError("supabase down")
            return [{"question": "q", "answer": "a", "unified_category": "임금", "similarity": 0.9}]

        out = build_retrieval("주휴수당?", ["pkb", "faq"], embedder=embedder,
                              rpc_caller=flaky_rpc, top_k=5)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source"], "상담 FAQ")


if __name__ == "__main__":
    unittest.main(verbosity=2)
