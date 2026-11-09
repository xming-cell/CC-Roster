<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <span class="app-header__brand">CC-Roster</span>
      <nav class="app-header__nav">
        <RouterLink to="/">首页</RouterLink>
        <RouterLink to="/tools">工具</RouterLink>
      </nav>
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
  display: flex;
  align-items: center;
  gap: 1.5rem;
  border-bottom: 1px solid #e4e7ec;
  padding: 0.75rem 1.5rem;
}

.app-header__brand {
  font-weight: 600;
}

.app-header__nav {
  display: flex;
  gap: 1rem;
}

.app-header__nav a {
  color: inherit;
  text-decoration: none;
}

.app-header__nav a.router-link-active {
  color: #175cd3;
  font-weight: 600;
}

.app-main {
  flex: 1;
  padding: 1.5rem;
}
</style>