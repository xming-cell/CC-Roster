<script setup lang="ts">
import { computed } from 'vue'

import type { ChatSessionView } from '../api/chat'
import { projectName, relativeTime } from '../utils/chatDisplay'

const props = defineProps<{
  sessions: ChatSessionView[]
  selectedId: string | null
  loading: boolean
  loaded: boolean
  error: string | null
}>()

const emit = defineEmits<{
  select: [sessionId: string]
  retry: []
}>()

interface ProjectGroup {
  path: string
  name: string
  sessions: ChatSessionView[]
}

const groups = computed<ProjectGroup[]>(() => {
  const byPath = new Map<string, ChatSessionView[]>()
  for (const session of props.sessions) {
    const list = byPath.get(session.project_dir) ?? []
    list.push(session)
    byPath.set(session.project_dir, list)
  }
  return Array.from(byPath.entries()).map(([path, sessions]) => ({
    path,
    name: projectName(path),
    sessions: [...sessions].sort(
      (left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at),
    ),
  }))
})
</script>

<template>
  <section class="sessions" aria-labelledby="sessions-title">
    <header class="sessions__header">
      <h2 id="sessions-title" class="sessions__title">最近会话</h2>
      <button class="sessions__refresh" type="button" aria-label="刷新会话列表" :disabled="loading" @click="emit('retry')">
        ↻
      </button>
    </header>

    <div v-if="loading && !loaded" class="sessions__state" role="status">正在读取会话…</div>
    <div v-else-if="error" class="sessions__state sessions__state--error" role="alert">
      <p>{{ error }}</p>
      <button class="button button--secondary" type="button" @click="emit('retry')">重试</button>
    </div>
    <div v-else-if="sessions.length === 0" class="sessions__state">
      还没有会话。点击右上角「+」开始。
    </div>
    <div v-else class="sessions__body">
      <section v-for="group in groups" :key="group.path" class="sessions__group">
        <h3 class="sessions__project" :title="group.path">{{ group.name }}</h3>
        <ul class="sessions__list">
          <li v-for="session in group.sessions" :key="session.id">
            <button
              class="sessions__item"
              :class="{ 'sessions__item--active': session.id === selectedId }"
              type="button"
              :aria-current="session.id === selectedId ? 'true' : undefined"
              @click="emit('select', session.id)"
            >
              <span class="sessions__item-title">{{ session.title }}</span>
              <span class="sessions__item-meta">{{ relativeTime(session.updated_at) }}</span>
            </button>
          </li>
        </ul>
      </section>
    </div>
  </section>
</template>

<style scoped>
.sessions {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
}

.sessions__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md) var(--space-md) var(--space-sm);
}

.sessions__title {
  margin: 0;
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--color-text-secondary);
}

.sessions__refresh {
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.sessions__refresh:hover:not(:disabled) {
  background: var(--color-bg-subtle);
  color: var(--color-text);
}

.sessions__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  padding: 0 var(--space-sm) var(--space-lg);
}

.sessions__group {
  min-width: 0;
}

.sessions__project {
  margin: 0 0 var(--space-xs);
  padding: 0 var(--space-sm);
  color: var(--color-text-muted);
  font-size: 10px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sessions__list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.sessions__item {
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

.sessions__item:hover {
  background: var(--color-bg-subtle);
}

.sessions__item--active {
  background: var(--color-bg-selected);
}

.sessions__item-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sessions__item-meta {
  color: var(--color-text-muted);
  font-size: 10px;
}

.sessions__state {
  padding: var(--space-md);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.sessions__state--error {
  color: var(--color-danger-fg);
}

.sessions__state p {
  margin: 0 0 var(--space-sm);
  overflow-wrap: anywhere;
}
</style>
