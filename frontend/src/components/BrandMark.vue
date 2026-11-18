<template>
  <svg class="brand-mark" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <rect class="brand-mark__bg" width="24" height="24" rx="7" />
    <path class="brand-mark__glyph" d="M7.5 9.2 10 12l-2.5 2.8M12.2 15h4.3" />
  </svg>
</template>

<style scoped>
.brand-mark {
  display: block;
  width: 24px;
  height: 24px;
  flex: none;
}

.brand-mark__bg {
  fill: var(--color-primary);
}

.brand-mark__glyph {
  fill: none;
  stroke: var(--color-surface);
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>
