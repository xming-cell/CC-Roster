<script setup lang="ts">
import type { ModelEntry } from '../api/profiles'
import ChatComposer from './ChatComposer.vue'
import ContextSwitcher from './ContextSwitcher.vue'

defineProps<{
  model: string | null
  models: ModelEntry[]
  effort: string | null
  effortLevels: string[]
  sending: boolean
  reason: string | null
}>()

const emit = defineEmits<{
  'update:model': [value: string | null]
  'update:effort': [value: string | null]
  send: [content: string]
  stop: []
}>()
</script>

<template>
  <div class="resume">
    <div v-if="reason !== null" class="resume__unavailable" role="status">
      {{ reason }}
    </div>
    <template v-else>
      <div class="resume__context">
        <ContextSwitcher
          :model="model"
          :models="models"
          :effort="effort"
          :effort-levels="effortLevels"
          :disabled="sending"
          @update:model="emit('update:model', $event)"
          @update:effort="emit('update:effort', $event)"
        />
        <span class="resume__hint">使用当前供应商默认值，发送后才创建续聊会话</span>
      </div>
      <ChatComposer
        :disabled="false"
        :sending="sending"
        placeholder="输入消息，从这段历史继续…"
        hint="不输入时保持只读 · Enter 发送 / Shift+Enter 换行"
        @send="emit('send', $event)"
        @stop="emit('stop')"
      />
    </template>
  </div>
</template>

<style scoped>
.resume {
  flex: none;
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}

.resume__context {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-xl) 0;
}

.resume__hint {
  color: var(--color-text-muted);
  font-size: 10px;
}

.resume__unavailable {
  padding: var(--space-md) var(--space-xl);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}
</style>