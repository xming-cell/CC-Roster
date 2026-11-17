import { ref } from 'vue'
import { defineStore } from 'pinia'

import { listToolSessions, readToolSession } from '../api/sessions'
import type { SessionMessage, SessionWarning, ToolSessionSummary } from '../api/sessions'
import { errorText } from '../utils/profileDisplay'

export const useHistoryStore = defineStore('history', () => {
  const toolId = ref<string | null>(null)
  const sessions = ref<ToolSessionSummary[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)
  const warnings = ref<SessionWarning[]>([])
  const hasMore = ref(false)
  const nextCursor = ref<number | null>(null)
  let listSeq = 0

  const currentId = ref<string | null>(null)
  const messages = ref<SessionMessage[]>([])
  const detailLoading = ref(false)
  const detailError = ref<string | null>(null)
  const detailWarnings = ref<SessionWarning[]>([])
  const messagesHasMore = ref(false)
  const messagesNextCursor = ref<number | null>(null)
  const totalMessages = ref<number | null>(null)
  let detailSeq = 0

  async function fetchSessions(nextToolId: string): Promise<void> {
    const seq = ++listSeq
    toolId.value = nextToolId
    loading.value = true
    error.value = null
    try {
      const response = await listToolSessions(nextToolId)
      if (seq !== listSeq) {
        return
      }
      sessions.value = response.sessions
      warnings.value = response.warnings
      hasMore.value = response.has_more
      nextCursor.value = response.next_cursor
      loaded.value = true
    } catch (caught) {
      if (seq !== listSeq) {
        return
      }
      error.value = errorText(caught, '历史会话读取失败')
    } finally {
      if (seq === listSeq) {
        loading.value = false
      }
    }
  }

  async function openSession(sessionId: string): Promise<void> {
    const currentTool = toolId.value
    if (currentTool === null) {
      return
    }
    const seq = ++detailSeq
    currentId.value = sessionId
    messages.value = []
    detailLoading.value = true
    detailError.value = null
    detailWarnings.value = []
    messagesHasMore.value = false
    messagesNextCursor.value = null
    totalMessages.value = null
    try {
      const response = await readToolSession(currentTool, sessionId)
      if (seq !== detailSeq) {
        return
      }
      messages.value = response.messages
      detailWarnings.value = response.warnings
      messagesHasMore.value = response.has_more
      messagesNextCursor.value = response.next_cursor
      totalMessages.value = response.total_messages
    } catch (caught) {
      if (seq !== detailSeq) {
        return
      }
      detailError.value = errorText(caught, '会话读取失败')
    } finally {
      if (seq === detailSeq) {
        detailLoading.value = false
      }
    }
  }

  async function loadEarlier(): Promise<void> {
    const currentTool = toolId.value
    const sessionId = currentId.value
    const cursor = messagesNextCursor.value
    if (currentTool === null || sessionId === null || cursor === null || detailLoading.value) {
      return
    }
    const seq = detailSeq
    detailLoading.value = true
    try {
      const response = await readToolSession(currentTool, sessionId, { cursor })
      if (seq !== detailSeq) {
        return
      }
      messages.value = [...response.messages, ...messages.value]
      messagesHasMore.value = response.has_more
      messagesNextCursor.value = response.next_cursor
    } catch (caught) {
      if (seq !== detailSeq) {
        return
      }
      detailError.value = errorText(caught, '加载更早的消息失败')
    } finally {
      if (seq === detailSeq) {
        detailLoading.value = false
      }
    }
  }

  function reset(): void {
    listSeq += 1
    detailSeq += 1
    toolId.value = null
    sessions.value = []
    loading.value = false
    loaded.value = false
    error.value = null
    warnings.value = []
    hasMore.value = false
    nextCursor.value = null
    currentId.value = null
    messages.value = []
    detailLoading.value = false
    detailError.value = null
    detailWarnings.value = []
    messagesHasMore.value = false
    messagesNextCursor.value = null
    totalMessages.value = null
  }

  return {
    toolId,
    sessions,
    loading,
    loaded,
    error,
    warnings,
    hasMore,
    nextCursor,
    currentId,
    messages,
    detailLoading,
    detailError,
    detailWarnings,
    messagesHasMore,
    messagesNextCursor,
    totalMessages,
    fetchSessions,
    openSession,
    loadEarlier,
    reset,
  }
})
