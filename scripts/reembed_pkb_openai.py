# -*- coding: utf-8 -*-
"""최영우 pkb를 OpenAI 1536으로 통일 재임베딩(Gemini 768 폐기).

embedding_1536 컬럼(마이그레이션 pkb_add_embedding_1536_openai로 이미 추가됨)을
채운다. 기존 embedding(768)·pkb_search는 건드리지 않는다(비파괴).

⚠️ 쓰기엔 service_role 키가 필요하다(anon은 RLS로 읽기전용). 이 스크립트는 사용자가
직접 실행한다. 시크릿은 .env.smoke(gitignore)에서만 읽고 출력하지 않는다.

.env.smoke 필요 항목:
  YELLOW_ENVELOPE_SUPABASE_URL=https://mewqgevgdgghhatqtuos.supabase.co
  YELLOW_ENVELOPE_SUPABASE_SERVICE_KEY=<service_role key>   # ← anon 아님, 쓰기용
  OPENAI_API_KEY=<sk-...>

실행:  python scripts/reembed_pkb_openai.py
끝나면 service_role 키는 rotate 권장.
"""
import importlib.util
import os
import pathlib
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_KO = _ROOT / "hrms" / "regional" / "south_korea"
_BATCH = 100          # OpenAI 배치 크기
_OPENAI_MODEL = "text-embedding-3-small"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _load_dotenv():
    f = _ROOT / ".env.smoke"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    _load_dotenv()
    core = _load("pkb_reembed", _KO / "pkb_reembed.py")

    url = os.environ.get("YELLOW_ENVELOPE_SUPABASE_URL", "").rstrip("/")
    svc = os.environ.get("YELLOW_ENVELOPE_SUPABASE_SERVICE_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not (url and svc and openai_key):
        print("[중단] .env.smoke에 YELLOW_ENVELOPE_SUPABASE_URL / "
              "YELLOW_ENVELOPE_SUPABASE_SERVICE_KEY / OPENAI_API_KEY 필요")
        return 2

    sb_headers = {"apikey": svc, "Authorization": f"Bearer {svc}",
                  "Content-Type": "application/json"}
    total = 0
    while True:
        # 1) 아직 embedding_1536 없는 청크 배치 조회(service_role → RLS 우회)
        rows = requests.get(
            f"{url}/rest/v1/pkb_chunks",
            headers=sb_headers,
            params={"select": "id,content", "embedding_1536": "is.null",
                    "content": "not.is.null", "order": "id", "limit": str(_BATCH)},
            timeout=60,
        ).json()
        if not rows:
            break
        ids = [r["id"] for r in rows]
        # 8k자 한국어 청크가 8192토큰 한도 초과(400) → 안전 절단(검색용이라 앞부분로 충분)
        texts = [core.truncate_for_embedding(r["content"]) for r in rows]

        # 2) OpenAI 배치 임베딩(1536)
        er = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {openai_key}",
                     "Content-Type": "application/json"},
            json={"model": _OPENAI_MODEL, "input": texts}, timeout=120,
        )
        er.raise_for_status()
        vectors = core.parse_openai_embeddings(er.json(), expected=len(texts))

        # 3) 개별 PATCH로 기록(service_role)
        for cid, vec in zip(ids, vectors):
            pr = requests.patch(
                f"{url}/rest/v1/pkb_chunks",
                headers=sb_headers, params={"id": f"eq.{cid}"},
                json={"embedding_1536": "[" + ",".join(map(str, vec)) + "]"},
                timeout=60,
            )
            pr.raise_for_status()
        total += len(ids)
        print(f"  {total} 완료 (last id={ids[-1]})")
        time.sleep(0.2)

    print(f"[완료] pkb 재임베딩 {total}건 → embedding_1536(OpenAI 1536). Gemini 불필요.")
    print("service_role 키는 rotate 권장.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
