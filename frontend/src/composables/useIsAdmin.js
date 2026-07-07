import { computed } from "vue"

import { userResource } from "@/data/user"

// admin 여부: HR Manager 또는 System Manager 롤이면 admin 기능
// (진단 실행·PDF·카톡 발송 등) 노출.
//
// 주의: PWA boot(window.frappe.boot)에는 user 객체가 없다
// (실측 boot keys: site_name, push_relay_server_url, default_route,
//  lang, translations_version). 따라서 boot 기반 롤 확인은 PWA에서
// 항상 false → hrms.api.get_current_user_info($user 리소스)의 roles를
// 사용한다. 리소스는 main.js router.beforeEach에서 로그인 시 항상
// reload되며, 데이터 도착 시 computed가 반응적으로 갱신된다.
const ADMIN_ROLES = ["HR Manager", "System Manager"]

export function useIsAdmin() {
	// 방어: 아직 로드 전이면 1회 fetch 트리거 (라우터 가드 밖에서 쓰일 때)
	if (!userResource.data && !userResource.loading) {
		userResource.fetch?.()
	}
	return computed(() => {
		const roles =
			userResource.data?.roles ?? window.frappe?.boot?.user?.roles
		if (!Array.isArray(roles)) return false
		return ADMIN_ROLES.some((role) => roles.includes(role))
	})
}
