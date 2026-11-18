<script setup lang="ts">
import type { ProfileView } from '../api/profiles'
import ModalShell from './ModalShell.vue'

defineProps<{
  profile: ProfileView
  stage: 'confirm' | 'in-use'
  busy: boolean
  error: string | null
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<template>
  <ModalShell labelled-by="provider-delete-title" role="alertdialog" @close="emit('cancel')">
    <div class="delete-dialog">
      <header class="delete-dialog__header">
        <div>
          <h2 id="provider-delete-title" class="delete-dialog__title">
            {{ stage === 'confirm' ? '删除供应商？' : '供应商仍被使用' }}
          </h2>
          <p class="delete-dialog__subtitle">{{ profile.name }}</p>
        </div>
      </header>

      <div v-if="error" class="delete-dialog__alert" role="alert">{{ error }}</div>

      <template v-if="stage === 'confirm'">
        <p class="delete-dialog__text">
          删除后会从所有工具移除绑定，并清理本地供应商数据。此操作不可恢复。
        </p>
        <p class="delete-dialog__hint">如果只想从当前工具移除，请先使用「从工具移除」。</p>
      </template>

      <template v-else>
        <p class="delete-dialog__text">以下工具仍在使用这个供应商。再次确认会同时解除它们的绑定：</p>
        <ul v-if="profile.used_by.length > 0" class="delete-dialog__tools">
          <li v-for="tool in profile.used_by" :key="tool.tool_id" class="delete-dialog__tool">
            <span>{{ tool.display_name }}</span>
            <span class="delete-dialog__tool-state">
              {{ tool.installed ? '已安装' : '已卸载' }}
            </span>
          </li>
        </ul>
        <p v-else class="delete-dialog__hint">占用信息未能完整读取；仍然删除会解除该供应商的所有绑定。</p>
      </template>

      <footer class="delete-dialog__footer">
        <button class="button button--secondary" type="button" :disabled="busy" @click="emit('cancel')">
          取消
        </button>
        <button class="button button--danger" type="button" :disabled="busy" @click="emit('confirm')">
          {{ busy ? '处理中…' : stage === 'confirm' ? '删除' : '仍然删除' }}
        </button>
      </footer>
    </div>
  </ModalShell>
</template>

<style scoped>
.delete-dialog {
  padding: var(--space-xl);
}

.delete-dialog__header {
  margin-bottom: var(--space-lg);
}

.delete-dialog__title {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: var(--line-height-tight);
}

.delete-dialog__subtitle {
  margin: var(--space-xs) 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
  overflow-wrap: anywhere;
}

.delete-dialog__alert {
  margin-bottom: var(--space-lg);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.delete-dialog__text {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
  line-height: var(--line-height-relaxed);
}

.delete-dialog__hint {
  margin: var(--space-sm) 0 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.delete-dialog__tools {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  margin: var(--space-md) 0 0;
  padding: 0;
  list-style: none;
}

.delete-dialog__tool {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.delete-dialog__tool-state {
  flex: none;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.delete-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
  margin-top: var(--space-xl);
}

.button--danger {
  border-color: transparent;
  background: var(--color-danger);
  color: var(--color-surface);
}

.button--danger:hover:not(:disabled) {
  background: var(--color-danger-fg);
}
</style>
