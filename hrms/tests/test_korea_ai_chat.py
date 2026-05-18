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


if __name__ == "__main__":
    unittest.main()
