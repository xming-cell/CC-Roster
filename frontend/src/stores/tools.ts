import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiError } from '../api/client'
import { getTool, getTools } from '../api/tools'
import type { ToolView, ToolWarning } from '../api/tools'
import { sortToolsByLastModified } from '../utils/tools'

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : '工具信息读取失败'
}

export const useToolsStore = defineStore('tools', () => {
  const tools = ref<ToolView[]>([])
  const warnings = ref<ToolWarning[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const refreshError = ref<string | null>(null)

  const sortedTools = computed(() => sortToolsByLastModified(tools.value))

  const selectedToolId = ref<string | null>(null)
  const selectedTool = ref<ToolView | null>(null)
  const detailLoading = ref(false)
  const detailError = ref<string | null>(null)

  let listRequestId = 0
  let detailRequestId = 0

  async function fetchTools(): Promise<void> {
    const requestId = ++listRequestId
    loading.value = true
    error.value = null
    refreshError.value = null
    try {
      const response = await getTools()
      if (requestId !== listRequestId) {
        return
      }
      tools.value = response.tools
      warnings.value = response.warnings
      if (
        selectedToolId.value !== null &&
        !response.tools.some((tool) => tool.id === selectedToolId.value)
      ) {
        clearSelection()
      }
    } catch (caught) {
      if (requestId !== listRequestId) {
        return
      }
      if (tools.value.length > 0) {
        refreshError.value = errorMessage(caught)
      } else {
        tools.value = []
        warnings.value = []
        error.value = errorMessage(caught)
      }
    } finally {
      if (requestId === listRequestId) {
        loading.value = false
      }
    }
  }

  async function selectTool(toolId: string): Promise<void> {
    const requestId = ++detailRequestId
    selectedToolId.value = toolId
    selectedTool.value = null
    detailError.value = null
    detailLoading.value = true
    try {
      const tool = await getTool(toolId)
      if (requestId === detailRequestId) {
        selectedTool.value = tool
      }
    } catch (caught) {
      if (requestId === detailRequestId) {
        detailError.value = errorMessage(caught)
      }
    } finally {
      if (requestId === detailRequestId) {
        detailLoading.value = false
      }
    }
  }

  function clearSelection(): void {
    detailRequestId += 1
    selectedToolId.value = null
    selectedTool.value = null
    detailError.value = null
    detailLoading.value = false
  }

  return {
    tools,
    sortedTools,
    warnings,
    loading,
    error,
    refreshError,
    selectedToolId,
    selectedTool,
    detailLoading,
    detailError,
    fetchTools,
    selectTool,
    clearSelection,
  }
})