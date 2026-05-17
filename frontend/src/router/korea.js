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
]

export default routes
