# -*- coding: utf-8 -*-
"""v2 시맨틱 검색 코어 — yellow-envelope-law 임베딩 코퍼스 조회(순수 로직). framework-free.

ai_chat v1(char-bigram + 로컬 JSON)의 정확도 한계를 대체한다. 실제 지식은
Supabase(yellow-envelope-law)에 임베딩+검색 RPC로 이미 존재:
- 최영우 레퍼런스/교재(pkb, 768d, Gemini) — pkb_search
- 행정해석(molab, 1536d, OpenAI) — search_interpretation_semantic
- 판례(cases, 1536d) — search_cases_semantic
- 상담 FAQ(1536d) — search_faq_semantic
- 노동위 판정례(nlrc, 텍스트) — search_nlrc

이 모듈은 외부 의존을 **주입**받는다:
- embedder(model:str, text:str) -> list[float] : 질문 임베딩(모델별 어댑터)
- rpc_caller(rpc:str, params:dict) -> list[dict] : Supabase RPC 호출

정규화된 공통 문서 형태: {source, title, text, ref, url, score}

frappe/requests/supabase import 없음 → `python3 hrms/tests/test_korea_semantic_retrieval.py`.
"""
from __future__ import annotations

from typing import Any, Callable

# 검색 단계 최소 유사도 — 낮게 뽑고 판정은 팩트체크 게이트(ai_chat_factcheck τ)가 한다.
# text-embedding-3-small은 인도메인 top 유사도도 ~0.35라 RPC 기본값(0.4)이면 다 걸러짐.
_SEMANTIC_MIN_SIMILARITY = 0.2

# ── 소스 레지스트리 ──────────────────────────────────────────────────────────
# 각 소스: label, rpc, model(None이면 텍스트검색), semantic 여부,
# params(vec_or_query, cap)→dict, normalize(row)→공통dict


def _first(*vals):
    for v in vals:
        if v:
            return v
    return ""


SOURCES: dict[str, dict[str, Any]] = {
    "pkb": {
        "label": "최영우 레퍼런스",
        "rpc": "pkb_search_1536",  # OpenAI 1536으로 통일 재임베딩(Gemini 768 pkb_search 폐기)
        "model": "openai-1536",
        "params": lambda vec, cap: {"query_embedding": vec, "match_count": cap},
        "normalize": lambda r: {
            "title": _first(r.get("title"), r.get("section"), r.get("folder")),
            "text": r.get("content") or "",
            "ref": _first(r.get("source_path"), r.get("doc_id")),
            "url": r.get("url"),
            "score": float(r.get("similarity") or 0.0),
        },
    },
    "interpretation": {
        "label": "행정해석",
        "rpc": "search_interpretation_semantic",
        "model": "openai-1536",
        "params": lambda vec, cap: {
            "query_embedding": vec, "max_results": cap,
            "min_similarity": _SEMANTIC_MIN_SIMILARITY,
        },
        "normalize": lambda r: {
            "title": r.get("title") or "",
            "text": _first(r.get("answer_summary"), r.get("inquiry_summary")),
            "ref": r.get("case_number") or "",
            "url": r.get("url"),
            "score": float(r.get("similarity") or 0.0),
        },
    },
    "cases": {
        "label": "판례",
        "rpc": "search_cases_semantic",
        "model": "openai-1536",
        "params": lambda vec, cap: {
            "query_embedding": vec, "max_results": cap,
            "min_similarity": _SEMANTIC_MIN_SIMILARITY,
        },
        "normalize": lambda r: {
            "title": _first(r.get("title"), r.get("case_number")),
            "text": r.get("summary") or "",
            "ref": r.get("case_number") or "",
            "url": r.get("url"),
            "score": float(r.get("similarity") or 0.0),
        },
    },
    "faq": {
        "label": "상담 FAQ",
        "rpc": "search_faq_semantic",
        "model": "openai-1536",
        "params": lambda vec, cap: {
            "query_embedding": vec, "max_results": cap,
            "min_similarity": _SEMANTIC_MIN_SIMILARITY,
        },
        "normalize": lambda r: {
            "title": r.get("question") or "",
            "text": r.get("answer") or "",
            "ref": _first(r.get("unified_category"), str(r.get("id") or "")),
            "url": r.get("url"),
            "score": float(r.get("similarity") or 0.0),
        },
    },
    "nlrc": {
        "label": "노동위 판정례",
        "rpc": "search_nlrc",
        "model": None,  # 텍스트 검색(임베딩 불필요)
        "params": lambda query, cap: {"query": query, "result_limit": cap},
        "normalize": lambda r: {
            "title": r.get("title") or "",
            "text": _first(r.get("holding_summary"), r.get("summary_short"), r.get("key_issue")),
            "ref": r.get("case_number") or "",
            "url": _first(r.get("url"), r.get("original_url")),
            "score": float(r.get("relevance") or 0.0),
        },
    },
}


def select_model(source: str) -> str | None:
    """소스의 질문 임베딩 모델. 텍스트검색 소스는 None."""
    return SOURCES[source]["model"]


def normalize_row(source: str, row: dict) -> dict:
    """RPC 결과 row를 공통 문서 형태로 정규화(source 라벨 부착)."""
    spec = SOURCES[source]
    doc = spec["normalize"](row)
    doc["source"] = spec["label"]
    return doc


def merge_and_rank(
    results_by_source: dict[str, list[dict]],
    *,
    top_k: int = 5,
    per_source_cap: int = 3,
) -> list[dict]:
    """소스별 결과를 병합·랭킹. 소스별 상한 적용 → score 내림차순 → (source,ref) 중복 제거 → top_k."""
    pooled: list[dict] = []
    for docs in results_by_source.values():
        capped = sorted(docs, key=lambda d: d.get("score", 0.0), reverse=True)[:per_source_cap]
        pooled.extend(capped)
    pooled.sort(key=lambda d: d.get("score", 0.0), reverse=True)

    seen: set[tuple] = set()
    merged: list[dict] = []
    for d in pooled:
        key = (d.get("source"), d.get("ref"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(d)
        if len(merged) >= top_k:
            break
    return merged


def build_retrieval(
    query: str,
    sources: list[str],
    *,
    embedder: Callable[[str, str], list[float]],
    rpc_caller: Callable[[str, dict], list[dict]],
    top_k: int = 5,
    per_source_cap: int = 3,
    redactor: Callable[[str], str] | None = None,
) -> list[dict]:
    """질문을 각 소스의 올바른 모델로 임베딩→RPC 조회→정규화→병합·랭킹.

    - redactor 주면 임베딩/검색 전에 질문 PII를 제거(외부 임베딩 API로 원문 PII 유출 방지).
    - 한 소스가 실패해도 나머지는 진행(fail-soft).
    """
    q = redactor(query) if redactor else query
    results_by_source: dict[str, list[dict]] = {}
    # 모델별 임베딩 캐시(같은 1536 모델을 여러 소스가 공유 → 1회만 임베딩)
    embed_cache: dict[str, list[float]] = {}

    for source in sources:
        spec = SOURCES.get(source)
        if spec is None:
            continue
        try:
            model = spec["model"]
            if model is None:
                params = spec["params"](q, per_source_cap)
            else:
                if model not in embed_cache:
                    embed_cache[model] = embedder(model, q)
                params = spec["params"](embed_cache[model], per_source_cap)
            rows = rpc_caller(spec["rpc"], params) or []
            results_by_source[source] = [normalize_row(source, r) for r in rows]
        except Exception:  # noqa: BLE001 — 소스 단위 fail-soft
            results_by_source[source] = []

    return merge_and_rank(results_by_source, top_k=top_k, per_source_cap=per_source_cap)
