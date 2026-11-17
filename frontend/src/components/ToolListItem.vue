<script setup lang="ts">
import { computed } from 'vue'

import type { ToolView } from '../api/tools'
import {
  configurationLabel,
  installationLabel,
  modelLabel,
  providerLabel,
} from '../utils/toolDisplay'
import ToolLogo from './ToolLogo.vue'
import ToolStatusBadge from './ToolStatusBadge.vue'

const props = defineProps<{
  tool: ToolView
  selected: boolean
}>()

const emit = defineEmits<{
  select: [toolId: string]
}>()

const installLabel = computed(() => installationLabel(props.tool))
const configLabel = computed(() => configurationLabel(props.tool))
const provider = computed(() => providerLabel(props.tool))
const model = computed(() => modelLabel(props.tool))
</script>

<template>
  <li class="tool-item" :class="{ 'tool-item--selected': selected }">
    <button
      type="button"
      class="tool-item__button"
      :aria-pressed="selected"
      @click="emit('select', tool.id)"
    >
      <span class="tool-item__icon" aria-hidden="true">
        <ToolLogo :tool-id="tool.id" size="sm" />
      </span>

      <span class="tool-item__content">
        <span class="tool-item__top">
          <span class="tool-item__name">{{ tool.display_name }}</span>
          <ToolStatusBadge :status="tool.status" />
        </span>
        <span class="tool-item__meta">{{ installLabel }} · {{ configLabel }}</span>
        <span class="tool-item__meta">供应商：{{ provider }} · 模型：{{ model }}</span>
      </span>
    </button>
  </li>
</template>

<style scoped>
.tool-item {
  margin: 0;
}

.tool-item__button {
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

.tool-item__button:hover {
  background: var(--color-bg-subtle);
}

.tool-item--selected .tool-item__button {
  border-color: var(--color-border-selected);
  background: var(--color-bg-selected);
}

.tool-item__icon {
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

.tool-item--selected .tool-item__icon {
  background: var(--color-surface);
  color: var(--color-primary);
}



.tool-item__content {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-xs);
  min-width: 0;
}

.tool-item__top {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  min-width: 0;
}

.tool-item__name {
  flex: 1;
  min-width: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
  line-height: var(--line-height-tight);
  overflow-wrap: anywhere;
}

.tool-item__meta {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
  overflow-wrap: anywhere;
}
</style>

