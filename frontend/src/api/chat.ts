import { ApiError, requestJson } from './client'

export type ChatStatus = 'idle' | 'running' | 'cancelled' | 'failed'
export type ChatRole = 'user' | 'assistant' | 'tool' | 'system'
export type ChatEventType = 'status' | 'token' | 'tool' | 'done' | 'error' | 'cancelled'

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  created_at: string
  tool_name: string | null
  is_error: boolean
}

export interface ChatSessionView {
  id: string
  tool_id: string
  profile_id: string
  project_dir: string
  title: string
  status: ChatStatus
  model: string | null
  reasoning_effort: string | null
  resume_from_tool_id: string | null
  resume_from_session_id: string | null
  messages: ChatMessage[]
  created_at: string
  updated_at: string
}

export interface ChatSessionListResponse {
  sessions: ChatSessionView[]
}

export interface ChatCreateInput {
  tool_id: string
  profile_id: string
  project_dir: string
  title?: string
  model?: string
  reasoning_effort?: string
  resume_from_tool_id?: string
  resume_from_session_id?: string
}

export interface ChatUpdateInput {
  model?: string | null
  reasoning_effort?: string | null
}

export interface ChatEvent {
  type: ChatEventType
  content: string | null
  status: string | null
  tool_name: string | null
  message: string | null
}

export interface ChatCancelResponse {
  cancelled: boolean
  message: string
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export function listChatSessions(): Promise<ChatSessionListResponse> {
  return requestJson<ChatSessionListResponse>('/api/chat/sessions')
}

export function getChatSession(sessionId: string): Promise<ChatSessionView> {
  return requestJson<ChatSessionView>(`/api/chat/sessions/${encodeURIComponent(sessionId)}`)
}

export function createChatSession(input: ChatCreateInput): Promise<ChatSessionView> {
  return requestJson<ChatSessionView>('/api/chat/sessions', jsonInit('POST', input))
}

export function updateChatSession(
  sessionId: string,
  input: ChatUpdateInput,
): Promise<ChatSessionView> {
  return requestJson<ChatSessionView>(
    `/api/chat/sessions/${encodeURIComponent(sessionId)}`,
    jsonInit('PATCH', input),
  )
}

export function cancelChatSession(sessionId: string): Promise<ChatCancelResponse> {
  return requestJson<ChatCancelResponse>(
    `/api/chat/sessions/${encodeURIComponent(sessionId)}/cancel`,
    { method: 'POST' },
  )
}

function parseStreamError(body: unknown, status: number): ApiError {
  if (typeof body === 'object' && body !== null) {
    const record = body as Record<string, unknown>
    if (typeof record.code === 'string' && typeof record.message === 'string') {
      return new ApiError(record.code, record.message, status)
    }
  }
  return new ApiError('HTTP_ERROR', `请求失败（HTTP ${status}）`, status)
}

export async function streamChatMessage(
  sessionId: string,
  content: string,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(
    `/api/chat/sessions/${encodeURIComponent(sessionId)}/messages`,
    {
      ...jsonInit('POST', { content }),
      signal,
    },
  )
  if (!response.ok) {
    let body: unknown = null
    try {
      body = await response.json()
    } catch {
      // 非 JSON 错误走兜底
    }
    throw parseStreamError(body, response.status)
  }
  if (response.body === null) {
    throw new ApiError('STREAM_UNAVAILABLE', '当前浏览器不支持流式响应')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const chunk = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      for (const line of chunk.split('\n')) {
        if (!line.startsWith('data: ')) {
          continue
        }
        try {
          onEvent(JSON.parse(line.slice(6)) as ChatEvent)
        } catch {
          // 单个坏事件不终止整条流
        }
      }
      boundary = buffer.indexOf('\n\n')
    }
  }
}
