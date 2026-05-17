<template>
	<BaseLayout :pageTitle="__('한국 노무 AI 보조')">
		<template #body>
			<div class="flex flex-col h-full">
				<!-- Disclaimer Banner -->
				<div class="bg-yellow-50 border-b border-yellow-200 px-4 py-2 text-xs text-yellow-800 flex items-start gap-2">
					<span class="mt-0.5 shrink-0">⚠</span>
					<span>
						이 챗봇은 AI 보조입니다. 실제 결정은 반드시 담당자 또는 공인노무사의 검토를 거쳐 주세요.
						법률 자문이 아니며, 개별 사안에 따라 결과가 달라질 수 있습니다.
					</span>
				</div>

				<!-- Chat History -->
				<div ref="chatContainer" class="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
					<!-- Welcome message -->
					<div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full gap-4 text-center px-4">
						<div class="text-4xl">⚖️</div>
						<div>
							<p class="text-lg font-bold text-gray-800">한국 노무 AI 보조</p>
							<p class="text-sm text-gray-500 mt-1">
								근로기준법, 연차, 급여, 해고 등 HR 관련 질문을 입력하세요.
							</p>
						</div>
					</div>

					<!-- Message Thread -->
					<template v-for="msg in messages" :key="msg.id">
						<!-- User message -->
						<div v-if="msg.role === 'user'" class="flex justify-end">
							<div class="bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2 max-w-[80%] text-sm">
								{{ msg.content }}
							</div>
						</div>

						<!-- Assistant message -->
						<div v-else class="flex flex-col gap-2">
							<div class="flex items-start gap-2">
								<div class="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center text-xs shrink-0 mt-0.5">
									AI
								</div>
								<div class="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 max-w-[85%]">
									<p class="text-sm text-gray-800 whitespace-pre-wrap">{{ msg.content }}</p>
								</div>
							</div>

							<!-- Citations -->
							<div v-if="msg.citations && msg.citations.length > 0" class="ml-9">
								<div class="text-xs text-gray-500 mb-1 font-medium">근거 인용</div>
								<div class="flex flex-col gap-1">
									<div
										v-for="(cite, ci) in msg.citations"
										:key="ci"
										class="bg-blue-50 border border-blue-100 rounded-lg px-3 py-2"
									>
										<div class="text-xs font-semibold text-blue-700">
											[{{ citationTypeLabel(cite.type) }}] {{ cite.ref }}
										</div>
										<div class="text-xs text-gray-600 mt-0.5 line-clamp-2">{{ cite.snippet }}</div>
									</div>
								</div>
							</div>

							<!-- Suggested Actions — 사용자 직접 클릭 전용, 자동 실행 X -->
							<div v-if="msg.suggestedActions && msg.suggestedActions.length > 0" class="ml-9">
								<div class="text-xs text-gray-500 mb-1 font-medium">관련 링크</div>
								<div class="flex flex-wrap gap-2">
									<component
										v-for="(action, ai) in msg.suggestedActions"
										:key="ai"
										:is="isExternalUrl(action.url) ? 'a' : 'router-link'"
										v-bind="isExternalUrl(action.url)
											? { href: action.url, target: '_blank', rel: 'noopener noreferrer' }
											: { to: action.url }"
										class="inline-flex items-center gap-1 text-xs bg-white border border-gray-200 rounded-full px-3 py-1.5 text-gray-700 hover:bg-gray-50 transition-colors"
									>
										{{ action.label }}
									</component>
								</div>
							</div>

							<!-- Disclaimer per message -->
							<div v-if="msg.disclaimer" class="ml-9">
								<p class="text-xs text-gray-400 italic">{{ msg.disclaimer }}</p>
							</div>
						</div>
					</template>

					<!-- Loading indicator -->
					<div v-if="isLoading" class="flex items-start gap-2">
						<div class="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center text-xs shrink-0">
							AI
						</div>
						<div class="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3">
							<div class="flex gap-1">
								<span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
								<span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
								<span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
							</div>
						</div>
					</div>
				</div>

				<!-- Suggested Questions -->
				<div v-if="messages.length === 0" class="px-4 pb-2">
					<p class="text-xs text-gray-500 mb-2 font-medium">자주 묻는 질문</p>
					<div class="flex flex-col gap-2">
						<button
							v-for="(q, qi) in suggestedQuestions"
							:key="qi"
							@click="sendSuggestedQuestion(q)"
							class="text-left text-sm bg-gray-50 hover:bg-gray-100 rounded-xl px-3 py-2.5 text-gray-700 transition-colors border border-gray-100"
						>
							{{ q }}
						</button>
					</div>
				</div>

				<!-- Input Area -->
				<div class="px-4 py-3 border-t border-gray-100 bg-white">
					<div class="flex items-end gap-2">
						<textarea
							v-model="inputText"
							:placeholder="__('근로기준법, 연차, 급여, 해고 등 질문하세요...')"
							class="flex-1 resize-none rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 max-h-32 min-h-[42px]"
							rows="1"
							@keydown.enter.exact.prevent="sendMessage"
							@input="autoResize"
							ref="textareaRef"
						></textarea>
						<button
							@click="sendMessage"
							:disabled="!inputText.trim() || isLoading"
							class="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-blue-700 transition-colors shrink-0"
						>
							<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
								<path stroke-linecap="round" stroke-linejoin="round" d="M12 19V5m-7 7l7-7 7 7" />
							</svg>
						</button>
					</div>
					<p class="text-xs text-gray-400 mt-1.5 text-center">
						AI 보조 도구입니다. 법률 자문이 아닙니다.
					</p>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { ref, nextTick, inject } from "vue"
import { createResource } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"

const __ = inject("$translate")

// ── State ──────────────────────────────────────
const messages = ref([])
const inputText = ref("")
const isLoading = ref(false)
const chatContainer = ref(null)
const textareaRef = ref(null)

// Session ID: 브라우저 세션 단위 유지
const sessionId = ref(
	sessionStorage.getItem("korea_ai_chat_session") ||
	(() => {
		const id = crypto.randomUUID?.() || Date.now().toString(36)
		sessionStorage.setItem("korea_ai_chat_session", id)
		return id
	})()
)

// ── 자주 묻는 질문 ──────────────────────────────
const suggestedQuestions = [
	"연차 유급휴가는 언제부터 발생하나요?",
	"주 52시간 제도에서 연장근로 한도는 얼마인가요?",
	"퇴직금은 어떻게 계산하나요?",
	"최저임금 위반 시 어떤 제재를 받나요?",
	"부당해고 구제신청은 어디에 하나요?",
	"야간수당은 얼마나 가산되나요?",
	"육아휴직 기간은 얼마나 되나요?",
	"4대보험 사업주 부담률은 얼마인가요?",
]

// ── Frappe resource ─────────────────────────────
// createResource — POST to whitelist API (assistant_only, read-only)
const chatResource = createResource({
	url: "hrms.regional.south_korea._api.chat_query_api",
	method: "POST",
})

// ── Actions ─────────────────────────────────────
async function sendMessage() {
	const question = inputText.value.trim()
	if (!question || isLoading.value) return

	// 사용자 메시지 추가
	messages.value.push({
		id: Date.now(),
		role: "user",
		content: question,
	})

	inputText.value = ""
	resetTextarea()
	isLoading.value = true
	scrollToBottom()

	try {
		const result = await chatResource.submit({
			user_question: question,
			user_role: "employee",
			session_id: sessionId.value,
		})

		messages.value.push({
			id: Date.now() + 1,
			role: "assistant",
			content: result.answer || "답변을 불러오지 못했습니다.",
			citations: result.citations || [],
			suggestedActions: result.suggested_actions || [],
			disclaimer: result.disclaimer || "",
		})
	} catch (err) {
		messages.value.push({
			id: Date.now() + 1,
			role: "assistant",
			content: "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
			citations: [],
			suggestedActions: [],
			disclaimer: "이 답변은 AI 보조 정보입니다. 실제 결정은 담당자 또는 공인노무사의 검토를 거쳐 주세요.",
		})
	} finally {
		isLoading.value = false
		await nextTick()
		scrollToBottom()
	}
}

function sendSuggestedQuestion(question) {
	inputText.value = question
	sendMessage()
}

function scrollToBottom() {
	nextTick(() => {
		if (chatContainer.value) {
			chatContainer.value.scrollTop = chatContainer.value.scrollHeight
		}
	})
}

function autoResize(e) {
	e.target.style.height = "auto"
	e.target.style.height = Math.min(e.target.scrollHeight, 128) + "px"
}

function resetTextarea() {
	if (textareaRef.value) {
		textareaRef.value.style.height = "auto"
	}
}

// ── Helpers ──────────────────────────────────────
function citationTypeLabel(type) {
	const map = { law: "법령", case: "판례", internal: "내부문서" }
	return map[type] || type
}

function isExternalUrl(url) {
	return url && (url.startsWith("http://") || url.startsWith("https://"))
}
</script>
