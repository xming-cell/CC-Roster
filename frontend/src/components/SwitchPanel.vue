<script setup lang="ts">
import { computed, watch } from 'vue'
import { storeToRefs } from 'pinia'

import type { BindingView, ProfileView } from '../api/profiles'
import type { SwitchApplyResponse } from '../api/switch'
import type { ToolView } from '../api/tools'
import { useSwitchesStore } from '../stores/switches'
import SwitchPreviewDialog from './SwitchPreviewDialog.vue'

const props = defineProps<{
  tool: ToolView
  profiles: ProfileView[]
  bindings: BindingView[]
}>()

const emit = defineEmits<{
  applied: [result: SwitchApplyResponse]
}>()

const store = useSwitchesStore()
const {
  selectedProfileId,
  selectedModelId,
  preview,
  previewing,
  applying,
  error,
  details,
  lastApplied,
} = storeToRefs(store)

const selectedProfile = computed(
  () => props.profiles.find((profile) => profile.id === selectedProfileId.value) ?? null,
)
const modelOptions = computed(() => selectedProfile.value?.models ?? [])
const modelValue = computed(() => selectedModelId.value ?? '')

watch(
  () => [props.tool.id, props.profiles, props.bindings] as const,
  () => store.sync(props.tool.id, props.profiles, props.bindings),
  { immediate: true },
)

function onProfileChange(event: Event): void {
  const target = event.target
  if (target instanceof HTMLSelectElement) {
    store.selectProfile(target.value, props.profiles)
  }
}

function onModelChange(event: Event): void {
  const target = event.target
  if (target instanceof HTMLSelectElement) {
    store.selectModel(target.value === '' ? null : target.value)
  }
}

async function openPreview(): Promise<void> {
  await store.startPreview()
}

async function confirmApply(): Promise<void> {
  const result = await store.startApply()
  if (result !== null) {
    emit('applied', result)
  }
}

function cancelPreview(): void {
  store.clearPreview()
}

function repreview(): void {
  void store.startPreview()
}
</script>

<template>
  <section class="switch" aria-labelledby="switch-panel-title">
    <header class="switch__header">
      <h2 id="switch-panel-title">切换档案</h2>
      <p class="switch__hint">
        预览只读取配置，不会写盘；确认后才会生成快照并写入。
      </p>
    </header>

    <div class="switch__controls">
      <label for="switch-profile">选择档案</label>
      <select
        id="switch-profile"
        :value="selectedProfileId ?? ''"
        :disabled="previewing || applying || profiles.length === 0"
        @change="onProfileChange"
      >
        <option v-if="profiles.length === 0" value="">暂无可选档案</option>
        <option v-else value="" disabled>选择档案</option>
        <option v-for="profile in profiles" :key="profile.id" :value="profile.id">
          {{ profile.name }}
        </option>
      </select>

      <label for="switch-model">选择模型</label>
      <select
        id="switch-model"
        :value="modelValue"
        :disabled="previewing || applying || modelOptions.length === 0"
        @change="onModelChange"
      >
        <option v-if="modelOptions.length === 0" value="">保持当前模型</option>
        <option v-for="model in modelOptions" :key="model.id" :value="model.id">
          {{ model.display_name ?? model.id }}
        </option>
      </select>

      <button
        type="button"
        class="switch__preview"
        :disabled="!store.canPreview"
        @click="openPreview"
      >
        {{ previewing ? '正在预览…' : '预览改动' }}
      </button>
    </div>

    <p v-if="profiles.length === 0" class="switch__empty">
      暂无可切换档案，请先在「档案」页新建。
    </p>
    <p v-if="previewing" class="switch__status" role="status">正在生成预览…</p>
    <p v-if="error !== null && preview === null" class="switch__error" role="alert">
      {{ error }}
    </p>

    <div v-if="lastApplied !== null" class="switch__success" role="status">
      <p>已应用档案配置。快照 ID：{{ lastApplied.snapshot_id }}</p>
      <p>{{ lastApplied.restart_message }}</p>
    </div>

    <SwitchPreviewDialog
      v-if="preview !== null"
      :preview="preview"
      :profile-name="selectedProfile?.name ?? null"
      :busy="applying"
      :error="error"
      :error-code="store.errorCode"
      :details="details"
      @confirm="confirmApply"
      @cancel="cancelPreview"
      @repreview="repreview"
    />
  </section>
</template>

<style scoped>
.switch {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.switch__header h2 {
  margin: 0;
  font-size: var(--font-size-lg);
}

.switch__hint,
.switch__empty,
.switch__status {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.switch__controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.switch__controls label {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.switch__controls select {
  min-width: 12rem;
  max-width: 100%;
}

.switch__preview {
  border-color: var(--color-accent);
  color: var(--color-accent);
  font-weight: 600;
}

.switch__preview:focus-visible,
.switch__controls select:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.switch__error {
  margin: 0;
  color: var(--color-danger);
  overflow-wrap: anywhere;
}

.switch__success {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  border: 1px solid var(--status-ok-fg);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  background: var(--status-ok-bg);
  color: var(--status-ok-fg);
  font-size: var(--font-size-sm);
}

.switch__success p {
  margin: 0;
  overflow-wrap: anywhere;
}

@media (max-width: 767px) {
  .switch__controls {
    align-items: stretch;
    flex-direction: column;
  }

  .switch__controls select {
    width: 100%;
  }
}
</style>
