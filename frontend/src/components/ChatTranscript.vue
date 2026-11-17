<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import type { ChatMessage } from '../api/chat'
import type { StreamingState } from '../stores/chat'
import { groupMessages, processDetail, processLabel } from '../utils/chatDisplay'

const props = defineProps<{
  messages: ChatMessage[]
  streaming: StreamingState | null
}>()

const blocks = computed(() => groupMessages(props.messages))
const expanded = ref<Set<string>>(new Set())
const scroller = ref<HTMLElement | null>(null)

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

async function scrollToBottom(): Promise<void> {
  await nextTick()
  const element = scroller.value
  if (element !== null) {
    element.scrollTop = element.scrollHeight
  }
}

watch(
  () => [props.messages.length, props.streaming?.content.length, props.streaming?.tools.length],
  () => {
    void scrollToBottom()
  },
)
</script>

<template>
  <div ref="scroller" class="transcript" role="log" aria-live="polite" aria-label="对话消息">
    <div v-if="messages.length === 0 && streaming === null" class="transcript__empty">
      <h3>还没有消息</h3>
      <p>在下方输入任务；发送前会再校验项目目录与供应商。</p>
    </div>

    <template v-for="block in blocks" :key="block.key">
      <article v-if="block.kind === 'user'" class="msg msg--user">
        {{ block.message.content }}
      </article>
      <article v-else-if="block.kind === 'assistant'" class="msg msg--assistant">
        {{ block.message.content }}
      </article>
      <div v-else-if="block.kind === 'system'" class="msg msg--system" role="alert">
        {{ block.message.content }}
      </div>
      <section v-else class="process" aria-label="工具调用过程">
        <div v-for="message in block.messages" :key="message.id" class="process__item">
          <button
            class="process__row"
            type="button"
            :aria-expanded="isOpen(message.id)"
            @click="toggle(message.id)"
          >
            <span class="process__chevron" aria-hidden="true">{{ isOpen(message.id) ? '▾' : '▸' }}</span>
            <span class="process__label">{{ processLabel(message) }}</span>
            <span class="process__state">{{ message.is_error ? '失败' : '完成' }}</span>
          </button>
          <pre v-if="isOpen(message.id)" class="process__detail">{{ processDetail(message) }}</pre>
        </div>
      </section>
    </template>

    <section v-if="streaming !== null" class="process" aria-label="正在执行">
      <div v-if="streaming.content === ''" class="process__row process__row--status" role="status">
        <span class="process__dot" aria-hidden="true"></span>
        <span class="process__label">{{ streaming.status ?? '思考中…' }}</span>
      </div>
      <div v-for="tool in streaming.tools" :key="tool.key" class="process__item">
        <button
          class="process__row"
          type="button"
          :aria-expanded="isOpen(tool.key)"
          @click="toggle(tool.key)"
        >
          <span class="process__chevron" aria-hidden="true">{{ isOpen(tool.key) ? '▾' : '▸' }}</span>
          <span class="process__label">{{ tool.toolName }}</span>
          <span class="process__state">进行中</span>
        </button>
        <pre v-if="isOpen(tool.key)" class="process__detail">{{ tool.content || '（没有输出）' }}</pre>
      </div>
      <article v-if="streaming.content !== ''" class="msg msg--assistant">
        {{ streaming.content }}<span class="caret" aria-hidden="true">▍</span>
      </article>
    </section>
  </div>
</template>

<style scoped>
.transcript {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-md);
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-xl);
}

.transcript__empty {
  margin: auto;
  max-width: 420px;
  text-align: center;
  color: var(--color-text-secondary);
}

.transcript__empty h3 {
  margin: 0 0 var(--space-xs);
  color: var(--color-text);
  font-size: var(--font-size-md);
  font-weight: 600;
}

.transcript__empty p {
  margin: 0;
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}

.msg {
  max-width: 760px;
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
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
  font-size: var(--font-size-sm);
}

.process {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-width: 760px;
}

.process__item {
  display: flex;
  flex-direction: column;
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

.process__row--status {
  cursor: default;
  color: var(--color-warning-fg);
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

.process__dot {
  width: 6px;
  height: 6px;
  margin-left: 3px;
  border-radius: 50%;
  background: var(--color-warning);
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

.caret {
  color: var(--color-primary);
}
</style>
