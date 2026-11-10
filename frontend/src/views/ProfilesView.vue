<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { ApiError } from '../api/client'
import type { ProfileCreateInput, ProfileView } from '../api/profiles'
import BindingPanel from '../components/BindingPanel.vue'
import ConfirmDeleteDialog from '../components/ConfirmDeleteDialog.vue'
import ProfileCard from '../components/ProfileCard.vue'
import ProfileForm from '../components/ProfileForm.vue'
import SecretStoreBanner from '../components/SecretStoreBanner.vue'
import { useProfilesStore } from '../stores/profiles'
import { useToolsStore } from '../stores/tools'
import { warningLabel } from '../utils/profiles'

const store = useProfilesStore()
const toolsStore = useToolsStore()
const {
  profiles,
  bindings,
  secretStore,
  warnings,
  loading,
  error,
  refreshError,
  selectedProfile,
} = storeToRefs(store)
const { tools, error: toolsError } = storeToRefs(toolsStore)

const creating = ref(false)
const formError = ref<string | null>(null)
const formBusy = ref(false)
const pendingDelete = ref<ProfileView | null>(null)
const deleteBusy = ref(false)
const deleteError = ref<string | null>(null)
const bindingBusy = ref<string | null>(null)
const bindingError = ref<string | null>(null)
const notice = ref<string | null>(null)
const actionError = ref<string | null>(null)

const initialLoading = computed(
  () => loading.value && profiles.value.length === 0 && error.value === null,
)
const showForm = computed(() => creating.value || selectedProfile.value !== null)
const formProfile = computed(() => (creating.value ? null : selectedProfile.value))
const formKey = computed(() =>
  creating.value ? 'create' : (selectedProfile.value?.id ?? 'none'),
)

function messageOf(caught: unknown): string {
  return caught instanceof ApiError ? caught.message : '操作失败，请稍后重试'
}

function refreshAll(): void {
  void Promise.all([store.fetchProfiles(), toolsStore.fetchTools()])
}

function openCreate(): void {
  creating.value = true
  store.selectProfile(null)
  formError.value = null
  actionError.value = null
}

function openEdit(profile: ProfileView): void {
  creating.value = false
  store.selectProfile(profile.id)
  formError.value = null
  actionError.value = null
}

function cancelForm(): void {
  creating.value = false
  store.selectProfile(null)
  formError.value = null
}

async function submitForm(payload: ProfileCreateInput): Promise<void> {
  const editing = formProfile.value
  formBusy.value = true
  formError.value = null
  actionError.value = null
  try {
    if (editing !== null) {
      const updated = await store.update(editing.id, payload)
      notice.value = `已保存档案：${updated.name}`
    } else {
      const created = await store.create(payload)
      notice.value = `已创建档案：${created.name}`
    }
    creating.value = false
    store.selectProfile(null)
  } catch (caught) {
    formError.value = messageOf(caught)
  } finally {
    formBusy.value = false
  }
}

async function copyProfile(profile: ProfileView): Promise<void> {
  actionError.value = null
  try {
    const copied = await store.copy(profile.id)
    notice.value = `已复制档案：${copied.name}`
  } catch (caught) {
    actionError.value = messageOf(caught)
  }
}

function requestDelete(profile: ProfileView): void {
  pendingDelete.value = profile
  deleteError.value = null
}

async function confirmDelete(): Promise<void> {
  const target = pendingDelete.value
  if (target === null) {
    return
  }
  deleteBusy.value = true
  deleteError.value = null
  try {
    await store.remove(target.id, true)
    notice.value = `已删除档案：${target.name}`
    pendingDelete.value = null
  } catch (caught) {
    deleteError.value = messageOf(caught)
  } finally {
    deleteBusy.value = false
  }
}

async function bindTool(toolId: string, profileId: string): Promise<void> {
  bindingBusy.value = toolId
  bindingError.value = null
  try {
    await store.bind(toolId, profileId)
    notice.value = '已绑定，尚未应用（切换在 008 实现）'
  } catch (caught) {
    bindingError.value = messageOf(caught)
  } finally {
    bindingBusy.value = null
  }
}

async function unbindTool(toolId: string): Promise<void> {
  bindingBusy.value = toolId
  bindingError.value = null
  try {
    await store.unbind(toolId)
    notice.value = '已解除绑定；工具里已生效的配置不会被回滚'
  } catch (caught) {
    bindingError.value = messageOf(caught)
  } finally {
    bindingBusy.value = null
  }
}

onMounted(refreshAll)
</script>

<template>
  <section class="profiles">
    <header class="profiles__header">
      <h1>档案</h1>
      <div class="profiles__actions">
        <button type="button" :disabled="loading" @click="refreshAll">刷新</button>
        <button type="button" class="profiles__new" @click="openCreate">新建档案</button>
      </div>
    </header>

    <SecretStoreBanner v-if="secretStore !== null" :status="secretStore" />

    <p v-if="initialLoading" role="status">正在加载档案…</p>
    <div v-else-if="error !== null" class="profiles__fatal" role="alert">
      <p>{{ error }}</p>
      <button type="button" @click="refreshAll">重试</button>
    </div>

    <template v-else>
      <p v-if="refreshError !== null" class="profiles__refresh" role="status">
        刷新失败，当前显示上次结果：{{ refreshError }}
      </p>
      <p v-if="notice !== null" class="profiles__notice" role="status">{{ notice }}</p>
      <p v-if="actionError !== null" class="profiles__error" role="alert">
        {{ actionError }}
      </p>

      <section v-if="warnings.length > 0" class="profiles__warnings" role="alert">
        <h2>密钥存储提示</h2>
        <ul>
          <li v-for="warning in warnings" :key="`${warning.code}-${warning.message}`">
            {{ warningLabel(warning.code) }}：{{ warning.message }}
          </li>
        </ul>
      </section>

      <ul v-if="profiles.length > 0" class="profiles__list" aria-label="档案列表">
        <li v-for="profile in profiles" :key="profile.id">
          <ProfileCard
            :profile="profile"
            @edit="openEdit(profile)"
            @copy="copyProfile(profile)"
            @delete="requestDelete(profile)"
          />
        </li>
      </ul>
      <p v-else class="profiles__empty">
        还没有档案。新建一份档案，集中保存供应商、地址、模型与密钥。
      </p>

      <ProfileForm
        v-if="showForm"
        :key="formKey"
        :profile="formProfile"
        :busy="formBusy"
        :server-error="formError"
        @submit="submitForm"
        @cancel="cancelForm"
      />

      <BindingPanel
        :tools="tools"
        :profiles="profiles"
        :bindings="bindings"
        :tools-error="toolsError"
        :busy-tool-id="bindingBusy"
        :error="bindingError"
        @bind="bindTool"
        @unbind="unbindTool"
      />
    </template>

    <ConfirmDeleteDialog
      v-if="pendingDelete !== null"
      :profile="pendingDelete"
      :busy="deleteBusy"
      :error="deleteError"
      @confirm="confirmDelete"
      @cancel="pendingDelete = null"
    />
  </section>
</template>

<style scoped>
.profiles {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 56rem;
}

.profiles__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.profiles__header h1 {
  margin: 0;
  font-size: var(--font-size-xl);
}

.profiles__actions {
  display: flex;
  gap: var(--space-2);
}

.profiles__new {
  border-color: var(--color-accent);
  color: var(--color-accent);
  font-weight: 600;
}

.profiles__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.profiles__empty,
.profiles__refresh,
.profiles__notice {
  margin: 0;
  color: var(--color-text-secondary);
}

.profiles__notice {
  color: var(--status-ok-fg);
}

.profiles__error,
.profiles__fatal,
.profiles__warnings {
  margin: 0;
  color: var(--color-danger);
}

.profiles__warnings h2 {
  margin-top: 0;
  font-size: var(--font-size-md);
}

.profiles__warnings ul {
  margin: 0;
  padding-left: var(--space-4);
}
</style>