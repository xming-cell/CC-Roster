<script setup lang="ts">
import { computed } from 'vue'

import type { ToolStatus } from '../api/tools'

type BadgeStatus = ToolStatus | 'loading'

const props = defineProps<{ status: BadgeStatus }>()

const labels: Record<BadgeStatus, string> = {
  loading: '检测中',
  ok: '正常',
  unconfigured: '未配置',
  error: '异常',
}

const label = computed(() => labels[props.status] ?? '异常')
</script>

<template>
  <span class="status-badge" :class="`status-badge--${status}`">{{ label }}</span>
</template>

<style scoped>
.status-badge {
  display: inline-block;
  border-radius: var(--radius-full);
  padding: 0.125rem var(--space-2);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
  white-space: nowrap;
}

.status-badge--loading {
  background: var(--status-loading-bg);
  color: var(--status-loading-fg);
}

.status-badge--ok {
  background: var(--status-ok-bg);
  color: var(--status-ok-fg);
}

.status-badge--unconfigured {
  background: var(--status-unconfigured-bg);
  color: var(--status-unconfigured-fg);
}

.status-badge--error {
  background: var(--status-error-bg);
  color: var(--status-error-fg);
}
</style>