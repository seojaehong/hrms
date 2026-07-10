# -*- coding: utf-8 -*-
"""pkb 재임베딩 순수 코어 — 최영우 pkb를 OpenAI 1536으로 통일(Gemini 768 폐기). framework-free.

배치 분할·OpenAI 응답 파싱·쓰기 페이로드 조립만 담당(순수). 실제 OpenAI/Supabase
호출은 scripts/reembed_pkb_openai.py.

실행: python3 hrms/tests/test_korea_pkb_reembed.py
"""
from __future__ import annotations

from typing import Any


def chunk_batches(items: list, size: int) -> list[list]:
    """items를 size 단위 배치로 분할."""
    return [items[i:i + size] for i in range(0, len(items), size)]


def parse_openai_embeddings(response: dict, expected: int | None = None) -> list[list[float]]:
    """OpenAI /v1/embeddings 응답 → index 순 임베딩 리스트. expected 주면 개수 검증."""
    data = (response or {}).get("data") or []
    ordered = [d["embedding"] for d in sorted(data, key=lambda d: d.get("index", 0))]
    if expected is not None and len(ordered) != expected:
        raise ValueError(f"임베딩 개수 불일치: {len(ordered)} (기대 {expected})")
    return ordered


def assemble_write_payload(ids: list, vectors: list[list[float]]) -> list[dict[str, Any]]:
    """(ids, vectors) → pkb_write_1536용 [{id, emb}] 페이로드. 길이 불일치 시 에러."""
    if len(ids) != len(vectors):
        raise ValueError(f"ids({len(ids)})와 vectors({len(vectors)}) 길이 불일치")
    return [{"id": i, "emb": v} for i, v in zip(ids, vectors)]
