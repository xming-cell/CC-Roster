<script setup lang="ts">
import type { SwitchChange, SwitchFilePreview } from '../api/switch'

defineProps<{ file: SwitchFilePreview }>()

function actionLabel(action: SwitchFilePreview['action']): string {
  if (action === 'created') {
    return '新建文件'
  }
  if (action === 'updated') {
    return '更新文件'
  }
  return '无变化'
}

function changeActionLabel(action: SwitchChange['action']): string {
  return action === 'set' ? '设置' : '删除'
}

function beforeLabel(change: SwitchChange): string {
  return change.before ?? '（不存在）'
}

function afterLabel(change: SwitchChange): string {
  return change.action === 'remove' ? '（删除）' : (change.after ?? '（不存在）')
}
</script>

<template>
  <section class="file" :aria-label="`文件 ${file.path}`">
    <header class="file__header">
      <h4 class="file__path">{{ file.path }}</h4>
      <span class="file__action">{{ actionLabel(file.action) }}</span>
    </header>

    <table v-if="file.changes.length > 0" class="file__table">
      <caption class="file__caption">
        字段级改动
      </caption>
      <thead>
        <tr>
          <th scope="col">字段</th>
          <th scope="col">操作</th>
          <th scope="col">修改前</th>
          <th scope="col">修改后</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="change in file.changes"
          :key="`${file.path}|${change.path}|${change.field}|${change.action}`"
        >
          <td class="file__field" data-label="字段">{{ change.field }}</td>
          <td data-label="操作">{{ changeActionLabel(change.action) }}</td>
          <td class="file__value" data-label="修改前">{{ beforeLabel(change) }}</td>
          <td class="file__value" data-label="修改后">{{ afterLabel(change) }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="file__empty">此文件没有字段变更</p>
  </section>
</template>

<style scoped>
.file {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  background: var(--color-surface);
}

.file__header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.file__path {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.file__action {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.file__table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}

.file__caption {
  padding-bottom: var(--space-1);
  color: var(--color-text-secondary);
  text-align: left;
}

.file__table th,
.file__table td {
  border-top: 1px solid var(--color-border);
  padding: var(--space-2);
  text-align: left;
  vertical-align: top;
}

.file__table th {
  color: var(--color-text-secondary);
  font-weight: 600;
}

.file__field,
.file__value {
  overflow-wrap: anywhere;
}

.file__value {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.file__empty {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

@media (max-width: 767px) {
  .file__table,
  .file__table thead,
  .file__table tbody,
  .file__table tr,
  .file__table th,
  .file__table td {
    display: block;
  }

  .file__table thead {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }

  .file__table tr {
    border-top: 1px solid var(--color-border);
    padding: var(--space-2) 0;
  }

  .file__table td {
    display: grid;
    grid-template-columns: 4.5rem minmax(0, 1fr);
    gap: var(--space-2);
    border-top: 0;
  }

  .file__table td::before {
    content: attr(data-label);
  }
}
</style>
