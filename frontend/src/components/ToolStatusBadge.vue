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
  display: inline-block;
  border-radius: 999px;
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
  line-height: 1.5;
  white-space: nowrap;
}

.status-badge--loading {
  background: #eef2f6;
  color: #475467;
}

.status-badge--ok {
  background: #e7f6ec;
  color: #05603a;
}

.status-badge--unconfigured {
  background: #fef0c7;
  color: #93370d;
}

.status-badge--error {
  background: #fee4e2;
  color: #b42318;
}
</style>