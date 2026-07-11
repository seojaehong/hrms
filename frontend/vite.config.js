import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import { VitePWA } from "vite-plugin-pwa"
import frappeui from "frappe-ui/vite"

import path from "path"
import fs from "fs"

export default defineConfig({
	server: {
		port: 8080,
		proxy: getProxyOptions(),
		allowedHosts: true,
	},
	plugins: [
		vue(),
		frappeui(),
		VitePWA({
			registerType: "autoUpdate",
			strategies: "injectManifest",
			injectRegister: null,
			devOptions: {
				enabled: true,
			},
			manifest: {
				// ── 디자인 토큰 (2026-07 sprint에서 교체) ──────────────────
				// DESIGN_TOKEN_THEME_COLOR: #0066ff
				// DESIGN_TOKEN_BACKGROUND_COLOR: #ffffff
				// ────────────────────────────────────────────────────────────
				display: "standalone",
				orientation: "portrait",
				name: "SafeClaw HR",
				short_name: "SafeClaw HR",
				description: "한국 노동법 기반 HR 통합 관리 시스템",
				start_url: "/hrms",
				scope: "/hrms",
				theme_color: "#0066ff",
				background_color: "#ffffff",
				lang: "ko-KR",
				dir: "ltr",
				categories: ["business", "productivity"],
				shortcuts: [
					{
						name: "출근 체크",
						short_name: "출근",
						description: "GPS 기반 출근/퇴근",
						url: "/hrms/dashboard/attendance",
						icons: [
							{
								src: "/assets/hrms/manifest/manifest-icon-192.maskable.png",
								sizes: "192x192",
							},
						],
					},
					{
						name: "결재 인박스",
						short_name: "결재",
						description: "미결 결재 목록",
						url: "/hrms/dashboard/leaves",
						icons: [
							{
								src: "/assets/hrms/manifest/manifest-icon-192.maskable.png",
								sizes: "192x192",
							},
						],
					},
					{
						name: "급여명세서",
						short_name: "급여",
						description: "한국 급여명세서 조회",
						url: "/hrms/dashboard/salary-slips",
						icons: [
							{
								src: "/assets/hrms/manifest/manifest-icon-192.maskable.png",
								sizes: "192x192",
							},
						],
					},
					{
						name: "경비 청구",
						short_name: "경비",
						description: "경비 청구 내역",
						url: "/hrms/dashboard/expense-claims",
						icons: [
							{
								src: "/assets/hrms/manifest/manifest-icon-192.maskable.png",
								sizes: "192x192",
							},
						],
					},
				],
				icons: [
					{
						src: "/assets/hrms/manifest/manifest-icon-192.maskable.png",
						sizes: "192x192",
						type: "image/png",
						purpose: "any",
					},
					{
						src: "/assets/hrms/manifest/manifest-icon-192.maskable.png",
						sizes: "192x192",
						type: "image/png",
						purpose: "maskable",
					},
					{
						src: "/assets/hrms/manifest/manifest-icon-512.maskable.png",
						sizes: "512x512",
						type: "image/png",
						purpose: "any",
					},
					{
						src: "/assets/hrms/manifest/manifest-icon-512.maskable.png",
						sizes: "512x512",
						type: "image/png",
						purpose: "maskable",
					},
				],
			},
		}),
	],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "src"),
			// bench 밖(standalone checkout) 빌드: socket.js의 bench 상대경로 json이 없으면
			// 폴백 스텁으로 alias (bench 안에서는 실제 파일이 있어 alias가 추가되지 않음)
			...(fs.existsSync(path.resolve(__dirname, "../../../sites/common_site_config.json"))
				? {}
				: {
						"../../../../sites/common_site_config.json": path.resolve(
							__dirname,
							"src/common_site_config.fallback.json"
						),
					}),
		},
	},
	build: {
		outDir: "../hrms/public/frontend",
		emptyOutDir: true,
		target: "es2015",
		commonjsOptions: {
			include: [/tailwind.config.js/, /node_modules/],
		},
		sourcemap: true,
		rollupOptions: {
			output: {
				manualChunks: {
					"frappe-ui": ["frappe-ui"],
					"ionic-vue": ["@ionic/vue", "@ionic/vue-router"],
					firebase: ["firebase/app"],
				},
			},
		},
	},
	optimizeDeps: {
		include: [
			"frappe-ui > feather-icons",
			"showdown",
			"tailwind.config.js",
			"engine.io-client",
		],
	},
})

function getProxyOptions() {
	const config = getCommonSiteConfig()
	const webserver_port = config ? config.webserver_port : 8000
	if (!config) {
		console.log("No common_site_config.json found, using default port 8000")
	}
	return {
		"^/(app|login|api|assets|files|private)": {
			target: `http://127.0.0.1:${webserver_port}`,
			ws: true,
			router: function (req) {
				const site_name = req.headers.host.split(":")[0]
				console.log(`Proxying ${req.url} to ${site_name}:${webserver_port}`)
				return `http://${site_name}:${webserver_port}`
			},
		},
	}
}

function getCommonSiteConfig() {
	let currentDir = path.resolve(".")
	// traverse up till we find frappe-bench with sites directory
	// (루트 판정은 "/" 비교가 아니라 부모==자기 — Windows 드라이브 루트(C:\)에서 무한루프 방지)
	while (true) {
		if (
			fs.existsSync(path.join(currentDir, "sites")) &&
			fs.existsSync(path.join(currentDir, "apps"))
		) {
			let configPath = path.join(currentDir, "sites", "common_site_config.json")
			if (fs.existsSync(configPath)) {
				return JSON.parse(fs.readFileSync(configPath))
			}
			return null
		}
		const parentDir = path.resolve(currentDir, "..")
		if (parentDir === currentDir) return null
		currentDir = parentDir
	}
}
