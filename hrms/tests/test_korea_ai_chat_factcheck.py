# -*- coding: utf-8 -*-
"""ai_chat 팩트체크 하네스 게이트(ai_chat_factcheck.py + chat_query) 테스트.

PRD §7.4 / 원칙4 / 환각 리스크완화 계약을 v2 답변 경로에 강제한다:
- 신뢰도(top 유사도) < 임계치 → 단정 금지, "노무사 상담 권장" 하네스 fallback
- 답변마다 검증가능한 근거(사건번호·URL) 노출
- 점수 없는 v1 경로는 게이트 미적용(회귀 방지)

framework-free. 실행: python3 hrms/tests/test_korea_ai_chat_factcheck.py
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


_fc = _load("ai_chat_factcheck")
_chat = _load("ai_chat")

has_scores = _fc.has_scores
top_confidence = _fc.top_confidence
harness_fallback_answer = _fc.harness_fallback_answer
build_verification_footer = _fc.build_verification_footer
evaluate = _fc.evaluate
chat_query = _chat.chat_query


class TestConfidence(unittest.TestCase):
    def test_top_confidence_is_max_score(self):
        docs = [{"score": 0.3}, {"score": 0.72}, {"score": 0.5}]
        self.assertAlmostEqual(top_confidence(docs), 0.72)

    def test_has_scores_false_for_v1_docs(self):
        self.assertFalse(has_scores([{"law": "근기법", "text": "x"}]))
        self.assertTrue(has_scores([{"score": 0.1}]))

    def test_evaluate_grounded_above_threshold(self):
        v = evaluate([{"score": 0.6}], threshold=0.4)
        self.assertTrue(v["applicable"])
        self.assertTrue(v["grounded"])

    def test_evaluate_not_grounded_below_threshold(self):
        v = evaluate([{"score": 0.25}], threshold=0.4)
        self.assertTrue(v["applicable"])
        self.assertFalse(v["grounded"])

    def test_evaluate_not_applicable_for_v1(self):
        v = evaluate([{"law": "근기법", "text": "x"}], threshold=0.4)
        self.assertFalse(v["applicable"])  # 점수 없으면 게이트 미적용


class TestFallbackAndFooter(unittest.TestCase):
    def test_fallback_recommends_nomusa(self):
        msg = harness_fallback_answer("부당해고 맞나요?")
        self.assertIn("노무사", msg)

    def test_verification_footer_lists_refs_and_urls(self):
        docs = [{"law": "행정해석", "title": "주휴수당", "ref_code": "근기68207-216",
                 "url": "http://a"}]
        foot = build_verification_footer(docs)
        self.assertIn("근기68207-216", foot)
        self.assertIn("http://a", foot)

    def test_footer_empty_when_no_verifiable_refs(self):
        self.assertEqual(build_verification_footer([{"law": "x", "title": "y"}]), "")


class TestChatQueryFactcheckGate(unittest.TestCase):
    def test_low_confidence_routes_to_human(self):
        def weak_retriever(query, top_k):
            return [{"law": "행정해석", "title": "관련 낮음", "text": "…",
                     "type": "law", "score": 0.15, "ref_code": "x", "url": None}]

        r = chat_query(user_question="이거 부당해고?", user_role="worker",
                       session_id="f1", retriever=weak_retriever)
        self.assertTrue(r["requires_human_consult"])
        self.assertIn("노무사", r["answer"])

    def test_high_confidence_answers_with_verification_footer(self):
        def strong_retriever(query, top_k):
            return [{"law": "행정해석", "title": "주휴수당 산정 [근기68207-216]",
                     "text": "회시: 주휴수당은 1주 15시간 이상+개근 시 발생한다.",
                     "type": "law", "score": 0.83, "ref_code": "근기68207-216",
                     "url": "http://moel/1"}]

        r = chat_query(user_question="주휴수당 요건?", user_role="hr_manager",
                       session_id="f2", retriever=strong_retriever)
        self.assertFalse(r["requires_human_consult"])
        self.assertIn("주휴수당은", r["answer"])
        self.assertIn("http://moel/1", r["answer"])  # 검증 근거 노출

    def test_v1_path_unaffected_no_gate(self):
        r = chat_query(user_question="연차휴가 며칠?", user_role="hr_manager",
                       session_id="f3")
        # 점수 없는 v1 → 게이트 미적용, 사람연결 강제 안 함
        self.assertFalse(r["requires_human_consult"])
        self.assertTrue(r["answer"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
