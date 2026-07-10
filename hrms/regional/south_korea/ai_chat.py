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

import importlib.util as _ilu
import json
import os
import pathlib as _pl
import re
import uuid
from datetime import datetime
from typing import Any, Callable


def _load_sibling(name: str):
    """같은 폴더의 framework-free 모듈을 경로로 로드(패키지 컨텍스트 없이도 동작)."""
    spec = _ilu.spec_from_file_location(name, _pl.Path(__file__).resolve().parent / f"{name}.py")
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_factcheck = _load_sibling("ai_chat_factcheck")

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
# 카탈로그 로더 (법령/판례 카탈로그 + FAQ 카탈로그 병합)
# ──────────────────────────────────────────────
_LAW_CATALOG_FILENAME = "korea_labor_law_catalog.json"
_FAQ_CATALOG_FILENAME = "korea_labor_faq_catalog.json"
_ADMIN_CATALOG_FILENAME = "korea_admin_interpretation_catalog.json"

_CATALOG_CACHE: list[dict] | None = None
_INDEX_CACHE: dict | None = None


def _data_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "data")


def _load_catalog_files(law_path: str, *optional_paths: str) -> list[dict]:
    """법령 카탈로그(필수) + 부가 카탈로그(FAQ·행정해석 등, 선택)를 로드하여 병합합니다.

    부가 파일이 없거나 읽을 수 없으면 무시하고 나머지만 반환합니다.
    """
    with open(law_path, encoding="utf-8") as f:
        entries: list[dict] = json.load(f)

    for path in optional_paths:
        try:
            with open(path, encoding="utf-8") as f:
                extra = json.load(f)
            if isinstance(extra, list):
                entries = entries + extra
        except (OSError, json.JSONDecodeError):
            pass  # 부가 카탈로그는 optional

    return entries


def _load_catalog() -> list[dict]:
    """한국 노동법 카탈로그 JSON(법령+FAQ 병합)을 로드하여 캐시합니다."""
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE

    _CATALOG_CACHE = _load_catalog_files(
        os.path.join(_data_dir(), _LAW_CATALOG_FILENAME),
        os.path.join(_data_dir(), _FAQ_CATALOG_FILENAME),
        os.path.join(_data_dir(), _ADMIN_CATALOG_FILENAME),
    )
    return _CATALOG_CACHE


def _char_bigrams(text: str) -> set[str]:
    """공백/구두점으로 구분된 각 연속 문자열 조각의 문자 2-gram 집합.

    공백 없는 한국어 질문("수습기간중인직원도주휴수당을...")도
    제목/태그와 부분 일치할 수 있게 하는 보조 매칭 단위.
    """
    bigrams: set[str] = set()
    for chunk in _tokenize(text):
        for i in range(len(chunk) - 1):
            bigrams.add(chunk[i : i + 2])
    return bigrams


def _build_index() -> dict:
    """카탈로그 로드 시 1회 구축하는 역색인 + 엔트리 메타 캐시.

    - postings: 제목/법령명/태그의 문자 2-gram → 엔트리 인덱스 집합
      (질의 2-gram으로 후보를 축소한 뒤 기존 스코어링만 후보에 적용)
    - meta: 엔트리별 소문자 제목/본문/태그 + 제목 2-gram (질의당 재계산 방지)
    - always_candidates: 법령/판례 등 비-FAQ 엔트리는 항상 후보에 포함
      (기존 33건 카탈로그 질의 결과의 회귀 방지)
    """
    catalog = _load_catalog()
    postings: dict[str, set[int]] = {}
    meta: list[dict] = []
    always_candidates: set[int] = set()

    for idx, entry in enumerate(catalog):
        combined_title = (entry.get("law", "") + " " + entry.get("title", "")).lower()
        tags_lower = [tag.lower() for tag in entry.get("tags", [])]
        text_lower = entry.get("text", "").lower()
        title_bigrams = _char_bigrams(combined_title)

        indexable = combined_title + " " + " ".join(tags_lower)
        for bigram in _char_bigrams(indexable):
            postings.setdefault(bigram, set()).add(idx)

        if entry.get("type", "law") != "faq":
            always_candidates.add(idx)

        meta.append({
            "combined_title": combined_title,
            "text_lower": text_lower,
            "tags_lower": tags_lower,
            "title_bigrams": title_bigrams,
        })

    return {
        "postings": postings,
        "meta": meta,
        "always_candidates": always_candidates,
    }


def _ensure_index() -> dict:
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        _INDEX_CACHE = _build_index()
    return _INDEX_CACHE


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
    payroll_stats_provider: Callable[[], dict | None] | None = None,
    retriever: Callable[..., list[dict]] | None = None,
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

    # v2 시맨틱 retriever 주입 시 그것을, 아니면 v1 char-bigram 로컬 검색.
    if retriever is not None:
        docs = retriever(query=user_question, top_k=5)
    else:
        docs = retrieve_relevant_documents(query=user_question, top_k=5)

    # 팩트체크 하네스 게이트(PRD §7.4) — 점수기반(v2)일 때 신뢰도 미달이면 단정 대신 사람 연결.
    fc = _factcheck.evaluate(docs)
    requires_human_consult = fc["applicable"] and not fc["grounded"]

    if requires_human_consult:
        citations = []
        answer = _factcheck.harness_fallback_answer(user_question)
    else:
        citations = _docs_to_citations(docs)
        answer = _build_answer(
            intent=intent,
            question=user_question,
            citations=citations,
            context_doctype=context_doctype,
            user_role=user_role,
            docs=docs,
        )
        # 검증가능한 근거(사건번호·URL) 노출 — 있을 때만.
        answer += _factcheck.build_verification_footer(docs)

    # 사이트 급여 데이터 질의면 read-only 집계 한 줄 요약을 답변 앞에 붙인다.
    # provider 미제공(테스트 환경/기본값) 또는 stats None이면 기존 동작 그대로.
    if payroll_stats_provider is not None and detect_payroll_data_intent(user_question):
        try:
            stats = payroll_stats_provider()
        except Exception:
            stats = None
        if stats:
            answer = build_payroll_summary_line(stats) + "\n\n" + answer

    suggested_actions = _build_suggested_actions(
        intent=intent,
        context_doctype=context_doctype,
    )
    if requires_human_consult:
        suggested_actions.insert(0, {"label": "노무사 상담", "url": "/hrms/consultation/new"})

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
        "requires_human_consult": requires_human_consult,
        "retrieval_confidence": round(fc["confidence"], 4),
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
    use_index: bool = True,
) -> list[dict]:
    """관련 법령/판례/FAQ/내부 문서 retrieval.

    v1 stub: 키워드 + 문자 2-gram 매칭 (한국 노동법 카탈로그 + FAQ 카탈로그).
    - 제목(title/law) 토큰 매치 가중치 3 (본문 1보다 우선), 태그 1 유지
    - 공백 없는 질문 대응: 질의-제목 문자 2-gram 교집합 보조 점수
    - use_index=True(기본): 역색인으로 후보 축소 후 스코어링 (전체 스캔 방지)
    v2: vector embedding similarity 검색으로 교체 예정.

    Returns:
        list of catalog entries matching query keywords.
        Each entry: {"law": str, "title": str, "type": str, "text": str, "tags": list[str]}
    """
    query_lower = query.lower()
    catalog = _load_catalog()
    index = _ensure_index()
    meta = index["meta"]

    tokens = [t for t in _tokenize(query_lower) if t]
    query_bigrams = _char_bigrams(query_lower)

    if use_index:
        candidates: set[int] = set(index["always_candidates"])
        postings = index["postings"]
        for bigram in query_bigrams:
            hits = postings.get(bigram)
            if hits:
                candidates |= hits
        candidate_ids = sorted(candidates)
    else:
        candidate_ids = range(len(catalog))

    scored: list[tuple[int, int]] = []  # (score, idx)
    for idx in candidate_ids:
        m = meta[idx]
        score = 0
        # title/law 매칭 가중치 3, tags/text 매칭 가중치 1
        for token in tokens:
            if token in m["combined_title"]:
                score += 3
            if token in m["text_lower"]:
                score += 1
            for tag in m["tags_lower"]:
                if token in tag:
                    score += 1
        # 공백 없는 질문 보조 매칭: 제목과의 문자 2-gram 교집합 (2개 이상일 때만, 상한 10)
        bigram_overlap = len(query_bigrams & m["title_bigrams"])
        if bigram_overlap >= 2:
            score += min(bigram_overlap, 10)
        if score > 0:
            scored.append((score, idx))

    # 동점 시 카탈로그 원 순서 유지 (법령 카탈로그가 앞에 위치)
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = [idx for _, idx in scored[:top_k]]

    # FAQ/행정해석이 상위를 채우더라도 법령/판례 근거 1건은 결과에 보장
    # (답변의 "주요 근거" 인용 + 기존 법령 카탈로그 질의 회귀 방지)
    if top and all(catalog[idx].get("type", "law") not in ("law", "case") for idx in top):
        best_statutory = next(
            (idx for _, idx in scored if catalog[idx].get("type", "law") in ("law", "case")),
            None,
        )
        if best_statutory is not None:
            top[-1] = best_statutory

    return [catalog[idx] for idx in top]


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
# 사이트 급여 데이터 질의 인텐트 (read-only 집계 요약)
# ──────────────────────────────────────────────
# NOTE: 급여 "법령" 질의(급여/임금/수당/퇴직금 …, INTENT_KEYWORD_MAP["payroll"])와
# 반드시 구분한다. 여기 키워드는 "우리 사이트의 실제 숫자"를 묻는 질의에만 반응해야
# 하므로 좁게 유지한다("최저임금 위반 시 퇴직금…" 같은 법령 질문에는 걸리지 않음).
PAYROLL_DATA_INTENT_KEYWORDS: list[str] = [
    "총지급", "총 지급", "실지급", "실 지급", "지급 합계", "지급합계",
    "급여 총액", "급여총액", "급여 합계", "급여합계",
    "마감 상태", "마감상태", "마감 확정", "마감됐", "마감 됐", "마감했",
    "몇 명", "몇명", "인원 수", "인원수",
]


def detect_payroll_data_intent(question: str) -> bool:
    """질문이 사이트 급여 데이터(집계 수치) 질의인지 판별하는 순수 함수.

    급여 "법령" 질의가 아니라 "우리 사이트의 총지급/실지급/인원/마감 상태" 같은
    실제 데이터 조회 의도만 True. 점수/확률 없음.
    """
    if not question or not question.strip():
        return False
    return any(kw in question for kw in PAYROLL_DATA_INTENT_KEYWORDS)


def build_payroll_summary_line(stats: dict) -> str:
    """급여 집계 stats → 한 줄 요약 문구 (순수 함수, 원 단위 콤마).

    예: '2026-05 급여: 32명 · 실지급 합계 95,940,486원 · 마감 확정 대기'

    stats 키:
        - period: 'YYYY-MM'
        - employee_count: int
        - net_total: int (실지급 합계, 원)
        - closing_status: str (예: '마감 확정 대기' / '마감 확정')
    """
    period = str(stats.get("period", "")).strip()
    count = int(stats.get("employee_count", 0) or 0)
    net_total = int(round(float(stats.get("net_total", 0) or 0)))
    status = str(stats.get("closing_status", "")).strip()

    line = f"{period} 급여: {count}명 · 실지급 합계 {net_total:,}원"
    if status:
        line += f" · {status}"
    return line


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


# citation type → 한국어 라벨
CITATION_TYPE_LABELS: dict[str, str] = {
    "law": "법령",
    "case": "판례",
    "internal": "내부",
    "faq": "FAQ",
    "admin": "행정해석",
}

_SENTENCE_END_RE = re.compile(r"(?:다|요)\.")


def _clip_to_sentence(text: str, max_len: int = 400) -> str:
    """max_len 이내에서 마지막 문장 경계("다."/"요.")까지 클립.

    문장 중간 절단 방지: 경계가 없으면 마지막 공백, 그것도 없으면 hard cut.
    """
    if len(text) <= max_len:
        return text

    window = text[:max_len]
    last_end = 0
    for match in _SENTENCE_END_RE.finditer(window):
        last_end = match.end()
    if last_end:
        return window[:last_end]

    last_space = window.rfind(" ")
    if last_space > 0:
        return window[:last_space]
    return window


def _docs_to_citations(docs: list[dict]) -> list[dict]:
    """카탈로그 엔트리 → citation 형식 변환 (문장 경계 클립, 최대 400자)."""
    citations: list[dict] = []
    for doc in docs:
        ref = f"{doc.get('law', '')} — {doc.get('title', '')}"
        snippet = _clip_to_sentence(doc.get("text", ""), max_len=400)
        cite_type = doc.get("type", "law")
        citations.append({
            "type": cite_type,
            "label": CITATION_TYPE_LABELS.get(cite_type, "참고"),
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
    docs: list[dict] | None = None,
) -> str:
    """v1 답변 생성 (템플릿 기반, LLM X).

    인용 법령/FAQ를 근거로 한 사실 안내문. 점수/확률 표현 없음.
    - 본문(primary)은 최상위 매치 문서의 전문(이미 700자 이내) — 중간 절단 금지
    - 최상위 매치가 FAQ이면 답변 본문 = FAQ 답변 전문,
      "주요 근거"는 법령/판례 인용이 있을 때만 표기
    """
    if not citations:
        return (
            f"'{question}'에 해당하는 법령/판례를 찾지 못했습니다. "
            "보다 구체적인 키워드로 다시 질문하시거나, 담당 노무사에게 문의해 주세요."
        )

    docs = docs or []
    primary_doc = docs[0] if docs else None
    # 본문은 전문 사용 (citation snippet은 400자 클립본)
    primary_body = primary_doc.get("text", "") if primary_doc else citations[0]["snippet"]

    intent_label_map = {
        "leave": "휴가·휴직",
        "payroll": "급여·임금",
        "contract": "근로계약",
        "compliance": "법령 준수·제재",
        "working_hours": "근로시간",
        "general": "HR 일반",
    }
    label = intent_label_map.get(intent, "HR 일반")

    primary_is_faq = bool(primary_doc) and primary_doc.get("type") == "faq"

    if primary_is_faq:
        # FAQ가 최상위 매치 → 답변 본문 = FAQ answer 전문.
        # "주요 근거"는 법령/판례 인용이 있을 때만.
        law_refs = [
            f"[{c.get('label', CITATION_TYPE_LABELS.get(c['type'], '참고'))}] {c['ref']}"
            for c in citations
            if c["type"] in ("law", "case")
        ]
        answer = (
            f"[{label}] 관련 안내입니다.\n\n"
            f"[FAQ] {primary_doc.get('title', '')}\n\n"
            f"{primary_body}"
        )
        if law_refs:
            answer += f"\n\n주요 근거: {' / '.join(law_refs[:3])}."
    else:
        ref_list = " / ".join(
            f"[{c.get('label', CITATION_TYPE_LABELS.get(c['type'], '참고'))}] {c['ref']}"
            for c in citations[:3]
        )
        answer = (
            f"[{label}] 관련 안내입니다.\n\n"
            f"{primary_body}\n\n"
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
