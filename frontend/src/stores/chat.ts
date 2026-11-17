import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  cancelChatSession,
  createChatSession,
  getChatSession,
  listChatSessions,
  streamChatMessage,
  updateChatSession,
} from '../api/chat'
import type { ChatCreateInput, ChatMessage, ChatSessionView, ChatUpdateInput } from '../api/chat'
import { errorText } from '../utils/profileDisplay'

export interface StreamingTool {
  key: string
  toolName: string
  content: string
}

export interface StreamingState {
  content: string
  status: string | null
  tools: StreamingTool[]
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSessionView[]>([])
  const sessionsLoading = ref(false)
  const sessionsLoaded = ref(false)
  const sessionsError = ref<string | null>(null)

  const current = ref<ChatSessionView | null>(null)
  const currentLoading = ref(false)
  const currentError = ref<string | null>(null)

  const sending = ref(false)
  const streaming = ref<StreamingState | null>(null)
  const streamError = ref<string | null>(null)
  const cancelBusy = ref(false)

  async function fetchSessions(): Promise<void> {
    sessionsLoading.value = true
    sessionsError.value = null
    try {
      const response = await listChatSessions()
      const list = Array.isArray(response.sessions) ? response.sessions : []
      sessions.value = [...list].sort(
        (left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at),
      )
      sessionsLoaded.value = true
    } catch (caught) {
      sessionsError.value = errorText(caught, '会话列表读取失败')
    } finally {
      sessionsLoading.value = false
    }
  }

  let openSeq = 0

  async function openSession(sessionId: string): Promise<void> {
    if (current.value?.id === sessionId && sending.value) {
      return
    }
    const seq = ++openSeq
    currentLoading.value = true
    currentError.value = null
    try {
      const session = await getChatSession(sessionId)
      if (seq !== openSeq) {
        return
      }
      current.value = session
    } catch (caught) {
      if (seq !== openSeq) {
        return
      }
      currentError.value = errorText(caught, '会话读取失败')
    } finally {
      if (seq === openSeq) {
        currentLoading.value = false
      }
    }
  }

  async function createSession(input: ChatCreateInput): Promise<ChatSessionView | null> {
    try {
      const session = await createChatSession(input)
      current.value = session
      currentError.value = null
      await fetchSessions()
      return session
    } catch (caught) {
      currentError.value = errorText(caught, '创建会话失败')
      return null
    }
  }

  async function updateCurrent(patch: ChatUpdateInput): Promise<void> {
    const session = current.value
    if (session === null) {
      return
    }
    const updated = await updateChatSession(session.id, patch)
    current.value = updated
    sessions.value = sessions.value.map((item) => (item.id === updated.id ? updated : item))
  }

  async function send(content: string): Promise<void> {
    const session = current.value
    if (session === null || sending.value || content.trim().length === 0) {
      return
    }
    const message: ChatMessage = {
      id: 'local-' + Date.now().toString(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
      tool_name: null,
      is_error: false,
    }
    sending.value = true
    streamError.value = null
    streaming.value = { content: '', status: '正在发送…', tools: [] }
    current.value = {
      ...session,
      status: 'running',
      messages: [...session.messages, message],
    }
    try {
      await streamChatMessage(session.id, content, (event) => {
        const state = streaming.value
        if (state === null) {
          return
        }
        if (event.type === 'token' && event.content !== null) {
          state.content += event.content
        } else if (event.type === 'tool') {
          state.tools.push({
            key: 'tool-' + state.tools.length.toString(),
            toolName: event.tool_name ?? '工具调用',
            content: event.content ?? '',
          })
        } else if (event.type === 'status') {
          state.status = event.message ?? event.status ?? state.status
        } else if (event.type === 'error') {
          streamError.value = event.message ?? '执行失败'
        }
      })
    } catch (caught) {
      streamError.value = errorText(caught, '发送失败，请稍后重试')
    } finally {
      sending.value = false
      try {
        const refreshed = await getChatSession(session.id)
        current.value = refreshed
        sessions.value = sessions.value.map((item) =>
          item.id === refreshed.id ? refreshed : item,
        )
      } catch {
        // 刷新失败时保留本地消息，错误已在 streamError 中说明
      }
      streaming.value = null
    }
  }

  async function stop(): Promise<void> {
    const session = current.value
    if (session === null || cancelBusy.value) {
      return
    }
    cancelBusy.value = true
    try {
      await cancelChatSession(session.id)
    } catch (caught) {
      streamError.value = errorText(caught, '停止失败')
    } finally {
      cancelBusy.value = false
    }
  }

  function lastProjectFor(toolId: string): string | null {
    const match = sessions.value.find((item) => item.tool_id === toolId)
    return match?.project_dir ?? null
  }

  function clearCurrent(): void {
    current.value = null
    currentError.value = null
    streamError.value = null
    streaming.value = null
  }

  function reset(): void {
    sessions.value = []
    sessionsLoaded.value = false
    sessionsLoading.value = false
    sessionsError.value = null
    current.value = null
    currentLoading.value = false
    currentError.value = null
    sending.value = false
    streaming.value = null
    streamError.value = null
    cancelBusy.value = false
  }

  return {
    sessions,
    sessionsLoading,
    sessionsLoaded,
    sessionsError,
    current,
    currentLoading,
    currentError,
    sending,
    streaming,
    streamError,
    cancelBusy,
    fetchSessions,
    openSession,
    createSession,
    updateCurrent,
    send,
    stop,
    lastProjectFor,
    clearCurrent,
    reset,
  }
})



