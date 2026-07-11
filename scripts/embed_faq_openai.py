# -*- coding: utf-8 -*-
"""FAQ 임베딩 잔여분 채우기 — 기존 코퍼스와 동일 포맷/모델로.

실증으로 확정한 기존 컨벤션(id 3939 cos=1.0):
  input = f"질문: {question}\n답변: {answer}", model = text-embedding-3-small(1536)

reembed_pkb_openai.py와 동일 패턴: .env.smoke에서 service_role 키, 재개 가능
(embedding is null만 집음), Session keep-alive, 3000자 절단.

실행:  python scripts/embed_faq_openai.py
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
_BATCH = 100
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
        print("[중단] .env.smoke에 URL / SERVICE_KEY / OPENAI_API_KEY 필요")
        return 2

    sb_headers = {"apikey": svc, "Authorization": f"Bearer {svc}",
                  "Content-Type": "application/json"}
    ses = requests.Session()
    total = 0
    while True:
        rows = ses.get(
            f"{url}/rest/v1/faq",
            headers=sb_headers,
            params={"select": "id,question,answer", "embedding": "is.null",
                    "order": "id", "limit": str(_BATCH)},
            timeout=60,
        ).json()
        if not rows:
            break
        ids = [r["id"] for r in rows]
        # 기존 코퍼스 컨벤션 그대로(실증 cos=1.0): "질문: ...\n답변: ..."
        texts = [core.truncate_for_embedding(
            f"질문: {r.get('question') or ''}\n답변: {r.get('answer') or ''}") for r in rows]

        er = ses.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {openai_key}",
                     "Content-Type": "application/json"},
            json={"model": _OPENAI_MODEL, "input": texts}, timeout=120,
        )
        er.raise_for_status()
        vectors = core.parse_openai_embeddings(er.json(), expected=len(texts))

        for cid, vec in zip(ids, vectors):
            pr = ses.patch(
                f"{url}/rest/v1/faq",
                headers=sb_headers, params={"id": f"eq.{cid}"},
                json={"embedding": "[" + ",".join(map(str, vec)) + "]"},
                timeout=60,
            )
            pr.raise_for_status()
        total += len(ids)
        print(f"  {total} 완료 (last id={ids[-1]})")
        time.sleep(0.2)

    print(f"[완료] FAQ 임베딩 {total}건 채움.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
