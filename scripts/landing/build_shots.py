"""랜딩용 제품 스크린샷 — korea-tokens.css 실물 렌더(라이트), 윈도 크롬 프레임 포함.
렌더: chrome --headless=new --force-device-scale-factor=2 --default-background-color=00000000
      --window-size=820,480(wage)/820,420(net) --screenshot=assets/shot_*.png shotpage_*.html"""
import sys, pathlib
sys.stdout.reconfigure(encoding="utf-8")
REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).parent / "assets"
tokens = (REPO / "frontend/src/styles/korea-tokens.css").read_text(encoding="utf-8")

WAGE = """
<div class="win">
 <div class="bar"><span class="dot" style="background:#f37f74"></span><span class="dot" style="background:#f0b429"></span><span class="dot" style="background:#34c164"></span><span class="url">demo.safeclaw.kr · 임금명세서</span></div>
 <div style="background:var(--k-canvas);padding:28px 32px">
  <p class="k-eyebrow">2026년 6월 임금명세서</p>
  <div style="margin:10px 0 4px"><span class="k-display k-settled" style="font-size:44px">3,495,809원</span></div>
  <p class="k-label" style="margin:6px 0 18px">실수령액 · 확정</p>
  <div class="k-card" style="padding:6px 20px">
    <div class="row"><span>기본급</span><span class="k-amount">3,200,000</span></div>
    <div class="row"><span>고정연장수당 (§56)</span><span class="k-amount">295,809</span></div>
    <div class="row"><span>국민연금 (4.75%)</span><span class="k-amount">−156,550</span></div>
    <div class="row" style="border:none"><span>건강보험 (3.595%)</span><span class="k-amount">−118,480</span></div>
  </div>
  <div style="display:flex;gap:10px;margin-top:18px">
    <button class="k-btn-primary">명세서 PDF 발급</button>
    <button class="k-btn-secondary">지난 달 보기</button>
    <span style="margin-left:auto;align-self:center;color:var(--k-success);font-size:13px;font-weight:600">✓ 확정 대장과 1원 일치</span>
  </div>
 </div>
</div>"""

NET = """
<div class="win">
 <div class="bar"><span class="dot" style="background:#f37f74"></span><span class="dot" style="background:#f0b429"></span><span class="dot" style="background:#34c164"></span><span class="url">demo.safeclaw.kr · 포괄임금 설계</span></div>
 <div style="background:var(--k-canvas);padding:28px 32px">
  <p class="k-eyebrow">NET REVERSE · 세후 → 세전 역산</p>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:16px 0">
    <div><p class="k-label" style="margin-bottom:6px">목표 실수령액</p><input value="3,000,000"></div>
    <div><p class="k-label" style="margin-bottom:6px">비과세 (식대 등)</p><input value="200,000"></div>
  </div>
  <div class="k-block k-block--cream" style="padding:24px 28px;border-radius:16px">
    <p class="k-eyebrow">REQUIRED GROSS</p>
    <span class="k-display" style="font-size:44px">3,495,809원</span>
    <p class="k-label" style="margin-top:8px">1원 단위 일치 (exact) · 2026 요율</p>
  </div>
 </div>
</div>"""

TPL = """<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;box-sizing:border-box}} button{{border:none;cursor:pointer;font-family:inherit}}
body{{background:transparent;font-family:var(--k-font);color:var(--k-ink)}}
.win{{border-radius:12px;overflow:hidden;box-shadow:0 20px 48px rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.08)}}
.bar{{background:#25232f;display:flex;align-items:center;gap:7px;padding:11px 14px}}
.dot{{width:11px;height:11px;border-radius:50%;display:inline-block}}
.url{{margin-left:10px;color:#9a97a3;font-size:12px;font-family:var(--k-font-mono)}}
.row{{display:flex;justify-content:space-between;padding:11px 0;border-bottom:1px solid var(--k-hairline-soft);font-size:14px}}
.row span:first-child{{color:var(--k-ink-muted)}} .row .k-amount{{font-weight:600}}
input{{width:100%;border:1px solid var(--k-hairline);border-radius:8px;padding:10px 12px;background:var(--k-card);color:var(--k-ink);font-variant-numeric:tabular-nums;font-family:inherit;font-size:14px}}
{tokens}</style></head><body>{body}</body></html>"""

for name, body, h in [("wage", WAGE, 520), ("net", NET, 460)]:
    (OUT / f"shotpage_{name}.html").write_text(TPL.format(tokens=tokens, body=body), encoding="utf-8")
    print(name, h)
