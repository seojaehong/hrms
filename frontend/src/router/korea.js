const routes = [
	{
		name: "KoreaWageStatementDashboard",
		path: "/dashboard/korea-wage-statement",
		component: () => import("@/views/korea/KoreaWageStatementDashboard.vue"),
	},
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
		name: "KoreaComplianceCategoryDetail",
		path: "/dashboard/korea-compliance/category/:categoryKey",
		component: () => import("@/views/korea/KoreaComplianceCategoryDetail.vue"),
	},
]

export default routes
