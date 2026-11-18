<script setup lang="ts">
import { computed, ref } from 'vue'

import type { SessionMessage, SessionWarning } from '../api/sessions'

const props = defineProps<{
  title: string | null
  sessionId: string | null
  messages: SessionMessage[]
  loading: boolean
  error: string | null
  warnings: SessionWarning[]
  hasMore: boolean
  totalMessages: number | null
  resumeEnabled?: boolean
}>()

const emit = defineEmits<{
  loadEarlier: []
}>()

const expanded = ref<Set<string>>(new Set())

function toggle(key: string): void {
  const next = new Set(expanded.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expanded.value = next
}

function isOpen(key: string): boolean {
  return expanded.value.has(key)
}

function rowLabel(message: SessionMessage): string {
  const name = message.tool_name ?? (message.role === 'tool_result' ? '工具结果' : '工具调用')
  const firstLine = message.content.split('\n').find((line) => line.trim().length > 0) ?? ''
  return firstLine.length === 0 ? name : name + ' · ' + firstLine.slice(0, 64)
}

function detail(message: SessionMessage): string {
  const text = message.content.trim()
  return text.length === 0 ? '（没有输出）' : text
}

const headerMeta = computed(() => {
  if (props.resumeEnabled === true) {
    return props.totalMessages === null ? '只读 · 下方输入即继续' : '只读 · 下方输入即继续 · 共 ' + props.totalMessages + ' 条'
  }
  if (props.totalMessages === null) {
    return '只读回放'
  }
  return '只读 · 共 ' + props.totalMessages + ' 条'
})
</script>

<template>
  <section class="history" aria-labelledby="history-timeline-title">
    <header class="history__header">
      <div class="history__heading">
        <h2 id="history-timeline-title" class="history__title">{{ title ?? '选择一段历史会话' }}</h2>
        <span class="history__meta">{{ headerMeta }}</span>
      </div>
      <span v-if="sessionId !== null" class="history__id" :title="sessionId">{{ sessionId.slice(0, 8) }}</span>
    </header>

    <div v-if="loading && messages.length === 0" class="history__state" role="status">
      正在读取会话…
    </div>
    <div v-else-if="error" class="history__state history__state--error" role="alert">
      {{ error }}
    </div>
    <div v-else-if="sessionId === null" class="history__state">
      从左侧选择一段会话开始回放。
    </div>
    <div v-else-if="messages.length === 0" class="history__state">
      这段会话没有可展示的消息。
    </div>
    <div v-else class="history__scroll">
      <div v-if="warnings.length > 0" class="history__warning" role="status">
        {{ warnings.map((warning) => warning.message).join('；') }}
      </div>

      <template v-for="message in messages" :key="message.id">
        <article v-if="message.role === 'user'" class="msg msg--user">{{ message.content }}</article>
        <article v-else-if="message.role === 'assistant'" class="msg msg--assistant">{{ message.content }}</article>
        <div v-else-if="message.role === 'system'" class="msg msg--system" role="status">
          {{ message.content }}
        </div>
        <div v-else-if="message.role === 'unknown'" class="process__item">
          <button class="process__row" type="button" :aria-expanded="isOpen(message.id)" @click="toggle(message.id)">
            <span class="process__chevron" aria-hidden="true">{{ isOpen(message.id) ? '▾' : '▸' }}</span>
            <span class="process__label">未知事件 · raw_type: {{ message.raw_type ?? 'unknown' }}</span>
          </button>
          <pre v-if="isOpen(message.id)" class="process__detail">{{ detail(message) }}</pre>
        </div>
        <div v-else class="process__item">
          <button class="process__row" type="button" :aria-expanded="isOpen(message.id)" @click="toggle(message.id)">
            <span class="process__chevron" aria-hidden="true">{{ isOpen(message.id) ? '▾' : '▸' }}</span>
            <span class="process__label">{{ rowLabel(message) }}</span>
            <span class="process__state">{{ message.role === 'tool_result' ? '结果' : '调用' }}</span>
          </button>
          <pre v-if="isOpen(message.id)" class="process__detail">{{ detail(message) }}</pre>
        </div>
      </template>

      <div class="history__footer">
        <span v-if="!hasMore" class="history__earliest">已到最早一条</span>
        <button v-else class="button button--secondary" type="button" :disabled="loading" @click="emit('loadEarlier')">
          {{ loading ? '加载中…' : '加载更早的消息' }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.history {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.history__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  padding: var(--space-md) var(--space-xl);
  border-bottom: 1px solid var(--color-border-card);
}

.history__heading {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.history__title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history__meta {
  color: var(--color-text-muted);
  font-size: 10px;
}

.history__id {
  flex: none;
  padding: 2px 7px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 10px;
}

.history__scroll {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-md);
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-xl);
}

.history__state {
  padding: var(--space-2xl);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  text-align: center;
}

.history__state--error {
  color: var(--color-danger-fg);
}

.history__warning {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.history__footer {
  display: flex;
  justify-content: center;
  padding-top: var(--space-sm);
}

.history__earliest {
  color: var(--color-text-muted);
  font-size: 10px;
}

.msg {
  max-width: 720px;
  border-radius: var(--radius-lg);
  font-size: var(--font-size-md);
  line-height: var(--line-height-relaxed);
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.msg--user {
  align-self: flex-end;
  padding: 10px 14px;
  background: var(--color-primary);
  color: var(--color-surface);
}

.msg--assistant {
  align-self: flex-start;
  padding: 12px 16px;
  border: 1px solid var(--color-border-card);
  background: var(--color-surface);
  color: var(--color-text);
}

.msg--system {
  align-self: flex-start;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
  font-size: var(--font-size-sm);
}

.process__item {
  display: flex;
  flex-direction: column;
  max-width: 720px;
}

.process__row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  width: 100%;
  padding: 7px 10px;
  border: 0;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  text-align: left;
  cursor: pointer;
}

.process__row:hover {
  background: var(--color-bg-subtle);
}

.process__chevron {
  flex: none;
  width: 12px;
  color: var(--color-text-muted);
  font-size: 10px;
}

.process__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.process__state {
  flex: none;
  color: var(--color-text-muted);
  font-size: 10px;
}

.process__detail {
  margin: 0 0 var(--space-xs) 22px;
  padding: var(--space-sm) var(--space-md);
  max-height: 260px;
  overflow: auto;
  border-radius: var(--radius-md);
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1.5;
  white-space: pre-wrap;
}
</style>
