<script setup lang="ts">
import { computed } from 'vue'

import type { ToolView } from '../api/tools'
import { normalizeStatus, statusDescription } from '../utils/tools'
import { appearanceStyle, resolveAppearance } from '../utils/appearances'
import { useAppearancesStore } from '../stores/appearances'
import FriendAvatar from './FriendAvatar.vue'
import ToolStatusBadge from './ToolStatusBadge.vue'

const props = defineProps<{
  tool: ToolView
  selected: boolean
}>()

const emit = defineEmits<{
  select: [toolId: string]
}>()

const description = computed(() => statusDescription(props.tool))
const status = computed(() => normalizeStatus(props.tool.status))
const appearancesStore = useAppearancesStore()
const friendStyle = computed(() =>
  appearanceStyle(resolveAppearance(props.tool, appearancesStore.appearances[props.tool.id])),
)
</script>

<template>
  <li class="friend-item">
    <button
      type="button"
      class="friend-item__button"
      :style="friendStyle"
      :aria-label="`选择 ${tool.display_name}`"
      :aria-pressed="selected"
      @click="emit('select', tool.id)"
    >
      <FriendAvatar :name="tool.display_name" :tool-id="tool.id" />
      <span class="friend-item__content">
        <span class="friend-item__name">{{ tool.display_name }}</span>
        <span class="friend-item__description" :title="description">{{ description }}</span>
      </span>
      <ToolStatusBadge :status="status" />
    </button>
  </li>
</template>

<style scoped>
.friend-item {
  --friend-accent: var(--friend-accent-light);
  --friend-accent-soft: var(--friend-accent-soft-light);
  --friend-secondary: var(--friend-secondary-light);
  border-bottom: 1px solid var(--color-border);
  border-left: 3px solid var(--friend-secondary);
}

.friend-item__button {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-3) var(--space-4);
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.friend-item__button:hover {
  background: var(--color-surface-hover);
}

.friend-item__button:focus-visible {
  outline: 2px solid var(--friend-accent);
  outline-offset: -2px;
}

.friend-item__button[aria-pressed='true'] .friend-item__name {
  color: var(--friend-accent);
}

.friend-item__button[aria-pressed='true'] {
  background: var(--friend-accent-soft);
  box-shadow: inset 3px 0 0 var(--friend-accent);
}

.friend-item__content {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.friend-item__name {
  overflow: hidden;
  font-size: var(--font-size-md);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.friend-item__description {
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (prefers-color-scheme: dark) {
  .friend-item {
    --friend-accent: var(--friend-accent-dark);
    --friend-accent-soft: var(--friend-accent-soft-dark);
    --friend-secondary: var(--friend-secondary-dark);
  }
}
</style>