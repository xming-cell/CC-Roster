<script setup lang="ts">
import InstallGuide from './InstallGuide.vue'
</script>

<template>
  <section class="empty-tools" aria-labelledby="empty-tools-title">
    <div class="empty-tools__content">
      <h2 id="empty-tools-title" class="empty-tools__title">还没有发现任何 AI 工具</h2>
      <p class="empty-tools__hint">
        安装 Claude Code 或 Codex CLI 后，点击左上角「刷新」重新检测。
      </p>
      <InstallGuide />
    </div>
  </section>
</template>

<style scoped>
.empty-tools {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-5);
}

.empty-tools__content {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-width: 36rem;
  margin: 0 auto;
}

.empty-tools__title {
  margin: 0;
  font-size: var(--font-size-xl);
}

.empty-tools__hint {
  margin: 0;
  color: var(--color-text-secondary);
}
</style>