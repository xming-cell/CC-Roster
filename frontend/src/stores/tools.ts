import { ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiError } from '../api/client'
import { getTool, getTools } from '../api/tools'
import type { ToolView, ToolWarning } from '../api/tools'

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : '工具信息读取失败'
}

export const useToolsStore = defineStore('tools', () => {
  const tools = ref<ToolView[]>([])
  const warnings = ref<ToolWarning[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedToolId = ref<string | null>(null)
  const selectedTool = ref<ToolView | null>(null)
  const detailLoading = ref(false)
  const detailError = ref<string | null>(null)

  async function fetchTools(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await getTools()
      tools.value = response.tools
      warnings.value = response.warnings
    } catch (caught) {
      tools.value = []
      warnings.value = []
      error.value = errorMessage(caught)
    } finally {
      loading.value = false
    }
  }

  async function selectTool(toolId: string): Promise<void> {
    selectedToolId.value = toolId
    selectedTool.value = null
    detailError.value = null
    detailLoading.value = true
    try {
      selectedTool.value = await getTool(toolId)
    } catch (caught) {
      detailError.value = errorMessage(caught)
    } finally {
      detailLoading.value = false
    }
  }

  function clearSelection(): void {
    selectedToolId.value = null
    selectedTool.value = null
    detailError.value = null
    detailLoading.value = false
  }

  return {
    tools,
    warnings,
    loading,
    error,
    selectedToolId,
    selectedTool,
    detailLoading,
    detailError,
    fetchTools,
    selectTool,
    clearSelection,
  }
})