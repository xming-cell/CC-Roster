<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <span class="app-header__brand">CC-Roster</span>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  border-bottom: 1px solid #e4e7ec;
  padding: 0.75rem 1.5rem;
}

.app-header__brand {
  font-weight: 600;
}

.app-main {
  flex: 1;
  padding: 1.5rem;
}
</style>