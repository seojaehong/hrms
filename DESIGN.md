---
version: 2.0
name: Korea-HRMS-Ledger
description: "Korea HRMS 차기 디자인 시스템 「장부(Ledger)」. 웜 페이퍼 캔버스(#f6f5f4) 위에 순백 카드가 놓이고, 급여·세금·신고의 모든 숫자는 tabular-nums 딥 네이비(#0d253d)로 판각되며 확정 금액 아래에는 1px 네이비 '결산선'이 그어진다. 원칙은 하나 — 숫자는 절대 흔들리지 않는다. 7개 레퍼런스(figma·stripe·notion·vercel·linear·claude·apple) 패널 회의의 종합 결론으로, 웜 뉴트럴 온도 정렬과 절제된 마감은 claude/apple에서, 숫자 규율은 stripe에서, 구조는 linear에서 왔다. 파스텔 색블록은 내러티브 화면 전용으로 격리되고, 데이터 서피스는 모노크롬+네이비만 허용한다."

colors:
  # ── 캔버스 & 서피스 (Notion 웜 페이퍼 + Linear 래더) ──
  canvas: "#f6f5f4"
  card: "#ffffff"
  surface-1: "#f6f5f4"
  surface-2: "#ffffff"
  surface-3: "#fbfaf9"
  # 다크모드 예약 래더 (Linear 구조 × claude 웜 다크 온도 — 현행 무영향)
  surface-dark-1: "#181715"
  surface-dark-2: "#1f1e1b"
  surface-dark-3: "#252320"
  # ── 잉크 램프 (Vercel 명도 × claude 웜 캐스트 정렬) ──
  ink: "#171513"
  ink-muted: "#615d59"
  ink-faint: "#a39e98"
  on-inverse: "#f6f5f4"
  # ── 헤어라인 (claude: 잉크 선이 아니라 한 단계 낮은 서피스) ──
  hairline: "#e8e5e1"
  hairline-soft: "#f0eeeb"
  # ── 장부 잉크 (Stripe 시그니처) ──
  ledger-navy: "#0d253d"
  # ── 시맨틱 (글리프/배지 전용 — 서피스 금지) ──
  success: "#1ea64a"
  danger: "#dc2626"
  warn: "#f0b429"
  # ── 파스텔 색블록 (내러티브 화면 전용 — §Pastel Charter) ──
  block-lime: "#dceeb1"
  block-lilac: "#c5b0f4"
  block-cream: "#f4ecd6"
  block-mint: "#c8e6cd"
  block-pink: "#efd4d4"
  block-navy: "#1f1d3d"
  # ── 화이트라벨 기본값 (테넌트 오버라이드 가능 슬롯) ──
  tenant-accent: "#0d253d"

typography:
  display-num:
    fontFamily: appSans
    fontSize: 36px            # 데스크톱 56px, 와이드 64px
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: -0.025em   # 숫자 디스플레이 전용 상한
    fontVariantNumeric: tabular-nums
  serif-hero:
    fontFamily: serifDisplay  # Noto Serif KR — 리포트 표지·결산 히어로 전용
    fontSize: 30px            # 데스크톱 40px
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: -0.01em
  display:
    fontFamily: appSans
    fontSize: 28px            # 데스크톱 40px
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: -0.015em
  title:
    fontFamily: appSans
    fontSize: 20px            # 데스크톱 26px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: -0.01em
  headline:
    fontFamily: appSans
    fontSize: 17px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: -0.01em
  body:
    fontFamily: appSans
    fontSize: 14px            # 데스크톱 15px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: -0.025em   # 전역 base(자간 -25) 상속 — 사용자 확정 2026-07-13
  body-strong:
    fontFamily: appSans
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.6
    letterSpacing: 0
  amount:
    fontFamily: appSans
    fontSize: 15px
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: -0.01em
    fontVariantNumeric: tabular-nums
  numeric:
    fontFamily: appMono       # 라틴·숫자 전용 — 한글 라벨 금지
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.45
    letterSpacing: -0.01em
    fontVariantNumeric: tabular-nums
  mono-label-ko:
    fontFamily: appSans       # mono 열의 한글 라벨은 Pretendard로 대체
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.45
    letterSpacing: 0.05em
  caption:
    fontFamily: appSans
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0
  eyebrow:
    fontFamily: appMono
    fontSize: 11px            # 데스크톱 13px
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: 0.08em
    textTransform: uppercase

rounded:
  sm: 6px
  md: 8px
  lg: 24px                    # 파스텔 색블록 전용
  pill: 999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  section: 64px

components:
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 16px
    boxShadow: "inset 0 0 0 1px {colors.hairline}, 0 1px 1px #00000005, 0 2px 2px #0000000a"
  amount-settled:
    textColor: "{colors.ledger-navy}"
    typography: "{typography.amount}"
    borderBottom: "1px solid {colors.ledger-navy}"   # 결산선
    paddingBottom: 2px
  stat-tile:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ledger-navy}"
    typography: "{typography.display-num}"
    rounded: "{rounded.md}"
    padding: 16px 20px
  button-primary:
    backgroundColor: "{colors.tenant-accent}"
    textColor: "{colors.on-inverse}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.md}"
    padding: 10px 18px
    minHeight: 44px
  button-primary-active:
    transform: "scale(0.97)"                          # apple 프레스 규칙 (절제판)
  button-cta-narrative:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-inverse}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.pill}"                         # pill CTA — 내러티브 화면 전용
    padding: 12px 24px
    minHeight: 44px
  button-secondary:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.md}"
    padding: 10px 18px
    border: "1px solid {colors.hairline}"
    minHeight: 44px
  table-ledger:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    typography: "{typography.numeric}"
    rowBorder: "1px solid {colors.hairline-soft}"
    headerTypography: "{typography.caption}"
    headerColor: "{colors.ink-muted}"
  block-narrative:
    backgroundColor: "{colors.block-cream}"           # --t-block-* 슬롯
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    rounded: "{rounded.lg}"
    padding: 44px 48px                                # 모바일 20px
  modal:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.md}"
    boxShadow: "0 0 0 1px #00000008, 0 8px 16px #00000014, 0 24px 48px #0000001f"
  sticky-confirm-bar:
    backgroundColor: "{colors.canvas}"                # 80% 불투명 + backdrop blur
    textColor: "{colors.ink}"
    typography: "{typography.amount}"
    height: 64px
    backdropFilter: "saturate(180%) blur(20px)"
    borderTop: "1px solid {colors.hairline}"
  badge-danger:
    backgroundColor: "#fdeaea"
    textColor: "{colors.danger}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: 2px 8px
  badge-success:
    backgroundColor: "#e8f7ee"
    textColor: "{colors.success}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: 2px 8px
  focus-ring:
    outline: "2px solid {colors.tenant-accent}"
    outlineOffset: 2px
---

# Korea HRMS 디자인 시스템 v2 — 「장부(Ledger)」

## Overview

Korea HRMS는 급여·세금·4대보험 신고처럼 **틀리면 안 되는 숫자**를 다루는 한국 노무 SaaS다(Vue + Tailwind, PWA + 데스크톱). 이 시스템의 메타포는 **장부(Ledger)** — 잘 만든 종이 결산 장부의 정서를 디지털로 옮긴다.

- **바탕은 종이다.** 캔버스는 웜 페이퍼 `{colors.canvas}`(#f6f5f4), 그 위에 놓이는 데이터 카드만 순백 `{colors.card}`. 화면의 위계가 "종이 위의 문서"로 즉시 읽힌다.
- **숫자는 잉크다.** 모든 금액은 `tabular-nums` + 음수 트래킹, 확정 금액은 딥 네이비 `{colors.ledger-navy}`(#0d253d)로 판각되고 아래에 1px **결산선**이 그어진다. 시그니처 문장: **"숫자는 절대 흔들리지 않는다."**
- **마감은 조용하다.** 그림자는 위계가 아니라 무게다. 카드에는 헤어라인+초저알파 스택 섀도만, 컴포넌트 대부분은 서피스 색 변화와 헤어라인으로 구분한다.
- **색은 이야기할 때만 쓴다.** 파스텔 5블록 + pill CTA + radius 24px의 현행 Figma 언어는 내러티브 화면(홈·온보딩·리포트 히어로) 전용으로 격리한다. 테이블·대장·정산 화면에는 절대 들어오지 않는다.

### 원천별 기여 크레딧

| 원천 | 채택 요소 | 이 시스템에서의 역할 |
|---|---|---|
| **Notion** | 웜 페이퍼 캔버스 #f6f5f4 + 카드만 순백, 웜 잉크 램프(muted #615d59 / faint #a39e98) | 바탕 — "종이 위의 문서" 위계 |
| **Stripe** | 전 금액 tabular-nums + ls -0.01em 의무화, 금액 잉크 딥 네이비 #0d253d, 확정 금액 결산선 1px | 숫자 — 시스템의 심장 |
| **Vercel** | 잉크 명도 기준(#171717급), k-card 스택 섀도(0 1px 1px #00000005 + 0 2px 2px #0000000a) + 인셋 헤어라인, --k-focus-ring, 모달 섀도 토큰 | 마감 — 초저알파 정밀 마감 |
| **Linear** | 서피스 래더 --k-surface-1/2/3 (+ 다크 래더 예약 구조) | 구조 — 다크모드 대비, 현행 무영향 |
| **Figma(현행)** | 파스텔 5블록 + pill CTA + radius-lg 24px | 내러티브 — 용도 격리하여 유지 |
| **claude** (신규) | ① 잉크 온도 웜 정렬(#171717→#171513) ② 웜 헤어라인 #e8e5e1("한 단계 낮은 서피스" 원칙) ③ 세리프 히어로(리포트 표지 전용) ④ 다크 래더의 웜 다크 온도(#181715 계열) ⑤ "굵게보다 크게" 강조 원칙 | 온도 — 웜 뉴트럴의 일관성 |
| **apple** | ① 프레스 마이크로 인터랙션 scale(0.97) 단일 규칙 ② 라인하이트 컨텍스트 규율(display 1.05–1.3 / body 1.6 / dense 1.45) ③ backdrop-blur 스티키 확정 바 ④ 터치 타깃 44px 하한 ⑤ "색 변화가 곧 구분선" 내러티브 페이싱 ⑥ 웨이트 래더 고정(400/500/600/700 외 금지) | 절제 — 마감·인터랙션 규율 |

### claude / apple 검토 결과 — 기각 목록 (사유)

| 기각 요소 | 원천 | 사유 |
|---|---|---|
| 코럴 액센트 #cc785c | claude | 화이트라벨 --t-accent 슬롯과 충돌. 브랜드 액센트는 테넌트 소유, 코어는 네이비/잉크만 |
| 크림 서피스(#efe9de 등) 색조 카드 | claude | Notion 페이퍼 + 순백 카드 위계와 중복. 캔버스 온도는 하나만 |
| 세리프를 앱 크롬/헤딩 전반에 | claude | 한글 세리프(명조)는 UI 크롬에서 관공서 문서처럼 무거워짐 → 리포트 히어로로만 격리 채택 |
| 다크 페이지 페이싱(크림↔다크 밴드 교대) | claude | 데이터 SaaS에 부적합. 다크는 Linear 래더의 모드 전환으로만 |
| body 17px | apple | 급여 테이블·대장의 데이터 밀도에 과대. 14/15px 유지 |
| weight 300 | apple | 1차에서 이미 기각 — 한글 라이트 웨이트 붕괴 |
| radius 0 풀블리드 타일 | apple | 카드+헤어라인 위계와 충돌. 마케팅 문법 |
| 단일 블루 #0066cc 강제 | apple | "인터랙티브 = 단일 색" **규율만** 흡수(--t-accent 하나로 통일), 색 자체는 테넌트 소유 |
| 다크 마이크로 스텝 하드코딩(#272729 등) | apple | Linear 래더와 중복 — 기법(마이크로 스텝)만 다크 래더 값 산정에 반영 |
| caption-uppercase 아이브로 | claude | 현행 .k-eyebrow(mono uppercase ls 0.08em)와 중복 |

## Colors

### 캔버스 & 서피스
- **Canvas** `{colors.canvas}` #f6f5f4 — 페이지 바탕. 웜 페이퍼. 순백 금지.
- **Card** `{colors.card}` #ffffff — 데이터 카드·테이블·모달만 순백. 순백은 "문서"의 신호다.
- **Surface ladder** `--k-surface-1/2/3` — 1=캔버스, 2=카드, 3=카드 내 삽입 패널(#fbfaf9). 라이트에서는 미세하지만, 다크 전환 시 이 래더가 그대로 뒤집힌다.
- **Dark ladder (예약)** `--k-surface-dark-1/2/3` — #181715 / #1f1e1b / #252320. **claude의 웜 다크 온도** — 다크에서도 쿨 그레이가 아니라 웜 블랙. 현행 라이트 모드에는 아무 영향 없음.

### 잉크
- **Ink** `{colors.ink}` #171513 — 본문·헤딩. Vercel #171717의 명도에 **claude의 웜 캐스트를 정렬**한 값. 웜 캔버스 위 쿨 잉크는 온도가 어긋난다 — 잉크·캔버스·헤어라인은 같은 온도여야 한다.
- **Ink Muted** `{colors.ink-muted}` #615d59 — 보조 텍스트, 테이블 헤더.
- **Ink Faint** `{colors.ink-faint}` #a39e98 — 플레이스홀더, 비활성.
- **Ledger Navy** `{colors.ledger-navy}` #0d253d — **금액·결산 전용 잉크.** 확정된 돈만 이 색을 얻는다. 링크·버튼·장식에 유용(流用) 금지.

### 헤어라인
- **Hairline** `{colors.hairline}` #e8e5e1 / **Hairline Soft** #f0eeeb — claude 원칙: 헤어라인은 잉크 선이 아니라 **한 단계 낮은 서피스 톤**이다. 순회색(#e6e6e6)이 아닌 웜 그레이. 테이블 행 구분은 hairline-soft, 카드 윤곽은 hairline.

### 시맨틱
- Success #1ea64a / Danger #dc2626 / Warn #f0b429 — **글리프·배지 전용, 서피스 채색 금지.** 위험은 붉은 배지로만, 완료는 그린으로만 말한다.

### 파스텔 색블록
lime · lilac · cream · mint · pink · navy — 사용 범위는 §Pastel Charter 참조.

## Typography

### 폰트 패밀리
- **appSans**: `-apple-system, BlinkMacSystemFont, "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif`
- **appMono**: `"JetBrains Mono", "D2Coding", ui-monospace, monospace` — **라틴·숫자 전용.** mono 열의 한글 라벨은 `{typography.mono-label-ko}`(Pretendard 500 + ls 0.05em)로 대체.
- **serifDisplay**: `"Noto Serif KR", "Nanum Myeongjo", serif` — **claude 채택분.** 세리프의 "공증 문서" 정서가 장부 메타포와 시너지. 단 **리포트 표지·월 결산 히어로·온보딩 완료 화면에서만** 허용. 앱 크롬(내비·버튼·테이블 헤더)과 데이터 서피스 금지. weight 600 고정(700 금지 — claude: "굵게보다 크게").

### 스케일

| 토큰 | 모바일 → 데스크톱 | 웨이트 | LH | LS | 용도 |
|---|---|---|---|---|---|
| display-num | 36 → 56 → 64px | 700 | 1.05 | -0.025em | 금액 디스플레이(대시보드 총액). tabular-nums 필수 |
| serif-hero | 30 → 40px | 600 | 1.25 | -0.01em | 리포트 표지·결산 히어로 **전용** |
| display | 28 → 40px | 600 | 1.15 | -0.015em | 내러티브 화면 헤드 |
| title | 20 → 26px | 600 | 1.3 | -0.01em | 블록/섹션 타이틀 |
| headline | 17px | 600 | 1.4 | -0.01em | 카드 헤더 |
| body | 14 → 15px | 400 | 1.6 | 0 | 본문 (한글 LH 1.6) |
| amount | 15px | 700 | 1.4 | -0.01em | 인라인 금액. tabular-nums 필수 |
| numeric | 14px mono | 500 | 1.45 | -0.01em | 테이블 숫자 열 |
| caption | 12px | 500 | 1.4 | 0 | 라벨·배지 |
| eyebrow | 11 → 13px mono | 500 | 1.2 | +0.08em | 섹션 아이브로(uppercase) |

### 규율
1. **Stripe 숫자 의무** — 화면의 모든 금액은 `font-variant-numeric: tabular-nums` + `letter-spacing: -0.01em`. 예외 없음. 열이 흔들리는 숫자는 버그다.
2. **한글 트래킹 상한** — 음수 트래킹은 -0.01~-0.02em까지. **-0.025em은 숫자 디스플레이(display-num)에서만.** 한글 자소가 붙기 시작하는 지점이 상한 근거.
3. **웨이트 래더 고정** (apple 규율 이식) — 400(본문) / 500(라벨·mono) / 600(헤딩) / 700(금액·display-num)만. 300 금지(한글 붕괴), 사이값 금지. **700은 돈에만.**
4. **라인하이트 컨텍스트 규칙** (apple) — display류 1.05~1.3(타이트) / 본문 1.6(한글 보정) / 밀집 테이블 1.45. 본문을 1.5 아래로 조이지 말 것.
5. **강조는 굵게보다 크게** (claude) — 위계가 모자라면 웨이트를 올리지 말고 스케일을 한 단계 올린다. 세리프 히어로는 특히 600 초과 금지.

## Layout

- **스페이싱**: 4px 베이스 — 4 / 8 / 12 / 16 / 24 / 32 / 48 / section 64.
- **데이터 화면**: 캔버스 위 카드 스택, 카드 내부 패딩 16px(모바일)~24px(데스크톱), 카드 간 16px.
- **내러티브 화면**: 색블록이 레이아웃 단위. 블록 내부 44×48px(데스크톱)/20px(모바일), **한 뷰포트에 1블록 원칙.** 블록 사이 구분선 없음 — **색 변화가 곧 구분선**(apple).
- **터치 타깃** (apple): 모든 인터랙티브 요소 최소 44×44px. PWA 하단 액션은 48px.
- **최대 폭**: 데이터 화면 1200px, 리포트 뷰 880px(읽기 폭).

## Elevation & Depth

| 레벨 | 처리 | 용도 |
|---|---|---|
| 0 캔버스 | 없음 | 페이지 바탕 |
| 1 카드 | inset 헤어라인 + `0 1px 1px #00000005, 0 2px 2px #0000000a` | 데이터 카드·스탯 타일 (Vercel 스택 섀도) |
| 2 팝오버 | `0 0 0 1px #00000008, 0 4px 8px #0000000f` | 드롭다운·툴팁 |
| 3 모달 | `0 0 0 1px #00000008, 0 8px 16px #00000014, 0 24px 48px #0000001f` | 모달·시트 |
| blur | `saturate(180%) blur(20px)` + 80% 캔버스 | 스티키 확정 바 (apple) |

**섀도 철학** (Vercel × apple): 그림자는 위계 표현이 아니라 **떠 있는 것에만** 준다. 버튼·배지·테이블에 섀도 금지. 화면 대부분의 구분은 서피스 색과 헤어라인이 담당한다.

**포커스**: `--k-focus-ring: 0 0 0 2px var(--k-canvas), 0 0 0 4px var(--t-accent)` — 모든 인터랙티브 요소 공통.

**프레스** (apple): 모든 버튼의 active는 `transform: scale(0.97)` 단일 규칙. hover 스타일은 배경 1단계 변화까지만, 별도 섀도 부여 금지.

## Shapes

| 토큰 | 값 | 용도 |
|---|---|---|
| sm 6px | 배지·칩 |
| md 8px | 버튼·인풋·카드·모달 — 데이터 서피스 기본 |
| lg 24px | **파스텔 색블록 전용** — 데이터 카드에 사용 금지 |
| pill 999px | **내러티브 CTA 전용** — 데이터 화면 버튼은 md |

radius가 곧 모드 선언이다: 24px/pill이 보이면 내러티브, 8px이 보이면 장부.

## 결산선 (Settlement Rule) — 시그니처

**정의**: 확정 상태에 도달한 금액(급여 확정, 신고 마감, 정산 완료)의 숫자 아래에 그어지는 `1px solid var(--k-ledger-navy)` 밑줄. `border-bottom` + `padding-bottom: 2px`, 폭은 숫자 런 길이만큼(라벨 제외).

**규칙**:
1. 결산선은 **상태의 표현**이다. 임시 계산·미리보기·편집 중 금액에는 절대 긋지 않는다.
2. 결산선을 얻은 금액은 반드시 `{colors.ledger-navy}` 잉크 + weight 700 + tabular-nums — 세 가지가 한 세트다(`{component.amount-settled}`).
3. 화면당 결산선은 위계 최상위 금액에 우선한다. 테이블 전 행에 남발 금지 — 합계 행과 확정 셀에만.
4. 장식 밑줄(텍스트 링크 등)과 혼동될 위치에서는 사용하지 않는다.

종이 장부에서 결산 합계 아래 자를 대고 긋던 단선(單線)의 디지털 이식이며, 이 시스템의 브랜드 시그니처다.

## Pastel Charter — 파스텔 사용 범위 규정

| | 허용 | 금지 |
|---|---|---|
| **화면** | 홈 대시보드 히어로, 온보딩, 리포트 히어로/표지, 빈 상태(empty state), 마케팅·안내 | 테이블, 임금대장, 정산·신고 화면, 폼, 설정, 상세 뷰 |
| **요소** | 섹션 배경 블록(radius 24px), 내러티브 pill CTA | 카드 배경, 배지, 버튼(데이터 화면), 차트 시리즈 색 |
| **밀도** | 한 뷰포트 1블록 | 블록 위 블록 중첩 |
| **텍스트** | 블록 위 잉크는 `{colors.ink}` (navy 블록만 `{colors.on-inverse}`) | 파스텔 위 파스텔 텍스트 |

파스텔 위에 **금액을 배치할 수 없다.** 금액이 등장하는 순간 그 서피스는 데이터 서피스이며, 순백 카드로 승격해야 한다.

## 한글 이식 규칙 (Korean Adaptation)

라틴 중심 레퍼런스를 한글 UI로 옮길 때의 고정 규칙:

1. **트래킹**: 음수 -0.01~-0.02em 상한. -0.025em은 숫자 디스플레이만. 양수 트래킹은 eyebrow(+0.08em)와 mono-label-ko(+0.05em)만.
2. **웨이트**: 본문 400 / 라벨 500 / 헤딩 600 / 금액 700. thin·light(100~300) 전면 금지 — 한글 자형 붕괴.
3. **라인하이트**: 라틴 1.47 → 한글 1.6 보정(본문). 디스플레이는 1.05~1.3 유지 가능(짧은 런).
4. **mono**: 라틴·숫자 전용. 한글이 mono 폴백으로 렌더되면 오류 — 한글 라벨은 Pretendard 500 + ls 0.05em으로 분리.
5. **세리프**: Noto Serif KR 600 고정, 리포트 히어로 전용. 본문 명조 금지(관공서 문서화).
6. **단위 표기**: 금액 뒤 "원"은 숫자보다 1단계 작은 스케일 + ink-muted, 숫자와 2px 간격. 결산선은 "원"을 포함하지 않는다.

## 화이트라벨 레이어 (White-label)

```css
:root[data-tenant="acme"] {
    --t-accent: #7c3aed;          /* 오버라이드 가능 */
    --t-block-1: …; /* ~ --t-block-5 (파스텔 슬롯) */
}
```

- **오버라이드 가능**: `--t-accent`(버튼·포커스·링크), `--t-block-1~5`(내러티브 파스텔).
- **불변 코어**: 잉크 램프, 캔버스, 헤어라인, ledger-navy, 결산선, 시맨틱 색, 타이포 전부. **테넌트가 무엇을 하든 숫자는 항상 같은 네이비다** — 장부의 신뢰는 브랜딩보다 위에 있다.
- apple에서 이식한 규율: 인터랙티브 신호 색은 **--t-accent 하나뿐**이다. 두 번째 액센트를 도입하지 않는다.

## Components

- **`card`** — 순백 + inset 헤어라인 + 스택 섀도. 데이터의 기본 용기.
- **`stat-tile`** — 카드 위 display-num(ledger-navy). 라벨은 eyebrow, 확정 시 결산선.
- **`amount-settled`** — 결산선 세트(navy 700 tabular + 1px 밑줄).
- **`table-ledger`** — 헤더 caption/ink-muted, 숫자 열 numeric(우측 정렬), 행 구분 hairline-soft, LH 1.45. 합계 행 상단 `1px solid var(--k-hairline)` + 확정 합계에 결산선.
- **`button-primary` / `button-secondary`** — radius md, 44px 타깃, active scale(0.97), 포커스 링.
- **`button-cta-narrative`** — pill, ink 배경. 내러티브 화면 전용.
- **`block-narrative`** — 파스텔 블록, radius lg. §Pastel Charter 준수.
- **`sticky-confirm-bar`** (apple 이식) — PWA 급여 확정 플로우 하단 고정 바. blur + 80% 캔버스, 좌측 합계 금액(amount), 우측 확정 버튼. 확정 완료 시 금액에 결산선이 그어지며 바가 닫힌다.
- **`modal`** — 3단 스택 섀도 토큰, radius md.
- **`badge-danger` / `badge-success`** — 시맨틱은 배지로만.

## Migration — korea-tokens.css diff (문서 전용, 코드 미수정)

| 토큰 | 현행 | v2 | 비고 |
|---|---|---|---|
| `--k-ink` | #000000 | **#171513** | Vercel 명도 × claude 웜 정렬 |
| `--k-canvas` | #ffffff | **#f6f5f4** | Notion 페이퍼. 카드용 `--k-card:#ffffff` 신설 |
| `--k-ink-muted` | (없음, #6b7280 하드코딩) | **#615d59** | 신설 |
| `--k-ink-faint` | (없음) | **#a39e98** | 신설 |
| `--k-hairline` | #e6e6e6 | **#e8e5e1** | 웜 정렬 (claude) |
| `--k-hairline-soft` | #f1f1f1 | **#f0eeeb** | 〃 |
| `--k-surface-soft` | #f7f7f5 | `--k-surface-3` #fbfaf9로 개명·재정의 | Linear 래더 |
| `--k-surface-1/2/3` | (없음) | 신설 (+ dark-1/2/3 예약) | Linear 구조 + claude 웜 다크 |
| `--k-ledger-navy` | (없음) | **#0d253d** | Stripe — 금액 잉크 |
| `--k-font-serif` | (없음) | Noto Serif KR 스택 | claude — 리포트 히어로 전용 |
| `--korea-shadow-card` | none | 스택 섀도 2단 | Vercel |
| `--k-shadow-modal` | (없음) | 3단 스택 | 신설 |
| `--k-focus-ring` | (없음) | 2px 이중 링 | 신설 |
| `--k-press` | (없음) | scale(0.97) | apple |
| `.k-display` | ls -0.02/-0.025em | 유지 + `color: var(--k-ledger-navy)` 기본화 | 금액 디스플레이 |
| `.k-numeric` | tabular + ls -0.01em | 유지 (전 금액 의무 명문화) | Stripe |
| `--t-accent`, `--t-block-1~5` | (없음) | 화이트라벨 레이어 신설 | `:root[data-tenant]` |
| 파스텔 `--k-block-*` | 유지 | 유지 — 용도만 §Pastel Charter로 격리 | Figma |
| `--k-accent-magenta` | #ff3d8b | **폐기 예정** → `--t-accent` 흡수 | 단일 액센트 규율 (apple) |

## Do's and Don'ts

### Do
- 모든 금액에 tabular-nums + ls -0.01em. 확정 금액은 navy 700 + 결산선.
- 캔버스는 페이퍼, 카드만 순백. 잉크·헤어라인·캔버스는 같은 웜 온도로.
- 강조가 필요하면 굵게 말고 크게. 700은 돈에만.
- 데이터 화면은 radius 8px + 헤어라인, 내러티브 화면은 radius 24px + 파스텔.
- 버튼 active는 scale(0.97), 포커스는 --k-focus-ring — 예외 없이.

### Don't
- 파스텔 위에 금액 금지. 테이블·대장에 파스텔 금지.
- ledger-navy를 링크·버튼·장식에 유용 금지 — 돈의 색이다.
- 결산선을 임시 계산·미리보기 금액에 긋지 말 것.
- mono로 한글 렌더 금지. weight 300 금지. 본문 LH 1.5 미만 금지.
- 테넌트 오버라이드가 잉크·캔버스·헤어라인·결산선에 닿게 하지 말 것.
- 두 번째 액센트 색 도입 금지 — 인터랙티브 신호는 --t-accent 하나다.

## 다크모드 (Phase 3 확정 — 2026-07-12)

Linear 래더 구조 × claude 웜 다크 온도. 활성화: 저장 선호(`localStorage.k-theme`) > 시스템 `prefers-color-scheme`. 수동 토글은 설정 화면.

| 토큰 | 라이트 | 다크 |
|---|---|---|
| canvas / card / surface-3 | #f6f5f4 / #ffffff / #fbfaf9 | **#181715 / #1f1e1b / #252320** |
| ink / muted / faint | #171513 / #615d59 / #a39e98 | **#ece9e4 / #a39e98 / #6f6a64** |
| hairline / soft | #e8e5e1 / #f0eeeb | **#33302c / #292824** |
| **ledger-navy (돈의 색)** | #0d253d | **#9db8d6 — 밝은 네이비 틴트** (사용자 확정: 다크에서도 돈의 색은 네이비 정체성 유지, 결산선 동일) |
| success / danger / warn | #1ea64a / #dc2626 / #f0b429 | #34c164 / #ef6a6a / #f2c14e |
| 파스텔 블록 | 라이트 파스텔 5종 | 딥 틴트(#333d22 / #352b4d / #3a3427 / #263b2b / #3f2c2c) |

**전제 규율 (R7)**: 원시 `text-black`/`bg-white`/`border-black` 유틸 금지 — 토큰 유틸(`text-[var(--k-ink)]` 등)만. 알파 오버레이(`bg-white/55`)는 cream 히어로 관례로 1차 예외. KoreaLanding(.linear 다크 전용 표면)은 제외.
