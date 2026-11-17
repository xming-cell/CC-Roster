import type { UsageRecord } from '../api/usage'

const integerFormatter = new Intl.NumberFormat('zh-CN')

export function formatInteger(value: number): string {
  return integerFormatter.format(Number.isFinite(value) ? value : 0)
}

export function formatTokens(value: number): string {
  if (value >= 1_000_000) {
    return (value / 1_000_000).toFixed(2) + 'M'
  }
  if (value >= 1_000) {
    return (value / 1_000).toFixed(1) + 'K'
  }
  return formatInteger(value)
}

export function formatCost(value: string | null, priceKnown = true): string {
  if (!priceKnown || value === null) {
    return '未知'
  }
  const amount = Number(value)
  if (!Number.isFinite(amount)) {
    return '未知'
  }
  return '$' + amount.toFixed(2)
}

export function formatDate(value: string): string {
  const parsed = new Date(value + 'T00:00:00')
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

export interface UsageSegment {
  toolId: string
  calls: number
}

export interface DailyUsage {
  date: string
  calls: number
  segments: UsageSegment[]
}

export function dailyUsage(records: UsageRecord[]): DailyUsage[] {
  const byDate = new Map<string, Map<string, number>>()
  for (const record of records) {
    const tools = byDate.get(record.date) ?? new Map<string, number>()
    tools.set(record.tool_id, (tools.get(record.tool_id) ?? 0) + record.calls)
    byDate.set(record.date, tools)
  }
  return [...byDate.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, tools]) => {
      const segments = [...tools.entries()].map(([toolId, calls]) => ({ toolId, calls }))
      return { date, calls: segments.reduce((total, item) => total + item.calls, 0), segments }
    })
}
