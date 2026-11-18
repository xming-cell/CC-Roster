<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  disabled: boolean
  sending: boolean
  placeholder: string
  hint: string
}>()

const emit = defineEmits<{
  send: [content: string]
  stop: []
}>()

const draft = ref('')

function submit(): void {
  const content = draft.value.trim()
  if (content.length === 0 || props.disabled || props.sending) {
    return
  }
  draft.value = ''
  emit('send', content)
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) {
    return
  }
  event.preventDefault()
  submit()
}
</script>

<template>
  <div class="composer">
    <textarea
      v-model="draft"
      class="composer__input"
      rows="3"
      :placeholder="placeholder"
      :disabled="disabled"
      aria-label="输入消息"
      @keydown="handleKeydown"
    ></textarea>
    <div class="composer__bar">
      <span class="composer__hint">{{ hint }}</span>
      <button v-if="sending" class="button button--secondary" type="button" @click="emit('stop')">
        停止
      </button>
      <button
        v-else
        class="button"
        type="button"
        :disabled="disabled || draft.trim().length === 0"
        @click="submit"
      >
        发送
      </button>
    </div>
  </div>
</template>

<style scoped>
.composer {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  padding: var(--space-md) var(--space-xl) var(--space-lg);
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}

.composer__input {
  width: 100%;
  min-height: 72px;
  max-height: 180px;
  padding: 10px 12px;
  border: 1px solid var(--color-border-control);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  color: var(--color-text);
  font: inherit;
  font-size: var(--font-size-md);
  line-height: var(--line-height-relaxed);
  resize: vertical;
}

.composer__input:disabled {
  background: var(--color-bg-subtle);
  color: var(--color-text-muted);
  cursor: not-allowed;
}

.composer__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}

.composer__hint {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}
</style>
