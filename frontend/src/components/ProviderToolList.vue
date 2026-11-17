<script setup lang="ts">
import { computed } from 'vue'

import type { ToolView } from '../api/tools'
import type { ToolProviderSummary } from '../stores/profiles'
import ProviderToolItem from './ProviderToolItem.vue'

const props = defineProps<{
  tools: ToolView[]
  loading: boolean
  loaded: boolean
  error: string | null
  selectedToolId: string | null
  summaries: Record<string, ToolProviderSummary>
  summaryLoading: boolean
  summaryLoaded: boolean
  summaryError: string | null
}>()

const emit = defineEmits<{
  select: [toolId: string]
  refresh: []
}>()

const attentionCount = computed(() => props.tools.filter((tool) => tool.status !== 'ok').length)
const summaryState = computed<'loading' | 'error' | 'ready'>(() => {
  if (props.summaryError !== null) {
    return 'error'
  }
  if (props.summaryLoading || !props.summaryLoaded) {
    return 'loading'
  }
  return 'ready'
})
const busy = computed(() => props.loading || props.summaryLoading)
</script>

<template>
  <section class="tool-panel" role="region" aria-labelledby="provider-tool-title">
    <header class="tool-panel__header">
      <div class="tool-panel__heading">
        <div class="tool-panel__title-row">
          <h2 id="provider-tool-title" class="tool-panel__title">工具</h2>
          <span v-if="loaded" class="tool-panel__count">{{ tools.length }} 个</span>
        </div>
        <p v-if="loading && !loaded" class="tool-panel__status" role="status">正在检测本机工具…</p>
        <p v-else-if="summaryError" class="tool-panel__status tool-panel__status--error">供应商汇总读取失败</p>
        <p v-else-if="summaryLoading || !summaryLoaded" class="tool-panel__status" role="status">正在读取供应商汇总…</p>
        <p v-else class="tool-panel__status">
          共 {{ tools.length }} 个工具 · {{ attentionCount }} 个需处理
        </p>
      </div>

      <button
        class="icon-button"
        :class="{ 'icon-button--active': busy }"
        type="button"
        aria-label="重新检测工具与供应商汇总"
        :disabled="busy"
        @click="emit('refresh')"
      >
        <svg class="tool-panel__refresh" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
          <path d="M13 5.2A5.4 5.4 0 1 0 13.4 10" />
          <path d="M13 2.8v2.7H10.3" />
        </svg>
      </button>
    </header>

    <div class="tool-panel__body">
      <div v-if="loading && !loaded" class="state state--loading" aria-hidden="true">
        <span v-for="row in 3" :key="row" class="state__skeleton"></span>
      </div>

      <div v-else-if="error && !loaded" class="state state--error" role="alert">
        <h3 class="state__title">工具读取失败</h3>
        <p class="state__text">{{ error }}</p>
        <button class="button button--secondary" type="button" @click="emit('refresh')">重试</button>
      </div>

      <template v-else>
        <div v-if="summaryError" class="tool-panel__notice" role="alert">
          <strong>供应商汇总读取失败</strong>
          <span>{{ summaryError }}</span>
          <span class="tool-panel__notice-hint">工具仍可切换，右侧列表会单独加载。</span>
        </div>

        <div v-if="tools.length === 0" class="state">
          <h3 class="state__title">尚未发现 AI 工具</h3>
          <p class="state__text">安装 Claude Code 或 Codex CLI 后，点击右上角重新检测。</p>
        </div>

        <ul v-else class="tool-panel__list" aria-label="工具列表">
          <ProviderToolItem
            v-for="tool in tools"
            :key="tool.id"
            :tool="tool"
            :selected="tool.id === selectedToolId"
            :summary="summaries[tool.id]"
            :summary-state="summaryState"
            @select="emit('select', $event)"
          />
        </ul>
      </template>
    </div>
  </section>
</template>

<style scoped>
.tool-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
}

.tool-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-sm);
  padding: var(--space-lg) var(--space-md) var(--space-md);
  border-bottom: 1px solid var(--color-border);
}

.tool-panel__heading {
  min-width: 0;
}

.tool-panel__title-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.tool-panel__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 700;
  line-height: var(--line-height-tight);
}

.tool-panel__count {
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.tool-panel__status {
  margin: var(--space-xs) 0 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.tool-panel__status--error {
  color: var(--color-danger-fg);
}

.tool-panel__refresh {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.5;
}

.tool-panel__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-sm);
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-md);
}

.tool-panel__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  margin: 0;
  padding: 0;
  list-style: none;
}

.tool-panel__notice {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.tool-panel__notice-hint {
  color: var(--color-text-secondary);
}

.state {
  padding: var(--space-lg);
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.state--error {
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.state__title {
  margin: 0 0 var(--space-xs);
  font-size: var(--font-size-md);
  font-weight: 600;
}

.state__text {
  margin: 0 0 var(--space-md);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
  overflow-wrap: anywhere;
}

.state--error .state__text {
  color: var(--color-danger-fg);
}

.state--loading {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.state__skeleton {
  height: 58px;
  border-radius: var(--radius-lg);
  background: var(--color-bg-subtle);
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.55;
  }

  50% {
    opacity: 1;
  }
}

@media (max-width: 980px) {
  .tool-panel {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }
}
</style>
