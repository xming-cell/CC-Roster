<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'

import ToolDetailPanel from '../components/ToolDetailPanel.vue'
import ToolStatusBadge from '../components/ToolStatusBadge.vue'
import { useToolsStore } from '../stores/tools'

const store = useToolsStore()
const { tools, warnings, loading, error, selectedToolId, selectedTool, detailLoading, detailError } =
  storeToRefs(store)

onMounted(() => {
  void store.fetchTools()
})
</script>

<template>
  <section class="tools">
    <header class="tools__header">
      <h1>工具</h1>
      <button type="button" :disabled="loading" @click="store.fetchTools()">刷新</button>
    </header>

    <p v-if="loading" class="tools__loading" role="status">
      <ToolStatusBadge status="loading" />
      <span>正在检测已安装的工具…</span>
    </p>
    <p v-else-if="error !== null" class="tools__error" role="alert">{{ error }}</p>
    <template v-else>
      <p v-if="tools.length === 0" class="tools__empty">
        未发现已安装的 AI 工具。安装 Claude Code 或 Codex CLI 后点击刷新即可。
      </p>
      <ul v-else class="tools__list" aria-label="工具列表">
        <li v-for="tool in tools" :key="tool.id">
          <button
            type="button"
            class="tools__select"
            :aria-pressed="selectedToolId === tool.id"
            @click="store.selectTool(tool.id)"
          >
            <ToolStatusBadge :status="tool.status" />
            <span class="tools__name">{{ tool.display_name }}</span>
            <span class="tools__meta">{{ tool.provider ?? '供应商未知' }}</span>
            <span class="tools__meta">{{ tool.model ?? '模型未知' }}</span>
          </button>
        </li>
      </ul>

      <section v-if="warnings.length > 0" class="tools__warnings" role="alert">
        <h2>部分工具检测失败</h2>
        <ul>
          <li v-for="warning in warnings" :key="`${warning.code}-${warning.message}`">
            {{ warning.code }}: {{ warning.message }}
          </li>
        </ul>
      </section>

      <ToolDetailPanel
        v-if="selectedToolId !== null"
        :tool="selectedTool"
        :loading="detailLoading"
        :error="detailError"
      />
    </template>
  </section>
</template>

<style scoped>
.tools {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 46rem;
}

.tools__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tools__header h1 {
  margin: 0;
  font-size: 1.25rem;
}

.tools__list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.tools__select {
  display: grid;
  grid-template-columns: max-content 1fr auto auto;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  border: 1px solid #e4e7ec;
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.tools__select[aria-pressed='true'] {
  border-color: #175cd3;
}

.tools__name {
  font-weight: 600;
}

.tools__meta {
  color: #475467;
  font-size: 0.875rem;
}

.tools__error {
  color: #b42318;
}

.tools__warnings {
  border: 1px solid #fecdca;
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  color: #b42318;
}

.tools__warnings h2 {
  margin-top: 0;
  font-size: 1rem;
}
</style>