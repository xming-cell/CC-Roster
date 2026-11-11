<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type { ApiErrorDetails, FileConflictReason } from '../api/client'
import type { SwitchPreviewResponse } from '../api/switch'
import SwitchFileDiff from './SwitchFileDiff.vue'

const props = defineProps<{
  preview: SwitchPreviewResponse
  profileName: string | null
  busy: boolean
  error: string | null
  errorCode: string | null
  details: ApiErrorDetails | null
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
  repreview: []
}>()

const cancelButton = ref<HTMLButtonElement | null>(null)

const conflicts = computed(() => props.details?.conflicts ?? [])
const stalePaths = computed(() => props.details?.stale_paths ?? [])
const canRepreview = computed(
  () => props.errorCode === 'WRITE_CONFLICT' || props.errorCode === 'SWITCH_PREVIEW_STALE',
)
const title = computed(() =>
  props.profileName === null
    ? '确认应用切换？'
    : `确认切换到「${props.profileName}」？`,
)

function reasonLabel(reason: FileConflictReason): string {
  if (reason === 'MISSING') {
    return '文件已被删除'
  }
  if (reason === 'CREATED') {
    return '文件被新建'
  }
  return '文件内容已变化'
}

function cancel(): void {
  if (!props.busy) {
    emit('cancel')
  }
}

onMounted(() => {
  cancelButton.value?.focus()
})
</script>

<template>
  <div
    class="dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="switch-preview-title"
    aria-describedby="switch-restart-message"
    @keydown.esc.prevent="cancel"
  >
    <div class="dialog__panel">
      <h2 id="switch-preview-title">{{ title }}</h2>

      <p id="switch-restart-message" class="dialog__restart" role="status">
        {{ preview.restart_message }}
      </p>

      <section
        v-if="preview.blockers.length > 0"
        class="dialog__blockers"
        aria-labelledby="switch-blockers-title"
      >
        <h3 id="switch-blockers-title">阻止应用的问题</h3>
        <ul>
          <li
            v-for="blocker in preview.blockers"
            :key="`${blocker.code}-${blocker.path ?? ''}-${blocker.message}`"
          >
            <strong>{{ blocker.code }}</strong>：{{ blocker.message }}
            <span v-if="blocker.path !== null">（{{ blocker.path }}）</span>
          </li>
        </ul>
      </section>

      <section
        v-if="preview.warnings.length > 0"
        class="dialog__warnings"
        aria-labelledby="switch-warnings-title"
      >
        <h3 id="switch-warnings-title">警告</h3>
        <ul>
          <li
            v-for="warning in preview.warnings"
            :key="`${warning.code}-${warning.message}`"
          >
            <strong>{{ warning.code }}</strong>：{{ warning.message }}
          </li>
        </ul>
      </section>

      <section class="dialog__files" aria-labelledby="switch-files-title">
        <h3 id="switch-files-title">文件改动</h3>
        <SwitchFileDiff
          v-for="file in preview.files"
          :key="file.path"
          :file="file"
        />
        <p v-if="preview.files.length === 0" class="dialog__empty">
          没有可应用的文件改动
        </p>
      </section>

      <p v-if="error !== null" class="dialog__error" role="alert">{{ error }}</p>

      <section
        v-if="conflicts.length > 0 || stalePaths.length > 0"
        class="dialog__details"
        aria-label="冲突详情"
      >
        <p v-if="conflicts.length > 0">冲突文件：</p>
        <ul v-if="conflicts.length > 0">
          <li v-for="conflict in conflicts" :key="conflict.path">
            {{ conflict.path }}（{{ reasonLabel(conflict.reason) }}）
          </li>
        </ul>
        <p v-if="stalePaths.length > 0">过期文件：{{ stalePaths.join('、') }}</p>
      </section>

      <footer class="dialog__actions">
        <button
          v-if="canRepreview"
          type="button"
          :disabled="busy"
          @click="emit('repreview')"
        >
          重新预览
        </button>
        <button ref="cancelButton" type="button" :disabled="busy" @click="cancel">
          取消
        </button>
        <button
          type="button"
          class="dialog__confirm"
          :disabled="busy || !preview.can_apply"
          @click="emit('confirm')"
        >
          {{ busy ? '应用中…' : '确认应用' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.dialog {
  position: fixed;
  z-index: 10;
  inset: 0;
  display: grid;
  place-items: center;
  padding: var(--space-4);
  background: rgb(16 24 40 / 55%);
}

.dialog__panel {
  width: min(54rem, 100%);
  max-height: 100%;
  overflow-y: auto;
  border-radius: var(--radius-md);
  padding: var(--space-4);
  background: var(--color-surface);
  box-shadow: 0 12px 32px rgb(16 24 40 / 24%);
}

.dialog__panel h2 {
  margin-top: 0;
  font-size: var(--font-size-lg);
  overflow-wrap: anywhere;
}

.dialog__panel h3 {
  margin-bottom: var(--space-2);
  font-size: var(--font-size-md);
}

.dialog__restart {
  border: 1px solid var(--status-unconfigured-fg);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  background: var(--status-unconfigured-bg);
  color: var(--status-unconfigured-fg);
  font-weight: 600;
}

.dialog__blockers,
.dialog__warnings,
.dialog__details {
  margin-top: var(--space-3);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-sm);
}

.dialog__blockers {
  background: var(--status-error-bg);
  color: var(--status-error-fg);
}

.dialog__warnings {
  background: var(--status-unconfigured-bg);
  color: var(--status-unconfigured-fg);
}

.dialog__blockers ul,
.dialog__warnings ul,
.dialog__details ul {
  margin: 0;
  padding-left: var(--space-4);
  overflow-wrap: anywhere;
}

.dialog__files {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.dialog__empty {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.dialog__error {
  color: var(--color-danger);
  overflow-wrap: anywhere;
}

.dialog__details {
  background: var(--status-error-bg);
  color: var(--status-error-fg);
  overflow-wrap: anywhere;
}

.dialog__details p {
  margin: 0;
}

.dialog__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.dialog__confirm {
  color: var(--color-accent);
  font-weight: 600;
}

@media (max-width: 767px) {
  .dialog {
    padding: var(--space-2);
  }

  .dialog__panel {
    padding: var(--space-3);
  }
}
</style>
