<script setup lang="ts">
import { computed } from 'vue'

import type { SessionWarning, ToolSessionSummary } from '../api/sessions'
import { projectName, relativeTime } from '../utils/chatDisplay'

const props = defineProps<{
  sessions: ToolSessionSummary[]
  selectedId: string | null
  loading: boolean
  loaded: boolean
  error: string | null
  warnings: SessionWarning[]
}>()

const emit = defineEmits<{
  select: [sessionId: string]
  retry: []
}>()

interface ProjectGroup {
  key: string
  label: string
  sessions: ToolSessionSummary[]
}

const groups = computed<ProjectGroup[]>(() => {
  const buckets = new Map<string, ToolSessionSummary[]>()
  for (const session of props.sessions) {
    const key = session.project_path ?? ''
    const list = buckets.get(key) ?? []
    list.push(session)
    buckets.set(key, list)
  }
  return Array.from(buckets.entries()).map(([key, sessions]) => ({
    key: key === '' ? '__unknown__' : key,
    label: key === '' ? '未知项目' : projectName(key),
    sessions,
  }))
})
</script>

<template>
  <section class="history-list" aria-labelledby="history-list-title">
    <header class="history-list__header">
      <h2 id="history-list-title" class="history-list__title">历史会话</h2>
      <button class="history-list__refresh" type="button" aria-label="刷新历史会话" :disabled="loading" @click="emit('retry')">
        ↻
      </button>
    </header>

    <div v-if="loading && !loaded" class="history-list__state" role="status">正在读取历史…</div>
    <div v-else-if="error" class="history-list__state history-list__state--error" role="alert">
      <p>{{ error }}</p>
      <button class="button button--secondary" type="button" @click="emit('retry')">重试</button>
    </div>
    <div v-else-if="sessions.length === 0" class="history-list__state">
      这个工具还没有可回放的历史会话。
    </div>
    <div v-else class="history-list__body">
      <div v-if="warnings.length > 0" class="history-list__warning" role="status">
        部分会话读取失败：{{ warnings.map((warning) => warning.message).join('；') }}
      </div>
      <section v-for="group in groups" :key="group.key" class="history-list__group">
        <h3 class="history-list__project" :title="group.key">{{ group.label }}</h3>
        <ul class="history-list__items">
          <li v-for="session in group.sessions" :key="session.id">
            <button
              class="history-list__item"
              :class="{ 'history-list__item--active': session.id === selectedId }"
              type="button"
              :aria-current="session.id === selectedId ? 'true' : undefined"
              @click="emit('select', session.id)"
            >
              <span class="history-list__item-title">{{ session.title }}</span>
              <span class="history-list__item-meta">
                {{ relativeTime(session.updated_at) }}
                <template v-if="session.message_count !== null"> · {{ session.message_count }} 条</template>
              </span>
            </button>
          </li>
        </ul>
      </section>
      <p class="history-list__note">只读；读取前后原始文件 hash 不变。</p>
    </div>
  </section>
</template>

<style scoped>
.history-list {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
}

.history-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md) var(--space-md) var(--space-sm);
}

.history-list__title {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.history-list__refresh {
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.history-list__refresh:hover:not(:disabled) {
  background: var(--color-bg-subtle);
  color: var(--color-text);
}

.history-list__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  padding: 0 var(--space-sm) var(--space-lg);
}

.history-list__warning {
  padding: var(--space-sm);
  border-radius: var(--radius-md);
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
  font-size: 10px;
  overflow-wrap: anywhere;
}

.history-list__group {
  min-width: 0;
}

.history-list__project {
  margin: 0 0 var(--space-xs);
  padding: 0 var(--space-sm);
  color: var(--color-text-muted);
  font-size: 10px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-list__items {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.history-list__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 7px var(--space-sm);
  border: 0;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text);
  text-align: left;
  cursor: pointer;
}

.history-list__item:hover {
  background: var(--color-bg-subtle);
}

.history-list__item--active {
  background: var(--color-bg-selected);
}

.history-list__item-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-list__item-meta {
  color: var(--color-text-muted);
  font-size: 10px;
}

.history-list__state {
  padding: var(--space-md);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.history-list__state--error {
  color: var(--color-danger-fg);
}

.history-list__state p {
  margin: 0 0 var(--space-sm);
  overflow-wrap: anywhere;
}

.history-list__note {
  margin: var(--space-sm) 0 0;
  padding: 0 var(--space-sm);
  color: var(--color-text-muted);
  font-size: 10px;
}
</style>
