import { requestJson } from './client'

export type SessionRole =
  | 'user'
  | 'assistant'
  | 'tool_call'
  | 'tool_result'
  | 'system'
  | 'unknown'

export interface SessionWarning {
  code: string
  message: string
}

export interface ToolSessionSummary {
  id: string
  tool_id: string
  title: string
  project_path: string | null
  started_at: string
  updated_at: string
  message_count: number | null
  warnings: SessionWarning[]
}

export interface SessionListResponse {
  sessions: ToolSessionSummary[]
  warnings: SessionWarning[]
  next_cursor: number | null
  has_more: boolean
}

export interface SessionMessage {
  id: string
  role: SessionRole
  timestamp: string | null
  content: string
  tool_name: string | null
  is_error: boolean
  raw_type: string | null
}

export interface SessionMessagesResponse {
  tool_id: string
  session_id: string
  messages: SessionMessage[]
  next_cursor: number | null
  has_more: boolean
  total_messages: number | null
  warnings: SessionWarning[]
}

export function listToolSessions(
  toolId: string,
  options: { cursor?: number; limit?: number } = {},
): Promise<SessionListResponse> {
  const query = new URLSearchParams()
  query.set('tool_id', toolId)
  query.set('cursor', String(options.cursor ?? 0))
  query.set('limit', String(options.limit ?? 30))
  return requestJson<SessionListResponse>(`/api/sessions?${query.toString()}`)
}

export function readToolSession(
  toolId: string,
  sessionId: string,
  options: { cursor?: number; limit?: number } = {},
): Promise<SessionMessagesResponse> {
  const query = new URLSearchParams()
  query.set('cursor', String(options.cursor ?? 0))
  query.set('limit', String(options.limit ?? 100))
  return requestJson<SessionMessagesResponse>(
    `/api/sessions/${encodeURIComponent(toolId)}/${encodeURIComponent(sessionId)}?${query.toString()}`,
  )
}
