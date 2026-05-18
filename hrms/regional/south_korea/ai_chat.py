"""한국 HR/노동법 AI 챗봇 entry point (assistant_only).

v1: stub interface + retrieval simulation (keyword matching).
v2 (연말): 실제 LLM (Claude/GPT) + vector DB (Pinecone/pgvector) 연동.

설계 원칙:
- AI 역할은 assistant_only — DB/문서 mutation 절대 X
- 점수/확률/예측 수치 출력 X
- 모든 답변에 법령/판례/내부 문서 인용 (RAG citation) 필수
- 면책 문구 모든 답변에 포함
- v2 함수는 NotImplementedError로 명시적 표시
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from typing import Any

# ──────────────────────────────────────────────
# 모듈 상수 — contract / boundary 식별자
# ──────────────────────────────────────────────
CHAT_RUNTIME_ACTION = "ai_chat_assistant_only_read_only"
MUTATION_BOUNDARY = "no_save_submit_approve_send_provider_call_only_read_only_retrieval"
AI_ROLE = "assistant_only"
CONTRACT_TYPE = "korea_hr_ai_chat_response_v1"

DISCLAIMER = (
    "이 답변은 AI 보조 정보입니다. 실제 결정은 반드시 담당자 또는 공인노무사의 검토를 거쳐 주세요. "
    "본 챗봇은 법률 자문이 아니며, 개별 사안에 따라 결과가 달라질 수 있습니다."
)

# ──────────────────────────────────────────────
# 의도(intent) 키워드 매핑 (v1 휴리스틱)
# ──────────────────────────────────────────────
INTENT_KEYWORD_MAP: dict[str, list[str]] = {
    "leave": [
        "연차", "휴가", "연차유급휴가", "반차", "병가", "출산휴가", "육아휴직",
        "생리휴가", "공가", "휴일", "법정휴일", "대체휴무", "Leave",
    ],
    "payroll": [
        "급여", "임금", "월급", "통상임금", "최저임금", "연봉", "상여금", "수당",
        "가산임금", "시간외수당", "야간수당", "휴일수당", "퇴직금", "퇴직급여",
        "4대보험", "건강보험", "고용보험", "국민연금", "산재보험", "소득세",
        "연말정산", "원천징수", "Payroll",
    ],
    "contract": [
        "근로계약", "계약서", "취업규칙", "정규직", "비정규직", "계약직",
        "기간제", "단시간근로", "파견근로", "하청", "도급", "용역", "Contract",
    ],
    "compliance": [
        "위반", "처벌", "과태료", "시정명령", "근로감독", "고용노동부",
        "신고", "진정", "소청", "부당해고", "해고", "징계", "직장내괴롭힘",
        "성희롱", "산업재해", "산재", "중대재해", "Compliance",
    ],
    "working_hours": [
        "근로시간", "소정근로시간", "주52시간", "연장근로", "야간근로",
        "휴게시간", "탄력근무", "선택근무", "재량근무", "교대근무",
    ],
    "general": [],  # fallback
}

# ──────────────────────────────────────────────
# 인메모리 세션 / 감사 로그 저장소 (v1)
# v2에서는 DB/vector store로 교체
# ──────────────────────────────────────────────
_SESSION_STORE: dict[str, dict] = {}
_AUDIT_LOG: list[dict] = []

# ──────────────────────────────────────────────
# 카탈로그 로더
# ──────────────────────────────────────────────
_CATALOG_CACHE: list[dict] | None = None


def _load_catalog() -> list[dict]:
    """한국 노동법 카탈로그 JSON을 로드하여 캐시합니다."""
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE

    catalog_path = os.path.join(
        os.path.dirname(__file__), "data", "korea_labor_law_catalog.json"
    )
    with open(catalog_path, encoding="utf-8") as f:
        _CATALOG_CACHE = json.load(f)
    return _CATALOG_CACHE


# ──────────────────────────────────────────────
# 퍼블릭 API
# ──────────────────────────────────────────────


def chat_query(
    *,
    user_question: str,
    user_role: str,
    context_doctype: str | None = None,
    context_doc_name: str | None = None,
    session_id: str,
) -> dict:
    """사용자 질문 → 한국 노동법/HRMS 모듈 retrieval + 답변.

    답변 구조:
    - 직접 답변 (1-2 문장)
    - 근거 인용 (법령 조문 / 판례 / 내부 문서)
    - 관련 모듈 링크 (예: "연차 신청 → /hrms/leave-application/new")
    - 면책 ("이 답변은 AI 보조이며, 실제 결정은 담당자/노무사 검토 필수")

    절대 mutation X — 모든 액션 링크는 사용자 직접 클릭.

    Returns:
        {
            "contract_type": "korea_hr_ai_chat_response_v1",
            "runtime_action": "ai_chat_assistant_only_read_only",
            "session_id": str,
            "user_question": str,
            "answer": str,
            "citations": [
                {"type": "law", "ref": "근기법 60조", "snippet": "..."},
                {"type": "case", "ref": "대법 2020다123", "snippet": "..."},
                {"type": "internal", "ref": "hrms/regional/south_korea/...", "snippet": "..."},
            ],
            "suggested_actions": [
                {"label": "연차 신청", "url": "/hrms/leave-application/new"},
                ...
            ],
            "disclaimer": str,
            "ai_role": "assistant_only",
            "no_mutation_performed": True,
            "tokens_used": int,  # v1은 0 (no LLM)
        }
    """
    if not user_question or not user_question.strip():
        return _error_response(
            session_id=session_id,
            user_question=user_question or "",
            message="질문을 입력해 주세요.",
        )

    intent_result = detect_intent(user_question)
    intent = intent_result["intent"]

    docs = retrieve_relevant_documents(query=user_question, top_k=5)
    citations = _docs_to_citations(docs)

    answer = _build_answer(
        intent=intent,
        question=user_question,
        citations=citations,
        context_doctype=context_doctype,
        user_role=user_role,
    )

    suggested_actions = _build_suggested_actions(
        intent=intent,
        context_doctype=context_doctype,
    )

    # 세션 컨텍스트 갱신
    session_ctx = _SESSION_STORE.get(session_id, {"history": []})
    session_ctx["history"].append({
        "role": "user",
        "content": user_question,
        "ts": datetime.utcnow().isoformat(),
    })
    session_ctx["history"].append({
        "role": "assistant",
        "content": answer,
        "ts": datetime.utcnow().isoformat(),
    })
    _SESSION_STORE[session_id] = session_ctx

    response: dict[str, Any] = {
        "contract_type": CONTRACT_TYPE,
        "runtime_action": CHAT_RUNTIME_ACTION,
        "session_id": session_id,
        "user_question": user_question,
        "answer": answer,
        "citations": citations,
        "suggested_actions": suggested_actions,
        "disclaimer": DISCLAIMER,
        "ai_role": AI_ROLE,
        "no_mutation_performed": True,
        "tokens_used": 0,  # v1: no LLM call
    }

    # 감사 로그 기록 (v1 인메모리)
    store_chat_audit_log(
        session_id=session_id,
        user_id=user_role,
        question=user_question,
        answer=answer,
        citations=citations,
    )

    return response


def retrieve_relevant_documents(
    *,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """관련 법령/판례/내부 문서 retrieval.

    v1 stub: 키워드 매칭 (한국 노동법 카탈로그에서).
    v2: vector embedding similarity 검색으로 교체 예정.

    Returns:
        list of catalog entries matching query keywords.
        Each entry: {"law": str, "title": str, "text": str, "tags": list[str]}
    """
    query_lower = query.lower()
    catalog = _load_catalog()

    scored: list[tuple[int, dict]] = []
    for entry in catalog:
        score = 0
        # title/law 매칭 가중치 2, text 매칭 가중치 1
        combined_title = (entry.get("law", "") + " " + entry.get("title", "")).lower()
        for token in _tokenize(query_lower):
            if token in combined_title:
                score += 2
            if token in entry.get("text", "").lower():
                score += 1
            for tag in entry.get("tags", []):
                if token in tag.lower():
                    score += 1
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:top_k]]


def build_session_context(
    *,
    user_id: str,
    user_role: str,
    history: list[dict],
) -> dict:
    """세션 컨텍스트 (대화 흐름).

    Returns:
        {
            "user_id": str,
            "user_role": str,
            "history_count": int,
            "history": list[dict],
            "session_summary": str,
        }
    """
    return {
        "user_id": user_id,
        "user_role": user_role,
        "history_count": len(history),
        "history": history,
        "session_summary": f"대화 {len(history)}턴 기록됨 (user_role={user_role})",
    }


def detect_intent(question: str) -> dict:
    """의도 분류 — leave / payroll / contract / compliance / working_hours / general.

    v1: 키워드 휴리스틱 (점수/확률 출력 X).
    v2: NLU 모델 교체 예정.

    Returns:
        {
            "intent": str,           # e.g. "leave"
            "matched_keywords": list[str],  # 매칭된 키워드 (점수 X)
        }
    """
    question_lower = question.lower()
    tokens = _tokenize(question_lower)

    best_intent = "general"
    best_count = 0
    best_matched: list[str] = []

    for intent, keywords in INTENT_KEYWORD_MAP.items():
        if intent == "general":
            continue
        matched = [kw for kw in keywords if kw in question_lower or kw.lower() in tokens]
        if len(matched) > best_count:
            best_count = len(matched)
            best_intent = intent
            best_matched = matched

    return {
        "intent": best_intent,
        "matched_keywords": best_matched,
    }


# ──────────────────────────────────────────────
# v2 stubs — 연말 LLM 연동 시 구현
# ──────────────────────────────────────────────


def call_llm_with_context(
    messages: list[dict],
    system_prompt: str,
    max_tokens: int,
) -> dict:
    """v2: 실제 LLM 호출 (Claude/GPT).

    현재는 NotImplementedError — 연말 에이전트 단계에서 구현.
    """
    raise NotImplementedError("LLM integration is v2 (연말 에이전트)")


def _mask_pii_in_text(text: str) -> str:
    """감사 로그 저장 전 텍스트 내 PII 마스킹.

    적용 순서:
    1. 주민등록번호 (6자리-7자리) → 앞부분-1******
    2. 휴대폰 번호 (010/011/016/017/018/019 포함) → 010-****-5678
    3. 이메일 → a**@domain

    citations (법령 조문)은 이 함수를 통과하지 않으므로 별도 호출 없음.
    """
    if not text:
        return text

    # 주민등록번호: NNNNNN-NNNNNNN 또는 NNNNNNNNNNNNN (13자리 연속)
    text = re.sub(
        r"\b(\d{6})-(\d{7})\b",
        lambda m: f"{m.group(1)}-{m.group(2)[0]}{'*' * 6}",
        text,
    )
    text = re.sub(
        r"\b(\d{6})(\d{7})\b",
        lambda m: f"{m.group(1)}{m.group(2)[0]}{'*' * 6}",
        text,
    )

    # 휴대폰: 010-NNNN-NNNN / 01012345678 / 010 1234 5678
    text = re.sub(
        r"\b(01[016789])[-\s]?(\d{3,4})[-\s]?(\d{4})\b",
        lambda m: f"{m.group(1)}-{'*' * len(m.group(2))}-{m.group(3)}",
        text,
    )

    # 이메일
    text = re.sub(
        r"\b([A-Za-z0-9._%+\-]{2,})(@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b",
        lambda m: f"{m.group(1)[0]}{'*' * (len(m.group(1)) - 1)}{m.group(2)}",
        text,
    )

    return text


def store_chat_audit_log(
    session_id: str,
    user_id: str,
    question: str,
    answer: str,
    citations: list[dict],
) -> dict:
    """감사 로그 기록 — AI 답변은 모두 기록 (책임 추적).

    v1: 인메모리 리스트에 append.
    v2: Frappe DB / audit 테이블로 영구 저장.

    # TODO v2: frappe.get_doc("Korea AI Chat Log").insert()

    PII 보호: question/answer 저장 시 전화번호·주민번호·이메일을 마스킹합니다.
    citations는 법령 조문이므로 마스킹하지 않습니다.
    """
    entry = {
        "log_id": str(uuid.uuid4()),
        "session_id": session_id,
        "user_id": user_id,
        "question": _mask_pii_in_text(question),
        "answer": _mask_pii_in_text(answer),
        "citations": citations,
        "ai_role": AI_ROLE,
        "no_mutation_performed": True,
        "ts": datetime.utcnow().isoformat(),
    }
    _AUDIT_LOG.append(entry)
    return entry


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────


def _tokenize(text: str) -> list[str]:
    """단순 공백/구두점 기반 토크나이저 (v1)."""
    import re
    return re.split(r"[\s,\.?!;:\"'()]+", text)


def _docs_to_citations(docs: list[dict]) -> list[dict]:
    """카탈로그 엔트리 → citation 형식 변환."""
    citations: list[dict] = []
    for doc in docs:
        ref = f"{doc.get('law', '')} — {doc.get('title', '')}"
        snippet = doc.get("text", "")[:200]
        citations.append({
            "type": doc.get("type", "law"),
            "ref": ref.strip(" —"),
            "snippet": snippet,
        })
    return citations


def _build_answer(
    *,
    intent: str,
    question: str,
    citations: list[dict],
    context_doctype: str | None,
    user_role: str,
) -> str:
    """v1 답변 생성 (템플릿 기반, LLM X).

    인용 법령을 근거로 한 사실 안내문. 점수/확률 표현 없음.
    """
    if not citations:
        return (
            f"'{question}'에 해당하는 법령/판례를 찾지 못했습니다. "
            "보다 구체적인 키워드로 다시 질문하시거나, 담당 노무사에게 문의해 주세요."
        )

    primary = citations[0]
    ref_list = " / ".join(c["ref"] for c in citations[:3])

    intent_label_map = {
        "leave": "휴가·휴직",
        "payroll": "급여·임금",
        "contract": "근로계약",
        "compliance": "법령 준수·제재",
        "working_hours": "근로시간",
        "general": "HR 일반",
    }
    label = intent_label_map.get(intent, "HR 일반")

    answer = (
        f"[{label}] 관련 안내입니다.\n\n"
        f"{primary['snippet']}\n\n"
        f"주요 근거: {ref_list}."
    )

    if context_doctype:
        answer += f"\n\n현재 문서({context_doctype}) 관련 세부 사항은 아래 '관련 링크'를 참고하거나 담당자에게 확인하세요."

    return answer


def _build_suggested_actions(
    *,
    intent: str,
    context_doctype: str | None,
) -> list[dict]:
    """의도별 사용자 직접 클릭 액션 링크 목록. 자동 실행 절대 X."""
    actions_map: dict[str, list[dict]] = {
        "leave": [
            {"label": "연차 신청", "url": "/hrms/leave-application/new"},
            {"label": "휴가 잔여 확인", "url": "/hrms/dashboard/leaves"},
            {"label": "휴직 규정 보기", "url": "/hrms/hr-policy/leave"},
        ],
        "payroll": [
            {"label": "급여명세서 확인", "url": "/hrms/dashboard/salary-slips"},
            {"label": "임금 대장", "url": "/hrms/payroll/payroll-entry"},
        ],
        "contract": [
            {"label": "근로계약서 조회", "url": "/hrms/employee/employment-contract"},
            {"label": "취업규칙 보기", "url": "/hrms/hr-policy/employment-rules"},
        ],
        "compliance": [
            {"label": "근로감독 체크리스트", "url": "/hrms/compliance/checklist"},
            {"label": "진정 접수 안내", "url": "https://minwon.moel.go.kr"},
        ],
        "working_hours": [
            {"label": "근태 현황", "url": "/hrms/dashboard/attendance"},
            {"label": "연장근로 신청", "url": "/hrms/attendance-request/new"},
        ],
        "general": [
            {"label": "홈으로", "url": "/hrms/home"},
        ],
    }

    base_actions = actions_map.get(intent, actions_map["general"])

    # context_doctype 기반 추가 링크
    if context_doctype == "Leave Application":
        base_actions.insert(0, {"label": "이 신청서 보기", "url": f"/hrms/leave-application"})
    elif context_doctype == "Salary Slip":
        base_actions.insert(0, {"label": "이 급여명세서 보기", "url": "/hrms/salary-slip"})

    return base_actions


def _error_response(
    *,
    session_id: str,
    user_question: str,
    message: str,
) -> dict:
    """에러 시에도 동일한 contract 구조 반환 (no_mutation_performed 포함)."""
    return {
        "contract_type": CONTRACT_TYPE,
        "runtime_action": CHAT_RUNTIME_ACTION,
        "session_id": session_id,
        "user_question": user_question,
        "answer": message,
        "citations": [],
        "suggested_actions": [{"label": "홈으로", "url": "/hrms/home"}],
        "disclaimer": DISCLAIMER,
        "ai_role": AI_ROLE,
        "no_mutation_performed": True,
        "tokens_used": 0,
    }
