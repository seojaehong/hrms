---
version: alpha
name: Korea-HRMS
description: "신뢰 우선의 한국 노무 SaaS 캔버스. 화이트 서피스 위에 단일 블루(#0066ff)를 아껴 쓰는 모노-액센트 시스템 — 급여·세금·신고처럼 '틀리면 안 되는' 숫자를 다루므로 장식보다 판독성이 우선한다. 데이터는 카드·스탯 타일·테이블로 정돈되고, 위험(마감 차단·검증 실패)은 붉은 배지로만, 완료는 그린으로만 말한다. 모바일 PWA와 데스크(Frappe) 두 표면이 같은 토큰을 공유한다."

colors:
  primary: "#0066ff"
  on-primary: "#ffffff"
  ink: "#1a1d21"
  ink-soft: "#6b7280"
  canvas: "#ffffff"
  surface-soft: "#f7f8fa"
  hairline: "#e5e7eb"
  hairline-strong: "#d7dce3"
  brand-navy: "#0b3ea8"
  semantic-success: "#16a34a"
  semantic-danger: "#dc2626"
  semantic-warning: "#f0b429"
  badge-danger-bg: "#fdeaea"
  badge-success-bg: "#e8f7ee"
  block-info: "#eef4ff"
  block-warn: "#fff8e6"
  overlay-scrim: "#000000"

typography:
  display:
    fontFamily: appSans
    fontSize: 24px
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: -0.4px
  headline:
    fontFamily: appSans
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: -0.2px
  stat-value:
    fontFamily: appSans
    fontSize: 22px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: -0.3px
  body:
    fontFamily: appSans
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0
  body-strong:
    fontFamily: appSans
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.55
    letterSpacing: 0
  caption:
    fontFamily: appSans
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.35
    letterSpacing: 0.1px
  numeric:
    fontFamily: appMono
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0

rounded:
  sm: 6px
  md: 8px
  lg: 12px
  pill: 999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  section: 48px

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.md}"
    padding: 8px 16px
  button-secondary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.md}"
    padding: 8px 16px
  stat-tile:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.stat-value}"
    rounded: "{rounded.md}"
    padding: 12px 16px
  card:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 16px
  badge-status-danger:
    backgroundColor: "{colors.badge-danger-bg}"
    textColor: "{colors.semantic-danger}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: 2px 8px
  badge-status-success:
    backgroundColor: "{colors.badge-success-bg}"
    textColor: "{colors.semantic-success}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: 2px 8px
  info-note:
    backgroundColor: "{colors.block-warn}"
    textColor: "{colors.ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: 8px 12px
  quick-link-row:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 12px 16px
---

## Overview

Korea HRMS는 급여·4대보험·노무 데이터를 다루는 **신뢰-우선(trust-first)** 시스템이다.
디자인의 제1원칙은 "숫자가 주인공"이다: 실지급액·공제액·인원수는 `{typography.stat-value}`와
`{typography.numeric}`로 크게, 나머지 장식은 물러난다.

- 서피스는 `{colors.canvas}` 화이트 단일. 섹션 구분은 색이 아니라 `{colors.hairline}` 헤어라인과 여백.
- 액센트는 `{colors.primary}` 블루 **하나**. Figma의 pastel color-block 같은 다색 블록은 쓰지 않는다 —
  노무 도메인에서 색은 곧 의미(위험/완료)여야 하기 때문.
- 상태는 배지로만: 위험/차단 `{components.badge-status-danger}`, 완료 `{components.badge-status-success}`.
- 두 표면(모바일 PWA `/hrms`, 데스크 `/app`)이 같은 토큰을 공유하고, PWA는 mobile-first 1컬럼이다.

## 참고: Figma 마케팅 시스템에서 가져올 것 / 버릴 것

DESIGN-figma.md(Figma 마케팅 분석) 대비 우리의 선택:

**가져온다**
- 토큰 이름으로 컴포넌트를 지칭하는 규율 (`{components.stat-tile}` 식 참조)
- "weight로 위계를 만든다" — 본문 14px 고정, 굵기(400/600/700)로만 강조
- pill 계열 상태 표시(배지)와 촘촘한 letter-spacing의 디스플레이 타입
- 섹션 사이 화이트 리듬 (`{spacing.section}`)

**버린다 (도메인 부적합)**
- 다색 pastel color-block 스토리텔링 — 급여 화면에서 색은 의미 없는 장식이 될 수 없다
- 86px 디스플레이 타입 — 업무 도구의 최대 타이틀은 `{typography.display}` 24px
- 마퀴 스트립·프로모 배너 — 마케팅 표면이 아니다

## Do's and Don'ts

### Do
- 금액·인원은 항상 `{typography.numeric}`(탭ular) 정렬, 원 단위 1의 자리까지.
- 위험 상태(마감 차단, 검증 실패, 미신고)는 `{colors.semantic-danger}` 계열 배지 하나로만 표시.
- 새 화면은 스탯 타일 행(최대 4개) → 카드/테이블 순서로 구성 (Korea HR 워크스페이스 패턴).
- 안내·주의 문구는 `{components.info-note}` (노란 좌측 보더) 하나로 통일.
- 한국어가 1급 시민: 모든 노출 문자열은 ko.po에 등재하고 `test_korea_po_quality.py`에 assert를 남긴다.

### Don't
- 새 액센트 색 추가 금지. 두 번째 브랜드 색이 필요해 보이면 위계 문제이지 색 문제가 아니다.
- 급여 수치를 축약("95.94 M")하지 말 것 — 한국식 단위(9,594만원) 또는 전체 자릿수.
- 그림자로 위계 만들지 말 것 — 헤어라인과 여백이 먼저다.
- 영문 폴백 문자열을 그대로 배포하지 말 것 (브랜딩 잔재 "Frappe HR" 사고 재발 방지).

## Iteration Guide

1. 컴포넌트는 `components:` 토큰 이름으로 지칭해 한 번에 하나씩 다듬는다.
2. 색을 추가하고 싶다면 먼저 semantic(성공/위험/경고) 매핑이 불가능한지 자문한다.
3. `npx @google/design.md lint DESIGN.md` 로 참조 무결성·명도 대비를 검사한다.
4. PWA 컴포넌트 변경 시 `node --test frontend/tests/` 회귀 필수.

## Known Gaps

- appSans = 현재 시스템 폰트 스택(Malgun Gothic/Noto Sans KR). 브랜드 확정(P2 스프린트) 시 서체 교체 예정.
- 데스크(Frappe)는 프레임워크 테마 제약으로 토큰 일부만 적용 가능 — theme_color·워크스페이스 구성으로 근사.
- 다크 모드 미정의.
