// Admin enforcement: _api.py의 _assert_system_manager() (서버), 뷰의 isAdmin computed (UI).
// 전역 router.beforeEach 가드는 이 코드베이스에 없으므로 meta 필드는 사용하지 않음.
const routes = [
	{
		name: "KoreaSubscription",
		path: "/dashboard/korea-subscription",
		component: () => import("@/views/KoreaSubscription.vue"),
	},
]

export default routes
