# frontend/ 에이전트 노트

## 빌드 (Windows, bench 밖 standalone checkout)
- 명령: `cd frontend && npx -y yarn@1 build` (yarn 미설치 환경 — 반드시 npx 경유, ~65초).
- 산출물 `hrms/public/frontend`·`hrms/www/hrms.html`은 gitignored — 커밋 대상 아님.
- `vite.config.js.timestamp-*.mjs` 잔재 파일은 vite config 로드가 죽었을 때 남는 흔적 — 커밋 금지, 삭제 가능.

## Windows 빌드 함정 (2026-07-12 해결)
1. `getCommonSiteConfig()`류의 `while (currentDir !== "/")` 순회는 Windows 드라이브 루트(`C:\`)에서
   무한루프 — vite가 config 단계에서 영구 행. vite.config.js는 부모==자기 판정으로 수정됨.
   node_modules의 `frappe-ui/vite.js`에도 같은 루프가 있어 **저장소 루트의 빈 `sites/`·`apps/`
   디렉터리(git 미추적)가 루프 종료 조건** — 지우면 빌드가 다시 행 걸림.
2. `src/socket.js`는 bench 레이아웃 상대경로 `../../../../sites/common_site_config.json`을 정적
   임포트 — bench 밖에서는 vite.config.js의 조건부 alias가 `src/common_site_config.fallback.json`
   스텁으로 대체한다(bench 안에서는 실제 파일이 존재해 alias 미적용, 동작 불변).

## Korea 화면 추가 컨벤션
- 데이터: `src/data/korea<기능>Runtime.js` — `createResource({ url: "hrms.regional.south_korea.<모듈>_api.<함수>", makeParams })`.
- 뷰: `src/views/korea/Korea<기능>.vue` — `BaseLayout` + 디자인 토큰(`k-eyebrow`/`k-card`/`k-label`/`k-block--cream`/`k-numeric`/`k-display`) + `formatKRW` 헬퍼 + 합니다체. 표본: `KoreaSeverancePreview.vue`.
- 라우트: `src/router/korea.js`에 `/dashboard/korea-<기능>` 추가.
