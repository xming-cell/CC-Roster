<script setup lang="ts">
import { computed } from 'vue'

import { avatarInitial, avatarTone } from '../utils/tools'

const props = defineProps<{
  name: string
  toolId: string
}>()

const initial = computed(() => avatarInitial(props.name))
const tone = computed(() => avatarTone(props.toolId))
</script>

<template>
  <span class="friend-avatar" :class="`friend-avatar--tone-${tone}`" aria-hidden="true">
    {{ initial }}
  </span>
</template>

<style scoped>
.friend-avatar {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: var(--avatar-size);
  height: var(--avatar-size);
  border-radius: var(--avatar-radius);
  background: var(--friend-avatar-bg, var(--avatar-tone-1));
  color: var(--friend-avatar-fg);
  font-size: var(--font-size-lg);
  font-weight: 600;
  user-select: none;
}

.friend-avatar--tone-0 {
  --friend-avatar-bg: var(--avatar-tone-0);
}

.friend-avatar--tone-1 {
  --friend-avatar-bg: var(--avatar-tone-1);
}

.friend-avatar--tone-2 {
  --friend-avatar-bg: var(--avatar-tone-2);
}

.friend-avatar--tone-3 {
  --friend-avatar-bg: var(--avatar-tone-3);
}

.friend-avatar--tone-4 {
  --friend-avatar-bg: var(--avatar-tone-4);
}

.friend-avatar--tone-5 {
  --friend-avatar-bg: var(--avatar-tone-5);
}
</style>