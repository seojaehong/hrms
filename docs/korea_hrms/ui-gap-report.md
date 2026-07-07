# 노호 1차 런칭 — UI/UX 검증 결과 및 빅테크 격차 보고서 (2026-07-06 밤)

전수 점검 대상: 데스크(/app) + PWA(/hrms), 계정 = Administrator·류두선(ryoo@noho.im, HR Manager).
기준: "차단급은 즉시 수정, 격차는 등급표" (그릴 합의).

## A. 오늘 밤 발견 → 즉시 수정 완료 (차단급)

| # | 결함 | 원인 | 수정 |
|---|------|------|------|
| 1 | 사이트 전체 영문 노출 | 노호 사이트 System Settings language=en (프로비저닝 갭) | ko 전환 + Administrator/admin@noho.kr/ryoo 사용자 언어 ko |
| 2 | PWA 전 화면 영어 고정 | `translationsPlugin`이 이 Frappe 버전에 없는 `load_all_translations`를 호출 → 조용히 영어 폴백 | 엔드포인트 폴백(`get_boot_translations` 우선) + `{message}` 언랩. TDD 8케이스 (`frontend/tests/translationsPlugin.test.mjs`) |
| 3 | PWA 탭/앱 이름 "노란봉투법 HRMS" | 구프로젝트 브랜딩 잔재 (index.html·manifest·offline·설치 다이얼로그) | "Korea HRMS"로 4파일 교체 + 재빌드 |
| 4 | 직원 목록에 "급여테스트" 더미 노출 | QA 시드 잔재 (Active + 7월 Draft 슬립 1건) | Draft 슬립 삭제 + Inactive 처리 (급여 32건 무결성 재확인) |
| 5 | Branch → "나뭇가지" 오역 | Frappe 내장 ko 번역 오역 | 사이트 Translation 레코드 "지점" 추가 |
| 6 | 관리자 PWA 진입 불가 | Employee 미연결 (fail-closed 정상 동작이나 온보딩 누락) | 류두선(HR-EMP-00004) ↔ ryoo@noho.im 연결 + HR Manager 권한 |
| 7 | 데스크 홈 밋밋함 (오버뷰 부재) | Korea HR 워크스페이스에 Number Card 0개 | 카드 4종 추가: 재직 인원(32)·급여명세서(32)·실지급 합계(95.94M)·휴가 신청 대기(0) |
| 8 | ko.po 어색한 번역 ("요청 출근기록" 등) | 기계번역풍 msgstr | 서브에이전트로 PWA 노출 19문자열 교정 + 빈 msgstr 보충 (TDD `test_korea_po_quality.py`) |

## B. 남은 격차 — 등급표 (2차 백로그)

### B1. 중요 (다음 스프린트 — 노호 사용에 실영향)
| 항목 | 현상 | 제안 |
|------|------|------|
| 마감 대시보드 데모 폴백 | 노호에 Payroll Entry·마감 Draft가 없어 "Korea Demo Franchise Co" 예시 데이터 표시 (배너로 고지는 됨) | **6월 급여부터 Payroll Entry 경유 실플로우** 태워 실데이터 대시보드 전환. 밤중 실DB 시드는 위험해 보류 |
| 5월 슬립 32건 전부 Draft(미제출) | docstatus=0 | 노호 확정 후 일괄 Submit 운영 절차 확정 (제출=확정 의미 공유 필요) |
| 통화 표기 "KRW 95.94 M" | 서구식 축약 | 한국식 "9,594만" 포맷터 커스텀 |
| Frappe 코어 영문 잔존 | ~~Status/Draft/Department 등~~ → **07-07 코어 25종 hrms ko.po로 해소**. 잔여: "Add 직원"·"Filters" 등 조합 문자열 | frappe 코어 템플릿 문자열 — upstream 기여 대상 |
| AI Q&A 붙여쓴 질문 미매칭 | "수습기간중인직원도주휴수당을줘야하나요"(무공백) → 법령/판례 못 찾음. fail-safe 안내+딥링크는 정상 | retrieval 전처리에 한국어 형태소/공백 정규화 추가. AI v2(call_llm_with_context)에서 근본 해결 |

### B2. 브랜딩/폴리시 (브랜드 확정 후)
| 항목 | 현상 |
|------|------|
| PWA 상단 로고 텍스트 "Frappe HR" | 로그인 페이지 "Login to Frappe HR" 포함. 브랜드(SafeClaw 병용 vs NODE) 확정 후 일괄 교체 (로드맵 P2 디자인 스프린트) |
| 데스크탑 앱 아이콘 3종 영문 | Frappe Framework/ERPNext/Frappe HR |
| PWA 데스크톱 레이아웃 | 모바일 우선이라 데스크톱에서 우측 여백 큼 — 반응형 2컬럼 검토 |

### B3. 빅테크 대비 구조 격차 (로드맵)
- 오버뷰 카드에 **추이(spark line)·전월비** 없음 — Number Card percentage stats + Dashboard Chart 추가
- 온보딩 허브·조직도·평가 사이클 등(사용자 제시 템플릿 수준)은 Frappe HR 기본 모듈로 존재하나 한국화·활성화 미완 — 수요 확인 후 화면 승격
- AI HR 담당자(구글챗·PWA 챗)와 화면 딥링크 연동 강화

## C. 전수 기능 검증 결과 (서버사이드)
- 프레임워크-프리 코어: **87파일 · 1,222+ 테스트 전부 PASS**
- 급여 무결성: 32건, 실지급 총 **95,940,486원 = 기준값 1원 일치**, 내부수식 불일치 0
- 신고서: 승인게이트 blocked(정상) · 빈대상 fail-closed(정상) · 취득 5월 5명 실생성 OK (rrn_missing 처리 확인)
- 명세서 PDF: frappe.get_print 30.6KB 정상 생성
- 채널: 텔레그램(기존 가동) + **구글챗 신규 실가동** (JWT 이중모드·부가기능 스키마·바인딩 2건)


## D. 07-07 추가 라운드 (담당자 피드백 반영)
- 담당자 계정 전환: **문종원 moon@noho.im** (HR Manager, 데스크용 — 직원명단에 없어 PWA 미적용) / 류두선 ryoo@noho.im 보조(PWA 가능)
- **급여 외 기능 숨김**: 노호 사용자 3계정에 20개 모듈 차단 (영업·구매·재고·제조·CRM·자산·프로젝트·회계 등) — 데스크 사이드바·앱 아이콘 정리됨
- 데스크 코어 영문 25종 ko 번역 추가 (상태·임시저장·부서·이름·지점·재직 등) — 직원/명세서 목록 사실상 전면 한글화
- **DESIGN.md 신설** (google-labs-code/design.md 포맷): Korea HRMS 디자인 토큰 + Figma 레퍼런스 채택/기각 근거. P2 디자인 스프린트의 SSOT

## E. 07-07 3차 라운드 (전달 직전 정리)
- **[치명] SW 데스크 납치 수정**: sw.js가 모든 navigate를 가로채 /app이 PWA 화면으로 납치되던 사고 → /hrms 스코프 가드(isPwaNavigation, TDD) + 오염 캐시(pages-v1) 폐기
- **PWA 프론트 미번역 0건**: i18n 스윕 스크립트(.superpowers/sdd/sweep_i18n.py)로 __() 191개 전수 대조 → 56건 보충 (모바일 출퇴근·요일·상태 등)
- frappe 코어 폼/타임라인 118종 ko 보충 (First Name·Comments·Activity·상대시간) — frappe 공식 ko.po가 빈 msgstr인 것 실측
- **'한국' 접두어 제거**: 한국 사업장 프로필→사업장 프로필, 한국 페이롤→급여, 한국 HR→HR 홈 (워크스페이스+독타입명, 테스트 갱신)
- 잔여 minor: 날짜 "Tue, 7 July 2026" (dayjs ko locale 미적용), 데스크 조합 문자열 일부

## F. 07-07 디자인 마감 (ralph 루프)
- **US-P1 파랑 잔재 스윕**: frontend/src 의 `blue-[4-9]00` 계열 클래스를 DESIGN-figma 모노크롬/시맨틱으로 전량 교체 — grep 잔존 **0건**. 주요 CTA `bg-black text-white rounded-full`, focus ring `focus:ring-black/20`, 상태없는 배지 `bg-gray-100`, 성공/위험은 green/red 시맨틱 유지. 13개 뷰(InstallPrompt·AI챗·연차·결재인박스·모바일출퇴근·마감·구독·알림·오프라인·컴플라이언스·퇴직금·임금명세서) 대상.
- **US-P2 로그인 리디자인**: Login.vue 를 화이트 배경 → 중앙 `k-block k-block--lilac` 안 `k-card` 구조로. 상단 `.k-eyebrow "KOREA HRMS"` + 볼드 타이틀, 로그인 버튼 블랙 `!rounded-full` pill. submit/에러 로직 무변경(마크업/클래스만).
- **US-P3 날짜 한국식**: 영문식 `ddd, D MMMM YYYY` / `D MMM, YYYY` 표기를 `YYYY년 M월 D일 (ddd)` 로 통일. KoreaMobileCheckin·CheckInPanel·AttendanceCalendar 3종. `grep MMMM` 잔존 0건.
- **US-P4 한국식 금액 유틸 + 데스크 훅**: `frontend/src/utils/koreanCurrency.js` `formatKoreanCurrencyShort` 순수함수(1만미만 원·1만~1억 만원절사·1억+ 억원 소수1자리) + `koreanCurrency.test.mjs` **7 케이스 GREEN**. `hrms/public/js/korea_desk_format.js`(frappe 전역 가드 IIFE, `shorten_number` 오버라이드) 신설 + `hooks.py` app_include_js 등재.
- **US-P5 온보딩 PDF 갱신**: noho_onboarding.html '관리자 화면' 표를 현행 6메뉴(급여/퇴직금/연차/근태/사업장·직원/감사·컴플라이언스)로 갱신, '한국 ' 접두어 제거. headless Chrome 으로 노호_KoreaHRMS_시작안내_20260707.pdf 재생성(138KB).
- **검증**: `scripts/run_korea_regional_smoke.py` → `passed: true`, `failed_count: 0` · koreanCurrency 테스트 7/7 · `blue-[4-9]00` 잔존 0.
