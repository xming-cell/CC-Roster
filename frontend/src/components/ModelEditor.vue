<script setup lang="ts">
import { computed, ref } from 'vue'

import type { ModelEntry } from '../api/profiles'

interface ModelRow {
  key: number
  id: string
  display_name: string
}

const props = defineProps<{ models: ModelEntry[] }>()
const emit = defineEmits<{ 'update:models': [models: ModelEntry[]] }>()

let nextRowKey = 1

const rows = ref<ModelRow[]>(
  props.models.map((model) => ({
    key: nextRowKey++,
    id: model.id,
    display_name: model.display_name ?? '',
  })),
)

const duplicates = computed(() => {
  const seen = new Set<string>()
  const repeated = new Set<string>()
  for (const row of rows.value) {
    const id = row.id.trim()
    if (id === '') {
      continue
    }
    if (seen.has(id)) {
      repeated.add(id)
    }
    seen.add(id)
  }
  return [...repeated]
})

function sync(): void {
  emit(
    'update:models',
    rows.value.map((row) => ({
      id: row.id,
      display_name: row.display_name === '' ? null : row.display_name,
    })),
  )
}

function addRow(): void {
  rows.value.push({ key: nextRowKey++, id: '', display_name: '' })
  sync()
}

function removeRow(key: number): void {
  rows.value = rows.value.filter((row) => row.key !== key)
  sync()
}
</script>

<template>
  <fieldset class="models">
    <legend>模型清单</legend>
    <p v-if="rows.length === 0" class="models__empty">尚未添加模型（可先保存为空清单）</p>

    <div v-for="(row, index) in rows" :key="row.key" class="models__row">
      <label :for="`model-id-${row.key}`">模型标识</label>
      <input
        :id="`model-id-${row.key}`"
        v-model="row.id"
        type="text"
        maxlength="120"
        placeholder="例如 claude-sonnet-4"
        @input="sync"
      />
      <label :for="`model-name-${row.key}`">显示名（可选）</label>
      <input
        :id="`model-name-${row.key}`"
        v-model="row.display_name"
        type="text"
        placeholder="例如 Sonnet 4"
        @input="sync"
      />
      <button
        type="button"
        class="models__remove"
        :aria-label="`删除模型 ${row.id.trim() || index + 1}`"
        @click="removeRow(row.key)"
      >
        删除
      </button>
    </div>

    <p v-if="duplicates.length > 0" class="models__duplicate" role="alert">
      模型清单存在重复项：{{ duplicates.join('、') }}
    </p>

    <button type="button" class="models__add" @click="addRow">添加模型</button>
  </fieldset>
</template>

<style scoped>
.models {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
  margin: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}

.models legend {
  padding: 0 var(--space-1);
  font-weight: 600;
}

.models__empty {
  margin: 0;
  color: var(--color-text-secondary);
}

.models__row {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  align-items: center;
  gap: var(--space-1) var(--space-3);
  border-bottom: 1px solid var(--color-border);
  padding-bottom: var(--space-2);
}

.models__row input {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-2);
  font: inherit;
}

.models__remove {
  grid-column: 2;
  justify-self: start;
}

.models__duplicate {
  margin: 0;
  color: var(--color-danger);
}

.models__add {
  align-self: flex-start;
}
</style>