import type { ToolStatus, ToolView } from '../api/tools'

const AVATAR_TONE_COUNT = 6

export function normalizeStatus(status: string): ToolStatus {
  if (status === 'ok' || status === 'unconfigured' || status === 'error') {
    return status
  }
  return 'error'
}

export function statusDescription(tool: ToolView): string {
  const status = normalizeStatus(tool.status)
  if (status === 'unconfigured') {
    return '已安装，尚未配置'
  }
  if (status === 'error') {
    return tool.warnings[0]?.message ?? '配置解析失败'
  }

  const parts = [tool.provider, tool.model].filter(
    (value): value is string => value !== null && value !== '',
  )
  return parts.length > 0 ? parts.join(' / ') : '已配置'
}

function parseTimestamp(value: string | null): number | null {
  if (value === null) {
    return null
  }
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? null : parsed
}

export function sortToolsByLastModified(tools: ToolView[]): ToolView[] {
  return [...tools].sort((left, right) => {
    const leftTime = parseTimestamp(left.last_modified)
    const rightTime = parseTimestamp(right.last_modified)

    if (leftTime !== null && rightTime !== null && leftTime !== rightTime) {
      return rightTime - leftTime
    }
    if (leftTime === null && rightTime !== null) {
      return 1
    }
    if (leftTime !== null && rightTime === null) {
      return -1
    }

    const byName = left.display_name.localeCompare(right.display_name, 'zh-CN')
    if (byName !== 0) {
      return byName
    }
    return left.id.localeCompare(right.id)
  })
}

export function avatarInitial(name: string): string {
  const first = Array.from(name.trim())[0]
  return first ?? '?'
}

export function avatarTone(toolId: string): number {
  let hash = 0
  for (const character of toolId) {
    hash = (hash * 31 + (character.codePointAt(0) ?? 0)) % 997
  }
  return Math.abs(hash) % AVATAR_TONE_COUNT
}