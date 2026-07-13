<template>
	<ion-page>
		<ion-content class="ion-padding">
			<div class="flex flex-col h-screen w-screen">
				<div class="w-full sm:w-96 md:w-[44rem] xl:w-[64rem] 2xl:w-[76rem] mx-auto">
					<header
						class="flex flex-row bg-[var(--k-card)] shadow-sm py-4 px-3 items-center justify-between border-b sticky top-0 z-10"
					>
						<div class="flex flex-row items-center">
							<Button
								variant="ghost"
								class="!pl-0 hover:bg-[var(--k-card)]"
								@click="router.back()"
							>
								<FeatherIcon name="chevron-left" class="h-5 w-5" />
							</Button>
							<h2 class="k-t-title text-[var(--k-ink)]">{{ __("Profile") }}</h2>
						</div>
					</header>

					<div class="flex flex-col items-center mt-5 p-4">
						<!-- Profile Image -->
						<img
							v-if="user.data.user_image"
							class="h-24 w-24 rounded-full object-cover"
							:src="user.data.user_image"
							:alt="user.data.first_name"
						/>
						<div
							v-else
							class="flex items-center justify-center bg-[var(--k-hairline)] uppercase text-[var(--k-ink-muted)] h-24 w-24 rounded-full object-cover"
						>
							{{ user.data.first_name[0] }}
						</div>

						<div class="flex flex-col gap-1.5 items-center mt-2 mb-5">
							<span v-if="employee" class="k-t-title text-[var(--k-ink)]">{{
								employee?.data?.employee_name
							}}</span>
							<span v-if="employee" class="font-normal text-sm text-[var(--k-ink-muted)]">{{
								employee?.data?.designation
							}}</span>
						</div>

						<!-- Profile Links -->
						<div class="flex flex-col gap-5 my-4 w-full">
							<div class="flex flex-col bg-[var(--k-card)] rounded">
								<div
									class="flex flex-row cursor-pointer flex-start p-4 items-center justify-between border-b"
									v-for="link in profileLinks"
									:key="link.title"
									@click="openInfoModal(link)"
								>
									<div class="flex flex-row items-center gap-3 grow">
										<FeatherIcon
											:name="link.icon"
											class="h-5 w-5 text-[var(--k-ink-muted)]"
										/>
										<div class="text-base font-normal text-[var(--k-ink)]">
											{{ link.title }}
										</div>
									</div>
									<FeatherIcon
										name="chevron-right"
										class="h-5 w-5 text-[var(--k-ink-muted)]"
									/>
								</div>
							</div>
						</div>

						<!-- Settings -->
						<div
							class="flex flex-col gap-5 my-4 w-full"
							v-if="allowPushNotifications"
						>
							<div class="flex flex-col bg-[var(--k-card)] rounded">
								<router-link
									:to="{ name: 'Settings' }"
									class="flex flex-row cursor-pointer flex-start p-4 items-center justify-between border-b"
								>
									<div class="flex flex-row items-center gap-3 grow">
										<FeatherIcon
											name="settings"
											class="h-5 w-5 text-[var(--k-ink-muted)]"
										/>
										<div class="text-base font-normal text-[var(--k-ink)]">
											{{ __("Settings") }}
										</div>
									</div>
									<FeatherIcon
										name="chevron-right"
										class="h-5 w-5 text-[var(--k-ink-muted)]"
									/>
								</router-link>
							</div>
						</div>

						<Button
							@click="logout"
							variant="outline"
							theme="red"
							class="w-full shadow py-4 mt-5"
						>
							<template #prefix>
								<FeatherIcon name="log-out" class="w-4" />
							</template>
							{{ __("Log Out") }}
						</Button>
					</div>
				</div>
			</div>

			<ion-modal
				ref="modal"
				:is-open="isInfoModalOpen"
				@didDismiss="closeInfoModal"
				:initial-breakpoint="1"
				:breakpoints="[0, 1]"
			>
				<ProfileInfoModal
					:title="selectedItem.title"
					:data="selectedItemData"
					:emptyMessage="selectedItem.emptyMessage"
				/>
			</ion-modal>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, ref, onMounted, onBeforeUnmount } from "vue"
import { useRouter } from "vue-router"
import { IonModal, IonPage, IonContent } from "@ionic/vue"
import { FeatherIcon, createDocumentResource, createResource } from "frappe-ui"

import { showErrorAlert } from "@/utils/dialogs"
import { formatCurrency } from "@/utils/formatters"

import ProfileInfoModal from "@/components/ProfileInfoModal.vue"

import { arePushNotificationsEnabled } from "@/data/notifications"

const DOCTYPE = "Employee"

const socket = inject("$socket")
const session = inject("$session")
const user = inject("$user")
const employee = inject("$employee")
const __ = inject("$translate")

const router = useRouter()

const profileLinks = [
	{
		icon: "user",
		title: __("Employee Details"),
		emptyMessage: __("직원 정보가 아직 등록되지 않았습니다"),
		fields: [
			"employee_name",
			"employee_number",
			"gender",
			"date_of_birth",
			"date_of_joining",
			"blood_group",
		],
	},
	{
		icon: "file",
		title: __("Company Information"),
		emptyMessage: __("회사 정보가 아직 등록되지 않았습니다"),
		fields: [
			"company",
			"department",
			"designation",
			"branch",
			"grade",
			"reports_to",
			"employment_type",
		],
	},
	{
		icon: "book",
		title: __("Contact Information"),
		emptyMessage: __("연락처 정보가 아직 등록되지 않았습니다"),
		fields: [
			"cell_number",
			"personal_email",
			"company_email",
			"preferred_email",
		],
	},
	{
		icon: "dollar-sign",
		title: __("Salary Information"),
		emptyMessage: __("급여 정보가 아직 등록되지 않았습니다"),
		fields: [
			"ctc",
			"payroll_cost_center",
			"pan_number",
			"provident_fund_account",
			"salary_mode",
			"bank_name",
			"bank_ac_no",
			"ifsc_code",
			"micr_code",
			"iban",
		],
	},
]

const isInfoModalOpen = ref(false)
const selectedItem = ref(null)

const allowPushNotifications = computed(
	() =>
		window.frappe?.boot.push_relay_server_url &&
		arePushNotificationsEnabled.data
)

const openInfoModal = async (request) => {
	selectedItem.value = request
	isInfoModalOpen.value = true
}

const closeInfoModal = async (_request) => {
	isInfoModalOpen.value = false
	selectedItem.value = null
}

const employeeDoc = createDocumentResource({
	doctype: DOCTYPE,
	name: employee.data.name,
	fields: "*",
	auto: true,
	transform: (data) => {
		// 미등록(null) 급여는 "₩ 0"으로 둔갑시키지 않고 빈 값으로 유지 (행 숨김 대상)
		data.ctc = data.ctc == null ? data.ctc : formatCurrency(data.ctc, data.salary_currency)
		return data
	},
})

const employeeDocType = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: DOCTYPE },
	auto: true,
})

const getFieldInfo = (fieldname) => {
	const field = employeeDocType.data?.find(
		(field) => field.fieldname === fieldname
	)
	return [__(field?.label, null, "Employee"), field?.fieldtype]
}

// 값 없는 행("-" 나열) 숨김 규칙 — null/undefined/빈 문자열은 숨기고 0은 유지
function hasProfileValue(value) {
	if (value === undefined || value === null) return false
	if (typeof value === "string" && !value.trim()) return false
	return true
}

// 선택된 섹션의 표시 행 — 값 있는 행만 (전부 없으면 모달이 빈 상태 한 줄 표시)
const selectedItemData = computed(() => {
	if (!selectedItem.value || !employeeDoc?.doc) return []
	return selectedItem.value.fields
		.map((field) => {
			const [label, fieldtype] = getFieldInfo(field)
			return {
				fieldname: field,
				value: employeeDoc.doc[field],
				label: label,
				fieldtype: fieldtype,
			}
		})
		.filter((row) => hasProfileValue(row.value))
})

const logout = async () => {
	try {
		await session.logout.submit()
	} catch (e) {
		const msg = "An error occurred while attempting to log out!"
		console.error(msg, e)
		showErrorAlert(msg)
	}
}

onMounted(() => {
	socket.emit("doctype_subscribe", DOCTYPE)
	socket.on("list_update", (data) => {
		if (data.doctype === DOCTYPE && data.name === employee.data.name) {
			employeeDoc.reload()
		}
	})
})

onBeforeUnmount(() => {
	socket.emit("doctype_unsubscribe", DOCTYPE)
	socket.off("list_update")
})
</script>
