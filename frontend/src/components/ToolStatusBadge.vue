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

const label = computed(() => labels[props.status])
</script>

<template>
  <span class="status-badge" :class="`status-badge--${status}`">{{ label }}</span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
}

.status-badge--loading {
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
}

.status-badge--ok {
  background: var(--color-success-bg);
  color: var(--color-success-fg);
}

.status-badge--unconfigured {
  background: var(--color-warning-bg);
  color: var(--color-warning-fg);
}

.status-badge--error {
  background: var(--color-danger-bg);
  color: var(--color-danger-fg);
}
</style>
