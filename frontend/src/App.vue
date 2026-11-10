<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()
const fullBleed = computed(() => route.name === 'home')
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <span class="app-header__brand">CC-Roster</span>
      <nav class="app-header__nav">
        <RouterLink to="/">首页</RouterLink>
        <RouterLink to="/tools">工具</RouterLink>
        <RouterLink to="/profiles">档案</RouterLink>
      </nav>
    </header>
    <main class="app-main" :class="{ 'app-main--full': fullBleed }">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
}

.app-header {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: var(--space-5);
  border-bottom: 1px solid var(--color-border);
  padding: var(--space-3) var(--space-5);
  background: var(--color-surface);
}

.app-header__brand {
  font-weight: 600;
}

.app-header__nav {
  display: flex;
  gap: var(--space-4);
}

.app-header__nav a {
  color: inherit;
  text-decoration: none;
}

.app-header__nav a.router-link-active {
  color: var(--color-accent);
  font-weight: 600;
}

.app-main {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-5);
}

.app-main--full {
  display: flex;
  overflow: hidden;
  padding: 0;
}
</style>