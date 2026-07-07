# Korea HRMS 디자인 리비전 계획 (DESIGN-figma.md 기반)

기준 문서: `~/Downloads/DESIGN-figma.md` (Figma 마케팅 시스템 분석, design.md 포맷) + 레포 루트 `DESIGN.md`(현행 토큰).
원칙: **Figma의 "시스템 규율"은 전면 채택, "마케팅 표현"은 표면별 선별 채택.**

## 0. Figma 시스템에서 무엇을 가져오나 — 표면별 매핑

| Figma 원칙 | 급여/데이터 화면 (PWA·데스크) | 온보딩·랜딩·빈 화면 |
|---|---|---|
| 모노크롬 코어 + 액센트 절제 | ✅ 전면 채택 — primary(#0066ff→흑백 위주로 후퇴 검토) 버튼·선택상태에만 | ✅ |
| **pill 버튼 단일 형태** | ✅ 모든 CTA pill 통일 (현재 md 라운드 혼재) | ✅ |
| weight로 위계 (mid-gray 금지) | ✅ ink 단일 + 400/600/700 — 현행 ink-soft(#6b7280) 사용처 축소 | ✅ |
| mono 서체 = 분류 라벨 전용 | ✅ eyebrow/caption을 mono·uppercase로 — 섹션 마커, 상태 코드 | ✅ |
| 파스텔 color-block 스토리텔링 | ❌ 데이터 화면 금지 (색=의미 원칙 유지) | ⚠️ 제한 채택 — 온보딩 스텝·빈 상태(empty state) 일러스트 배경 1블록만 |
| 디스플레이 대형 타입(-tracking) | ⚠️ 대시보드 히어로 수치에만 (stat-value 22→28px, -0.4px) | ✅ 환영 화면 |
| 색-블록 사이 화이트 리듬 | ✅ 섹션 간격 `spacing.section` 일관화 | ✅ |

## 1. Phase D1 — PWA 토큰 정착 (반나절, 코드)
대상: `frontend/tailwind.config.js` + 주요 뷰 6종 (Home, KoreaPayrollClosing, 연차/근태 대시보드, Login, BaseLayout)
1. DESIGN.md 토큰을 tailwind theme로 이식 (colors/rounded/spacing) — 하드코딩 hex 제거
2. 버튼 전부 pill (`rounded-full`) + primary/secondary 2종으로 수렴
3. `typography.numeric`: 금액에 `tabular-nums` 적용, **한국식 단위 포맷터** (95,940,486원 · 9,594만) 공용화
4. Login: 파스텔 1블록(block-info) 배경 + 디스플레이 타입 환영 문구 — Figma식 첫인상
- 검증: `node --test frontend/tests/` + 스크린샷 비교 (before/after)

## 2. Phase D2 — 대시보드 히어로 (반나절)
1. 마감 대시보드 다크 히어로 유지하되 Figma 리듬 적용: eyebrow(mono·uppercase) → 디스플레이 기간 → 스탯 3타일
2. Korea HR 워크스페이스 Number Card에 전월비/스파크라인 (Frappe Dashboard Chart)
3. 빈 상태(empty state): 파스텔 1블록 + 다음 행동 CTA(pill) — "데모 폴백" 대신 안내형

## 3. Phase D3 — 데스크 근사(近似) (1일)
Frappe 테마 제약 내: theme_color·워크스페이스 아이콘·Number Card 색상만 토큰 정렬. 전면 커스텀은 비용 대비 낮음 → PWA를 대표 표면으로 승격하는 전략 유지.

## 4. Phase D4 — 브랜드 게이트 (브랜드 확정 후)
서체(현 시스템 폰트 → Pretendard 검토: Figma의 fine-weight 원칙에 부합하는 국문 variable), 로고, block 팔레트 확정. `npx @google/design.md lint DESIGN.md` CI 편입.

## 실행 규칙
- 매 Phase: DESIGN.md 토큰 갱신 → lint → 구현 → `node --test` 회귀 → 노호 사이트 스크린샷 검증
- 컴포넌트는 토큰 이름으로 지칭 (`{components.button-primary}`) — PR 설명에도 동일
- 색 추가 요청은 semantic 매핑 불가 증명 후에만 (DESIGN.md Don't 조항)

## 일정 제안
| Phase | 소요 | 시점 |
|---|---|---|
| D1 토큰+pill+포맷터 | 0.5일 | 이번 주 (노호 안착과 병행 가능) |
| D2 히어로+카드 | 0.5일 | D1 직후 |
| D3 데스크 근사 | 1일 | 다음 주 |
| D4 브랜드 게이트 | - | 브랜드 확정 후 (로드맵 P2) |
