# 디자인 리비전 전수 개선 — 「장부(Ledger)」 v2 정합 스윕

날짜: 2026-07-12 · 상태: 승인됨 (사용자 "고") · 기반: `DESIGN.md` v2.0 Korea-HRMS-Ledger

## 목적

DESIGN.md v2가 확정된 뒤에도 화면 구현이 규율을 따라오지 못했다.
실측: Korea 뷰 15/15가 데이터 화면인데 pill+검정 버튼(내러티브 문법), `k-amount` 채택 1/15,
다크모드 코드 0줄, 토큰 래더 값 문서 불일치. 이 스펙은 35개 화면 전부를 v2 규율로 정렬하고,
재발을 게이트로 차단한다.

## 결정 사항

- **버튼 표준 = DESIGN.md 원문 준수**: 데이터 화면 버튼은 `tenant-accent`(기본 #0d253d) 배경 +
  radius 8px + 44px 타깃 + active scale(0.97) + focus-ring. pill·검정 버튼은 내러티브 화면 전용.
- **화면 로직 무수정**: 클래스·토큰·마크업 스타일만 바꾼다. API·데이터 흐름·컴포넌트 구조 불변.
- **매 Phase 종료 조건**: `run_korea_tests.sh` 그린 + 디자인 감사기 위반 0 + 라이브 스크린샷 리뷰 +
  노호(실고객) 무영향 확인.

## Phase 0 — 규율 감사기 (선행, 이 세션에서 직접 구현)

`scripts/design_audit.py` — frontend/src/views/**를 정적 스캔, 규칙 위반 리포트.

| # | 규칙 | 검출 패턴 |
|---|---|---|
| R1 | 데이터 화면 pill 금지 | korea 데이터 뷰의 `rounded-full` (내러티브 화이트리스트 제외) |
| R2 | 데이터 화면 검정 버튼 금지 | `bg-black` 버튼 (동일 화이트리스트) |
| R3 | 금액 잉크 의무 | 금액 바인딩(formatKRW 등)에 `k-amount`/`k-display`/`k-settled` 미적용 |
| R4 | 하드코딩 색 금지 | `text-gray-*`, `bg-gray-*`, 인라인 `#hex` (토큰 파일 제외) |
| R5 | 파스텔 차터 | 테이블·정산·폼 화면의 `k-block--*` 사용 |
| R6 | ledger-navy 유용 금지 | 버튼·링크에 `--k-ledger-navy` 직접 사용 |

- 화이트리스트: 내러티브 화면 목록(홈 히어로·온보딩·리포트 표지)을 스크립트 상수로 관리.
- `scripts/run_korea_tests.sh`에 편입 — 위반 신규 유입 시 게이트 실패.
- R3는 휴리스틱(오탐 허용): 경고 레벨로 시작, 안정화 후 에러 승격.

## Phase 1 — PWA 데이터 화면 정합 (랄프 루프)

- `korea-tokens.css`에 `.k-btn-primary` / `.k-btn-secondary` 신설
  (tenant-accent·radius 8·min-height 44·press·focus-ring / 순백+헤어라인).
- Korea 15개 화면 + 베이스 화면 중 데이터 화면: pill·검정 버튼 전량 치환.
- 금액 표기 전수: `k-amount`(임시·인라인) / `k-settled`(확정, 화면당 최상위 1개) 적용.
  "원" 단위는 숫자보다 1단계 작은 스케일 + ink-muted + 2px 간격(결산선은 "원" 제외).
- 토큰 정정: `--k-surface-1/2/3` = #f6f5f4/#ffffff/#fbfaf9 (DESIGN.md 일치),
  `--k-accent-magenta` 참조 제거 완료 확인.
- 스토리 단위: 화면 1개 = 스토리 1개 (감사기 위반 목록이 곧 acceptance criteria).

## Phase 2 — 내러티브 화면

- 파스텔 차터 감사: 금액이 파스텔 블록 위에 있으면 순백 카드로 승격.
- 홈 대시보드 "한 뷰포트 1블록" 정리, 블록 사이 구분선 제거(색 변화가 구분선).
- serif-hero(Noto Serif KR 600)는 리포트 표지·결산 히어로에만 — 크롬 유입 검사.

## Phase 3 — 다크모드 활성화 (선행 설계 필요 — 별도 승인 지점)

- **DESIGN.md 개정 선행**: 다크 잉크 램프(ink/muted/faint의 다크 값), 다크 헤어라인,
  다크에서의 ledger-navy 대응(어두운 배경에서 네이비 불가시 → 밝은 네이비 틴트 신설),
  다크 결산선 색. 개정안을 사용자 승인 후 구현.
- 토큰: `--k-surface-dark-1/2/3`(#181715/#1f1e1b/#252320) 신설,
  `:root[data-theme=dark]` 오버라이드 + `prefers-color-scheme` 기본 + 수동 토글.
- 대상: PWA 전 화면. 마케팅 랜딩은 원래 다크(무영향).

## Phase 4 — 마케팅 랜딩 (hr.safeclaw.kr)

- Linear 다크 문법 유지. 폴리시: 자간·섹션 페이싱·CTA 마이크로 인터랙션 정밀화.
- 목업 스크린샷을 실제 PWA(라이트 Ledger) 캡처로 교체.
- 갱신 경로: `scripts/landing/build_landing.cjs` → docker cp (기존 절차).

## 검증

- Phase 0 감사기 자체는 TDD(픽스처 뷰 문자열로 red→green).
- 각 Phase: 게이트 그린 + 감사기 0건 + 데모사이트(hrms.localhost) 라이브 스크린샷 +
  noho 스모크(홈·명세서 200, 랜딩 미노출).
- 롤백: 커밋 단위 revert + bench build 재실행.

## 비범위 (YAGNI)

- 새 기능·화면 추가 없음. 컴포넌트 리팩터링(구조 변경) 없음.
- 차트 색 시스템, PDF 명세서 디자인, 이메일 템플릿 — 별도 사이클.
