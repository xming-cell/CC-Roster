import type { AuditAction, AuditEntry, AuditResult } from '../api/audit'

const ACTION_LABELS: Record<AuditAction, string> = {
  apply: '切换供应商',
  rollback: '回滚快照',
  profile_create: '新增供应商',
  profile_update: '更新供应商',
  profile_copy: '复制供应商',
  profile_delete: '删除供应商',
  profile_bind: '绑定供应商',
  profile_unbind: '解绑供应商',
  profile_import: '导入供应商',
}

const RESULT_LABELS: Record<AuditResult, string> = {
  success: '成功',
  failed: '失败',
  conflict: '冲突',
}

export type AuditResultTone = 'success' | 'danger' | 'warning'

export function auditActionLabel(action: AuditAction): string {
  return ACTION_LABELS[action]
}

export function auditResultLabel(result: AuditResult): string {
  return RESULT_LABELS[result]
}

export function auditResultTone(result: AuditResult): AuditResultTone {
  if (result === 'success') {
    return 'success'
  }
  return result === 'failed' ? 'danger' : 'warning'
}

export function formatAuditTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function auditDateKey(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

export function auditDateLabel(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  const today = new Date()
  const start = new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate())
  const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const diff = Math.round((todayStart.getTime() - start.getTime()) / 86_400_000)
  const dateText = parsed.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })
  if (diff === 0) {
    return '今天 · ' + dateText
  }
  if (diff === 1) {
    return '昨天 · ' + dateText
  }
  return parsed.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

export interface AuditDateGroup {
  key: string
  label: string
  entries: AuditEntry[]
}

export function groupAuditEntries(entries: AuditEntry[]): AuditDateGroup[] {
  const groups: AuditDateGroup[] = []
  for (const entry of entries) {
    const key = auditDateKey(entry.created_at)
    const last = groups[groups.length - 1]
    if (last?.key === key) {
      last.entries.push(entry)
      continue
    }
    groups.push({ key, label: auditDateLabel(entry.created_at), entries: [entry] })
  }
  return groups
}

export function fileBasename(path: string): string {
  const parts = path.split(/[\\/]/).filter((part) => part.length > 0)
  return parts[parts.length - 1] ?? path
}
