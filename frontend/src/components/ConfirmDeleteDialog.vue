<script setup lang="ts">
import { onMounted, ref } from 'vue'

import type { ProfileView } from '../api/profiles'

defineProps<{
  profile: ProfileView
  busy: boolean
  error: string | null
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const cancelButton = ref<HTMLButtonElement | null>(null)

onMounted(() => {
  cancelButton.value?.focus()
})
</script>

<template>
  <div
    class="dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="delete-profile-title"
    @keydown.esc.prevent="emit('cancel')"
  >
    <div class="dialog__panel">
      <h2 id="delete-profile-title">删除档案「{{ profile.name }}」？</h2>
      <p>
        删除后档案、绑定关系和对应密钥都会移除，此操作不可撤销。
      </p>
      <p v-if="profile.used_by.length > 0" class="dialog__in-use">
        以下工具仍在使用该档案，删除后将解除这些绑定（不会回滚工具里已生效的配置）：
      </p>
      <ul v-if="profile.used_by.length > 0" class="dialog__tools">
        <li v-for="reference in profile.used_by" :key="reference.tool_id">
          {{ reference.display_name }}
          <span v-if="!reference.installed">（已不可用）</span>
        </li>
      </ul>

      <p v-if="error !== null" class="dialog__error" role="alert">{{ error }}</p>

      <footer class="dialog__actions">
        <button ref="cancelButton" type="button" :disabled="busy" @click="emit('cancel')">
          取消
        </button>
        <button
          type="button"
          class="dialog__confirm"
          :disabled="busy"
          @click="emit('confirm')"
        >
          {{ busy ? '删除中…' : '确认删除' }}
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
  width: min(32rem, 100%);
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

.dialog__in-use {
  color: var(--color-danger);
}

.dialog__tools {
  margin: 0;
  padding-left: var(--space-4);
}

.dialog__error {
  color: var(--color-danger);
}

.dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.dialog__confirm {
  color: var(--color-danger);
  font-weight: 600;
}
</style>