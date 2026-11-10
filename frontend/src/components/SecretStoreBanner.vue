<script setup lang="ts">
import type { SecretStoreStatus } from '../api/profiles'

defineProps<{ status: SecretStoreStatus }>()
</script>

<template>
  <p v-if="status.backend === 'unavailable'" class="banner banner--error" role="alert">
    密钥存储不可用：{{ status.message ?? '当前无法保存密钥' }}
  </p>
  <p v-else-if="status.fallback" class="banner banner--warning" role="status">
    系统钥匙串不可用，密钥保存在本机文件。{{ status.message }}
  </p>
</template>

<style scoped>
.banner {
  margin: 0;
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
}

.banner--warning {
  background: var(--status-unconfigured-bg);
  color: var(--status-unconfigured-fg);
}

.banner--error {
  background: var(--status-error-bg);
  color: var(--status-error-fg);
}
</style>