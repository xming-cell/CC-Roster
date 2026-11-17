<script setup lang="ts">
import { computed } from 'vue'

import type { ToolView, ToolWarning } from '../api/tools'
import ToolListItem from './ToolListItem.vue'

const props = defineProps<{
  tools: ToolView[]
  warnings: ToolWarning[]
  loading: boolean
  loaded: boolean
  error: string | null
  selectedToolId: string | null
}>()

const emit = defineEmits<{
  refresh: []
  select: [toolId: string]
}>()

const attentionCount = computed(() => props.tools.filter((tool) => tool.status !== 'ok').length)
</script>

<template>
  <section class="panel" role="region" aria-labelledby="tool-list-title">
    <header class="panel__header">
      <div class="panel__heading">
        <h2 id="tool-list-title" class="panel__title">工具</h2>
        <p v-if="loaded" class="panel__count">
          共 {{ tools.length }} 个工具 · {{ attentionCount }} 个需处理
        </p>
        <p v-if="loading" class="panel__status" role="status">
          <span v-if="loaded">正在重新检测…</span>
          <span v-else>正在检测本机工具…</span>
        </p>
        <p v-else-if="!loaded && error" class="panel__status panel__status--error">检测失败</p>
      </div>

      <button
        class="icon-button"
        :class="{ 'icon-button--active': loading }"
        type="button"
        aria-label="重新检测工具列表"
        :disabled="loading"
        @click="emit('refresh')"
      >
        <svg class="icon-button__icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
          <path d="M13 5.2A5.4 5.4 0 1 0 13.4 10" />
          <path d="M13 2.8v2.7H10.3" />
        </svg>
      </button>
    </header>

    <div class="panel__body">
      <div v-if="loading && !loaded" class="state state--loading" aria-hidden="true">
        <div class="skeleton-list">
          <div v-for="row in 3" :key="row" class="skeleton">
            <span class="skeleton__badge"></span>
            <span class="skeleton__lines">
              <span class="skeleton__line skeleton__line--title"></span>
              <span class="skeleton__line"></span>
            </span>
          </div>
        </div>
      </div>

      <div v-else-if="error && !loaded" class="state state--error" role="alert">
        <h3 class="state__title">工具读取失败</h3>
        <p class="state__text">{{ error }}</p>
        <p class="state__hint">请确认后端服务已启动，然后重试。</p>
        <button class="button button--secondary" type="button" @click="emit('refresh')">
          重试
        </button>
      </div>

      <template v-else>
        <div v-if="error" class="notice notice--error" role="alert">
          <h3 class="notice__title">刷新失败</h3>
          <p class="notice__text">{{ error }}</p>
          <p class="notice__hint">当前显示上次的检测结果。</p>
        </div>

        <section
          v-if="warnings.length > 0"
          class="notice notice--warning"
          role="status"
          aria-labelledby="partial-warning-title"
        >
          <h3 id="partial-warning-title" class="notice__title">部分工具检测失败</h3>
          <ul class="notice__list">
            <li v-for="warning in warnings" :key="`${warning.code}-${warning.message}`">
              {{ warning.code }}: {{ warning.message }}
            </li>
          </ul>
        </section>

        <div v-if="tools.length === 0" class="state">
          <h3 class="state__title">
            {{ warnings.length > 0 ? '未发现可读取的工具' : '尚未发现已安装的 AI 工具' }}
          </h3>
          <p class="state__text">
            {{
              warnings.length > 0
                ? '部分工具的配置读取失败，请查看上方原因。'
                : '安装 Claude Code 或 Codex CLI 后，点击「重新检测」。'
            }}
          </p>
          <p class="state__hint">扫描只读取本地配置，不会修改任何文件。</p>
        </div>

        <ul v-else class="tool-list" aria-label="工具列表">
          <ToolListItem
            v-for="tool in tools"
            :key="tool.id"
            :tool="tool"
            :selected="tool.id === selectedToolId"
            @select="emit('select', $event)"
          />
        </ul>
      </template>
    </div>
  </section>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
}

.panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-sm);
  padding: var(--space-lg) var(--space-md) var(--space-md);
  border-bottom: 1px solid var(--color-border);
}

.panel__heading {
  min-width: 0;
}

.panel__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 700;
  line-height: var(--line-height-tight);
}

.panel__count {
  margin: 2px 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
}

.panel__status {
  margin: 2px 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
}

.panel__status--error {
  color: var(--color-danger-fg);
}

.icon-button__icon {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.panel__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-md);
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.state {
  padding: var(--space-xl) var(--space-md);
  text-align: center;
}

.state--error {
  border-radius: var(--radius-lg);
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.state__title {
  margin: 0 0 var(--space-sm);
  font-size: var(--font-size-md);
  font-weight: 600;
  line-height: var(--line-height-tight);
}

.state__text {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.state--error .state__text {
  color: var(--color-danger-fg);
}

.state__hint {
  margin: var(--space-sm) 0 var(--space-md);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.notice {
  margin-bottom: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
}

.notice--error {
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}

.notice--warning {
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
}

.notice__title {
  margin: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
  line-height: var(--line-height-tight);
}

.notice__text,
.notice__hint {
  margin: var(--space-xs) 0 0;
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.notice__hint {
  color: var(--color-text-secondary);
}

.notice__list {
  margin: var(--space-xs) 0 0;
  padding-left: 18px;
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.skeleton {
  display: flex;
  gap: var(--space-sm);
  padding: 10px;
}

.skeleton__badge,
.skeleton__line {
  background: var(--color-bg-subtle);
  animation: pulse 1.2s ease-in-out infinite;
}

.skeleton__badge {
  width: 24px;
  height: 24px;
  flex: none;
  border-radius: var(--radius-sm);
}

.skeleton__lines {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.skeleton__line {
  width: 100%;
  height: 10px;
  border-radius: 999px;
}

.skeleton__line--title {
  width: 58%;
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
  .panel {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }
}
</style>
