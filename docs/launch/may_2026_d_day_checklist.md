# 5월말 런칭 D-Day 체크리스트

> 목표: 2026-05-31 공식 베타 announcement | 첫 NOHO 미팅: D-3 (5/28)

---

## D-7 (5/24, 일요일) — 기술/인프라 확정

### 코드 / PR
- [ ] 모든 진행 중인 PR 머지 완료 (develop 기준)
- [ ] Gate 15 (한국 로컬라이제이션 batch 1) 머지 완료
- [ ] `develop` → 스테이징 배포 검증 (https://hrms.safeclaw.kr 기준)
- [ ] 프론트엔드 빌드 오류 없음 (`yarn build` 통과)
- [ ] 한국 regional smoke 전체 통과 (`python3 scripts/run_korea_regional_smoke.py`)

### 모니터링 / 알림
- [ ] Frappe 서버 업타임 모니터링 설정 확인 (UptimeRobot 또는 동급)
- [ ] 알림 임계값 설정 검증:
  - 서버 다운 → 5분 이내 텔레그램 알림
  - 디스크 사용량 80% 초과 → 알림
  - 메모리 사용량 90% 초과 → 알림
- [ ] Docker 컨테이너 자동 재시작 설정 확인 (`restart: unless-stopped`)
- [ ] 백업 스크립트 실행 확인 (`docs/operations/backup_recovery.md` 기준)
- [ ] 백업 최신 성공 일시 확인 (D-7 기준 48시간 이내)

### 데모 환경
- [ ] 데모 계정(demo.hr.manager@node.pe.kr) 접속 확인
- [ ] 데모 데이터 seed 최신 상태: 직원 2명 / 사업장 2개 / 마감 Draft 1건
- [ ] fixture fallback UI 정상 작동 확인
- [ ] HRMS PWA `/hrms` 모바일 레이아웃 확인 (실기기 or DevTools)

### 문서
- [ ] `docs/announcements/2026_05_hrms_beta_launch.md` 최종 검토
- [ ] `docs/onboarding/quickstart_5min.md` 최종 검토
- [ ] `docs/onboarding/operator_manual.md` 최종 검토
- [ ] 베타 신청 폼 구현 완료 (Google Form 또는 Notion) + 링크 확보

### 커뮤니케이션 채널
- [ ] 슬랙 `#hrms-beta` 채널 개설 완료
- [ ] 슬랙 `#hrms-beta-signups` 알림 채널 개설 + Zapier 연동
- [ ] 카카오 비즈니스 채널 가입 완료 (알림톡 발송용, 베타 기간 중 활성화 목표)
- [ ] abc@winhr.co.kr 이메일 응답 템플릿 준비

---

## D-5 (5/26, 화요일) — 콘텐츠 / 세일즈 준비

- [ ] node.pe.kr 게시물 초안 최종 확정 (발행 준비 상태로 임시저장)
- [ ] 데모 영상 촬영 완료 (5분, 스크린레코딩 + 간단 설명)
  - 로그인 → 급여마감 대시보드 → 마감 세션 → Salary Slip → 임금명세서 발송
- [ ] 데모 영상 유튜브/드라이브 업로드 + 링크 확보
- [ ] 베타 신청 폼 링크 announcement 문서에 삽입 완료
- [ ] NOHO 첫 미팅 어젠다 (`docs/sales/noho_first_meeting_deck.md`) 최종 검토
  - 노호 현 직원 수 / 급여일 / 매장 수 실제 수치로 교체 완료
- [ ] 베타 5사 타깃 리스트 2~3개 추가 준비 (NOHO 외 다른 자문사 포함 검토)

---

## D-3 (5/28, 목요일) — NOHO 첫 미팅 + 베타 컨택 시작

### NOHO 미팅
- [ ] NOHO 첫 미팅 진행 (조서형 대표 / 류두선 COO)
  - 현황 파악 (급여 마감 방식, 직원 수, 매장 수)
  - 라이브 데모 5분
  - 베타 조건 제안 + 구두 동의
  - 다음 단계 확정 (슬랙 채널, CSV 전달 일정)
- [ ] 미팅 후: 슬랙 `#hrms-beta-noho` 채널 생성 + NOHO 담당자 초대
- [ ] NOHO 직원 마스터 CSV 전달 요청 (D+3 기한 부여)

### 베타 컨택 시작
- [ ] 베타 신청 폼 링크 이메일 발송 (자문사 네트워크 대상, 5~10개사)
- [ ] 자문사 Slack/카카오 커뮤니티에 간단 소개 메시지 게시 (재홍님 직접)
- [ ] 신청 현황 `#hrms-beta-signups` 채널에서 모니터링 시작

---

## D-day (5/31, 일요일) — 공식 런칭

### 콘텐츠 발행
- [ ] node.pe.kr 게시물 발행 (`2026_05_hrms_beta_launch.md` 기준)
  - 카테고리: AI×노동 (또는 현장)
  - 데모 영상 임베드
  - 베타 신청 폼 링크 삽입
- [ ] 게시물 URL 확보

### 텔레그램 알림 (재홍님 확인)
- [ ] 텔레그램 채널(@Jehus_legalbot)에 런칭 공지
  - "NOHO HRMS 베타 런칭 완료. node.pe.kr 포스팅 링크: [링크]"
  - 베타 신청 현황 공유

### Slack 알림
- [ ] 슬랙 `thenoho` 워크스페이스에 런칭 알림 게시
- [ ] 기타 연결된 슬랙 채널 알림

### 마지막 기술 확인
- [ ] https://hrms.safeclaw.kr 정상 접속 확인
- [ ] 데모 계정 로그인 확인
- [ ] 서버 모니터링 정상 동작 확인

---

## 런칭 이후 D+7 (6/7) 팔로우업

- [ ] 베타 신청 현황 집계 (목표: 2~3사 이상 구두 동의)
- [ ] NOHO 직원 CSV 수령 + import 지원
- [ ] node.pe.kr 포스팅 유입 통계 확인
- [ ] 미응답 신청자 follow-up 이메일 발송
- [ ] D-Day 체크리스트 미완료 항목 처리

---

## 비상 연락 / 에스컬레이션

| 상황 | 조치 |
|------|------|
| 서버 다운 | 텔레그램 즉시 알림 → 재홍님 확인 → Docker 재시작 |
| 데모 계정 접속 불가 | abc@winhr.co.kr → 운영팀 즉시 처리 |
| 베타 신청 폼 링크 오류 | 임시: 이메일(abc@winhr.co.kr) 신청으로 안내 |
| NOHO 미팅 연기 | D+2 이내 재일정 확정 + 베타 컨택은 독립적으로 진행 |
