<template>
  <div class="detail-skeleton" aria-hidden="true">
    <div class="detail-skeleton__header">
      <span class="skeleton-block detail-skeleton__title"></span>
      <span class="skeleton-block detail-skeleton__badge"></span>
    </div>
    <div class="detail-skeleton__body">
      <span v-for="row in 6" :key="row" class="skeleton-block detail-skeleton__row"></span>
    </div>
  </div>
</template>

<style scoped>
.detail-skeleton {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.detail-skeleton__header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.detail-skeleton__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
}

.skeleton-block {
  display: block;
  border-radius: var(--radius-sm);
  background: var(--color-surface-hover);
  animation: skeleton-pulse 1.2s ease-in-out infinite;
}

.detail-skeleton__title {
  width: 8rem;
  height: var(--font-size-xl);
}

.detail-skeleton__badge {
  width: 3.5rem;
  height: var(--font-size-lg);
  border-radius: var(--radius-full);
}

.detail-skeleton__row {
  width: 100%;
  height: var(--font-size-md);
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