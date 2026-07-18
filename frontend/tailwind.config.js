import frappeUIPreset from "frappe-ui/src/tailwind/preset"
export default {
	presets: [frappeUIPreset],
	content: [
		"./index.html",
		"./src/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
		"../node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
	],
	theme: {
		extend: {
			// bare `border`의 기본색을 토큰으로 — 다크 쉼의 .border 블랭킷 대체(시맨틱 보더 보존)
			borderColor: {
				DEFAULT: "var(--k-hairline)",
			},
			// frappe-ui 프리셋의 sans=Inter를 Pretendard로 교체 — preflight(html)·font-sans 유틸 모두 통일
			fontFamily: {
				sans: [
					'"Pretendard Variable"',
					"Pretendard",
					"-apple-system",
					"BlinkMacSystemFont",
					'"Apple SD Gothic Neo"',
					'"Noto Sans KR"',
					"sans-serif",
				],
			},
			screens: {
				standalone: {
					raw: "(display-mode: standalone)",
				},
			},
			padding: {
				"safe-top": "env(safe-area-inset-top)",
				"safe-right": "env(safe-area-inset-right)",
				"safe-bottom": "env(safe-area-inset-bottom)",
				"safe-left": "env(safe-area-inset-left)",
			},
		},
	},
	plugins: [],
}
