<script setup lang="ts">
import type { ToolView } from '../api/tools'
import FriendListItem from './FriendListItem.vue'
import ToolStatusBadge from './ToolStatusBadge.vue'

defineProps<{
  tools: ToolView[]
  loading: boolean
  error: string | null
  selectedId: string | null
}>()

const emit = defineEmits<{
  select: [toolId: string]
  retry: []
}>()
</script>

<template>
  <div class="friend-list">
    <div v-if="error !== null" class="friend-list__error">
      <p class="friend-list__error-text" role="alert">{{ error }}</p>
      <button type="button" class="friend-list__retry" @click="emit('retry')">重试</button>
    </div>

    <ul class="friend-list__items" aria-label="AI 好友列表">
      <template v-if="loading && tools.length === 0">
        <li class="friend-list__loading" role="status">
          <ToolStatusBadge status="loading" />
          <span>正在检测…</span>
        </li>
        <li
          v-for="row in 3"
          :key="`skeleton-${row}`"
          class="friend-list__skeleton"
          aria-hidden="true"
        >
          <span class="skeleton-block friend-list__skeleton-avatar"></span>
          <span class="friend-list__skeleton-lines">
            <span class="skeleton-block friend-list__skeleton-line friend-list__skeleton-line--name"></span>
            <span class="skeleton-block friend-list__skeleton-line friend-list__skeleton-line--desc"></span>
          </span>
        </li>
      </template>
      <template v-else>
        <FriendListItem
          v-for="tool in tools"
          :key="tool.id"
          :tool="tool"
          :selected="selectedId === tool.id"
          @select="emit('select', $event)"
        />
      </template>
    </ul>
  </div>
</template>

<style scoped>
.friend-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
}

.friend-list__items {
  margin: 0;
  padding: 0;
  list-style: none;
}

.friend-list__loading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.friend-list__skeleton {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.friend-list__skeleton-avatar {
  width: var(--avatar-size);
  height: var(--avatar-size);
  flex-shrink: 0;
  border-radius: var(--avatar-radius);
}

.friend-list__skeleton-lines {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.friend-list__skeleton-line {
  height: var(--font-size-sm);
}

.friend-list__skeleton-line--name {
  width: 55%;
}

.friend-list__skeleton-line--desc {
  width: 80%;
}

.friend-list__error {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
}

.friend-list__error-text {
  margin: 0;
  color: var(--color-danger);
  font-size: var(--font-size-sm);
}

.friend-list__retry {
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-full);
  padding: var(--space-1) var(--space-3);
  background: var(--color-surface);
  color: var(--color-danger);
  font-size: var(--font-size-sm);
  cursor: pointer;
}

.friend-list__retry:focus-visible {
  outline: 2px solid var(--color-danger);
  outline-offset: 2px;
}

.skeleton-block {
  display: block;
  border-radius: var(--radius-sm);
  background: var(--color-surface-hover);
  animation: skeleton-pulse 1.2s ease-in-out infinite;
}

@keyframes skeleton-pulse {
  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.55;
  }
}

@media (prefers-reduced-motion: reduce) {
  .skeleton-block {
    animation: none;
  }
}
</style>