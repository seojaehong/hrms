# -*- coding: utf-8 -*-
"""ai_chat v2 시맨틱 배선 — 정규화 문서(semantic_retrieval)→v1 문서 매핑 + retriever 팩토리.

v2 시맨틱 결과를 v1 문서 형태({law,title,text,type})로 바꿔 기존 _build_answer/
_docs_to_citations를 그대로 재사용한다. chat_query(retriever=...)로 주입.

framework-free. 실행: python3 hrms/tests/test_korea_ai_chat_semantic.py
"""
from __future__ import annotations

from typing import Callable

# v2 소스 라벨 → v1 citation type
_SOURCE_TO_TYPE = {
    "행정해석": "law",
    "판례": "case",
    "노동위 판정례": "case",
    "상담 FAQ": "faq",
    "최영우 레퍼런스": "internal",
}

# 사건번호를 title에 병기해 추적성을 보존할 소스(FAQ 카테고리·최영우 경로는 제외)
_APPEND_REF_SOURCES = {"행정해석", "판례", "노동위 판정례"}


def map_v2_to_v1_doc(nd: dict) -> dict:
    """정규화 문서 {source,title,text,ref,url,score} → v1 문서 {law,title,text,type,...}."""
    source = nd.get("source", "")
    title = nd.get("title") or nd.get("ref") or ""
    ref = nd.get("ref") or ""
    if ref and source in _APPEND_REF_SOURCES and ref not in title:
        title = f"{title} [{ref}]".strip()
    return {
        "law": source,
        "title": title,
        "text": nd.get("text", ""),
        "type": _SOURCE_TO_TYPE.get(source, "internal"),
        "url": nd.get("url"),
        "ref_code": ref,
        "score": nd.get("score"),
    }


def make_semantic_retriever(
    *,
    retrieve_fn: Callable[..., list[dict]],
    sources: list[str],
) -> Callable[..., list[dict]]:
    """retrieve_fn(query, sources, top_k)→정규화 문서 리스트를 v1 문서 리스트로 변환하는 retriever.

    chat_query(retriever=...)에 그대로 주입 가능한 (query, top_k)→docs 콜러블 반환.
    """
    def retriever(query: str, top_k: int = 5) -> list[dict]:
        normalized = retrieve_fn(query, sources, top_k) or []
        return [map_v2_to_v1_doc(nd) for nd in normalized]

    return retriever
