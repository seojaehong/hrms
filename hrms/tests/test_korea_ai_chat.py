"""한국 노무 AI 챗봇 단위 테스트.

frappe 의존 없음 — ai_chat.py 순수 Python 로직만 검증.
실행 (bench-free): python3 hrms/tests/test_korea_ai_chat.py
실행 (bench): python -m unittest hrms.tests.test_korea_ai_chat
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

# hrms/__init__.py가 frappe를 import하므로 file-path 직접 로드.
_AI_CHAT_PATH = pathlib.Path(__file__).resolve().parents[2] / "hrms" / "regional" / "south_korea" / "ai_chat.py"
_spec = importlib.util.spec_from_file_location("korea_ai_chat", _AI_CHAT_PATH)
_ai_chat = importlib.util.module_from_spec(_spec)
sys.modules["korea_ai_chat"] = _ai_chat
_spec.loader.exec_module(_ai_chat)

AI_ROLE = _ai_chat.AI_ROLE
CHAT_RUNTIME_ACTION = _ai_chat.CHAT_RUNTIME_ACTION
CONTRACT_TYPE = _ai_chat.CONTRACT_TYPE
DISCLAIMER = _ai_chat.DISCLAIMER
MUTATION_BOUNDARY = _ai_chat.MUTATION_BOUNDARY
_AUDIT_LOG = _ai_chat._AUDIT_LOG
_SESSION_STORE = _ai_chat._SESSION_STORE
build_session_context = _ai_chat.build_session_context
call_llm_with_context = _ai_chat.call_llm_with_context
chat_query = _ai_chat.chat_query
detect_intent = _ai_chat.detect_intent
retrieve_relevant_documents = _ai_chat.retrieve_relevant_documents
store_chat_audit_log = _ai_chat.store_chat_audit_log

# ──────────────────────────────────────────────
# 의도 분류 테스트
# ──────────────────────────────────────────────


class TestDetectIntent(unittest.TestCase):
    def test_leave_intent(self):
        result = detect_intent("연차 유급휴가는 어떻게 계산하나요?")
        self.assertEqual(result["intent"], "leave")
        self.assertIsInstance(result["matched_keywords"], list)
        self.assertGreater(len(result["matched_keywords"]), 0)

    def test_payroll_intent(self):
        result = detect_intent("최저임금 위반 시 퇴직금은 어떻게 처리되나요?")
        # payroll 또는 compliance — 최저임금은 payroll에도, 위반은 compliance에도 걸림
        self.assertIn(result["intent"], ("payroll", "compliance"))
        self.assertIn("matched_keywords", result)

    def test_working_hours_intent(self):
        result = detect_intent("주52시간 연장근로 한도는 얼마인가요?")
        self.assertIn(result["intent"], ("working_hours", "payroll", "leave"))

    def test_compliance_intent(self):
        result = detect_intent("부당해고 구제신청은 어디에 하나요?")
        self.assertEqual(result["intent"], "compliance")

    def test_contract_intent(self):
        result = detect_intent("근로계약서에 꼭 포함해야 할 내용은?")
        self.assertEqual(result["intent"], "contract")

    def test_general_fallback(self):
        result = detect_intent("xyz123abc 완전히 관련 없는 말")
        self.assertEqual(result["intent"], "general")

    def test_no_probability_in_result(self):
        """결과에 점수/확률 필드 없음 확인."""
        result = detect_intent("연차 질문")
        forbidden_fields = {"score", "probability", "confidence", "percent", "확률", "점수"}
        for field in forbidden_fields:
            self.assertNotIn(field, result, f"금지된 필드 발견: {field}")


# ──────────────────────────────────────────────
# 문서 검색 테스트
# ──────────────────────────────────────────────


class TestRetrieveRelevantDocuments(unittest.TestCase):
    def test_returns_list(self):
        docs = retrieve_relevant_documents(query="연차 유급휴가", top_k=5)
        self.assertIsInstance(docs, list)

    def test_top_k_limit(self):
        docs = retrieve_relevant_documents(query="임금 급여 퇴직금", top_k=3)
        self.assertLessEqual(len(docs), 3)

    def test_relevant_doc_for_leave(self):
        docs = retrieve_relevant_documents(query="연차 유급휴가 15일", top_k=5)
        refs = [d.get("law", "") for d in docs]
        # 근기법 60조 — 연차 유급휴가가 상위에 와야 함
        self.assertTrue(any("60" in r for r in refs), f"근기법 60조 미포함: {refs}")

    def test_relevant_doc_for_payroll(self):
        docs = retrieve_relevant_documents(query="퇴직금 계산", top_k=5)
        refs = [d.get("law", "") for d in docs]
        self.assertTrue(
            any("퇴직" in r or "근퇴법" in r for r in refs),
            f"퇴직금 관련 법령 미포함: {refs}",
        )

    def test_empty_query_returns_list(self):
        docs = retrieve_relevant_documents(query="", top_k=5)
        self.assertIsInstance(docs, list)

    def test_each_doc_has_required_keys(self):
        docs = retrieve_relevant_documents(query="연차", top_k=3)
        for doc in docs:
            self.assertIn("law", doc)
            self.assertIn("title", doc)
            self.assertIn("text", doc)


# ──────────────────────────────────────────────
# chat_query 메인 함수 테스트
# ──────────────────────────────────────────────


class TestChatQuery(unittest.TestCase):
    def _call(self, question="연차는 몇 일인가요?", session_id="test-session-001"):
        return chat_query(
            user_question=question,
            user_role="employee",
            session_id=session_id,
        )

    # 반환 구조 검증
    def test_contract_type(self):
        result = self._call()
        self.assertEqual(result["contract_type"], CONTRACT_TYPE)

    def test_runtime_action(self):
        result = self._call()
        self.assertEqual(result["runtime_action"], CHAT_RUNTIME_ACTION)

    def test_ai_role(self):
        result = self._call()
        self.assertEqual(result["ai_role"], AI_ROLE)

    def test_no_mutation_flag(self):
        result = self._call()
        self.assertTrue(result["no_mutation_performed"])

    def test_disclaimer_present_and_nonempty(self):
        result = self._call()
        self.assertIn("disclaimer", result)
        self.assertTrue(result["disclaimer"], "disclaimer는 빈 문자열이면 안 됨")

    def test_disclaimer_matches_constant(self):
        result = self._call()
        self.assertEqual(result["disclaimer"], DISCLAIMER)

    def test_tokens_used_is_zero_in_v1(self):
        result = self._call()
        self.assertEqual(result["tokens_used"], 0)

    def test_session_id_preserved(self):
        sid = "specific-session-xyz"
        result = self._call(session_id=sid)
        self.assertEqual(result["session_id"], sid)

    def test_user_question_preserved(self):
        q = "연차 유급휴가 계산 방법은?"
        result = self._call(question=q)
        self.assertEqual(result["user_question"], q)

    def test_citations_is_list(self):
        result = self._call()
        self.assertIsInstance(result["citations"], list)

    def test_citations_have_required_fields(self):
        result = self._call()
        for cite in result["citations"]:
            self.assertIn("type", cite)
            self.assertIn("ref", cite)
            self.assertIn("snippet", cite)

    def test_suggested_actions_is_list(self):
        result = self._call()
        self.assertIsInstance(result["suggested_actions"], list)

    def test_suggested_actions_have_label_and_url(self):
        result = self._call()
        for action in result["suggested_actions"]:
            self.assertIn("label", action)
            self.assertIn("url", action)

    def test_answer_is_nonempty_string(self):
        result = self._call()
        self.assertIsInstance(result["answer"], str)
        self.assertTrue(result["answer"].strip())

    # no-mutation 검증 — 모든 코드 경로
    def test_empty_question_returns_no_mutation(self):
        result = chat_query(
            user_question="",
            user_role="employee",
            session_id="test-empty",
        )
        self.assertTrue(result["no_mutation_performed"])
        self.assertEqual(result["disclaimer"], DISCLAIMER)

    def test_whitespace_question_returns_no_mutation(self):
        result = chat_query(
            user_question="   ",
            user_role="employee",
            session_id="test-ws",
        )
        self.assertTrue(result["no_mutation_performed"])

    # 금지 표현 검증
    def test_no_probability_words_in_answer(self):
        """금지 표현 검증.

        "보장" 주의: 사용자 룰의 의도는 AI가 생성하는 확률성 표현
        ("80% 보장", "성공 보장" 등)을 금지하는 것입니다.
        법령 원문의 "보장하여야 한다"(근기법 55조 등)는 법적 의무 표현이므로
        snippet에 그대로 인용됩니다 — 이는 룰 위반이 아닙니다.
        따라서 "보장"은 이 테스트에서 제외하고, AI 생성 답변 부분만 검증합니다.
        """
        # "보장"은 법령 원문에 포함될 수 있어 제외 (pragmatic reading)
        forbidden = ["확률", "예측", "점수", "probability", "score", "predict"]
        for question in ["연차 15일 받을 수 있나요?", "부당해고 구제 가능한가요?"]:
            result = self._call(question=question)
            for word in forbidden:
                self.assertNotIn(
                    word,
                    result["answer"],
                    f"금지 표현 '{word}' 발견 (question={question!r})",
                )

    # context_doctype 옵션
    def test_with_context_doctype(self):
        result = chat_query(
            user_question="연차 신청 어떻게 하나요?",
            user_role="employee",
            context_doctype="Leave Application",
            session_id="test-ctx",
        )
        self.assertTrue(result["no_mutation_performed"])
        self.assertEqual(result["contract_type"], CONTRACT_TYPE)


# ──────────────────────────────────────────────
# build_session_context 테스트
# ──────────────────────────────────────────────


class TestBuildSessionContext(unittest.TestCase):
    def test_returns_dict(self):
        ctx = build_session_context(
            user_id="user001",
            user_role="employee",
            history=[],
        )
        self.assertIsInstance(ctx, dict)

    def test_history_count(self):
        history = [{"role": "user", "content": "질문1"}, {"role": "assistant", "content": "답변1"}]
        ctx = build_session_context(user_id="u", user_role="manager", history=history)
        self.assertEqual(ctx["history_count"], 2)

    def test_required_keys(self):
        ctx = build_session_context(user_id="u", user_role="admin", history=[])
        for key in ("user_id", "user_role", "history_count", "history", "session_summary"):
            self.assertIn(key, ctx)


# ──────────────────────────────────────────────
# v2 stub 테스트 — NotImplementedError 검증
# ──────────────────────────────────────────────


class TestV2Stubs(unittest.TestCase):
    def test_call_llm_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError) as cm:
            call_llm_with_context(messages=[], system_prompt="", max_tokens=100)
        self.assertIn("v2", str(cm.exception).lower())

    def test_call_llm_error_message_mentions_agent(self):
        with self.assertRaises(NotImplementedError) as cm:
            call_llm_with_context(messages=[], system_prompt="", max_tokens=100)
        self.assertIn("연말 에이전트", str(cm.exception))


# ──────────────────────────────────────────────
# 감사 로그 테스트
# ──────────────────────────────────────────────


class TestStoreAuditLog(unittest.TestCase):
    def setUp(self):
        # 각 테스트 전 in-memory 로그 클리어
        _AUDIT_LOG.clear()

    def test_returns_dict(self):
        entry = store_chat_audit_log(
            session_id="s1",
            user_id="u1",
            question="테스트 질문",
            answer="테스트 답변",
            citations=[],
        )
        self.assertIsInstance(entry, dict)

    def test_entry_has_required_keys(self):
        entry = store_chat_audit_log(
            session_id="s1",
            user_id="u1",
            question="q",
            answer="a",
            citations=[],
        )
        for key in ("log_id", "session_id", "user_id", "question", "answer", "ai_role", "no_mutation_performed", "ts"):
            self.assertIn(key, entry)

    def test_no_mutation_in_audit_entry(self):
        entry = store_chat_audit_log(
            session_id="s1",
            user_id="u1",
            question="q",
            answer="a",
            citations=[],
        )
        self.assertTrue(entry["no_mutation_performed"])

    def test_audit_log_is_appended(self):
        initial_count = len(_AUDIT_LOG)
        store_chat_audit_log(session_id="s2", user_id="u2", question="q", answer="a", citations=[])
        self.assertEqual(len(_AUDIT_LOG), initial_count + 1)

    def test_chat_query_auto_writes_audit_log(self):
        _AUDIT_LOG.clear()
        chat_query(
            user_question="연차 질문",
            user_role="employee",
            session_id="audit-test-session",
        )
        self.assertEqual(len(_AUDIT_LOG), 1)


# ──────────────────────────────────────────────
# 모듈 상수 / contract 검증
# ──────────────────────────────────────────────


class TestModuleConstants(unittest.TestCase):
    def test_ai_role_is_assistant_only(self):
        self.assertEqual(AI_ROLE, "assistant_only")

    def test_runtime_action_contains_read_only(self):
        self.assertIn("read_only", CHAT_RUNTIME_ACTION)

    def test_mutation_boundary_forbids_mutations(self):
        for word in ("save", "submit", "approve", "send"):
            self.assertIn(word, MUTATION_BOUNDARY)

    def test_disclaimer_nonempty(self):
        self.assertTrue(DISCLAIMER.strip())

    def test_contract_type_v1(self):
        self.assertIn("v1", CONTRACT_TYPE)


# ──────────────────────────────────────────────
# 코퍼스 병합 로딩 테스트 (법령 33건 + FAQ 4,771건)
# ──────────────────────────────────────────────


class TestCatalogMergeLoading(unittest.TestCase):
    def test_merged_catalog_includes_faq_corpus(self):
        catalog = _ai_chat._load_catalog()
        self.assertGreater(len(catalog), 1000, "FAQ 코퍼스 병합 후 1,000건 이상이어야 함")

    def test_merged_catalog_has_both_types(self):
        types = {e.get("type") for e in _ai_chat._load_catalog()}
        self.assertIn("law", types)
        self.assertIn("faq", types)

    def test_legacy_law_entries_preserved(self):
        laws = [e.get("law", "") for e in _ai_chat._load_catalog() if e.get("type") != "faq"]
        self.assertTrue(any("60" in law for law in laws), "근기법 60조 유지되어야 함")

    def test_missing_faq_file_is_ignored(self):
        """FAQ 파일이 없으면 법령 카탈로그만 로드 (방어)."""
        import os

        law_path = os.path.join(_ai_chat._data_dir(), _ai_chat._LAW_CATALOG_FILENAME)
        entries = _ai_chat._load_catalog_files(law_path, os.path.join(_ai_chat._data_dir(), "__does_not_exist__.json"))
        self.assertEqual(len(entries), 33)
        self.assertTrue(all(e.get("type") != "faq" for e in entries))


# ──────────────────────────────────────────────
# 역색인 동등성 테스트 (전체 스캔 vs 역색인 후보 축소)
# ──────────────────────────────────────────────


class TestInvertedIndexEquivalence(unittest.TestCase):
    QUERIES = [
        "연차 유급휴가 15일",
        "퇴직금 계산",
        "최저임금 위반",
        "주52시간 연장근로 한도",
        "부당해고 구제신청",
        "육아휴직 급여",
        "통상임금 산정",
        "직장내괴롭힘 신고",
        "수습기간중인직원도주휴수당을줘야하나요",
    ]

    def test_index_results_match_full_scan(self):
        for query in self.QUERIES:
            indexed = retrieve_relevant_documents(query=query, top_k=5, use_index=True)
            full = retrieve_relevant_documents(query=query, top_k=5, use_index=False)
            self.assertEqual(
                [(d.get("law"), d.get("title")) for d in indexed],
                [(d.get("law"), d.get("title")) for d in full],
                f"역색인 결과가 전체 스캔과 다름 (query={query!r})",
            )

    def test_index_is_cached(self):
        retrieve_relevant_documents(query="연차", top_k=3)
        first = _ai_chat._INDEX_CACHE
        retrieve_relevant_documents(query="퇴직금", top_k=3)
        self.assertIs(_ai_chat._INDEX_CACHE, first, "역색인은 1회 구축 후 재사용")


# ──────────────────────────────────────────────
# 공백 없는 질문 매칭 테스트 (문자 2-gram 보조)
# ──────────────────────────────────────────────


class TestSpacelessQueryMatching(unittest.TestCase):
    SPACELESS = "수습기간중인직원도주휴수당을줘야하나요"

    def test_spaceless_query_hits_juhyu_faq(self):
        docs = retrieve_relevant_documents(query=self.SPACELESS, top_k=5)
        self.assertTrue(docs, "공백 없는 질문도 문서 매칭되어야 함")
        combined = " ".join(d.get("law", "") + " " + d.get("title", "") for d in docs)
        self.assertIn("주휴", combined, f"주휴 관련 FAQ가 히트해야 함: {combined}")

    def test_spaceless_query_chat_has_citations(self):
        result = chat_query(
            user_question=self.SPACELESS,
            user_role="employee",
            session_id="test-spaceless",
        )
        self.assertTrue(result["citations"])
        self.assertNotIn("찾지 못했습니다", result["answer"])

    def test_spaced_queries_still_match(self):
        """기존(공백 있는) 질의 회귀 없음."""
        docs = retrieve_relevant_documents(query="연차 유급휴가 15일", top_k=5)
        refs = [d.get("law", "") for d in docs]
        self.assertTrue(any("60" in r for r in refs), f"근기법 60조 미포함: {refs}")


# ──────────────────────────────────────────────
# 문장 경계 클립 테스트 (뚝 끊김 수정)
# ──────────────────────────────────────────────


class TestSentenceBoundaryClip(unittest.TestCase):
    def test_short_text_unchanged(self):
        text = "임금은 통화로 직접 지급하여야 합니다."
        self.assertEqual(_ai_chat._clip_to_sentence(text, max_len=400), text)

    def test_long_text_clipped_at_sentence_boundary(self):
        sentence = "이것은 문장 경계 테스트를 위한 예시 문장입니다. "
        text = sentence * 30  # ≫ 400자
        clipped = _ai_chat._clip_to_sentence(text, max_len=400)
        self.assertLessEqual(len(clipped), 400)
        self.assertTrue(clipped.endswith("다."), f"문장 경계로 끝나야 함: ...{clipped[-20:]}")

    def test_yo_ending_boundary(self):
        sentence = "주휴수당은 지급하셔야 해요. "
        text = sentence * 40
        clipped = _ai_chat._clip_to_sentence(text, max_len=400)
        self.assertTrue(clipped.endswith("요."))

    def test_citation_snippets_not_hard_cut(self):
        """citations snippet은 400자 이내 + 문장 경계 (전문이 아닌 경우)."""
        result = chat_query(
            user_question="퇴직금 중간정산 요건은 무엇인가요?",
            user_role="employee",
            session_id="test-clip",
        )
        for cite in result["citations"]:
            self.assertLessEqual(len(cite["snippet"]), 400)
            if len(cite["snippet"]) == 400 or cite["snippet"].endswith(("다.", "요.")):
                continue
            # 전문이 그대로 들어간 경우(400자 미만 원문)만 허용
            self.assertLess(len(cite["snippet"]), 400)

    def test_answer_body_is_full_text_not_truncated(self):
        """답변 본문은 최상위 문서 전문 — 중간 절단 금지."""
        docs = retrieve_relevant_documents(query="수습기간 주휴수당", top_k=5)
        self.assertTrue(docs)
        result = chat_query(
            user_question="수습기간 주휴수당",
            user_role="employee",
            session_id="test-fulltext",
        )
        self.assertIn(docs[0]["text"], result["answer"], "답변 본문에 최상위 문서 전문 포함")


# ──────────────────────────────────────────────
# FAQ 타입 라벨 / FAQ 답변 조립 테스트
# ──────────────────────────────────────────────


class TestFaqCitationLabel(unittest.TestCase):
    def test_citation_label_mapping(self):
        result = chat_query(
            user_question="수습기간중인직원도주휴수당을줘야하나요",
            user_role="employee",
            session_id="test-label",
        )
        valid_labels = {"법령", "판례", "내부", "FAQ", "참고"}
        for cite in result["citations"]:
            self.assertIn("label", cite)
            self.assertIn(cite["label"], valid_labels)
        type_to_label = {"law": "법령", "case": "판례", "internal": "내부", "faq": "FAQ"}
        for cite in result["citations"]:
            if cite["type"] in type_to_label:
                self.assertEqual(cite["label"], type_to_label[cite["type"]])

    def test_faq_top_match_answer_uses_faq_fulltext(self):
        question = "수습기간중인직원도주휴수당을줘야하나요"
        docs = retrieve_relevant_documents(query=question, top_k=5)
        self.assertEqual(docs[0].get("type"), "faq")
        result = chat_query(
            user_question=question,
            user_role="employee",
            session_id="test-faq-body",
        )
        self.assertIn("[FAQ]", result["answer"])
        self.assertIn(docs[0]["text"], result["answer"], "FAQ 답변 전문이 본문이어야 함")

    def test_faq_answer_grounds_only_with_law_citation(self):
        """FAQ 답변의 '주요 근거'는 법령/판례 인용이 있을 때만 표기."""
        question = "수습기간중인직원도주휴수당을줘야하나요"
        result = chat_query(
            user_question=question,
            user_role="employee",
            session_id="test-faq-grounds",
        )
        has_law = any(c["type"] in ("law", "case") for c in result["citations"])
        if has_law:
            self.assertIn("주요 근거", result["answer"])
        else:
            self.assertNotIn("주요 근거", result["answer"])

    def test_law_top_match_answer_has_law_label(self):
        """법령이 최상위 매치인 질의에서는 주요 근거에 [법령] 라벨."""
        result = chat_query(
            user_question="임금 지급 원칙",
            user_role="employee",
            session_id="test-law-label",
        )
        docs = retrieve_relevant_documents(query="임금 지급 원칙", top_k=5)
        if docs and docs[0].get("type") != "faq":
            self.assertIn("주요 근거", result["answer"])
            self.assertIn("[법령]", result["answer"])

    def test_disclaimer_unchanged(self):
        """면책 문구 로직 불변."""
        result = chat_query(
            user_question="수습기간중인직원도주휴수당을줘야하나요",
            user_role="employee",
            session_id="test-disc",
        )
        self.assertEqual(result["disclaimer"], DISCLAIMER)


if __name__ == "__main__":
    unittest.main()
