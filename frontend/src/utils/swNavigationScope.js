// 서비스워커 네비게이션 스코프 판정 (노호 런칭 검증에서 발견된 사고의 재발 방지).
//
// 사고: sw.js가 mode=navigate 전체를 가로채 /app(데스크) 요청까지 PWA 캐시로
// 응답 → 데스크 진입이 PWA 화면으로 납치됨. SW는 /hrms(PWA) 밖의 문서
// 네비게이션에 절대 개입하면 안 된다.
export function isPwaNavigation(pathname) {
	if (typeof pathname !== "string") return false
	return pathname === "/hrms" || pathname.startsWith("/hrms/")
}
