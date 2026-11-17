<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'

import ToolDetailPanel from '../components/ToolDetailPanel.vue'
import ToolListPanel from '../components/ToolListPanel.vue'
import { useToolsStore } from '../stores/tools'

const store = useToolsStore()
const {
  tools,
  warnings,
  loading,
  loaded,
  error,
  selectedToolId,
  selectedTool,
  detailLoading,
  detailError,
} = storeToRefs(store)

onMounted(() => {
  void store.fetchTools()
})

function handleRefresh(): void {
  void store.fetchTools()
}

function handleSelect(toolId: string): void {
  void store.selectTool(toolId)
}

function handleRetryDetail(): void {
  if (store.selectedToolId !== null) {
    void store.selectTool(store.selectedToolId)
  }
}
</script>

<template>
  <div class="workbench">
    <h1 class="sr-only">工作台</h1>

    <ToolListPanel
      :tools="tools"
      :warnings="warnings"
      :loading="loading"
      :loaded="loaded"
      :error="error"
      :selected-tool-id="selectedToolId"
      @refresh="handleRefresh"
      @select="handleSelect"
    />

    <ToolDetailPanel
      :tool="selectedTool"
      :loading="detailLoading"
      :error="detailError"
      :selected-tool-id="selectedToolId"
      @retry="handleRetryDetail"
    />
  </div>
</template>

<style scoped>
.workbench {
  display: grid;
  grid-template-columns: var(--layout-list-width) minmax(0, 1fr);
  height: 100%;
  min-width: 0;
  min-height: 0;
}

@media (max-width: 980px) {
  .workbench {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(0, 40vh) minmax(0, 1fr);
  }
}
</style>
