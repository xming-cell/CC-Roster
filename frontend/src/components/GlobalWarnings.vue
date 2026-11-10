<script setup lang="ts">
import { ref } from 'vue'

import type { ToolWarning } from '../api/tools'

defineProps<{
  warnings: ToolWarning[]
}>()

const open = ref(false)
</script>

<template>
  <section class="global-warnings" aria-label="全局警告">
    <button
      type="button"
      class="global-warnings__toggle"
      :aria-expanded="open"
      aria-controls="global-warnings-list"
      @click="open = !open"
    >
      部分工具检测失败（{{ warnings.length }}）
    </button>

    <ul v-if="open" id="global-warnings-list" class="global-warnings__list">
      <li v-for="warning in warnings" :key="`${warning.code}-${warning.message}`">
        <span class="global-warnings__code">{{ warning.code }}</span>
        <span class="global-warnings__message">{{ warning.message }}</span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.global-warnings {
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  background: var(--status-error-bg);
}

.global-warnings__toggle {
  width: 100%;
  border: 0;
  padding: var(--space-1) 0;
  background: transparent;
  color: var(--status-error-fg);
  font-size: var(--font-size-sm);
  text-align: left;
  cursor: pointer;
}

.global-warnings__toggle:focus-visible {
  outline: 2px solid var(--status-error-fg);
  outline-offset: 2px;
}

.global-warnings__list {
  margin: var(--space-1) 0 0;
  padding: 0;
  list-style: none;
  color: var(--status-error-fg);
  font-size: var(--font-size-sm);
}

.global-warnings__list li {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-1) 0;
}

.global-warnings__code {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
  font-size: var(--font-size-xs);
}

.global-warnings__message {
  overflow-wrap: anywhere;
}
</style>