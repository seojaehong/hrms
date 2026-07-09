<template>
	<div class="linear">
		<!-- ══ Top Nav ══ -->
		<nav class="ln-nav">
			<div class="ln-container" style="height:56px;display:flex;align-items:center;justify-content:space-between;">
				<div style="display:flex;align-items:center;gap:8px;">
					<span class="ln-mark" aria-hidden="true"></span>
					<span style="font-family:var(--ln-font-display);font-weight:600;letter-spacing:-0.02em;font-size:1.0625rem;">SafeClaw HR</span>
				</div>
				<div class="ln-navlinks">
					<a class="ln-link" href="#features">기능</a>
					<a class="ln-link" href="#accuracy">정확성</a>
					<a class="ln-link" href="#pricing">요금</a>
					<a class="ln-link" href="#ai">AI 담당자</a>
				</div>
				<div style="display:flex;align-items:center;gap:8px;">
					<a class="ln-btn ln-btn-tertiary ln-hide-sm" href="/hrms/login">로그인</a>
					<a class="ln-btn ln-btn-primary" href="#signup">시작하기</a>
				</div>
			</div>
		</nav>

		<!-- ══ Hero ══ -->
		<header class="ln-hero-glow">
			<div class="ln-container ln-section" style="text-align:center;">
				<span class="ln-status-badge" style="margin-bottom:20px;"><span class="ln-dot"></span>한국 노무 특화 · 급여부터 4대보험까지 하나로</span>
				<h1 class="ln-display-xl" style="color:var(--ln-ink);">틀리면 안 되는 급여를<br />1원 단위로.</h1>
				<p class="ln-body-lg" style="max-width:52ch;margin:20px auto 0;">
					한국 노무에 특화된 HR SaaS. 급여·4대보험 신고·명세서를 자동으로 처리하고,
					AI HR 담당자가 텔레그램·메일·슬랙에서 직원 문의에 바로 답합니다.
				</p>
				<div style="display:flex;gap:12px;justify-content:center;margin-top:32px;flex-wrap:wrap;">
					<a class="ln-btn ln-btn-primary" href="#signup" style="min-height:44px;padding:12px 20px;">사업장 무료로 시작</a>
					<a class="ln-btn ln-btn-secondary" href="#accuracy" style="min-height:44px;padding:12px 20px;">정확성 원리 보기</a>
				</div>
				<!-- 제품 스크린샷 프레임 (히어로 프로덕트 패널) -->
				<div class="ln-screenshot ln-card--edge" style="margin-top:56px;text-align:left;">
					<div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
						<span class="ln-mono" style="color:var(--ln-ink-subtle);">급여 마감 미리보기 · 예시</span>
						<span class="ln-status-badge" style="margin-left:auto;"><span class="ln-dot"></span>확정</span>
					</div>
					<div class="ln-grid-3">
						<div v-for="s in heroStats" :key="s.label" class="ln-card" style="padding:20px;">
							<div class="ln-caption" style="color:var(--ln-ink-subtle);">{{ s.label }}</div>
							<div class="ln-num" :class="{ 'ln-num--accent': s.accent }">{{ s.value }}</div>
							<div class="ln-caption" style="margin-top:4px;color:var(--ln-ink-tertiary);">{{ s.note }}</div>
						</div>
					</div>
				</div>
			</div>
		</header>

		<!-- ══ Features (3-up) ══ -->
		<section id="features" class="ln-container ln-section">
			<div style="max-width:44ch;margin-bottom:40px;">
				<div class="ln-eyebrow">플랫폼</div>
				<h2 class="ln-display-md" style="margin-top:12px;color:var(--ln-ink);">급여실무 전 과정을 한 곳에서</h2>
			</div>
			<div class="ln-grid-3">
				<article v-for="f in features" :key="f.title" class="ln-card ln-card--edge">
					<div class="ln-ficon" aria-hidden="true">{{ f.icon }}</div>
					<h3 class="ln-card-title" style="margin-top:16px;color:var(--ln-ink);">{{ f.title }}</h3>
					<p class="ln-body-sm" style="margin-top:8px;">{{ f.body }}</p>
				</article>
			</div>
		</section>

		<!-- ══ Accuracy (제품 하이라이트) ══ -->
		<section id="accuracy" style="background:var(--ln-surface-1);border-top:1px solid var(--ln-hairline);border-bottom:1px solid var(--ln-hairline);">
			<div class="ln-container ln-section ln-two-col">
				<div>
					<div class="ln-eyebrow">정확성</div>
					<h2 class="ln-display-md" style="margin-top:12px;color:var(--ln-ink);">숫자는 흔들리지 않는다</h2>
					<p class="ln-body" style="margin-top:16px;">
						모든 급여는 확정 대장과 1원 단위로 크로스체크한 뒤에만 반영됩니다.
						엔진과 엑셀이 다르면 엑셀이 권위 — 사유를 분석하고 엔진을 고칩니다.
						마감·신고 제출 같은 확정 행위는 항상 사람 승인 게이트를 거칩니다.
					</p>
					<ul class="ln-checklist">
						<li v-for="c in accuracyPoints" :key="c"><span class="ln-check">✓</span>{{ c }}</li>
					</ul>
				</div>
				<div class="ln-screenshot ln-card--edge">
					<div class="ln-mono" style="color:var(--ln-ink-subtle);margin-bottom:12px;">검증 로그 · results</div>
					<div v-for="r in verifyRows" :key="r.name" class="ln-verify-row">
						<span class="ln-body-sm" style="color:var(--ln-ink-muted);">{{ r.name }}</span>
						<span class="ln-num-sm ln-num--accent">{{ r.amt }}</span>
						<span class="ln-status-badge"><span class="ln-dot"></span>1원 일치</span>
					</div>
				</div>
			</div>
		</section>

		<!-- ══ AI HR 담당자 ══ -->
		<section id="ai" class="ln-container ln-section">
			<div style="text-align:center;max-width:52ch;margin:0 auto 40px;">
				<div class="ln-eyebrow">AI HR 담당자</div>
				<h2 class="ln-display-md" style="margin-top:12px;color:var(--ln-ink);">직원 문의에 24시간 바로 답합니다</h2>
				<p class="ln-body" style="margin-top:16px;">
					연차·급여·4대보험 질문을 노동법 조문 근거와 함께 응답. 5개 채널에서 동일하게 작동합니다.
				</p>
			</div>
			<div style="display:flex;gap:12px;flex-wrap:wrap;justify-content:center;">
				<span v-for="ch in channels" :key="ch" class="ln-chip">{{ ch }}</span>
			</div>
		</section>

		<!-- ══ Pricing (3-up) ══ -->
		<section id="pricing" style="background:var(--ln-surface-1);border-top:1px solid var(--ln-hairline);">
			<div class="ln-container ln-section">
				<div style="text-align:center;max-width:44ch;margin:0 auto 40px;">
					<div class="ln-eyebrow">요금</div>
					<h2 class="ln-display-md" style="margin-top:12px;color:var(--ln-ink);">사업장 규모에 맞게</h2>
				</div>
				<div class="ln-grid-3">
					<article v-for="p in plans" :key="p.name" class="ln-card" :class="{ 'ln-card-lift': p.featured, 'ln-card--edge': p.featured }">
						<div style="display:flex;align-items:center;gap:8px;">
							<h3 class="ln-card-title" style="color:var(--ln-ink);">{{ p.name }}</h3>
							<span v-if="p.featured" class="ln-status-badge" style="margin-left:auto;color:var(--ln-primary);border-color:var(--ln-primary);">추천</span>
						</div>
						<div style="margin-top:16px;display:flex;align-items:baseline;gap:6px;">
							<span class="ln-num">{{ p.price }}</span>
							<span class="ln-caption">{{ p.unit }}</span>
						</div>
						<p class="ln-body-sm" style="margin-top:8px;min-height:40px;">{{ p.desc }}</p>
						<ul class="ln-checklist" style="margin-top:16px;">
							<li v-for="feat in p.features" :key="feat"><span class="ln-check">✓</span>{{ feat }}</li>
						</ul>
						<a class="ln-btn" :class="p.featured ? 'ln-btn-primary' : 'ln-btn-secondary'" href="#signup" style="width:100%;margin-top:20px;">{{ p.cta }}</a>
					</article>
				</div>
			</div>
		</section>

		<!-- ══ Signup CTA ══ -->
		<section id="signup" class="ln-container ln-section">
			<div class="ln-cta-banner ln-card--edge" style="max-width:640px;margin:0 auto;">
				<h2 class="ln-headline" style="color:var(--ln-ink);">2분이면 사업장이 열립니다</h2>
				<p class="ln-body" style="margin-top:12px;">사업장명과 이메일만 입력하면 전용 테넌트가 자동 생성됩니다.</p>
				<form class="ln-form" @submit.prevent="onSignup">
					<div style="text-align:left;">
						<label class="ln-label" for="ln-company">사업장명</label>
						<input id="ln-company" class="ln-input" v-model.trim="signup.company" placeholder="예: (주)윈하이어" />
					</div>
					<div style="text-align:left;">
						<label class="ln-label" for="ln-email">담당자 이메일</label>
						<input id="ln-email" class="ln-input" type="email" v-model.trim="signup.email" placeholder="you@company.com" />
					</div>
					<button class="ln-btn ln-btn-primary" type="submit" style="width:100%;min-height:44px;" :disabled="!signupValid">
						무료로 사업장 만들기
					</button>
					<p class="ln-caption" style="margin-top:4px;">가입 시 이용약관·개인정보처리방침에 동의하게 됩니다.</p>
					<p v-if="signupMsg" class="ln-body-sm" style="color:var(--ln-primary);">{{ signupMsg }}</p>
				</form>
			</div>
		</section>

		<!-- ══ Footer ══ -->
		<footer class="ln-footer">
			<div class="ln-container" style="display:flex;justify-content:space-between;gap:32px;flex-wrap:wrap;">
				<div>
					<div style="font-family:var(--ln-font-display);font-weight:600;color:var(--ln-ink);">SafeClaw HR</div>
					<p class="ln-caption" style="margin-top:8px;max-width:36ch;">한국 노무 특화 HR SaaS · 급여·4대보험·AI HR 담당자</p>
				</div>
				<div style="display:flex;gap:48px;flex-wrap:wrap;">
					<div class="ln-fcol"><span class="ln-fhead">제품</span><a class="ln-link" href="#features">기능</a><a class="ln-link" href="#pricing">요금</a><a class="ln-link" href="#ai">AI 담당자</a></div>
					<div class="ln-fcol"><span class="ln-fhead">회사</span><a class="ln-link" href="/hrms/login">로그인</a><a class="ln-link" href="#signup">시작하기</a></div>
				</div>
			</div>
			<div class="ln-container ln-caption" style="margin-top:48px;color:var(--ln-ink-tertiary);">© 2026 SafeClaw HR. All rights reserved.</div>
		</footer>
	</div>
</template>

<script setup>
import { computed, reactive } from "vue"

import "@/styles/linear-tokens.css"

// 히어로 제품 패널 — 상품 정확성 약속을 보여주는 예시 수치 (특정 고객 데이터 아님)
const heroStats = [
	{ label: "이번 달 급여", value: "124,800,000원", note: "직원 48명 · 예시" },
	{ label: "대장 대비 오차", value: "0원", note: "1원 단위 일치", accent: true },
	{ label: "명세서 발송", value: "48 / 48", note: "자동 발송" },
]

const features = [
	{ icon: "₩", title: "급여 자동 계산", body: "월급제·시급제·일용직 급여를 사업장 규칙대로 계산하고, 확정 대장과 1원 단위로 대조합니다." },
	{ icon: "🛡", title: "4대보험 신고", body: "취득·상실·근로내용확인 신고서를 서식 그대로 자동 생성. 사람 승인 게이트를 거쳐 제출합니다." },
	{ icon: "🤖", title: "AI HR 담당자", body: "연차·급여·노동법 문의를 조문 근거와 함께 응답. 텔레그램·메일·슬랙·디스코드·구글챗 5채널." },
	{ icon: "📄", title: "임금명세서", body: "근로기준법 제48조제2항 요건을 충족하는 명세서를 구성항목·계산방법·공제내역까지 자동 생성." },
	{ icon: "📊", title: "급여 마감 워크플로", body: "업로드→검증→미리보기→승인. 확정 전에는 어떤 숫자도 반영되지 않습니다." },
	{ icon: "🔒", title: "테넌트 격리", body: "사업장마다 독립 데이터. 개인정보는 암호화 필드로 관리하고 감사 로그를 남깁니다." },
]

const accuracyPoints = [
	"엑셀이 권위 — 엔진 불일치 시 사유 분석 후 엔진 수정",
	"확정 행위(마감·신고)는 항상 사람 승인 게이트",
	"모든 변경은 results 저널에 기록",
]

// 예시 데이터 (특정 고객 아님)
const verifyRows = [
	{ name: "직원 A", amt: "3,120,400원" },
	{ name: "직원 B", amt: "2,845,900원" },
	{ name: "직원 C", amt: "3,507,120원" },
]

const channels = ["텔레그램", "이메일", "슬랙", "디스코드", "구글챗"]

const plans = [
	{ name: "스타터", price: "무료", unit: "~5인", desc: "소규모 사업장 · 급여·명세서 기본", features: ["급여 자동계산", "임금명세서 PDF", "직원 셀프 조회"], cta: "무료 시작", featured: false },
	{ name: "프로", price: "월 3만원~", unit: "인원 비례", desc: "4대보험 신고 + AI HR 담당자 5채널", features: ["스타터 전체", "4대보험 신고 3종", "AI HR 담당자", "급여 마감 승인 플로우"], cta: "프로 시작", featured: true },
	{ name: "엔터프라이즈", price: "문의", unit: "다사업장", desc: "노무법인·다사업장 · 전용 지원", features: ["프로 전체", "다사업장 관리", "전용 온보딩", "SLA·우선지원"], cta: "상담 요청", featured: false },
]

const signup = reactive({ company: "", email: "" })
const signupMsg = computed(() => "")
const signupValid = computed(() => signup.company.length > 0 && /.+@.+\..+/.test(signup.email))

function onSignup() {
	// 셀프서브 가입 파이프라인(create_tenant) 연동 지점 — P3에서 백엔드 활성화
	if (!signupValid.value) return
	window.location.href = `/hrms/login?signup_company=${encodeURIComponent(signup.company)}&signup_email=${encodeURIComponent(signup.email)}`
}
</script>

<style scoped>
/* 페이지 전용 보조 스타일 (linear-tokens.css의 .linear 스코프 보완) */
.linear { min-height: 100vh; }
.ln-mark { width: 20px; height: 20px; border-radius: 6px; background: linear-gradient(135deg, var(--ln-primary), var(--ln-primary-hover)); display: inline-block; }
.ln-navlinks { display: flex; gap: 28px; font-size: 0.875rem; }
.ln-num { font-family: var(--ln-font-display); font-size: 1.75rem; font-weight: 600; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; color: var(--ln-ink); line-height: 1.1; }
.ln-num--accent { color: var(--ln-primary); }
.ln-num-sm { font-family: var(--ln-font-display); font-weight: 600; font-variant-numeric: tabular-nums; }
.ln-ficon { width: 40px; height: 40px; border-radius: 10px; background: var(--ln-surface-2); border: 1px solid var(--ln-hairline); display: flex; align-items: center; justify-content: center; font-size: 20px; }
.ln-checklist { list-style: none; padding: 0; margin: 16px 0 0; display: flex; flex-direction: column; gap: 8px; }
.ln-checklist li { display: flex; align-items: flex-start; gap: 8px; font-size: 0.875rem; color: var(--ln-ink-muted); }
.ln-check { color: var(--ln-success); font-weight: 700; }
.ln-verify-row { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-top: 1px solid var(--ln-hairline); }
.ln-verify-row .ln-num-sm { margin-left: auto; }
.ln-chip { background: var(--ln-surface-1); border: 1px solid var(--ln-hairline); border-radius: var(--ln-r-pill); padding: 8px 16px; font-size: 0.875rem; color: var(--ln-ink-muted); }
.ln-form { display: flex; flex-direction: column; gap: 14px; margin-top: 24px; }
.ln-fcol { display: flex; flex-direction: column; gap: 10px; font-size: 0.8125rem; }
.ln-fhead { color: var(--ln-ink); font-weight: 600; }
.ln-two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 48px; align-items: center; }
@media (max-width: 768px) {
	.ln-navlinks { display: none; }
	.ln-hide-sm { display: none; }
	.ln-two-col { grid-template-columns: 1fr; }
}
</style>
