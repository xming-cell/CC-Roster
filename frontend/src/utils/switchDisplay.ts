import type { SnapshotChange, SwitchFileAction } from '../api/switch'

export function fileBasename(path: string): string {
  const parts = path.split(/[\\/]/).filter((part) => part.length > 0)
  return parts[parts.length - 1] ?? path
}

export function fileActionLabel(action: SwitchFileAction): string {
  if (action === 'created') {
    return '新建'
  }
  if (action === 'updated') {
    return '更新'
  }
  return '不变'
}

export function formatChangeValue(value: string | null): string {
  if (value === null) {
    return '—'
  }
  const trimmed = value.trim()
  return trimmed.length === 0 ? '（空）' : value
}

export function shortHash(value: string | null): string {
  if (value === null) {
    return '—'
  }
  return value.length > 12 ? value.slice(0, 8) + '…' + value.slice(-4) : value
}

export interface ChangeCounts {
  set: number
  remove: number
}

export function changeCounts(changes: SnapshotChange[]): ChangeCounts {
  let set = 0
  let remove = 0
  for (const change of changes) {
    if (change.action === 'set') {
      set += 1
    } else {
      remove += 1
    }
  }
  return { set, remove }
}

export function fileCountLabel(count: number): string {
  return count === 0 ? '没有文件变化' : `${count} 个文件`
}
