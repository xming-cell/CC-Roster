import type { ChatMessage } from '../api/chat'

export interface UserBlock {
  kind: 'user'
  key: string
  message: ChatMessage
}

export interface AssistantBlock {
  kind: 'assistant'
  key: string
  message: ChatMessage
}

export interface SystemBlock {
  kind: 'system'
  key: string
  message: ChatMessage
}

export interface ToolsBlock {
  kind: 'tools'
  key: string
  messages: ChatMessage[]
}

export type TranscriptBlock = UserBlock | AssistantBlock | SystemBlock | ToolsBlock

export function groupMessages(messages: ChatMessage[]): TranscriptBlock[] {
  const blocks: TranscriptBlock[] = []
  let pendingTools: ChatMessage[] = []

  function flushTools(): void {
    if (pendingTools.length === 0) {
      return
    }
    blocks.push({
      kind: 'tools',
      key: 'tools-' + (pendingTools[0]?.id ?? ''),
      messages: pendingTools,
    })
    pendingTools = []
  }

  for (const message of messages) {
    if (message.role === 'tool') {
      pendingTools.push(message)
      continue
    }
    flushTools()
    if (message.role === 'user') {
      blocks.push({ kind: 'user', key: message.id, message })
    } else if (message.role === 'assistant') {
      blocks.push({ kind: 'assistant', key: message.id, message })
    } else {
      blocks.push({ kind: 'system', key: message.id, message })
    }
  }
  flushTools()
  return blocks
}

export function relativeTime(value: string, now: Date = new Date()): string {
  const then = new Date(value).getTime()
  if (Number.isNaN(then)) {
    return ''
  }
  const diffMs = Math.max(0, now.getTime() - then)
  const minutes = Math.floor(diffMs / 60_000)
  if (minutes < 1) {
    return '刚刚'
  }
  if (minutes < 60) {
    return `${minutes} 分钟前`
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    return `${hours} 小时前`
  }
  const days = Math.floor(hours / 24)
  return days === 1 ? '昨天' : `${days} 天前`
}

export function projectName(path: string): string {
  const parts = path.split(/[\\/]/).filter((part) => part.length > 0)
  return parts[parts.length - 1] ?? path
}

export function processLabel(message: ChatMessage): string {
  const name = message.tool_name ?? '工具调用'
  const firstLine = message.content.split('\n').find((line) => line.trim().length > 0) ?? ''
  const summary = firstLine.trim()
  if (summary.length === 0) {
    return name
  }
  return summary.length > 64 ? `${name} · ${summary.slice(0, 64)}…` : `${name} · ${summary}`
}

export function processDetail(message: ChatMessage): string {
  const text = message.content.trim()
  return text.length === 0 ? '（没有输出）' : text
}
