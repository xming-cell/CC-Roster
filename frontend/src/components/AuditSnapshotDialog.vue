<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiError } from '../api/client'
import { getSnapshot } from '../api/snapshots'
import type { SnapshotView } from '../api/snapshots'
import { errorText, formatDateTime } from '../utils/profileDisplay'
import ModalShell from './ModalShell.vue'

const props = defineProps<{ snapshotId: string }>()
const emit = defineEmits<{ close: [] }>()

const snapshot = ref<SnapshotView | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    snapshot.value = await getSnapshot(props.snapshotId)
  } catch (caught) {
    error.value =
      caught instanceof ApiError && caught.status === 404
        ? '快照不存在或已删除'
        : errorText(caught, '快照读取失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <ModalShell labelled-by="snapshot-title" size="wide" @close="emit('close')">
    <div class="snapshot">
      <header class="snapshot__header">
        <div>
          <h2 id="snapshot-title" class="snapshot__title">快照详情</h2>
          <p class="snapshot__subtitle">{{ snapshotId }}</p>
        </div>
        <button class="snapshot__close" type="button" aria-label="关闭" @click="emit('close')">✕</button>
      </header>

      <div v-if="loading" class="snapshot__state" role="status">正在读取快照…</div>
      <div v-else-if="error" class="snapshot__state snapshot__state--danger" role="alert">
        <strong>{{ error }}</strong>
        <button class="button button--secondary" type="button" @click="load">重试</button>
      </div>
      <template v-else-if="snapshot">
        <dl class="snapshot__meta">
          <div><dt>创建时间</dt><dd>{{ formatDateTime(snapshot.created_at) }}</dd></div>
          <div><dt>原因</dt><dd>{{ snapshot.reason === 'apply' ? '切换前快照' : '回滚前快照' }}</dd></div>
          <div><dt>工具</dt><dd>{{ snapshot.tool_id }}</dd></div>
          <div><dt>固定</dt><dd>{{ snapshot.pinned ? '已固定' : '未固定' }}</dd></div>
        </dl>

        <section class="snapshot__section">
          <h3>文件</h3>
          <ul v-if="snapshot.files.length > 0" class="snapshot__files">
            <li v-for="file in snapshot.files" :key="file.path">
              <span class="snapshot__path">{{ file.path }}</span>
              <span>{{ file.existed ? file.size + ' B' : '当时不存在' }}</span>
            </li>
          </ul>
          <p v-else class="snapshot__muted">没有文件记录。</p>
        </section>

        <section class="snapshot__section">
          <h3>字段变更</h3>
          <ul v-if="snapshot.changes.length > 0" class="snapshot__changes">
            <li v-for="change in snapshot.changes" :key="change.path + change.field">
              <strong>{{ change.field }}</strong>
              <span>{{ change.action === 'set' ? '设置' : '移除' }}</span>
              <code>{{ change.before ?? '—' }} → {{ change.after ?? '—' }}</code>
            </li>
          </ul>
          <p v-else class="snapshot__muted">没有字段变更摘要。</p>
        </section>
      </template>
    </div>
  </ModalShell>
</template>

<style scoped>
.snapshot { display: flex; flex-direction: column; gap: var(--space-lg); }
.snapshot__header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-lg); }
.snapshot__title { margin: 0; font-size: var(--font-size-xl); }
.snapshot__subtitle { margin: 2px 0 0; color: var(--color-text-muted); font-family: var(--font-mono); font-size: var(--font-size-xs); overflow-wrap: anywhere; }
.snapshot__close { border: 0; background: transparent; color: var(--color-text-muted); font-size: var(--font-size-lg); cursor: pointer; }
.snapshot__state { display: flex; align-items: center; justify-content: space-between; gap: var(--space-md); padding: var(--space-lg); border-radius: var(--radius-lg); background: var(--color-bg); color: var(--color-text-secondary); }
.snapshot__state--danger { background: var(--color-danger-bg); color: var(--color-danger-fg); }
.snapshot__meta { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-md); margin: 0; }
.snapshot__meta div { padding: var(--space-md); border-radius: var(--radius-md); background: var(--color-bg); }
.snapshot__meta dt { color: var(--color-text-muted); font-size: var(--font-size-xs); }
.snapshot__meta dd { margin: 3px 0 0; font-size: var(--font-size-sm); overflow-wrap: anywhere; }
.snapshot__section h3 { margin: 0 0 var(--space-sm); font-size: var(--font-size-sm); }
.snapshot__files, .snapshot__changes { display: flex; flex-direction: column; gap: var(--space-xs); margin: 0; padding: 0; list-style: none; }
.snapshot__files li, .snapshot__changes li { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-sm) var(--space-md); border: 1px solid var(--color-border-card); border-radius: var(--radius-md); font-size: var(--font-size-xs); }
.snapshot__path { flex: 1; font-family: var(--font-mono); overflow-wrap: anywhere; }
.snapshot__changes li { flex-wrap: wrap; }
.snapshot__changes code { width: 100%; color: var(--color-text-secondary); font-family: var(--font-mono); overflow-wrap: anywhere; }
.snapshot__muted { margin: 0; color: var(--color-text-muted); font-size: var(--font-size-sm); }
@media (max-width: 720px) { .snapshot__meta { grid-template-columns: 1fr 1fr; } }
</style>
