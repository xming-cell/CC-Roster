<script setup lang="ts">
import type { SwitchFilePreview } from '../api/switch'
import {
  changeCounts,
  fileActionLabel,
  fileBasename,
  formatChangeValue,
} from '../utils/switchDisplay'

defineProps<{
  files: SwitchFilePreview[]
}>()

function counts(file: SwitchFilePreview): string {
  const value = changeCounts(file.changes)
  const parts: string[] = []
  if (value.set > 0) {
    parts.push('+' + value.set)
  }
  if (value.remove > 0) {
    parts.push('−' + value.remove)
  }
  return parts.length === 0 ? '无变化' : parts.join(' ')
}
</script>

<template>
  <div class="diff">
    <p v-if="files.length === 0" class="diff__empty">没有需要写入的文件。</p>
    <article v-for="file in files" :key="file.path" class="diff__file">
      <header class="diff__header">
        <div class="diff__heading">
          <strong class="diff__name" :title="file.path">{{ fileBasename(file.path) }}</strong>
          <span class="diff__path">{{ file.path }}</span>
        </div>
        <span class="diff__badge" :class="'diff__badge--' + file.action">
          {{ fileActionLabel(file.action) }}
        </span>
        <span class="diff__count">{{ counts(file) }}</span>
      </header>

      <table v-if="file.changes.length > 0" class="diff__table">
        <thead>
          <tr>
            <th scope="col">字段</th>
            <th scope="col">当前</th>
            <th scope="col">切换后</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="change in file.changes" :key="change.field + change.action + (change.before ?? '')">
            <td class="diff__field">{{ change.field }}</td>
            <td class="diff__before">{{ formatChangeValue(change.before) }}</td>
            <td class="diff__after">
              <span class="diff__dot" aria-hidden="true"></span>
              {{ formatChangeValue(change.after) }}
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="diff__empty">这个文件的字段没有变化。</p>
    </article>
  </div>
</template>

<style scoped>
.diff {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.diff__empty {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.diff__file {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  overflow: hidden;
}

.diff__header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-md) var(--space-lg);
  border-bottom: 1px solid var(--color-border-card);
}

.diff__heading {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.diff__name {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.diff__path {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.diff__badge {
  flex: none;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.diff__badge--created {
  background: var(--color-success-bg);
  color: var(--color-success-fg);
}

.diff__badge--updated {
  background: var(--color-bg-selected);
  color: var(--color-primary-hover);
}

.diff__badge--unchanged {
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
}

.diff__count {
  flex: none;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
}

.diff__table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.diff__table th {
  padding: var(--space-sm) var(--space-md);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  font-weight: 400;
  text-align: left;
}

.diff__table th:first-child {
  width: 38%;
}

.diff__table td {
  padding: var(--space-sm) var(--space-md);
  border-top: 1px solid var(--color-bg-subtle);
  font-size: var(--font-size-xs);
  vertical-align: top;
  overflow-wrap: anywhere;
}

.diff__field {
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
}

.diff__before {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.diff__after {
  color: var(--color-text);
  font-family: var(--font-mono);
}

.diff__dot {
  display: inline-block;
  width: 5px;
  height: 5px;
  margin-right: var(--space-xs);
  border-radius: 50%;
  background: var(--color-success);
  vertical-align: middle;
}
</style>

