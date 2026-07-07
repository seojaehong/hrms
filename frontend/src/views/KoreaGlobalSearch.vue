<template>
	<BaseLayout :pageTitle="__('통합 검색')">
		<template #body>
			<div class="flex flex-col w-full h-full px-4 pt-5 pb-8 gap-4">
				<!-- 검색 입력창 -->
				<div class="relative">
					<span class="absolute inset-y-0 left-3 flex items-center pointer-events-none text-gray-400">
						<SearchIcon class="h-5 w-5" />
					</span>
					<input
						ref="searchInputRef"
						v-model="rawQuery"
						type="search"
						:placeholder="__('검색어 입력 (2자 이상)')"
						class="w-full pl-10 pr-4 py-2.5 rounded-lg border border-gray-300 bg-white text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
						autocomplete="off"
						@keydown.esc="clearQuery"
					/>
					<button
						v-if="rawQuery"
						class="absolute inset-y-0 right-3 flex items-center text-gray-400 hover:text-gray-700"
						@click="clearQuery"
						:aria-label="__('검색어 지우기')"
					>
						<FeatherIcon name="x" class="h-4 w-4" />
					</button>
				</div>

				<!-- 필터 pill -->
				<div class="flex flex-wrap gap-2">
					<button
						v-for="pill in FILTER_PILLS"
						:key="pill.key"
						:class="[
							'px-3 py-1 rounded-full text-xs font-medium border transition',
							selectedPills.has(pill.key)
								? 'bg-gray-900 text-white border-gray-900'
								: 'bg-white text-gray-600 border-gray-300 hover:border-gray-600',
						]"
						@click="onTogglePill(pill.key)"
					>
						{{ pill.label }}
					</button>
				</div>

				<!-- 검색 결과 -->
				<div v-if="isSearching" class="flex justify-center py-8">
					<div class="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-800"></div>
				</div>

				<template v-else-if="hasSearched">
					<!-- 결과 있음 -->
					<template v-if="resultGroups.length > 0">
						<div
							v-for="group in resultGroups"
							:key="group.doctype"
							class="flex flex-col gap-2"
						>
							<!-- 그룹 헤더 -->
							<div class="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-1">
								{{ group.label }}
							</div>
							<!-- 결과 카드 -->
							<div class="flex flex-col gap-1.5">
								<component
									:is="pwaRoutePath(item) ? 'router-link' : 'a'"
									v-for="item in group.items"
									:key="item.name"
									v-bind="linkProps(item)"
									class="flex flex-col bg-white rounded-lg border border-gray-200 px-3.5 py-3 hover:border-gray-400 transition cursor-pointer"
									@click="onResultClick(item)"
								>
									<span class="text-sm font-medium text-gray-900 leading-5">
										{{ formatResultLabel(item.label) || item.name }}
									</span>
									<span
										v-if="item.snippet"
										class="text-xs text-gray-500 mt-0.5"
										v-html="renderSnippet(item.snippet)"
									></span>
								</component>
							</div>
						</div>
					</template>

					<!-- 결과 없음 -->
					<div v-else class="flex flex-col items-center py-12 gap-2 text-gray-500">
						<FeatherIcon name="search" class="h-8 w-8 text-gray-300" />
						<span class="text-sm">{{ __('검색 결과 없음') }}</span>
						<span class="text-xs text-gray-400">
							{{ __('다른 키워드를 입력해 보세요') }}
						</span>
					</div>
				</template>

				<!-- 최근 검색어 (검색 전 상태) -->
				<template v-else-if="recentSearches.length > 0">
					<div class="flex flex-col gap-2">
						<div class="flex items-center justify-between">
							<span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
								{{ __('최근 검색') }}
							</span>
							<button
								class="text-xs text-gray-400 hover:text-gray-700"
								@click="onClearRecent"
							>
								{{ __('전체 삭제') }}
							</button>
						</div>
						<div class="flex flex-col gap-1">
							<button
								v-for="term in recentSearches"
								:key="term"
								class="flex items-center gap-2 px-3 py-2.5 bg-white rounded-lg border border-gray-200 hover:border-gray-400 text-sm text-gray-700 text-left transition"
								@click="applyRecentSearch(term)"
							>
								<FeatherIcon name="clock" class="h-4 w-4 text-gray-400 flex-shrink-0" />
								{{ term }}
							</button>
						</div>
					</div>
				</template>

				<!-- 초기 빈 상태 -->
				<template v-else>
					<div class="flex flex-col items-center py-12 gap-2 text-gray-400">
						<SearchIcon class="h-10 w-10 text-gray-200" />
						<span class="text-sm">{{ __('직원, 근태, 급여 등을 통합 검색합니다') }}</span>
					</div>
				</template>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, inject } from "vue"
import { useRouter } from "vue-router"
import { createResource } from "frappe-ui"
import { FeatherIcon } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import SearchIcon from "@/components/icons/SearchIcon.vue"

import {
	debounce,
	renderSnippet,
	getRecentSearches,
	addRecentSearch,
	clearRecentSearches,
	FILTER_PILLS,
	toggleFilterPill,
	getSelectedDoctypes,
	groupResults,
	toRouterPath,
	formatResultLabel,
} from "@/utils/koreaGlobalSearch"

const __ = inject("$translate")
const router = useRouter()

// ---------------------------------------------------------------------------
// 상태
// ---------------------------------------------------------------------------

const rawQuery = ref("")
const isSearching = ref(false)
const hasSearched = ref(false)
const resultGroups = ref([])
const recentSearches = ref(getRecentSearches())
const selectedPills = ref(new Set(["all"]))
const searchInputRef = ref(null)

// ---------------------------------------------------------------------------
// API resource
// ---------------------------------------------------------------------------

const searchResource = createResource({
	url: "hrms.regional.south_korea._api.global_search_api",
	onSuccess(data) {
		isSearching.value = false
		hasSearched.value = true
		resultGroups.value = groupResults(data?.results_by_doctype ?? {})
	},
	onError() {
		isSearching.value = false
		hasSearched.value = true
		resultGroups.value = []
	},
})

// ---------------------------------------------------------------------------
// 검색 실행 (debounce)
// ---------------------------------------------------------------------------

const performSearch = debounce((query) => {
	const q = (query || "").trim()
	if (q.length < 2) {
		isSearching.value = false
		hasSearched.value = false
		resultGroups.value = []
		return
	}

	isSearching.value = true
	const doctypes = getSelectedDoctypes(selectedPills.value)
	searchResource.submit({
		query: q,
		doctypes: doctypes ? doctypes.join(",") : undefined,
	})
}, 300)

watch(rawQuery, (val) => {
	performSearch(val)
})

// pill 변경 시 재검색
watch(selectedPills, () => {
	if ((rawQuery.value || "").trim().length >= 2) {
		performSearch(rawQuery.value)
	}
})

// ---------------------------------------------------------------------------
// 이벤트 핸들러
// ---------------------------------------------------------------------------

function onTogglePill(key) {
	selectedPills.value = toggleFilterPill(selectedPills.value, key)
}

function clearQuery() {
	rawQuery.value = ""
	hasSearched.value = false
	resultGroups.value = []
	searchInputRef.value?.focus()
}

function onResultClick(item) {
	const q = (rawQuery.value || "").trim()
	if (q) addRecentSearch(q)
	recentSearches.value = getRecentSearches()
}

function applyRecentSearch(term) {
	rawQuery.value = term
	searchInputRef.value?.focus()
}

function onClearRecent() {
	clearRecentSearches()
	recentSearches.value = []
}

// ---------------------------------------------------------------------------
// 링크 헬퍼
// ---------------------------------------------------------------------------

// pwa_url("/hrms/..." 절대 경로)을 router 내부 경로로 변환한 뒤,
// 실제 등록된 라우트인지 확인. 라우트 없으면 null → 데스크(/app/...) 새 탭 폴백.
// router base 가 이미 /hrms 이므로 그대로 push 하면 "/hrms/hrms/..." 중복 → 빈 화면.
function pwaRoutePath(item) {
	const path = toRouterPath(item.pwa_url)
	if (!path) return null
	try {
		const resolved = router.resolve(path)
		return resolved?.matched?.length > 0 ? path : null
	} catch {
		return null
	}
}

function linkProps(item) {
	const path = pwaRoutePath(item)
	if (path) {
		return { to: path }
	}
	return { href: item.url, target: "_blank", rel: "noopener noreferrer" }
}

// ---------------------------------------------------------------------------
// 키보드 단축키 — Cmd/Ctrl+K (전역은 App.vue 에서 처리)
// 이 화면이 열린 상태에서 / 또는 포커스 복원
// ---------------------------------------------------------------------------

function handleKeydown(e) {
	if ((e.metaKey || e.ctrlKey) && e.key === "k") {
		e.preventDefault()
		searchInputRef.value?.focus()
	}
}

onMounted(() => {
	window.addEventListener("keydown", handleKeydown)
	// 화면 진입 시 자동 포커스
	searchInputRef.value?.focus()
})

onBeforeUnmount(() => {
	window.removeEventListener("keydown", handleKeydown)
	performSearch.cancel()
})

// 외부 export (테스트용)
defineExpose({ rawQuery, selectedPills, resultGroups, recentSearches })
</script>
