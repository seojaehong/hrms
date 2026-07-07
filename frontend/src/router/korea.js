// KoreaWageStatementDashboard 라우트는 하단탭 canonical 통일을 위해 router/index.js의 TabbedView 하위로 이동 (경로 동일)
const routes = [
	{
		name: "KoreaSeverancePreview",
		path: "/dashboard/korea-severance-preview",
		component: () => import("@/views/korea/KoreaSeverancePreview.vue"),
	},
	{
		name: "KoreaComplianceDashboard",
		path: "/dashboard/korea-compliance",
		component: () => import("@/views/korea/KoreaComplianceDashboard.vue"),
	},
	{
		name: "KoreaTimeInput",
		path: "/dashboard/korea-time-input",
		component: () => import("@/views/korea/KoreaTimeInput.vue"),
	},
	{
		name: "KoreaComplianceCategoryDetail",
		path: "/dashboard/korea-compliance/category/:categoryKey",
		component: () => import("@/views/korea/KoreaComplianceCategoryDetail.vue"),
	},
]

export default routes
