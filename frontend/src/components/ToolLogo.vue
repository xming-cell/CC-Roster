<script setup lang="ts">
import { computed } from 'vue'

import { TOOL_LOGOS } from '../utils/toolLogos'

const props = defineProps<{
  toolId: string
  size?: 'sm' | 'md' | 'lg'
}>()

const logo = computed(() => TOOL_LOGOS[props.toolId] ?? null)
const sizeClass = computed(() => 'tool-logo--' + (props.size ?? 'md'))
</script>

<template>
  <svg
    v-if="logo"
    class="tool-logo"
    :class="sizeClass"
    :viewBox="logo.viewBox"
    aria-hidden="true"
    focusable="false"
  >
    <path
      v-for="(shape, index) in logo.shapes"
      :key="index"
      :d="shape.d"
      :fill="shape.fill ?? 'none'"
      :stroke="shape.stroke"
      :stroke-width="shape.strokeWidth"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
  <span v-else class="tool-logo tool-logo--fallback" :class="sizeClass" aria-hidden="true">
    <svg viewBox="0 0 16 16">
      <path d="M4.2 5.3 6.7 8l-2.5 2.7M8.2 10.8h3.6" />
    </svg>
  </span>
</template>

<style scoped>
.tool-logo {
  display: block;
  flex: none;
}

.tool-logo--sm {
  width: 16px;
  height: 16px;
}

.tool-logo--md {
  width: 18px;
  height: 18px;
}

.tool-logo--lg {
  width: 20px;
  height: 20px;
}

.tool-logo--fallback {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
}

.tool-logo--fallback svg {
  width: 66%;
  height: 66%;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>

