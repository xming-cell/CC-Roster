import type { ToolView } from '../api/tools'

export function installationLabel(tool: ToolView): string {
  return tool.installed ? '已安装' : '未安装'
}

export function configurationLabel(tool: ToolView): string {
  return tool.configured ? '已配置' : '未配置（无托管字段）'
}

export function providerLabel(tool: ToolView): string {
  return tool.provider ?? '未知'
}

export function modelLabel(tool: ToolView): string {
  return tool.model ?? '未知'
}

export function baseUrlLabel(tool: ToolView): string {
  return tool.base_url ?? '未设置'
}

export function versionLabel(tool: ToolView): string {
  return tool.version ?? '未知'
}

export function configPathLabel(tool: ToolView): string {
  return tool.config_path ?? '未知'
}

export function thirdPartyLabel(value: boolean | null): string {
  if (value === null) {
    return '未知'
  }
  return value ? '是' : '否'
}

export function secretLabel(tool: ToolView): string {
  if (!tool.has_secret) {
    return '未配置'
  }
  return tool.secret_preview ?? '已配置（已脱敏）'
}

export function formatLastModified(value: string | null): string {
  if (value === null) {
    return '未知'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString('zh-CN', { hour12: false })
}
