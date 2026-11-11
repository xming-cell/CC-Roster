<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import type {
  RestoredFileView,
  SnapshotChange,
  SnapshotReason,
  SnapshotSummary,
} from '../api/snapshots'
import { useSnapshotsStore } from '../stores/snapshots'

const props = defineProps<{ toolId: string }>()

const store = useSnapshotsStore()
const {
  snapshots,
  retentionLimit,
  warnings,
  loading,
  error,
  refreshError,
  actionError,
  pinBusyId,
  rollbackBusyId,
  pendingRollback,
  lastRollback,
} = storeToRefs(store)

const cancelRollbackButton = ref<HTMLButtonElement | null>(null)

const initialLoading = computed(
  () => loading.value && snapshots.value.length === 0 && error.value === null,
)

watch(
  () => props.toolId,
  (toolId) => {
    void store.fetchSnapshots(toolId)
  },
  { immediate: true },
)

watch(pendingRollback, async (target) => {
  if (target !== null) {
    await nextTick()
    cancelRollbackButton.value?.focus()
  }
})

function reasonLabel(reason: SnapshotReason): string {
  return reason === 'apply' ? '应用前快照' : '回滚前快照'
}

function restoredLabel(action: RestoredFileView['action']): string {
  if (action === 'restored') {
    return '已恢复'
  }
  if (action === 'deleted') {
    return '已删除'
  }
  return '未变化'
}

function changeActionLabel(action: SnapshotChange['action']): string {
  return action === 'set' ? '设置' : '删除'
}

function beforeLabel(change: SnapshotChange): string {
  return change.before ?? '（不存在）'
}

function afterLabel(change: SnapshotChange): string {
  return change.action === 'remove' ? '（删除）' : (change.after ?? '（不存在）')
}

function formatTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString('zh-CN', { hour12: false })
}

function pinLabel(snapshot: SnapshotSummary): string {
  return snapshot.pinned ? '取消固定' : '固定'
}

function togglePin(snapshot: SnapshotSummary): void {
  void store.setPinned(snapshot.id, !snapshot.pinned)
}

function confirmRollback(): void {
  void store.confirmRollback()
}

function cancelRollback(): void {
  store.cancelRollback()
}
</script>

<template>
  <section class="snapshots" aria-labelledby="snapshot-panel-title">
    <header class="snapshots__header">
      <h2 id="snapshot-panel-title">快照 / 回滚</h2>
      <button
        type="button"
        class="snapshots__reload"
        :disabled="loading || rollbackBusyId !== null"
        aria-label="重新加载快照"
        @click="store.fetchSnapshots()"
      >
        重新加载
      </button>
    </header>
    <p class="snapshots__hint">
      每次应用前会自动生成快照；回滚会先为当前状态再生成一份快照。不提供快照内容下载。
    </p>
    <p v-if="retentionLimit !== null" class="snapshots__hint">
      最多保留最近 {{ retentionLimit }} 份快照，固定的快照不会被自动清理。
    </p>

    <p v-if="initialLoading" class="snapshots__status" role="status">
      正在加载快照…
    </p>
    <div v-else-if="error !== null" class="snapshots__fatal" role="alert">
      <p>{{ error }}</p>
      <button type="button" @click="store.fetchSnapshots()">重试</button>
    </div>

    <template v-else>
      <p v-if="refreshError !== null" class="snapshots__status" role="status">
        刷新失败，当前显示上次结果：{{ refreshError }}
      </p>
      <p
        v-if="actionError !== null && pendingRollback === null"
        class="snapshots__error"
        role="alert"
      >
        {{ actionError }}
      </p>

      <section v-if="warnings.length > 0" class="snapshots__warnings" aria-label="快照警告">
        <h3>部分快照无法读取</h3>
        <ul>
          <li v-for="warning in warnings" :key="`${warning.code}-${warning.message}`">
            {{ warning.code }}：{{ warning.message }}
          </li>
        </ul>
      </section>

      <section v-if="lastRollback !== null" class="snapshots__success" role="status">
        <p>
          已回滚到快照 {{ lastRollback.snapshot_id }}。回滚前快照 ID：{{
            lastRollback.pre_rollback_snapshot_id
          }}
        </p>
        <ul>
          <li v-for="file in lastRollback.files" :key="file.path">
            {{ file.path }}（{{ restoredLabel(file.action) }}）
          </li>
        </ul>
      </section>

      <p v-if="snapshots.length === 0" class="snapshots__empty">
        暂无快照，应用档案后会自动生成
      </p>
      <ul v-else class="snapshots__list" aria-label="快照列表">
        <li v-for="snapshot in snapshots" :key="snapshot.id" class="snapshot">
          <div class="snapshot__header">
            <strong class="snapshot__time">{{ formatTime(snapshot.created_at) }}</strong>
            <span class="snapshot__reason">{{ reasonLabel(snapshot.reason) }}</span>
            <span class="snapshot__pin">{{ snapshot.pinned ? '已固定' : '未固定' }}</span>
          </div>
          <p class="snapshot__id">快照 ID：{{ snapshot.id }}</p>

          <ul class="snapshot__files" aria-label="快照文件">
            <li v-for="file in snapshot.files" :key="file.path">
              <span class="snapshot__path">{{ file.path }}</span>
              <span v-if="!file.existed" class="snapshot__notation">（快照时不存在）</span>
            </li>
          </ul>

          <section class="snapshot__changes" aria-label="变更摘要">
            <h4>变更摘要</h4>
            <ul v-if="snapshot.changes.length > 0">
              <li
                v-for="change in snapshot.changes"
                :key="`${change.path}|${change.field}|${change.action}`"
              >
                <strong>{{ change.field }}</strong>
                （{{ changeActionLabel(change.action) }}）：{{ beforeLabel(change) }} →
                {{ afterLabel(change) }}
              </li>
            </ul>
            <p v-else class="snapshot__notation">无字段变更</p>
          </section>

          <div class="snapshot__actions">
            <button
              type="button"
              :aria-label="`${pinLabel(snapshot)}快照 ${snapshot.id}`"
              :aria-pressed="snapshot.pinned"
              :disabled="pinBusyId !== null || rollbackBusyId !== null"
              @click="togglePin(snapshot)"
            >
              {{ pinBusyId === snapshot.id ? '保存中…' : pinLabel(snapshot) }}
            </button>
            <button
              type="button"
              :aria-label="`回滚到快照 ${snapshot.id}`"
              :disabled="pinBusyId !== null || rollbackBusyId !== null"
              @click="store.requestRollback(snapshot)"
            >
              回滚到此快照
            </button>
          </div>
        </li>
      </ul>
    </template>

    <div
      v-if="pendingRollback !== null"
      class="dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="rollback-dialog-title"
      @keydown.esc.prevent="cancelRollback"
    >
      <div class="dialog__panel">
        <h3 id="rollback-dialog-title">
          确认回滚到快照 {{ pendingRollback.id }}？
        </h3>
        <p>
          回滚前会自动为当前状态生成一份快照。回滚会恢复该快照中的文件，快照内容不可下载。
        </p>
        <p v-if="actionError !== null" class="snapshots__error" role="alert">
          {{ actionError }}
        </p>
        <footer class="dialog__actions">
          <button
            ref="cancelRollbackButton"
            type="button"
            :disabled="rollbackBusyId !== null"
            @click="cancelRollback"
          >
            取消
          </button>
          <button
            type="button"
            class="dialog__confirm"
            :disabled="rollbackBusyId !== null"
            @click="confirmRollback"
          >
            {{ rollbackBusyId !== null ? '回滚中…' : '确认回滚' }}
          </button>
        </footer>
      </div>
    </div>
  </section>
</template>

<style scoped>
.snapshots {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.snapshots__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.snapshots__header h2 {
  margin: 0;
  font-size: var(--font-size-lg);
}

.snapshots__reload {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  padding: var(--space-1) var(--space-3);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}

.snapshots__reload:hover:not(:disabled) {
  color: var(--color-accent);
  border-color: var(--color-accent);
}

.snapshots__reload:focus-visible,
.snapshot__actions button:focus-visible,
.snapshots__fatal button:focus-visible,
.dialog__actions button:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.snapshots__reload:disabled,
.snapshot__actions button:disabled,
.snapshots__fatal button:disabled,
.dialog__actions button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.snapshots__hint,
.snapshots__status,
.snapshots__empty {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.snapshots__error,
.snapshots__fatal {
  margin: 0;
  color: var(--color-danger);
  overflow-wrap: anywhere;
}

.snapshots__warnings {
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  background: var(--status-unconfigured-bg);
  color: var(--status-unconfigured-fg);
  font-size: var(--font-size-sm);
}

.snapshots__warnings h3 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-size-md);
}

.snapshots__warnings ul {
  margin: 0;
  padding-left: var(--space-4);
  overflow-wrap: anywhere;
}

.snapshots__success {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  border: 1px solid var(--status-ok-fg);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  background: var(--status-ok-bg);
  color: var(--status-ok-fg);
  font-size: var(--font-size-sm);
}

.snapshots__success p,
.snapshots__success ul {
  margin: 0;
  overflow-wrap: anywhere;
}

.snapshots__success ul {
  padding-left: var(--space-4);
}

.snapshots__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.snapshot {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  background: var(--color-surface);
}

.snapshot__header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
}

.snapshot__time {
  font-size: var(--font-size-md);
}

.snapshot__reason,
.snapshot__pin,
.snapshot__notation,
.snapshot__id {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.snapshot__pin {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  padding: 0 var(--space-2);
}

.snapshot__id,
.snapshot__notation {
  margin: 0;
  overflow-wrap: anywhere;
}

.snapshot__files,
.snapshot__changes ul {
  margin: 0;
  padding-left: var(--space-4);
  font-size: var(--font-size-sm);
}

.snapshot__files {
  list-style: none;
  padding-left: 0;
}

.snapshot__path {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  overflow-wrap: anywhere;
}

.snapshot__changes h4 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-size-sm);
}

.snapshot__changes ul {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  overflow-wrap: anywhere;
}

.snapshot__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.snapshot__actions button {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  padding: var(--space-1) var(--space-3);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}

.snapshot__actions button:hover:not(:disabled) {
  color: var(--color-accent);
  border-color: var(--color-accent);
}

.dialog {
  position: fixed;
  z-index: 10;
  inset: 0;
  display: grid;
  place-items: center;
  padding: var(--space-4);
  background: rgb(16 24 40 / 55%);
}

.dialog__panel {
  width: min(36rem, 100%);
  max-height: 100%;
  overflow-y: auto;
  border-radius: var(--radius-md);
  padding: var(--space-4);
  background: var(--color-surface);
  box-shadow: 0 12px 32px rgb(16 24 40 / 24%);
}

.dialog__panel h3 {
  margin-top: 0;
  font-size: var(--font-size-lg);
  overflow-wrap: anywhere;
}

.dialog__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.dialog__confirm {
  color: var(--color-danger);
  font-weight: 600;
}

@media (max-width: 767px) {
  .dialog {
    padding: var(--space-2);
  }

  .dialog__panel {
    padding: var(--space-3);
  }

  .snapshot__actions button {
    width: 100%;
  }
}
</style>