<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'

import BrandMark from './components/BrandMark.vue'
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <div class="brand">
        <BrandMark />
        <span class="brand__name">CC-Roster</span>
      </div>

      <nav class="app-nav" aria-label="主导航">
        <RouterLink class="app-nav__link" to="/" aria-label="工作台">
          <svg class="app-nav__icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
            <rect x="2" y="2" width="5" height="5" rx="1.4" />
            <rect x="9" y="2" width="5" height="5" rx="1.4" />
            <rect x="2" y="9" width="5" height="5" rx="1.4" />
            <rect x="9" y="9" width="5" height="5" rx="1.4" />
          </svg>
          <span class="app-nav__label">工作台</span>
        </RouterLink>
        <RouterLink class="app-nav__link" to="/providers" aria-label="供应商">
          <svg class="app-nav__icon app-nav__icon--outline" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
            <rect x="2.5" y="3" width="11" height="10" rx="2" />
            <path d="M5 6h6M5 9h3" />
          </svg>
          <span class="app-nav__label">供应商</span>
        </RouterLink>
      </nav>
    </aside>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: var(--layout-nav-width) minmax(0, 1fr);
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  background: var(--color-bg);
}

.app-sidebar {
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
  min-height: 0;
  padding: var(--space-lg) 14px;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 0 10px;
}

.brand__name {
  overflow: hidden;
  color: var(--color-text);
  font-size: var(--font-size-lg);
  font-weight: 700;
  letter-spacing: -0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.app-nav__link {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 38px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
  text-decoration: none;
  transition:
    background 120ms ease-out,
    color 120ms ease-out;
}

.app-nav__link:hover {
  background: var(--color-bg-subtle);
  color: var(--color-text);
}

.app-nav__link[aria-current='page'] {
  background: var(--color-bg-selected);
  color: var(--color-primary-hover);
  font-weight: 600;
}

.app-nav__icon {
  width: 16px;
  height: 16px;
  flex: none;
  fill: currentColor;
}

.app-nav__icon--outline {
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.5;
}

.app-main {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 1180px) {
  .app-shell {
    grid-template-columns: 200px minmax(0, 1fr);
  }
}

@media (max-width: 980px) {
  .app-shell {
    grid-template-columns: 184px minmax(0, 1fr);
  }

  .app-sidebar {
    padding: var(--space-md) 10px;
  }
}

@media (max-width: 720px) {
  .app-shell {
    grid-template-columns: 64px minmax(0, 1fr);
  }

  .app-sidebar {
    align-items: center;
    padding: var(--space-md) var(--space-xs);
  }

  .brand {
    justify-content: center;
    padding: 0;
  }

  .brand__name,
  .app-nav__label {
    display: none;
  }

  .app-nav__link {
    width: 40px;
    justify-content: center;
    padding: 0;
  }
}
</style>
