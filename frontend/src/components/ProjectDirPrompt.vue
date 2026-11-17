<script setup lang="ts">
import { ref } from 'vue'

import ModalShell from './ModalShell.vue'

defineProps<{
  busy: boolean
  error: string | null
}>()

const emit = defineEmits<{
  confirm: [path: string]
  cancel: []
}>()

const value = ref('')

function submit(): void {
  const path = value.value.trim()
  if (path.length === 0) {
    return
  }
  emit('confirm', path)
}
</script>

<template>
  <ModalShell labelled-by="project-dir-title" @close="emit('cancel')">
    <div class="dir">
      <h2 id="project-dir-title" class="dir__title">选择项目目录</h2>
      <p class="dir__text">
        这个工具还没有历史会话。输入一次绝对路径后，后续新会话会自动沿用。
      </p>
      <label class="dir__label" for="project-dir-input">项目目录（绝对路径）</label>
      <input
        id="project-dir-input"
        v-model="value"
        class="dir__input"
        type="text"
        placeholder="D:\\projects\\demo"
        @keydown.enter.prevent="submit"
      />
      <p v-if="error !== null" class="dir__error" role="alert">{{ error }}</p>
      <footer class="dir__footer">
        <button class="button button--secondary" type="button" :disabled="busy" @click="emit('cancel')">
          取消
        </button>
        <button class="button" type="button" :disabled="busy || value.trim().length === 0" @click="submit">
          {{ busy ? '创建中…' : '创建会话' }}
        </button>
      </footer>
    </div>
  </ModalShell>
</template>

<style scoped>
.dir {
  padding: var(--space-xl);
}

.dir__title {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 700;
}

.dir__text {
  margin: var(--space-sm) 0 var(--space-lg);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}

.dir__label {
  display: block;
  margin-bottom: var(--space-xs);
  color: var(--color-info-fg);
  font-size: var(--font-size-xs);
}

.dir__input {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--color-border-control);
  border-radius: var(--radius-md);
  font: inherit;
  font-size: var(--font-size-sm);
}

.dir__error {
  margin: var(--space-sm) 0 0;
  color: var(--color-danger-fg);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.dir__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
  margin-top: var(--space-xl);
}
</style>
