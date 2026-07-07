import { computed } from "vue"

// admin 여부: window.frappe.boot의 사용자 롤 확인 (KoreaSubscription.vue 패턴 공용화)
// HR Manager 또는 System Manager 롤이면 admin 기능(진단 실행·PDF·카톡 발송 등) 노출.
const ADMIN_ROLES = ["HR Manager", "System Manager"]

export function useIsAdmin() {
	return computed(() => {
		const roles = window.frappe?.boot?.user?.roles
		if (!Array.isArray(roles)) return false
		return ADMIN_ROLES.some((role) => roles.includes(role))
	})
}
