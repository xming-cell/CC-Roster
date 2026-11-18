<script setup lang="ts">
import { computed } from 'vue'

import type { ToolView } from '../api/tools'
import type { ToolProviderSummary } from '../stores/profiles'
import {
  configurationLabel,
  installationLabel,
} from '../utils/toolDisplay'
import ToolLogo from './ToolLogo.vue'
import ToolStatusBadge from './ToolStatusBadge.vue'

const props = defineProps<{
  tool: ToolView
  selected: boolean
  summary: ToolProviderSummary | undefined
  summaryState: 'loading' | 'error' | 'ready'
}>()

const emit = defineEmits<{
  select: [toolId: string]
}>()

const summaryText = computed(() => {
  if (props.summaryState === 'error') {
    return '供应商 — · 汇总读取失败'
  }
  if (props.summaryState === 'loading') {
    return '正在读取供应商…'
  }
  const summary = props.summary
  if (summary === undefined || summary.count === 0) {
    return '0 个供应商 · 当前未启用'
  }
  if (summary.activeName !== null) {
    return summary.count + ' 个供应商 · 启用中 ' + summary.activeName
  }
  return summary.count + ' 个供应商 · 当前未启用'
})
</script>

<template>
  <li class="provider-tool">
    <button
      class="provider-tool__button"
      :class="{ 'provider-tool__button--selected': selected }"
      type="button"
      :aria-pressed="selected"
      @click="emit('select', tool.id)"
    >
      <span class="provider-tool__icon" aria-hidden="true">
        <ToolLogo :tool-id="tool.id" size="sm" />
      </span>

      <span class="provider-tool__content">
        <span class="provider-tool__top">
          <span class="provider-tool__name">{{ tool.display_name }}</span>
          <ToolStatusBadge :status="tool.status" />
        </span>
        <span class="provider-tool__meta">
          {{ installationLabel(tool) }} · {{ configurationLabel(tool) }}
        </span>
        <span
          class="provider-tool__meta"
          :class="{ 'provider-tool__meta--error': summaryState === 'error', 'provider-tool__meta--active': summary?.activeName }"
        >
          {{ summaryText }}
        </span>
      </span>
    </button>
  </li>
</template>

<style scoped>
.provider-tool {
  margin: 0;
}

.provider-tool__button {
  display: flex;
  width: 100%;
  align-items: flex-start;
  gap: var(--space-sm);
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--color-text);
  text-align: left;
  cursor: pointer;
  transition:
    background 120ms ease-out,
    border-color 120ms ease-out;
}

.provider-tool__button:hover {
  background: var(--color-bg-subtle);
}

.provider-tool__button--selected {
  border-color: var(--color-border-selected);
  background: var(--color-bg-selected);
}

.provider-tool__icon {
  display: inline-flex;
  width: 24px;
  height: 24px;
  flex: none;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
}

.provider-tool__button--selected .provider-tool__icon {
  background: var(--color-surface);
  color: var(--color-primary);
}


.provider-tool__content {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-xs);
  min-width: 0;
}

.provider-tool__top {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  min-width: 0;
}

.provider-tool__name {
  flex: 1;
  min-width: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
  line-height: var(--line-height-tight);
  overflow-wrap: anywhere;
}

.provider-tool__meta {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
  overflow-wrap: anywhere;
}

.provider-tool__meta--active {
  color: var(--color-primary-hover);
}

.provider-tool__meta--error {
  color: var(--color-danger-fg);
}
</style>
