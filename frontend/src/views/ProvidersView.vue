<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { ApiError } from '../api/client'
import type {
  ProfileCreateInput,
  ProfileUpdateInput,
  ProfileView,
} from '../api/profiles'
import ProviderDeleteDialog from '../components/ProviderDeleteDialog.vue'
import ProviderFormDialog from '../components/ProviderFormDialog.vue'
import ProviderListPanel from '../components/ProviderListPanel.vue'
import ProviderToolList from '../components/ProviderToolList.vue'
import SwitchPreviewDialog from '../components/SwitchPreviewDialog.vue'
import { useProfilesStore } from '../stores/profiles'
import type { ProviderItem } from '../stores/profiles'
import { useToolsStore } from '../stores/tools'
import { errorText } from '../utils/profileDisplay'

const toolsStore = useToolsStore()
const profilesStore = useProfilesStore()

const {
  tools,
  loading: toolsLoading,
  loaded: toolsLoaded,
  error: toolsError,
} = storeToRefs(toolsStore)
const {
  selectedToolId,
  items,
  listLoading,
  listLoaded,
  listError,
  listSecretStore,
  listWarnings,
  summariesByTool,
  summaryLoading,
  summaryLoaded,
  summaryError,
  healthResults,
  healthLoading,
  healthErrors,
} = storeToRefs(profilesStore)

const selectedTool = computed(
  () => tools.value.find((tool) => tool.id === selectedToolId.value) ?? null,
)
const selectedToolName = computed(() => selectedTool.value?.display_name ?? '当前工具')
const addButton = ref<HTMLButtonElement | null>(null)
const pageError = ref<string | null>(null)
const busyProfileId = ref<string | null>(null)

const formOpen = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const formProfile = ref<ProfileView | null>(null)
const formBusy = ref(false)
const formError = ref<string | null>(null)

const switchTarget = ref<ProviderItem | null>(null)
let switchTrigger: HTMLElement | null = null

const deleteTarget = ref<ProfileView | null>(null)
const deleteStage = ref<'confirm' | 'in-use'>('confirm')
const deleteBusy = ref(false)
const deleteError = ref<string | null>(null)

let formTrigger: HTMLElement | null = null
let deleteTrigger: HTMLElement | null = null

async function refreshPage(): Promise<void> {
  await Promise.all([toolsStore.fetchTools(), profilesStore.fetchSummary()])
  await profilesStore.reloadSelected()
}

onMounted(() => {
  void refreshPage()
})

function rememberFocus(fallback: HTMLElement | null): HTMLElement | null {
  return document.activeElement instanceof HTMLElement ? document.activeElement : fallback
}

function handleSelect(toolId: string): void {
  void profilesStore.selectTool(toolId)
}

function handleRetryList(): void {
  void profilesStore.reloadSelected()
}

function openCreate(): void {
  formTrigger = rememberFocus(addButton.value)
  formMode.value = 'create'
  formProfile.value = null
  formError.value = null
  formOpen.value = true
}

function openEdit(profile: ProfileView): void {
  formTrigger = rememberFocus(addButton.value)
  formMode.value = 'edit'
  formProfile.value = profile
  formError.value = null
  formOpen.value = true
}

async function closeForm(): Promise<void> {
  formOpen.value = false
  formBusy.value = false
  formError.value = null
  await nextTick()
  formTrigger?.focus()
}

async function handleFormSubmit(payload: ProfileCreateInput | ProfileUpdateInput): Promise<void> {
  formBusy.value = true
  formError.value = null
  try {
    if (formMode.value === 'create') {
      await profilesStore.createAndBind(payload as ProfileCreateInput)
    } else if (formProfile.value !== null) {
      await profilesStore.updateItem(formProfile.value.id, payload as ProfileUpdateInput)
    }
    await closeForm()
  } catch (caught) {
    formError.value = errorText(caught, '保存失败，请稍后重试')
  } finally {
    formBusy.value = false
  }
}

async function handleCopy(profileId: string): Promise<void> {
  if (busyProfileId.value !== null) {
    return
  }
  busyProfileId.value = profileId
  pageError.value = null
  try {
    await profilesStore.copyAndBind(profileId)
  } catch (caught) {
    pageError.value = errorText(caught, '复制供应商失败')
  } finally {
    busyProfileId.value = null
  }
}

async function handleRemove(profileId: string): Promise<void> {
  if (busyProfileId.value !== null) {
    return
  }
  busyProfileId.value = profileId
  pageError.value = null
  try {
    await profilesStore.removeBinding(profileId)
  } catch (caught) {
    pageError.value = errorText(caught, '从工具移除失败')
  } finally {
    busyProfileId.value = null
  }
}

function openSwitch(profileId: string): void {
  const item = items.value.find((candidate) => candidate.profile.id === profileId)
  if (item === undefined || selectedTool.value === null) {
    return
  }
  switchTrigger = rememberFocus(addButton.value)
  switchTarget.value = item
}

async function closeSwitch(): Promise<void> {
  switchTarget.value = null
  await nextTick()
  switchTrigger?.focus()
}

async function handleSwitchChanged(): Promise<void> {
  await refreshPage()
}

function handleHealth(profileId: string): void {
  void profilesStore.checkHealth(profileId)
}

function openDelete(profile: ProfileView): void {
  deleteTrigger = rememberFocus(addButton.value)
  deleteTarget.value = profile
  deleteStage.value = 'confirm'
  deleteError.value = null
  deleteBusy.value = false
}

async function closeDelete(): Promise<void> {
  deleteTarget.value = null
  deleteStage.value = 'confirm'
  deleteError.value = null
  deleteBusy.value = false
  await nextTick()
  deleteTrigger?.focus()
}

async function confirmDelete(): Promise<void> {
  const target = deleteTarget.value
  if (target === null) {
    return
  }
  deleteBusy.value = true
  deleteError.value = null
  try {
    await profilesStore.deleteItem(target.id, deleteStage.value === 'in-use')
    await closeDelete()
  } catch (caught) {
    if (
      caught instanceof ApiError &&
      caught.code === 'PROFILE_IN_USE' &&
      deleteStage.value === 'confirm'
    ) {
      deleteStage.value = 'in-use'
    } else {
      deleteError.value = errorText(caught, '删除失败，请稍后重试')
    }
  } finally {
    deleteBusy.value = false
  }
}
</script>

<template>
  <div class="providers">
    <ProviderToolList
      :tools="tools"
      :loading="toolsLoading"
      :loaded="toolsLoaded"
      :error="toolsError"
      :selected-tool-id="selectedToolId"
      :summaries="summariesByTool"
      :summary-loading="summaryLoading"
      :summary-loaded="summaryLoaded"
      :summary-error="summaryError"
      @select="handleSelect"
      @refresh="refreshPage"
    />

    <section class="providers__main" aria-labelledby="providers-title">
      <header class="providers__header">
        <div class="providers__heading">
          <h1 id="providers-title" class="providers__title">供应商</h1>
          <p class="providers__subtitle">
            {{ selectedToolId ? '为 ' + selectedToolName + ' 管理接口、模型与密钥' : '按工具管理供应商与绑定关系' }}
          </p>
        </div>
        <button
          ref="addButton"
          class="button"
          type="button"
          :disabled="selectedToolId === null"
          @click="openCreate"
        >
          新增供应商
        </button>
      </header>

      <div v-if="pageError" class="providers__notice" role="alert">
        <span>{{ pageError }}</span>
        <button class="providers__notice-close" type="button" aria-label="关闭提示" @click="pageError = null">
          关闭
        </button>
      </div>

      <div v-if="selectedToolId === null" class="providers__guide">
        <h2>选择一个工具</h2>
        <p>从左侧工具列表选择一项，查看它已绑定的供应商。未配置或异常的工具也可以先查看。</p>
      </div>

      <ProviderListPanel
        v-else
        :tool="selectedTool"
        :items="items"
        :loading="listLoading"
        :loaded="listLoaded"
        :error="listError"
        :secret-store="listSecretStore"
        :warnings="listWarnings"
        :health-results="healthResults"
        :health-loading="healthLoading"
        :health-errors="healthErrors"
        :busy-profile-id="busyProfileId"
        :switchable="selectedTool?.installed === true && selectedTool?.capabilities.write === true"
        @retry="handleRetryList"
        @switch="openSwitch"
        @add="openCreate"
        @health="handleHealth"
        @edit="openEdit"
        @copy="handleCopy"
        @remove="handleRemove"
        @delete="openDelete"
      />
    </section>

    <ProviderFormDialog
      v-if="formOpen"
      :mode="formMode"
      :tool-name="selectedToolName"
      :profile="formProfile"
      :busy="formBusy"
      :error="formError"
      @submit="handleFormSubmit"
      @close="closeForm"
    />

    <SwitchPreviewDialog
      v-if="switchTarget !== null && selectedTool !== null"
      :tool="selectedTool"
      :profile="switchTarget.profile"
      @close="closeSwitch"
      @changed="handleSwitchChanged"
    />

    <ProviderDeleteDialog
      v-if="deleteTarget"
      :profile="deleteTarget"
      :stage="deleteStage"
      :busy="deleteBusy"
      :error="deleteError"
      @confirm="confirmDelete"
      @cancel="closeDelete"
    />
  </div>
</template>

<style scoped>
.providers {
  display: grid;
  grid-template-columns: var(--layout-list-width) minmax(0, 1fr);
  height: 100%;
  min-width: 0;
  min-height: 0;
}

.providers__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: var(--color-bg);
}

.providers__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-lg);
  min-height: 65px;
  padding: var(--space-md) var(--space-xl);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.providers__heading {
  min-width: 0;
}

.providers__title {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: var(--line-height-tight);
}

.providers__subtitle {
  margin: 2px 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.providers__notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  margin: var(--space-md) var(--space-xl) 0;
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.providers__notice-close {
  flex: none;
  padding: 2px 6px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: inherit;
  font-size: var(--font-size-xs);
  cursor: pointer;
}

.providers__guide {
  margin: var(--space-xl);
  padding: var(--space-2xl);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.providers__guide h2 {
  margin: 0 0 var(--space-sm);
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.providers__guide p {
  max-width: 560px;
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
  line-height: var(--line-height-relaxed);
}

@media (max-width: 980px) {
  .providers {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(0, 40vh) minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .providers__header {
    align-items: flex-start;
    padding: var(--space-md) var(--space-lg);
  }
}
</style>

