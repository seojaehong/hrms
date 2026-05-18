# Korea HRMS 디자인 결정 사전 자료 (2026-07 sprint)

작성: 2026-05-18 | 상태: 사전 준비 / 결정 미완료

---

## 현황 파악

### 현재 사용 중인 색값 인벤토리 (Korea*.vue 전체)

| 위치 | 값 | 용도 | 토큰 후보 |
|---|---|---|---|
| KoreaAttendanceDashboard | `var(--color-primary, #2563eb)` | 버튼, 합계 배경 | `--korea-primary` 결정 시 fallback 교체 |
| KoreaAttendanceDashboard | `var(--color-text-primary, #111827)` | 입력 텍스트 | 기존 Tailwind `text-gray-900` 사용 권장 |
| KoreaAttendanceDashboard | `var(--color-surface, #fff)` | 입력 배경 | 기존 `bg-white` 사용 권장 |
| KoreaAttendanceDashboard | `#fbbf24` (bare) | 마감 적용 버튼 | `--korea-warn: #ffa500`와 다름 → 7월에 맞춤 |
| KoreaAIChat | 내용 버튼은 텍스트 있음 | — | — |
| KoreaComplianceDashboard/CategoryDetail | `cat.badgeStyle` / `categoryDetail.badgeStyle` | JS에서 동적 주입 | 7월에 JS → CSS class 리팩터 권장 |

**주의:** `--color-primary`는 `--korea-primary`와 다른 색(#2563eb vs #0066ff). 7월 결정 전 swap 금지.

---

## 3안 비교 (7월 결정 대상)

### 안 A — NODE 디자인 차용 (node.pe.kr 시스템 재사용)

- 장점: 브랜드 일관성 (서재홍 개인 브랜드 + HRMS 연계), 구축 비용 절감
- 단점: HRMS는 B2B SaaS, node.pe.kr은 개인 블로그 → 사용 맥락 불일치
- 색감: node.pe.kr 현행 팔레트 (확인 필요 — 코랄 등 임의 적용 금지 원칙)
- 타이포: Pretendard (공유 가능)
- 컴포넌트: 기존 NODE 컴포넌트는 HRMS 데이터 테이블/카드에 직접 맞지 않음

### 안 B — HRMS 전용 신규 브랜드

- 장점: B2B 맥락에 최적화, 확장성, 화이트라벨 대응
- 단점: 디자인 리소스 필요, sprint 비용 높음
- 색감 candidate: Primary `#2563eb` (현행) → 7월 검토, Accent `#ff6b35`
- 타이포: Pretendard + Inter (한/영 혼용 최적)
- 컴포넌트: Tailwind + Ionic 조합 유지, 공통 카드/배지/버튼 컴포넌트화

### 안 C — 혼합 (NODE 타이포 차용 + HRMS 색상 신규)

- 장점: 타이포 일관성 + 색상 자유도
- 단점: 두 시스템 유지 부담
- 색감: 안 B Primary + NODE 타이포/여백 시스템
- 추천 조건: NODE 디자인이 Figma/토큰으로 구조화되어 있을 경우

---

## 타이포그래피 현황 및 결정 사항

| 항목 | 현재 | 7월 후보 |
|---|---|---|
| 영문 font | `InterVar` (Ionic 기본) | Inter 유지 또는 Pretendard |
| 한글 font | 없음 (시스템 폰트 fallback) | Pretendard (가중치 다양, 가독성 우수) |
| 한자/특수문자 fallback | 시스템 폰트 의존 | `Apple SD Gothic Neo`, `Noto Sans KR` 추가 (토큰에 이미 포함) |
| 기본 크기 | 16px (Tailwind 기본) | 유지 |
| 줄 높이 | Tailwind leading 기본 | 모바일 가독성 위해 `leading-relaxed` (1.625) 표준화 검토 |
| 한국어 body | `text-sm` (14px) 비중 높음 | 최소 `text-sm` 유지 (모바일 PWA 한계) |

**토큰 준비 완료:** `--korea-font-family`에 Pretendard + 한글 fallback 체인 정의됨.
**주의:** `--ion-font-family`는 변경 금지 (Ionic 컴포넌트 영향).

---

## 접근성 점검 결과 (2026-05-18 기준)

### 수정 완료
- `KoreaAIChat`: 전송 버튼 (아이콘 전용) → `aria-label="메시지 전송"` 추가
- `KoreaMobileCheckin`: 뒤로가기 버튼 → `aria-label="뒤로 가기"` 추가
- `KoreaMobileCheckin`: 셀카 삭제 버튼 (`×`) → `aria-label="셀카 삭제"` 추가

### 7월 sprint 전 개선 권장 (시각 변경 포함이므로 이번 pass 제외)
- `text-gray-400` on white background: WCAG AA 미달 가능성 (contrast ratio ~3.4:1).
  영향 파일: KoreaAnnualLeaveDashboard, KoreaAttendanceDashboard 다수 사용.
  대안: `text-gray-500` (contrast ~4.6:1) 또는 `text-gray-600`.
- `text-gray-300` on dark background (KoreaAnnualLeaveDashboard line 184): 확인 필요.
- `KoreaComplianceDashboard/CategoryDetail`의 `badgeStyle` JS 주입: 색상 대비 런타임 검증 불가 → CSS class 방식으로 전환 권장.
- 버튼 다수: 내부에 텍스트 있음 → aria-label 불필요. 단, 아이콘 전용 버튼은 계속 점검.

### 대비율 계산 참고 (주요 조합)
- `text-gray-500 (#6b7280)` on white: ~4.63:1 → WCAG AA 통과
- `text-gray-400 (#9ca3af)` on white: ~3.38:1 → 미달 (14px 이하)
- `text-white` on `#2563eb` (primary button): ~4.52:1 → 통과
- `text-white` on `#fbbf24` (amber button): ~1.9:1 → 미달, 텍스트를 `text-gray-900`으로 유지 (현행 올바름)

---

## 7월 sprint 결정 사항 체크리스트

- [ ] 안 A/B/C 중 1안 선택
- [ ] Primary 색 확정 (`#2563eb` 현행 vs `#0066ff` candidate)
- [ ] Accent 색 확정 (`#ff6b35`)
- [ ] `#fbbf24` (마감 버튼 amber) → `--korea-warn`으로 흡수 or 유지
- [ ] Pretendard CDN or 번들 방식 결정
- [ ] `--ion-font-family` 변경 여부 (Ionic 전반 영향)
- [ ] `text-gray-400` → `text-gray-500` 일괄 교체 (접근성)
- [ ] `badgeStyle` JS 동적 주입 → CSS class 리팩터 여부
- [ ] NODE 디자인 차용 시 Figma 토큰 sync 방법 결정
- [ ] 화이트라벨 다국어 지원 시 폰트 전략 (일본어 등)
