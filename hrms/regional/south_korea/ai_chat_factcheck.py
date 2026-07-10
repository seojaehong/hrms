# -*- coding: utf-8 -*-
"""ai_chat 팩트체크 하네스 게이트 — PRD §7.4/원칙4 계약 강제. framework-free.

임베딩 검색은 "유사한 것"을 줄 뿐 정확성을 보장하지 않는다. 상용 노무 서비스는
(마이그레이션된 권위 코퍼스 위에서) 팩트체크 계약을 강제해야 한다:
- 신뢰도(top 유사도) < 임계치 → 단정 금지, "노무사 상담 권장" fallback(하네스)
- 답변마다 검증가능한 근거(사건번호·URL) 노출
- 점수가 없는 v1(char-bigram) 경로는 게이트 미적용(회귀 방지)

실행: python3 hrms/tests/test_korea_ai_chat_factcheck.py
"""
from __future__ import annotations

# 기본 신뢰 임계치 — pgvector 코사인 유사도. search_*_semantic RPC의 min_similarity(0.3~0.4)와 정합.
DEFAULT_CONFIDENCE_THRESHOLD = 0.4


def has_scores(docs: list[dict]) -> bool:
    """문서에 수치 score가 하나라도 있으면 True(시맨틱 v2 경로). v1은 False."""
    return any(isinstance(d.get("score"), (int, float)) for d in docs or [])


def top_confidence(docs: list[dict]) -> float:
    """문서 중 최고 score. 없으면 0.0."""
    scores = [d["score"] for d in docs or [] if isinstance(d.get("score"), (int, float))]
    return float(max(scores)) if scores else 0.0


def evaluate(docs: list[dict], *, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> dict:
    """팩트체크 판정. applicable=점수기반(v2)일 때만 게이트 작동."""
    applicable = has_scores(docs)
    confidence = top_confidence(docs)
    grounded = (not applicable) or (confidence >= threshold)
    return {"applicable": applicable, "confidence": confidence, "grounded": grounded}


def harness_fallback_answer(question: str) -> str:
    """근거 신뢰도 미달 시 단정 대신 사람 연결(PRD §7.4 하네스 계약)."""
    return (
        f"'{question}'에 대해 확실한 법적 근거를 충분히 찾지 못했습니다. "
        "잘못된 단정은 위험하므로 답변을 보류합니다. "
        "구체적 사실관계 확인이 필요한 사안이니 담당 노무사 상담을 권장합니다."
    )


def build_verification_footer(docs: list[dict]) -> str:
    """검증가능한 근거(사건번호·URL)를 클릭 확인용 푸터로. 없으면 빈 문자열."""
    lines: list[str] = []
    for d in docs or []:
        ref = (d.get("ref_code") or "").strip()
        url = (d.get("url") or "").strip()
        if not ref and not url:
            continue
        label = ref or d.get("title") or "근거"
        lines.append(f"- {label}{(' — ' + url) if url else ''}")
        if len(lines) >= 3:
            break
    if not lines:
        return ""
    return "\n\n[검증 근거]\n" + "\n".join(lines)
