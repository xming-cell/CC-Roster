<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import type { ModelEntry } from '../api/profiles'

const props = defineProps<{
  model: string | null
  models: ModelEntry[]
  effort: string | null
  effortLevels: string[]
  disabled: boolean
}>()

const emit = defineEmits<{
  'update:model': [value: string | null]
  'update:effort': [value: string | null]
}>()

const root = ref<HTMLElement | null>(null)
const openMenu = ref<'model' | 'effort' | null>(null)

const modelLabel = computed(() => props.model ?? props.models[0]?.id ?? '未设置')
const effortLabel = computed(() => props.effort ?? '默认')
const modelDisabled = computed(() => props.disabled || props.models.length === 0)

function toggle(menu: 'model' | 'effort'): void {
  if (menu === 'model' && modelDisabled.value) {
    return
  }
  if (menu === 'effort' && (props.disabled || props.effortLevels.length === 0)) {
    return
  }
  openMenu.value = openMenu.value === menu ? null : menu
}

function chooseModel(value: string | null): void {
  openMenu.value = null
  if (value !== props.model) {
    emit('update:model', value)
  }
}

function chooseEffort(value: string | null): void {
  openMenu.value = null
  if (value !== props.effort) {
    emit('update:effort', value)
  }
}

function handleDocumentClick(event: MouseEvent): void {
  if (root.value !== null && !root.value.contains(event.target as Node)) {
    openMenu.value = null
  }
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    openMenu.value = null
  }
}

onMounted(() => {
  document.addEventListener('mousedown', handleDocumentClick)
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleDocumentClick)
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div ref="root" class="context">
    <div class="context__item">
      <button
        class="context__chip"
        type="button"
        aria-haspopup="listbox"
        :aria-expanded="openMenu === 'model'"
        :disabled="modelDisabled"
        @click="toggle('model')"
      >
        <span class="context__label">模型</span>
        <span class="context__value">{{ modelLabel }}</span>
        <span class="context__caret" aria-hidden="true">⌄</span>
      </button>
      <ul v-if="openMenu === 'model'" class="context__menu" role="listbox" aria-label="选择模型">
        <li>
          <button
            class="context__option"
            type="button"
            :class="{ 'context__option--active': model === null }"
            @click="chooseModel(null)"
          >
            默认（清单第一项）
            <span v-if="model === null" aria-hidden="true">✓</span>
          </button>
        </li>
        <li v-for="entry in models" :key="entry.id">
          <button
            class="context__option"
            type="button"
            :class="{ 'context__option--active': model === entry.id }"
            @click="chooseModel(entry.id)"
          >
            {{ entry.id }}
            <span v-if="model === entry.id" aria-hidden="true">✓</span>
          </button>
        </li>
      </ul>
    </div>

    <div v-if="effortLevels.length > 0" class="context__item">
      <button
        class="context__chip"
        type="button"
        aria-haspopup="listbox"
        :aria-expanded="openMenu === 'effort'"
        :disabled="disabled"
        @click="toggle('effort')"
      >
        <span class="context__label">思考强度</span>
        <span class="context__value">{{ effortLabel }}</span>
        <span class="context__caret" aria-hidden="true">⌄</span>
      </button>
      <ul v-if="openMenu === 'effort'" class="context__menu" role="listbox" aria-label="选择思考强度">
        <li>
          <button
            class="context__option"
            type="button"
            :class="{ 'context__option--active': effort === null }"
            @click="chooseEffort(null)"
          >
            默认
            <span v-if="effort === null" aria-hidden="true">✓</span>
          </button>
        </li>
        <li v-for="level in effortLevels" :key="level">
          <button
            class="context__option"
            type="button"
            :class="{ 'context__option--active': effort === level }"
            @click="chooseEffort(level)"
          >
            {{ level }}
            <span v-if="effort === level" aria-hidden="true">✓</span>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.context {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.context__item {
  position: relative;
}

.context__chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  min-height: 32px;
  padding: 4px 10px;
  border: 1px solid var(--color-border-control);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text);
  cursor: pointer;
}

.context__chip:hover:not(:disabled) {
  border-color: var(--color-border-selected);
  background: var(--color-bg-subtle);
}

.context__chip:disabled {
  color: var(--color-text-muted);
  cursor: not-allowed;
}

.context__label {
  color: var(--color-text-muted);
  font-size: 10px;
}

.context__value {
  max-width: 220px;
  font-size: var(--font-size-xs);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context__caret {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.context__menu {
  position: absolute;
  z-index: 20;
  top: calc(100% + 4px);
  left: 0;
  width: max-content;
  min-width: 220px;
  max-width: 320px;
  max-height: 240px;
  margin: 0;
  padding: var(--space-xs);
  overflow-y: auto;
  list-style: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.context__option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  width: 100%;
  padding: 7px 10px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text);
  font-size: var(--font-size-xs);
  text-align: left;
  cursor: pointer;
}

.context__option:hover {
  background: var(--color-bg-subtle);
}

.context__option--active {
  background: var(--color-bg-selected);
  color: var(--color-primary-hover);
  font-weight: 600;
}
</style>
